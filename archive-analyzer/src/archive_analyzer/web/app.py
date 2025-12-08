"""NAS Auto Sync Web Monitoring Application

Issue #43: Docker 서버 배포 + GUI 모니터링

FastAPI 기반 웹 대시보드:
- 실시간 동기화 상태
- 파일 변경 이력 조회
- 로그 스트리밍 (WebSocket)
- 수동 동기화/정합성 검증 트리거

Usage:
    uvicorn archive_analyzer.web.app:app --host 0.0.0.0 --port 8080
"""

import asyncio
import logging
import os
import sqlite3
from collections import deque
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional

from fastapi import BackgroundTasks, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

logger = logging.getLogger(__name__)

# =============================================================================
# Configuration
# =============================================================================


@dataclass
class WebConfig:
    """Web 모니터링 설정"""

    archive_db: str = "data/output/archive.db"
    pokervod_db: str = "D:/AI/claude01/shared-data/pokervod.db"
    nas_mount_path: str = "Z:/GGPNAs/ARCHIVE"
    sync_interval: int = 1800
    log_buffer_size: int = 1000
    host: str = "0.0.0.0"
    port: int = 8080

    def __post_init__(self):
        self.archive_db = os.environ.get("ARCHIVE_DB", self.archive_db)
        self.pokervod_db = os.environ.get("POKERVOD_DB", self.pokervod_db)
        self.nas_mount_path = os.environ.get("NAS_MOUNT_PATH", self.nas_mount_path)
        if interval := os.environ.get("SYNC_INTERVAL"):
            self.sync_interval = int(interval)
        if port := os.environ.get("WEB_PORT"):
            self.port = int(port)


# =============================================================================
# Service State
# =============================================================================


@dataclass
class ServiceState:
    """서비스 상태 관리"""

    is_running: bool = False
    last_sync_time: Optional[datetime] = None
    last_sync_result: Optional[Dict[str, Any]] = None
    sync_in_progress: bool = False
    error_message: Optional[str] = None
    log_buffer: Deque[str] = field(default_factory=lambda: deque(maxlen=1000))
    connected_clients: List[WebSocket] = field(default_factory=list)
    config: WebConfig = field(default_factory=WebConfig)

    # Issue #49: Google Sheets 동기화 연동 (Optional)
    # ISheetsSync Protocol을 구현하는 어댑터 (None이면 비활성화)
    sheets_sync: Optional[Any] = None  # Type: Optional[ISheetsSync]


state = ServiceState()


# =============================================================================
# Log Handler for WebSocket Streaming
# =============================================================================


class WebSocketLogHandler(logging.Handler):
    """WebSocket으로 로그 스트리밍"""

    def __init__(self, state: ServiceState):
        super().__init__()
        self.state = state
        self.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        )

    def emit(self, record: logging.LogRecord):
        try:
            msg = self.format(record)
            self.state.log_buffer.append(msg)
            # WebSocket 클라이언트에 브로드캐스트
            asyncio.create_task(self._broadcast(msg))
        except Exception:
            pass

    async def _broadcast(self, message: str):
        disconnected = []
        for client in self.state.connected_clients:
            try:
                await client.send_text(message)
            except Exception:
                disconnected.append(client)
        for client in disconnected:
            self.state.connected_clients.remove(client)


# =============================================================================
# Database Helpers
# =============================================================================


def get_db_stats(db_path: str) -> Dict[str, Any]:
    """DB 통계 조회 (archive.db, pokervod.db 둘 다 지원)"""
    if not Path(db_path).exists():
        return {"error": f"DB not found: {db_path}"}

    conn = sqlite3.connect(db_path)
    try:
        stats = {}

        # 테이블 컬럼 확인
        cursor = conn.execute("PRAGMA table_info(files)")
        columns = {row[1] for row in cursor.fetchall()}

        # 전체 파일 수
        cursor = conn.execute("SELECT COUNT(*) FROM files")
        stats["total_files"] = cursor.fetchone()[0]

        # 상태별 파일 수 (스키마에 따라 다른 컬럼 사용)
        if "scan_status" in columns:
            # archive.db
            cursor = conn.execute(
                """SELECT COALESCE(scan_status, 'unknown'), COUNT(*)
                   FROM files GROUP BY scan_status"""
            )
            stats["by_status"] = dict(cursor.fetchall())
        elif "analysis_status" in columns:
            # pokervod.db
            cursor = conn.execute(
                """SELECT COALESCE(analysis_status, 'unknown'), COUNT(*)
                   FROM files GROUP BY analysis_status"""
            )
            stats["by_status"] = dict(cursor.fetchall())
        else:
            stats["by_status"] = {}

        # 파일 타입별 (archive.db only)
        if "file_type" in columns:
            cursor = conn.execute(
                """SELECT file_type, COUNT(*)
                   FROM files GROUP BY file_type
                   ORDER BY COUNT(*) DESC LIMIT 10"""
            )
            stats["by_type"] = dict(cursor.fetchall())
        elif "codec" in columns:
            # pokervod.db - codec별 통계
            cursor = conn.execute(
                """SELECT COALESCE(codec, 'unknown'), COUNT(*)
                   FROM files GROUP BY codec
                   ORDER BY COUNT(*) DESC LIMIT 10"""
            )
            stats["by_type"] = dict(cursor.fetchall())
        else:
            stats["by_type"] = {}

        # 최근 파일 (스키마에 따라 다른 컬럼)
        if "path" in columns:
            # archive.db
            time_col = "created_at" if "created_at" in columns else "modified_at"
            cursor = conn.execute(
                f"""SELECT path, filename, {time_col}
                   FROM files
                   ORDER BY {time_col} DESC LIMIT 5"""
            )
            stats["recent_files"] = [
                {"path": r[0], "filename": r[1], "updated_at": r[2]}
                for r in cursor.fetchall()
            ]
        elif "nas_path" in columns:
            # pokervod.db
            cursor = conn.execute(
                """SELECT nas_path, filename, updated_at
                   FROM files
                   ORDER BY updated_at DESC LIMIT 5"""
            )
            stats["recent_files"] = [
                {"path": r[0], "filename": r[1], "updated_at": r[2]}
                for r in cursor.fetchall()
            ]
        else:
            stats["recent_files"] = []

        # DB 파일 크기
        stats["db_size_mb"] = round(Path(db_path).stat().st_size / (1024 * 1024), 2)

        return stats

    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()


# HLS 호환 확장자 (sync.py와 동일)
HLS_COMPATIBLE_EXTENSIONS = ("mp4", "mov", "ts", "m4v", "m2ts", "mts")

# Issue #51: 미등록 사유 분류
NOT_SYNCED_REASONS = {
    "hls_incompatible": "HLS 비호환 포맷",
    "duplicate_excluded": "중복 파일 제외",
    "non_video": "비디오 아님",
    "pending_sync": "동기화 대기",
}

# 비디오 확장자
VIDEO_EXTENSIONS = ("mp4", "mov", "ts", "m4v", "m2ts", "mts", "mkv", "avi", "wmv", "flv", "webm", "mxf")

# HLS 비호환 확장자
NON_HLS_EXTENSIONS = ("mxf", "webm", "mkv", "avi", "wmv", "flv")


def get_matching_summary(
    archive_db: str, pokervod_db: str
) -> Dict[str, Any]:
    """매칭 요약 통계 계산 (Issue #51: 미등록 사유별 분류)"""
    summary = {
        "synced": 0,
        "not_synced": 0,
        "duplicates": 0,
        "catalogs": [],
        # Issue #51: 미등록 사유별 상세
        "not_synced_reasons": {
            "hls_incompatible": 0,
            "duplicate_excluded": 0,
            "non_video": 0,
            "pending_sync": 0,
        },
    }

    if not Path(archive_db).exists():
        return summary

    conn_archive = sqlite3.connect(archive_db)
    conn_pokervod = None
    pokervod_filenames = set()

    if Path(pokervod_db).exists():
        conn_pokervod = sqlite3.connect(pokervod_db)
        cursor = conn_pokervod.execute("SELECT filename FROM files")
        pokervod_filenames = {row[0] for row in cursor.fetchall()}

    try:
        # archive.db 전체 파일 조회
        cursor = conn_archive.execute("SELECT filename FROM files")
        all_files = [row[0] for row in cursor.fetchall()]

        # 중복 파일명 찾기
        cursor = conn_archive.execute(
            """SELECT filename FROM files
               GROUP BY filename HAVING COUNT(*) > 1"""
        )
        duplicate_filenames = {row[0] for row in cursor.fetchall()}

        # Issue #51: 파일별 사유 분류
        synced = 0
        hls_incompatible = 0
        duplicate_excluded = 0
        non_video = 0
        pending_sync = 0

        for filename in all_files:
            ext = filename.split(".")[-1].lower() if "." in filename else ""
            is_video = ext in VIDEO_EXTENSIONS
            is_hls_compatible = ext in HLS_COMPATIBLE_EXTENSIONS
            is_synced = filename in pokervod_filenames
            is_duplicate = filename in duplicate_filenames

            if is_synced:
                synced += 1
            elif not is_video:
                non_video += 1
            elif not is_hls_compatible:
                hls_incompatible += 1
            elif is_duplicate:
                # 중복 파일 중 하나만 동기화됨 - 나머지는 제외
                duplicate_excluded += 1
            else:
                pending_sync += 1

        # 카탈로그별 통계
        cursor = conn_archive.execute(
            """SELECT
                   CASE
                       WHEN path LIKE '%/WSOP/%' OR path LIKE 'WSOP/%' THEN 'WSOP'
                       WHEN path LIKE '%/HCL/%' OR path LIKE 'HCL/%' THEN 'HCL'
                       WHEN path LIKE '%/PAD/%' OR path LIKE 'PAD/%' THEN 'PAD'
                       WHEN path LIKE '%/MPP/%' OR path LIKE 'MPP/%' THEN 'MPP'
                       WHEN path LIKE '%/GOG/%' OR path LIKE 'GOG/%' THEN 'GOG'
                       WHEN path LIKE '%/GGMillions/%' OR path LIKE 'GGMillions/%' THEN 'GGMillions'
                       ELSE 'Other'
                   END as catalog,
                   COUNT(*) as count
               FROM files
               GROUP BY catalog
               ORDER BY count DESC"""
        )
        catalogs = [{"name": row[0], "count": row[1]} for row in cursor.fetchall()]

        not_synced_total = hls_incompatible + duplicate_excluded + non_video + pending_sync

        summary = {
            "synced": synced,
            "not_synced": not_synced_total,
            "duplicates": duplicate_excluded,
            "catalogs": catalogs,
            "not_synced_reasons": {
                "hls_incompatible": hls_incompatible,
                "duplicate_excluded": duplicate_excluded,
                "non_video": non_video,
                "pending_sync": pending_sync,
            },
        }

    except Exception as e:
        logger.error(f"매칭 요약 계산 오류: {e}")
    finally:
        conn_archive.close()
        if conn_pokervod:
            conn_pokervod.close()

    return summary


def get_matching_items(
    archive_db: str,
    pokervod_db: str,
    page: int = 1,
    per_page: int = 20,
    status_filter: Optional[str] = None,
    sort_by: str = "filename",
    sort_order: str = "asc",
) -> tuple:
    """1:1 매칭 아이템 목록 조회 (Issue #51: 정렬 + 미등록 사유)

    Args:
        archive_db: archive.db 경로
        pokervod_db: pokervod.db 경로
        page: 페이지 번호
        per_page: 페이지당 항목 수
        status_filter: 상태 필터 (synced, not_synced, synced_with_duplicates)
        sort_by: 정렬 기준 (filename, size, status, path, modified_at)
        sort_order: 정렬 순서 (asc, desc)
    """
    items = []
    total = 0
    summary = {"synced": 0, "not_synced": 0, "synced_with_duplicates": 0}

    if not Path(archive_db).exists():
        return items, total, summary

    conn_archive = sqlite3.connect(archive_db)
    conn_pokervod = None
    pokervod_files = {}

    if Path(pokervod_db).exists():
        conn_pokervod = sqlite3.connect(pokervod_db)
        # pokervod.db의 파일들을 filename으로 인덱싱
        cursor = conn_pokervod.execute(
            "SELECT id, filename, nas_path, size_bytes FROM files"
        )
        for row in cursor.fetchall():
            pokervod_files[row[1]] = {
                "id": row[0],
                "filename": row[1],
                "nas_path": row[2],
                "size_bytes": row[3],
            }

    try:
        # 중복 파일 목록 (동일 filename이 여러 path에 존재)
        cursor = conn_archive.execute(
            """SELECT filename FROM files
               GROUP BY filename HAVING COUNT(*) > 1"""
        )
        duplicate_filenames = {row[0] for row in cursor.fetchall()}

        # 모든 파일 조회 (modified_at 포함)
        cursor = conn_archive.execute(
            """SELECT id, path, filename, file_type, size_bytes, modified_at
               FROM files
               ORDER BY id"""
        )

        all_items = []
        for row in cursor.fetchall():
            source_id, path, filename, file_type, size_bytes, modified_at = row

            # 확장자로 HLS 호환 여부 확인
            ext = filename.split(".")[-1].lower() if "." in filename else ""
            is_hls_compatible = ext in HLS_COMPATIBLE_EXTENSIONS
            is_video = ext in VIDEO_EXTENSIONS

            # 매칭 상태 결정
            target_info = pokervod_files.get(filename)
            is_duplicate = filename in duplicate_filenames

            # Issue #51: 미등록 사유 분류
            not_synced_reason = None
            if target_info:
                if is_duplicate:
                    status = "synced_with_duplicates"
                    summary["synced_with_duplicates"] += 1
                else:
                    status = "synced"
                    summary["synced"] += 1
            else:
                status = "not_synced"
                summary["not_synced"] += 1
                # 미등록 사유 결정
                if not is_video:
                    not_synced_reason = "non_video"
                elif not is_hls_compatible:
                    not_synced_reason = "hls_incompatible"
                elif is_duplicate:
                    not_synced_reason = "duplicate_excluded"
                else:
                    not_synced_reason = "pending_sync"

            item = {
                "status": status,
                "not_synced_reason": not_synced_reason,
                "source": {
                    "id": source_id,
                    "path": path,
                    "filename": filename,
                    "file_type": file_type,
                    "size_bytes": size_bytes,
                    "modified_at": modified_at,
                },
                "target": target_info,
                "is_hls_compatible": is_hls_compatible,
            }

            if is_duplicate:
                # 중복 경로 조회
                dup_cursor = conn_archive.execute(
                    "SELECT id, path FROM files WHERE filename = ? AND id != ?",
                    (filename, source_id),
                )
                item["duplicates"] = [
                    {"id": r[0], "path": r[1]} for r in dup_cursor.fetchall()
                ]
            else:
                item["duplicates"] = []

            all_items.append(item)

        # 필터 적용 (필터링 후 total 계산)
        if status_filter:
            filtered_items = [item for item in all_items if item["status"] == status_filter]
        else:
            filtered_items = all_items

        # Issue #51: 정렬 적용
        sort_key_map = {
            "filename": lambda x: (x["source"]["filename"] or "").lower(),
            "size": lambda x: x["source"]["size_bytes"] or 0,
            "status": lambda x: x["status"],
            "path": lambda x: (x["source"]["path"] or "").lower(),
            "modified_at": lambda x: x["source"]["modified_at"] or "",
        }
        sort_key = sort_key_map.get(sort_by, sort_key_map["filename"])
        reverse = sort_order.lower() == "desc"
        filtered_items.sort(key=sort_key, reverse=reverse)

        # 필터 적용 후 total 계산
        total = len(filtered_items)

        # 페이지네이션 적용
        offset = (page - 1) * per_page
        items = filtered_items[offset : offset + per_page]

    except Exception as e:
        logger.error(f"매칭 아이템 조회 오류: {e}")
    finally:
        conn_archive.close()
        if conn_pokervod:
            conn_pokervod.close()

    return items, total, summary


def get_catalog_tree(archive_db: str, pokervod_db: str) -> List[Dict[str, Any]]:
    """카탈로그별 트리 구조 생성 (Issue #51: 재귀적 폴더 구조)"""
    catalogs = []

    if not Path(archive_db).exists():
        return catalogs

    conn_archive = sqlite3.connect(archive_db)
    conn_pokervod = None
    pokervod_files = set()

    if Path(pokervod_db).exists():
        conn_pokervod = sqlite3.connect(pokervod_db)
        cursor = conn_pokervod.execute("SELECT filename FROM files")
        pokervod_files = {row[0] for row in cursor.fetchall()}

    try:
        # 카탈로그 정의
        catalog_patterns = [
            ("WSOP", "%WSOP%"),
            ("HCL", "%HCL%"),
            ("PAD", "%PAD%"),
            ("MPP", "%MPP%"),
            ("GOG", "%GOG%"),
            ("GGMillions", "%GGMillions%"),
        ]

        for catalog_name, pattern in catalog_patterns:
            cursor = conn_archive.execute(
                """SELECT id, path, filename, size_bytes, parent_folder
                   FROM files WHERE path LIKE ?
                   ORDER BY path""",
                (pattern,),
            )
            files = cursor.fetchall()

            if not files:
                continue

            synced = sum(1 for f in files if f[2] in pokervod_files)
            not_synced = len(files) - synced

            # Issue #51: 재귀적 폴더 트리 구조 생성
            folder_tree = _build_folder_tree(files, pokervod_files)

            catalog = {
                "name": catalog_name,
                "total_files": len(files),
                "synced": synced,
                "not_synced": not_synced,
                "children": folder_tree,
            }
            catalogs.append(catalog)

    except Exception as e:
        logger.error(f"카탈로그 트리 생성 오류: {e}")
    finally:
        conn_archive.close()
        if conn_pokervod:
            conn_pokervod.close()

    return catalogs


def _build_folder_tree(
    files: List[tuple], pokervod_files: set
) -> List[Dict[str, Any]]:
    """파일 목록에서 계층적 폴더 트리 생성 (Issue #51)

    Args:
        files: [(id, path, filename, size_bytes, parent_folder), ...]
        pokervod_files: pokervod.db에 있는 파일명 집합

    Returns:
        계층적 트리 구조 (1단-2단-3단-4단...)
    """
    if not files:
        return []

    # 1. 폴더별 파일 수집
    folder_files: Dict[str, List[Dict]] = {}  # folder_path -> [file_info, ...]

    for file_id, path, filename, size_bytes, parent_folder in files:
        if not parent_folder:
            parent_folder = "/"

        if parent_folder not in folder_files:
            folder_files[parent_folder] = []

        is_synced = filename in pokervod_files
        folder_files[parent_folder].append({
            "id": file_id,
            "name": filename,
            "path": path,
            "size_bytes": size_bytes,
            "status": "synced" if is_synced else "not_synced",
        })

    # 2. 공통 prefix 찾기 (루트 경로)
    all_paths = list(folder_files.keys())
    if not all_paths:
        return []

    # 가장 짧은 경로를 기준으로 공통 prefix 찾기
    common_prefix = all_paths[0]
    for p in all_paths[1:]:
        while not p.startswith(common_prefix):
            common_prefix = "/".join(common_prefix.split("/")[:-1])
            if not common_prefix:
                break

    # 3. 계층적 트리 구조 구축
    tree_dict: Dict[str, Dict] = {}  # path -> node

    for folder_path, file_list in folder_files.items():
        # 공통 prefix 이후의 상대 경로
        if common_prefix and folder_path.startswith(common_prefix):
            rel_path = folder_path[len(common_prefix):].strip("/")
        else:
            rel_path = folder_path.split("/")[-1] if "/" in folder_path else folder_path

        # 경로 분해
        parts = rel_path.split("/") if rel_path else []

        # 파일 통계
        synced = sum(1 for f in file_list if f["status"] == "synced")
        not_synced = len(file_list) - synced

        # 현재 폴더 노드 생성
        current_path = ""
        for i, part in enumerate(parts):
            parent_path = current_path
            current_path = f"{current_path}/{part}" if current_path else part

            if current_path not in tree_dict:
                tree_dict[current_path] = {
                    "type": "folder",
                    "name": part,
                    "path": folder_path if i == len(parts) - 1 else "",
                    "depth": i + 1,
                    "children": {},
                    "files": [],
                    "synced": 0,
                    "not_synced": 0,
                    "total_files": 0,
                }

            # 마지막 레벨이면 파일 추가
            if i == len(parts) - 1:
                tree_dict[current_path]["files"] = file_list  # 모든 파일
                tree_dict[current_path]["synced"] = synced
                tree_dict[current_path]["not_synced"] = not_synced
                tree_dict[current_path]["total_files"] = len(file_list)
                tree_dict[current_path]["path"] = folder_path

            # 부모-자식 관계 설정
            if parent_path and parent_path in tree_dict:
                tree_dict[parent_path]["children"][current_path] = tree_dict[current_path]

    # 4. 트리 구조로 변환 (루트 노드들만 추출)
    root_nodes = []
    for path, node in tree_dict.items():
        # 1단계 폴더만 (부모가 없는 노드)
        if "/" not in path:
            root_nodes.append(_convert_tree_node(node, tree_dict))

    # 통계 집계 (하위 폴더 포함)
    for node in root_nodes:
        _aggregate_stats(node)

    return sorted(root_nodes, key=lambda x: x["name"])


def _convert_tree_node(node: Dict, tree_dict: Dict) -> Dict:
    """트리 노드를 재귀적으로 변환"""
    children = []
    for child_path, child_node in node.get("children", {}).items():
        children.append(_convert_tree_node(child_node, tree_dict))

    return {
        "type": "folder",
        "name": node["name"],
        "path": node.get("path", ""),
        "depth": node.get("depth", 1),
        "children": sorted(children, key=lambda x: x["name"]),
        "files": node.get("files", []),
        "synced": node.get("synced", 0),
        "not_synced": node.get("not_synced", 0),
        "total_files": node.get("total_files", 0),
    }


def _aggregate_stats(node: Dict) -> tuple:
    """하위 폴더 통계를 상위로 집계"""
    total_files = node.get("total_files", 0)
    synced = node.get("synced", 0)
    not_synced = node.get("not_synced", 0)

    for child in node.get("children", []):
        child_total, child_synced, child_not_synced = _aggregate_stats(child)
        total_files += child_total
        synced += child_synced
        not_synced += child_not_synced

    node["total_files_recursive"] = total_files
    node["synced_recursive"] = synced
    node["not_synced_recursive"] = not_synced

    return total_files, synced, not_synced


def get_file_history(db_path: str, limit: int = 50) -> List[Dict[str, Any]]:
    """파일 변경 이력 조회"""
    if not Path(db_path).exists():
        return []

    conn = sqlite3.connect(db_path)
    try:
        # file_history 테이블 존재 확인
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='file_history'"
        )
        if not cursor.fetchone():
            return []

        cursor = conn.execute(
            """SELECT fh.id, fh.file_id, fh.event_type, fh.old_path, fh.new_path,
                      fh.detected_at, f.filename
               FROM file_history fh
               LEFT JOIN files f ON fh.file_id = f.id
               ORDER BY fh.detected_at DESC
               LIMIT ?""",
            (limit,),
        )

        return [
            {
                "id": r[0],
                "file_id": r[1],
                "event_type": r[2],
                "old_path": r[3],
                "new_path": r[4],
                "detected_at": r[5],
                "filename": r[6],
            }
            for r in cursor.fetchall()
        ]

    except Exception as e:
        logger.error(f"파일 이력 조회 오류: {e}")
        return []
    finally:
        conn.close()


# =============================================================================
# Background Tasks
# =============================================================================


def run_sync_task():
    """동기화 작업 실행 (백그라운드)"""
    from archive_analyzer.nas_auto_sync import AutoSyncConfig, NASAutoSync

    state.sync_in_progress = True
    state.error_message = None

    try:
        config = AutoSyncConfig(
            archive_db=state.config.archive_db,
            pokervod_db=state.config.pokervod_db,
            sync_interval_seconds=state.config.sync_interval,
        )
        service = NASAutoSync(config)
        result = service.run_once()

        state.last_sync_time = datetime.now()
        state.last_sync_result = result
        logger.info(f"동기화 완료: {result}")

    except Exception as e:
        state.error_message = str(e)
        logger.error(f"동기화 실패: {e}")

    finally:
        state.sync_in_progress = False


def run_reconcile_task(dry_run: bool = True):
    """정합성 검증 작업 실행 (백그라운드)"""
    from archive_analyzer.nas_auto_sync import AutoSyncConfig, NASAutoSync

    state.sync_in_progress = True
    state.error_message = None

    try:
        config = AutoSyncConfig(
            archive_db=state.config.archive_db,
            pokervod_db=state.config.pokervod_db,
        )
        service = NASAutoSync(config)
        result = service.run_reconcile(
            nas_mount_path=state.config.nas_mount_path,
            dry_run=dry_run,
        )

        state.last_sync_time = datetime.now()
        state.last_sync_result = {"reconcile": result}
        logger.info(f"정합성 검증 완료: {result}")

    except Exception as e:
        state.error_message = str(e)
        logger.error(f"정합성 검증 실패: {e}")

    finally:
        state.sync_in_progress = False


# =============================================================================
# FastAPI Application
# =============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    state.is_running = True
    state.config = WebConfig()

    # 로그 핸들러 등록
    ws_handler = WebSocketLogHandler(state)
    logging.getLogger("archive_analyzer").addHandler(ws_handler)

    # Issue #49: Sheets 동기화 어댑터 초기화 (선택적)
    state.sheets_sync = _create_sheets_adapter()

    logger.info(f"Web 모니터링 서버 시작: http://{state.config.host}:{state.config.port}")

    yield

    # Shutdown
    state.is_running = False
    logger.info("Web 모니터링 서버 종료")


def _create_sheets_adapter():
    """Sheets 어댑터 생성 (선택적 초기화)

    Issue #49: Google Sheets 동기화 웹 대시보드 연동

    환경변수 SHEETS_SYNC_ENABLED=true 일 때만 활성화됩니다.
    초기화 실패 시 None을 반환하며, 기존 기능에 영향을 주지 않습니다.
    """
    import os

    if os.environ.get("SHEETS_SYNC_ENABLED", "").lower() not in ("true", "1", "yes"):
        logger.info("Sheets 동기화 비활성화 (SHEETS_SYNC_ENABLED 미설정)")
        return None

    try:
        from archive_analyzer.sheets_adapter import create_sheets_adapter

        adapter = create_sheets_adapter()
        if adapter:
            logger.info("Sheets 동기화 어댑터 초기화 성공")
        return adapter
    except Exception as e:
        logger.warning(f"Sheets 동기화 어댑터 초기화 실패: {e}")
        return None


def create_app() -> FastAPI:
    """FastAPI 앱 생성"""
    app = FastAPI(
        title="NAS Auto Sync Monitor",
        description="NAS 자동 동기화 모니터링 대시보드",
        version="1.0.0",
        lifespan=lifespan,
    )

    # 템플릿 및 정적 파일
    templates_dir = Path(__file__).parent / "templates"
    static_dir = Path(__file__).parent / "static"
    dashboard_template = templates_dir / "dashboard.html"

    # 템플릿 파일이 실제로 존재하는지 확인
    if dashboard_template.exists():
        templates = Jinja2Templates(directory=str(templates_dir))
    else:
        templates = None

    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # ==========================================================================
    # Routes
    # ==========================================================================

    @app.get("/", response_class=HTMLResponse)
    async def dashboard(request: Request):
        """메인 대시보드"""
        if templates:
            return templates.TemplateResponse(
                "dashboard.html",
                {
                    "request": request,
                    "state": state,
                    "archive_stats": get_db_stats(state.config.archive_db),
                    "pokervod_stats": get_db_stats(state.config.pokervod_db),
                },
            )
        else:
            return get_embedded_dashboard()

    @app.get("/health")
    async def health_check():
        """헬스 체크"""
        return {
            "status": "healthy" if state.is_running else "unhealthy",
            "sync_in_progress": state.sync_in_progress,
            "last_sync_time": state.last_sync_time.isoformat() if state.last_sync_time else None,
            "error": state.error_message,
        }

    @app.get("/api/status")
    async def get_status():
        """서비스 상태 조회"""
        return {
            "is_running": state.is_running,
            "sync_in_progress": state.sync_in_progress,
            "last_sync_time": state.last_sync_time.isoformat() if state.last_sync_time else None,
            "last_sync_result": state.last_sync_result,
            "error_message": state.error_message,
            "config": {
                "archive_db": state.config.archive_db,
                "pokervod_db": state.config.pokervod_db,
                "nas_mount_path": state.config.nas_mount_path,
                "sync_interval": state.config.sync_interval,
            },
        }

    @app.get("/api/stats")
    async def get_stats():
        """DB 통계 조회"""
        return {
            "archive": get_db_stats(state.config.archive_db),
            "pokervod": get_db_stats(state.config.pokervod_db),
        }

    @app.get("/api/history")
    async def get_history(limit: int = 50):
        """파일 변경 이력 조회"""
        return {
            "history": get_file_history(state.config.archive_db, limit),
        }

    @app.post("/api/sync")
    async def trigger_sync(background_tasks: BackgroundTasks):
        """수동 동기화 트리거"""
        if state.sync_in_progress:
            return JSONResponse(
                status_code=409,
                content={"error": "동기화가 이미 진행 중입니다"},
            )

        background_tasks.add_task(run_sync_task)
        return {"message": "동기화 시작됨", "status": "started"}

    @app.post("/api/reconcile")
    async def trigger_reconcile(background_tasks: BackgroundTasks, dry_run: bool = True):
        """정합성 검증 트리거"""
        if state.sync_in_progress:
            return JSONResponse(
                status_code=409,
                content={"error": "다른 작업이 진행 중입니다"},
            )

        background_tasks.add_task(run_reconcile_task, dry_run)
        return {
            "message": "정합성 검증 시작됨",
            "status": "started",
            "dry_run": dry_run,
        }

    @app.get("/api/logs")
    async def get_logs(limit: int = 100):
        """최근 로그 조회"""
        logs = list(state.log_buffer)[-limit:]
        return {"logs": logs}

    # =========================================================================
    # Issue #45: 1:1 매칭 API
    # =========================================================================

    @app.get("/api/dashboard")
    async def get_dashboard():
        """통합 대시보드 데이터 (PRD 7.2)"""
        archive_stats = get_db_stats(state.config.archive_db)
        pokervod_stats = get_db_stats(state.config.pokervod_db)

        # 매칭 요약 계산
        matching_summary = get_matching_summary(
            state.config.archive_db, state.config.pokervod_db
        )

        return {
            "source": {
                "name": "NAS 아카이브",
                "db_path": state.config.archive_db,
                "total_files": archive_stats.get("total_files", 0),
                "by_type": archive_stats.get("by_type", {}),
                "db_size_mb": archive_stats.get("db_size_mb", 0),
            },
            "target": {
                "name": "OTT 플랫폼",
                "db_path": state.config.pokervod_db,
                "total_files": pokervod_stats.get("total_files", 0),
                "by_format": pokervod_stats.get("by_type", {}),
                "excluded": {
                    "non_hls": matching_summary.get("not_synced", 0),
                    "duplicates": matching_summary.get("duplicates", 0),
                },
            },
            "sync_status": {
                "is_running": state.sync_in_progress,
                "last_sync_time": state.last_sync_time.isoformat() if state.last_sync_time else None,
                "last_result": state.last_sync_result,
            },
            "catalogs": matching_summary.get("catalogs", []),
        }

    @app.get("/api/matching")
    async def get_matching(
        page: int = 1,
        per_page: int = 20,
        status: Optional[str] = None,
        sort_by: str = "filename",
        sort_order: str = "asc",
    ):
        """1:1 매칭 테이블 데이터 (PRD 7.3, Issue #51: 정렬)"""
        items, total, summary = get_matching_items(
            state.config.archive_db,
            state.config.pokervod_db,
            page=page,
            per_page=per_page,
            status_filter=status,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        return {
            "total": total,
            "page": page,
            "per_page": per_page,
            "items": items,
            "summary": summary,
        }

    @app.get("/api/matching/tree")
    async def get_matching_tree():
        """트리 구조 매칭 데이터 (PRD 7.4)"""
        catalogs = get_catalog_tree(
            state.config.archive_db, state.config.pokervod_db
        )
        return {"catalogs": catalogs}

    # =========================================================================
    # Issue #49: Google Sheets 동기화 API
    # =========================================================================

    @app.get("/api/sheets/status")
    async def get_sheets_status():
        """Sheets 동기화 상태 조회

        Returns:
            enabled: Sheets 동기화 활성화 여부
            status: 연결 상태, 마지막 동기화 시간 등
        """
        if not state.sheets_sync:
            return {
                "enabled": False,
                "message": "Sheets sync not configured (set SHEETS_SYNC_ENABLED=true)",
            }

        status = state.sheets_sync.get_status()
        return {
            "enabled": True,
            **status.to_dict(),
        }

    @app.post("/api/sheets/sync")
    async def trigger_sheets_sync(
        background_tasks: BackgroundTasks,
        direction: str = "db_to_sheets",
    ):
        """Sheets 동기화 트리거

        Args:
            direction: 동기화 방향
                - db_to_sheets: DB → Sheets
                - sheets_to_db: Sheets → DB
                - hands: Archive Sheet → hands 테이블
                - bidirectional: 양방향 (Sheets 우선)
        """
        if not state.sheets_sync:
            return JSONResponse(
                status_code=400,
                content={"error": "Sheets sync not configured (set SHEETS_SYNC_ENABLED=true)"},
            )

        if state.sync_in_progress:
            return JSONResponse(
                status_code=409,
                content={"error": "Another sync is already in progress"},
            )

        def run_sheets_sync():
            state.sync_in_progress = True
            try:
                if direction == "db_to_sheets":
                    result = state.sheets_sync.sync_to_sheets()
                elif direction == "sheets_to_db":
                    result = state.sheets_sync.sync_from_sheets()
                elif direction == "hands":
                    result = state.sheets_sync.sync_hands()
                elif direction == "bidirectional":
                    result = state.sheets_sync.sync_bidirectional()
                else:
                    logger.warning(f"Unknown sync direction: {direction}")
                    return

                state.last_sync_result = {
                    "type": "sheets",
                    **result.to_dict(),
                }
                logger.info(f"Sheets 동기화 완료: {direction}")
            except Exception as e:
                logger.error(f"Sheets 동기화 오류: {e}")
                state.error_message = str(e)
            finally:
                state.sync_in_progress = False

        background_tasks.add_task(run_sheets_sync)
        return {
            "message": f"Sheets sync started ({direction})",
            "direction": direction,
            "status": "started",
        }

    @app.websocket("/ws/logs")
    async def websocket_logs(websocket: WebSocket):
        """로그 실시간 스트리밍 (WebSocket)"""
        await websocket.accept()
        state.connected_clients.append(websocket)

        try:
            # 기존 로그 전송
            for log in state.log_buffer:
                await websocket.send_text(log)

            # 연결 유지
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            if websocket in state.connected_clients:
                state.connected_clients.remove(websocket)

    return app


def get_embedded_dashboard() -> HTMLResponse:
    """내장 대시보드 HTML (Issue #45: 1:1 매칭 UI, Issue #51: 정렬/사유)"""
    html = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NAS → OTT 동기화 모니터</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .log-container { height: 300px; overflow-y: auto; font-family: monospace; font-size: 11px; }
        .status-dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
        .status-running { background-color: #22c55e; animation: pulse 2s infinite; }
        .status-stopped { background-color: #ef4444; }
        .status-syncing { background-color: #eab308; animation: pulse 1s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        .tab-active { border-bottom: 2px solid #3b82f6; color: #3b82f6; }
        .matching-table { font-size: 13px; }
        .badge { padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 500; }
        .badge-synced { background: #166534; color: #86efac; }
        .badge-not-synced { background: #991b1b; color: #fca5a5; }
        .badge-duplicate { background: #854d0e; color: #fde047; }
        .badge-reason { background: #374151; color: #9ca3af; font-size: 10px; margin-left: 4px; }
        .sort-btn { cursor: pointer; user-select: none; }
        .sort-btn:hover { color: #60a5fa; }
        .sort-active { color: #3b82f6; }
        .folder-item { transition: all 0.2s; }
        .folder-item:hover { background: rgba(59, 130, 246, 0.1); }
    </style>
</head>
<body class="bg-gray-900 text-gray-100 min-h-screen">
    <div class="container mx-auto px-4 py-6">
        <!-- Header -->
        <div class="flex justify-between items-center mb-6">
            <h1 class="text-2xl font-bold">🔄 NAS → OTT 동기화 모니터</h1>
            <div id="status-indicator" class="flex items-center gap-2 text-sm">
                <span class="status-dot status-running"></span>
                <span>정상 동작 중</span>
            </div>
        </div>

        <!-- Summary Cards (PRD 6.4) -->
        <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
            <!-- Source -->
            <div class="bg-gray-800 rounded-lg p-4">
                <div class="flex items-center gap-2 mb-2">
                    <span class="text-lg">📂</span>
                    <span class="text-sm text-gray-400">Source</span>
                </div>
                <div class="text-xs text-gray-500 mb-1">archive.db</div>
                <div id="source-count" class="text-2xl font-bold text-blue-400">-</div>
                <div class="text-xs text-gray-400">전체 파일</div>
            </div>

            <!-- Arrow -->
            <div class="hidden md:flex items-center justify-center text-2xl text-gray-600">
                →→
            </div>

            <!-- Target -->
            <div class="bg-gray-800 rounded-lg p-4">
                <div class="flex items-center gap-2 mb-2">
                    <span class="text-lg">📺</span>
                    <span class="text-sm text-gray-400">Target</span>
                </div>
                <div class="text-xs text-gray-500 mb-1">pokervod.db</div>
                <div id="target-count" class="text-2xl font-bold text-green-400">-</div>
                <div class="text-xs text-gray-400">HLS 등록</div>
            </div>

            <!-- Actions -->
            <div class="bg-gray-800 rounded-lg p-4">
                <div class="text-sm text-gray-400 mb-2">동기화</div>
                <button onclick="triggerSync()" class="w-full bg-blue-600 hover:bg-blue-700 px-3 py-2 rounded text-sm mb-2">
                    🔄 동기화 실행
                </button>
                <div id="last-sync" class="text-xs text-gray-500">-</div>
            </div>
        </div>

        <!-- Tabs -->
        <div class="flex gap-4 border-b border-gray-700 mb-4">
            <button id="tab-table" onclick="showTab('table')" class="px-4 py-2 tab-active">
                📋 1:1 매칭 테이블
            </button>
            <button id="tab-tree" onclick="showTab('tree')" class="px-4 py-2 text-gray-400 hover:text-gray-200">
                🌳 카탈로그 트리
            </button>
            <button id="tab-logs" onclick="showTab('logs')" class="px-4 py-2 text-gray-400 hover:text-gray-200">
                📜 로그
            </button>
        </div>

        <!-- Tab Content: Matching Table (PRD 6.2, Issue #51) -->
        <div id="content-table" class="bg-gray-800 rounded-lg p-4">
            <!-- Filter & Sort (Issue #51) -->
            <div class="flex flex-wrap gap-4 mb-4 text-sm">
                <select id="status-filter" onchange="loadMatching()" class="bg-gray-700 rounded px-3 py-1">
                    <option value="">전체 상태</option>
                    <option value="synced">✅ 동기화됨</option>
                    <option value="not_synced">❌ 미등록</option>
                    <option value="synced_with_duplicates">⚠️ 중복</option>
                </select>
                <select id="sort-by" onchange="loadMatching()" class="bg-gray-700 rounded px-3 py-1">
                    <option value="filename">파일명순</option>
                    <option value="size">크기순</option>
                    <option value="status">상태순</option>
                    <option value="path">경로순</option>
                    <option value="modified_at">수정일순</option>
                </select>
                <select id="sort-order" onchange="loadMatching()" class="bg-gray-700 rounded px-3 py-1">
                    <option value="asc">오름차순 ↑</option>
                    <option value="desc">내림차순 ↓</option>
                </select>
                <div id="matching-summary" class="text-gray-400 ml-auto"></div>
            </div>

            <!-- Issue #51: 미등록 사유별 통계 -->
            <div id="reason-summary" class="flex gap-3 mb-4 text-xs text-gray-500"></div>

            <!-- Table -->
            <div class="overflow-x-auto">
                <table class="w-full matching-table">
                    <thead>
                        <tr class="text-left border-b border-gray-700 text-gray-400">
                            <th class="pb-2 w-24">상태</th>
                            <th class="pb-2">📂 Source (archive.db)</th>
                            <th class="pb-2">📺 Target (pokervod.db)</th>
                            <th class="pb-2 w-16">ID</th>
                        </tr>
                    </thead>
                    <tbody id="matching-body">
                        <tr><td colspan="4" class="py-8 text-center text-gray-500">로딩 중...</td></tr>
                    </tbody>
                </table>
            </div>

            <!-- Pagination -->
            <div class="flex justify-between items-center mt-4 text-sm">
                <div id="pagination-info" class="text-gray-400"></div>
                <div class="flex gap-2">
                    <button onclick="changePage(-1)" class="bg-gray-700 hover:bg-gray-600 px-3 py-1 rounded">◀ 이전</button>
                    <button onclick="changePage(1)" class="bg-gray-700 hover:bg-gray-600 px-3 py-1 rounded">다음 ▶</button>
                </div>
            </div>
        </div>

        <!-- Tab Content: Tree View (PRD 6.3) -->
        <div id="content-tree" class="bg-gray-800 rounded-lg p-4 hidden">
            <div id="tree-container">
                <div class="text-gray-500">로딩 중...</div>
            </div>
        </div>

        <!-- Tab Content: Logs -->
        <div id="content-logs" class="bg-gray-800 rounded-lg p-4 hidden">
            <div class="flex justify-between items-center mb-2">
                <span class="text-sm text-gray-400">실시간 로그</span>
                <button onclick="clearLogs()" class="text-xs bg-gray-700 hover:bg-gray-600 px-2 py-1 rounded">
                    Clear
                </button>
            </div>
            <div id="log-container" class="log-container bg-gray-950 rounded p-3 text-green-400">
                <div id="logs"></div>
            </div>
        </div>
    </div>

    <script>
        let currentPage = 1;
        const perPage = 20;

        // Issue #51: 미등록 사유 라벨
        const REASON_LABELS = {
            'hls_incompatible': '🎬 HLS 비호환',
            'duplicate_excluded': '📋 중복 제외',
            'non_video': '📄 비디오 아님',
            'pending_sync': '⏳ 동기화 대기'
        };

        // Tab switching
        function showTab(tab) {
            ['table', 'tree', 'logs'].forEach(t => {
                document.getElementById('content-' + t).classList.toggle('hidden', t !== tab);
                document.getElementById('tab-' + t).classList.toggle('tab-active', t === tab);
                document.getElementById('tab-' + t).classList.toggle('text-gray-400', t !== tab);
            });
            if (tab === 'tree') loadTree();
        }

        // Load dashboard summary (Issue #51: 미등록 사유별 통계)
        async function loadDashboard() {
            try {
                const res = await fetch('/api/dashboard');
                const data = await res.json();
                document.getElementById('source-count').textContent = data.source?.total_files || 0;
                document.getElementById('target-count').textContent = data.target?.total_files || 0;
                if (data.sync_status?.last_sync_time) {
                    document.getElementById('last-sync').textContent =
                        '마지막: ' + new Date(data.sync_status.last_sync_time).toLocaleString('ko-KR');
                }

                // Issue #51: 미등록 사유별 통계 (Summary API에서 가져옴)
                const summaryRes = await fetch('/api/matching?page=1&per_page=1');
                const summaryData = await summaryRes.json();
                // 통계는 별도 API 필요 - 여기서는 로드시 갱신하지 않음
            } catch (e) {
                console.error('Dashboard load error:', e);
            }
        }

        // Load matching table (Issue #51: 정렬 + 미등록 사유)
        async function loadMatching() {
            try {
                const status = document.getElementById('status-filter').value;
                const sortBy = document.getElementById('sort-by').value;
                const sortOrder = document.getElementById('sort-order').value;

                let url = `/api/matching?page=${currentPage}&per_page=${perPage}`;
                url += `&sort_by=${sortBy}&sort_order=${sortOrder}`;
                if (status) url += `&status=${status}`;

                const res = await fetch(url);
                const data = await res.json();

                // Summary
                const sum = data.summary || {};
                document.getElementById('matching-summary').innerHTML =
                    `✅ ${sum.synced || 0} | ❌ ${sum.not_synced || 0} | ⚠️ ${sum.synced_with_duplicates || 0}`;

                // Pagination
                const start = data.total > 0 ? (currentPage-1)*perPage + 1 : 0;
                const end = Math.min(currentPage*perPage, data.total);
                document.getElementById('pagination-info').textContent =
                    `${data.total}개 중 ${start}-${end}`;

                // Table
                const tbody = document.getElementById('matching-body');
                if (!data.items || data.items.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="4" class="py-8 text-center text-gray-500">데이터 없음</td></tr>';
                    return;
                }

                tbody.innerHTML = data.items.map(item => {
                    const statusBadge = getStatusBadge(item.status, item.not_synced_reason);
                    const source = item.source || {};
                    const target = item.target;
                    const size = formatSize(source.size_bytes);

                    return `
                        <tr class="border-b border-gray-700/50 hover:bg-gray-700/30">
                            <td class="py-2">${statusBadge}</td>
                            <td class="py-2">
                                <div class="text-sm">${source.filename || '-'}</div>
                                <div class="text-xs text-gray-500 truncate max-w-md" title="${source.path || ''}">${source.path || ''}</div>
                                <div class="text-xs text-gray-600">${size} | ${item.is_hls_compatible ? 'HLS ✓' : 'HLS ✗'}</div>
                                ${item.duplicates?.length ? `<div class="text-xs text-yellow-600">+${item.duplicates.length} 중복</div>` : ''}
                            </td>
                            <td class="py-2">
                                ${target ? `
                                    <div class="text-sm text-green-400">${target.filename}</div>
                                    <div class="text-xs text-gray-500 truncate max-w-md">${target.nas_path || ''}</div>
                                ` : `<span class="text-gray-600">${getReasonText(item.not_synced_reason)}</span>`}
                            </td>
                            <td class="py-2 text-gray-500">${target?.id || '-'}</td>
                        </tr>
                    `;
                }).join('');
            } catch (e) {
                console.error('Matching load error:', e);
            }
        }

        // Issue #51: 미등록 사유 텍스트
        function getReasonText(reason) {
            switch(reason) {
                case 'hls_incompatible': return 'HLS 비호환 포맷';
                case 'duplicate_excluded': return '중복 제외';
                case 'non_video': return '비디오 아님';
                case 'pending_sync': return '동기화 대기';
                default: return '미등록';
            }
        }

        // Issue #51: 상태 배지 (미등록 사유 포함)
        function getStatusBadge(status, reason) {
            switch(status) {
                case 'synced': return '<span class="badge badge-synced">✅ 동기화</span>';
                case 'not_synced':
                    const reasonLabel = reason ? `<span class="badge badge-reason">${getReasonText(reason)}</span>` : '';
                    return `<span class="badge badge-not-synced">❌ 미등록</span>${reasonLabel}`;
                case 'synced_with_duplicates': return '<span class="badge badge-duplicate">⚠️ 중복</span>';
                default: return '<span class="badge bg-gray-600">?</span>';
            }
        }

        function formatSize(bytes) {
            if (!bytes) return '-';
            const gb = bytes / (1024 * 1024 * 1024);
            if (gb >= 1) return gb.toFixed(1) + ' GB';
            const mb = bytes / (1024 * 1024);
            return mb.toFixed(0) + ' MB';
        }

        function changePage(delta) {
            currentPage = Math.max(1, currentPage + delta);
            loadMatching();
        }

        // Load tree view (Issue #51: 폴더 트리 구조)
        async function loadTree() {
            try {
                const res = await fetch('/api/matching/tree');
                const data = await res.json();
                const container = document.getElementById('tree-container');

                if (!data.catalogs || data.catalogs.length === 0) {
                    container.innerHTML = '<div class="text-gray-500">카탈로그 없음</div>';
                    return;
                }

                container.innerHTML = data.catalogs.map(cat => `
                    <div class="mb-4">
                        <div class="flex items-center gap-2 cursor-pointer hover:bg-gray-700/50 p-2 rounded folder-item"
                             onclick="toggleCatalog('${cat.name}')">
                            <span id="icon-${cat.name}">📁</span>
                            <span class="font-medium">${cat.name}</span>
                            <span class="text-sm text-gray-400">(${cat.total_files} 파일)</span>
                            <span class="text-xs text-green-500">✅ ${cat.synced}</span>
                            <span class="text-xs text-red-500">❌ ${cat.not_synced}</span>
                        </div>
                        <div id="folders-${cat.name}" class="hidden ml-4">
                            ${renderFolderTree(cat.children || [], cat.name)}
                        </div>
                    </div>
                `).join('');
            } catch (e) {
                console.error('Tree load error:', e);
            }
        }

        // Issue #51: 계층적 폴더 트리 렌더링 (1단-2단-3단-4단...)
        function renderFolderTree(folders, parentId, depth = 1) {
            if (!folders || folders.length === 0) return '';

            return folders.map((folder, idx) => {
                const folderId = `${parentId}-${idx}`;
                const hasChildren = folder.children && folder.children.length > 0;
                const hasFiles = folder.files && folder.files.length > 0;

                // 재귀 통계 사용 (하위 폴더 포함)
                const totalFiles = folder.total_files_recursive || folder.total_files || 0;
                const synced = folder.synced_recursive || folder.synced || 0;
                const syncPercent = totalFiles > 0 ? Math.round((synced / totalFiles) * 100) : 0;

                // depth에 따른 들여쓰기 색상
                const borderColors = ['border-gray-600', 'border-gray-700', 'border-gray-800', 'border-gray-900'];
                const borderColor = borderColors[Math.min(depth - 1, borderColors.length - 1)];

                return `
                    <div class="border-l ${borderColor} pl-3 mt-1">
                        <div class="flex items-center gap-2 cursor-pointer hover:bg-gray-700/30 p-1 rounded folder-item"
                             onclick="toggleFolder('${folderId}')">
                            <span id="icon-${folderId}">${hasChildren || hasFiles ? '📁' : '📂'}</span>
                            <span class="text-sm ${depth === 1 ? 'font-medium' : ''}">${folder.name}</span>
                            <span class="text-xs text-gray-500">(${totalFiles})</span>
                            <span class="text-xs ${syncPercent >= 80 ? 'text-green-400' : syncPercent >= 50 ? 'text-yellow-400' : 'text-red-400'}">
                                ${syncPercent}%
                            </span>
                            ${hasChildren ? `<span class="text-xs text-gray-600">▶</span>` : ''}
                        </div>
                        <div id="content-${folderId}" class="hidden ml-2">
                            ${hasChildren ? renderFolderTree(folder.children, folderId, depth + 1) : ''}
                            ${hasFiles ? `
                                <div class="border-l border-gray-800 pl-2 mt-1">
                                    ${folder.files.map(f => `
                                        <div class="flex items-center gap-2 text-xs py-0.5 hover:bg-gray-800/30">
                                            <span>${f.status === 'synced' ? '✅' : '❌'}</span>
                                            <span class="text-gray-400 truncate max-w-sm" title="${f.path || f.name}">${f.name}</span>
                                            <span class="text-gray-600">${formatSize(f.size_bytes)}</span>
                                        </div>
                                    `).join('')}
                                </div>
                            ` : ''}
                        </div>
                    </div>
                `;
            }).join('');
        }

        function toggleCatalog(name) {
            const folders = document.getElementById('folders-' + name);
            const icon = document.getElementById('icon-' + name);
            folders.classList.toggle('hidden');
            icon.textContent = folders.classList.contains('hidden') ? '📁' : '📂';
        }

        function toggleFolder(id) {
            const content = document.getElementById('content-' + id);
            const icon = document.getElementById('icon-' + id);
            if (content) {
                content.classList.toggle('hidden');
                icon.textContent = content.classList.contains('hidden') ? '📁' : '📂';
            }
        }

        // Actions
        async function triggerSync() {
            if (!confirm('동기화를 시작하시겠습니까?')) return;
            try {
                const res = await fetch('/api/sync', { method: 'POST' });
                const data = await res.json();
                alert(data.message || data.error);
                loadDashboard();
            } catch (e) {
                alert('Error: ' + e.message);
            }
        }

        function clearLogs() {
            document.getElementById('logs').innerHTML = '';
        }

        // WebSocket for logs
        function connectWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const ws = new WebSocket(`${protocol}//${window.location.host}/ws/logs`);
            ws.onmessage = (event) => {
                const logsDiv = document.getElementById('logs');
                const line = document.createElement('div');
                line.textContent = event.data;
                logsDiv.appendChild(line);
                const container = document.getElementById('log-container');
                container.scrollTop = container.scrollHeight;
            };
            ws.onclose = () => setTimeout(connectWebSocket, 3000);
        }

        // Status check
        async function checkStatus() {
            try {
                const res = await fetch('/api/status');
                const data = await res.json();
                const indicator = document.getElementById('status-indicator');
                const dot = indicator.querySelector('.status-dot');
                const text = indicator.querySelector('span:last-child');

                if (data.sync_in_progress) {
                    dot.className = 'status-dot status-syncing';
                    text.textContent = '동기화 중...';
                } else if (data.is_running) {
                    dot.className = 'status-dot status-running';
                    text.textContent = '정상 동작 중';
                } else {
                    dot.className = 'status-dot status-stopped';
                    text.textContent = '중지됨';
                }
            } catch (e) {}
        }

        // Init
        loadDashboard();
        loadMatching();
        connectWebSocket();
        setInterval(loadDashboard, 30000);
        setInterval(checkStatus, 5000);
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html)


# 기본 앱 인스턴스
app = create_app()


# =============================================================================
# CLI
# =============================================================================


def main():
    import argparse

    import uvicorn

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    parser = argparse.ArgumentParser(description="NAS Auto Sync Web Monitor")
    parser.add_argument("--host", default="0.0.0.0", help="Host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8080, help="Port (default: 8080)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")

    args = parser.parse_args()

    uvicorn.run(
        "archive_analyzer.web.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
