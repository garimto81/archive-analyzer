#!/usr/bin/env python
"""NAS Path Tracker 스키마 마이그레이션

Issue #41: NAS 경로 변경 실시간 감지 및 DB 자동 동기화 시스템

이 스크립트는 다음 변경사항을 적용합니다:
1. files 테이블에 status, content_hash, deleted_at, last_verified_at 컬럼 추가
2. file_history 테이블 생성 (변경 이력 추적)
3. 인덱스 생성

Usage:
    python scripts/migrate_path_tracker.py [--dry-run] [--db-path PATH]
"""

import argparse
import logging
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# 기본 DB 경로
DEFAULT_ARCHIVE_DB = "data/output/archive.db"
DEFAULT_POKERVOD_DB = "D:/AI/claude01/shared-data/pokervod.db"

# 마이그레이션 버전
MIGRATION_VERSION = "41.1.0"


def backup_database(db_path: str) -> str:
    """DB 백업 생성"""
    backup_path = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(db_path, backup_path)
    logger.info(f"백업 생성: {backup_path}")
    return backup_path


def get_existing_columns(conn: sqlite3.Connection, table: str) -> set:
    """테이블의 기존 컬럼 목록 조회"""
    cursor = conn.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cursor.fetchall()}


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    """테이블 존재 여부 확인"""
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,)
    )
    return cursor.fetchone() is not None


def migrate_files_table(conn: sqlite3.Connection, dry_run: bool = False) -> int:
    """files 테이블에 새 컬럼 추가"""
    changes = 0
    existing = get_existing_columns(conn, "files")

    new_columns = [
        ("status", "TEXT DEFAULT 'active'"),
        ("content_hash", "TEXT"),
        ("deleted_at", "TIMESTAMP"),
        ("last_verified_at", "TIMESTAMP"),
    ]

    for col_name, col_def in new_columns:
        if col_name not in existing:
            sql = f"ALTER TABLE files ADD COLUMN {col_name} {col_def}"
            logger.info(f"  + 컬럼 추가: {col_name}")
            if not dry_run:
                conn.execute(sql)
            changes += 1
        else:
            logger.debug(f"  - 컬럼 존재: {col_name}")

    return changes


def create_file_history_table(conn: sqlite3.Connection, dry_run: bool = False) -> bool:
    """file_history 테이블 생성"""
    if table_exists(conn, "file_history"):
        logger.info("  - file_history 테이블 이미 존재")
        return False

    sql = """
    CREATE TABLE file_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_id TEXT NOT NULL,
        event_type TEXT NOT NULL,
        old_path TEXT,
        new_path TEXT,
        old_hash TEXT,
        new_hash TEXT,
        detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        synced_at TIMESTAMP,
        metadata TEXT,

        FOREIGN KEY (file_id) REFERENCES files(id)
    )
    """

    logger.info("  + file_history 테이블 생성")
    if not dry_run:
        conn.execute(sql)

    return True


def create_indexes(conn: sqlite3.Connection, dry_run: bool = False) -> int:
    """인덱스 생성"""
    indexes = [
        ("idx_files_status", "files", "status"),
        ("idx_files_content_hash", "files", "content_hash"),
        ("idx_file_history_file_id", "file_history", "file_id"),
        ("idx_file_history_detected_at", "file_history", "detected_at"),
        ("idx_file_history_event_type", "file_history", "event_type"),
    ]

    created = 0
    for idx_name, table, column in indexes:
        # 인덱스 존재 확인
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
            (idx_name,)
        )
        if cursor.fetchone():
            logger.debug(f"  - 인덱스 존재: {idx_name}")
            continue

        sql = f"CREATE INDEX {idx_name} ON {table}({column})"
        logger.info(f"  + 인덱스 생성: {idx_name}")
        if not dry_run:
            try:
                conn.execute(sql)
                created += 1
            except sqlite3.OperationalError as e:
                logger.warning(f"  ! 인덱스 생성 실패: {idx_name} - {e}")

    return created


def record_migration(conn: sqlite3.Connection, version: str, dry_run: bool = False):
    """마이그레이션 기록"""
    # migrations 테이블 생성 (없으면)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS _migrations (
            version TEXT PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            description TEXT
        )
    """)

    if not dry_run:
        conn.execute(
            "INSERT OR REPLACE INTO _migrations (version, description) VALUES (?, ?)",
            (version, "NAS Path Tracker: status, content_hash, file_history")
        )


def migrate_database(db_path: str, dry_run: bool = False) -> dict:
    """단일 DB 마이그레이션 실행"""
    result = {
        "db_path": db_path,
        "columns_added": 0,
        "tables_created": 0,
        "indexes_created": 0,
        "success": False,
    }

    if not Path(db_path).exists():
        logger.warning(f"DB 파일 없음: {db_path}")
        return result

    logger.info(f"\n{'=' * 50}")
    logger.info(f"마이그레이션: {db_path}")
    logger.info(f"{'=' * 50}")

    if not dry_run:
        backup_database(db_path)

    conn = sqlite3.connect(db_path)

    try:
        # files 테이블 확인
        if not table_exists(conn, "files"):
            logger.warning("files 테이블 없음, 스킵")
            return result

        # 1. files 테이블 컬럼 추가
        logger.info("\n[1/4] files 테이블 컬럼 추가...")
        result["columns_added"] = migrate_files_table(conn, dry_run)

        # 2. file_history 테이블 생성
        logger.info("\n[2/4] file_history 테이블 생성...")
        if create_file_history_table(conn, dry_run):
            result["tables_created"] = 1

        # 3. 인덱스 생성
        logger.info("\n[3/4] 인덱스 생성...")
        result["indexes_created"] = create_indexes(conn, dry_run)

        # 4. 마이그레이션 기록
        logger.info("\n[4/4] 마이그레이션 기록...")
        record_migration(conn, MIGRATION_VERSION, dry_run)

        if not dry_run:
            conn.commit()

        result["success"] = True
        logger.info("\n✅ 마이그레이션 완료")

    except Exception as e:
        logger.exception(f"마이그레이션 실패: {e}")
        conn.rollback()
    finally:
        conn.close()

    return result


def main():
    parser = argparse.ArgumentParser(
        description="NAS Path Tracker 스키마 마이그레이션",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="실제 변경 없이 시뮬레이션",
    )
    parser.add_argument(
        "--archive-db",
        type=str,
        default=DEFAULT_ARCHIVE_DB,
        help=f"archive.db 경로 (기본: {DEFAULT_ARCHIVE_DB})",
    )
    parser.add_argument(
        "--pokervod-db",
        type=str,
        default=DEFAULT_POKERVOD_DB,
        help=f"pokervod.db 경로 (기본: {DEFAULT_POKERVOD_DB})",
    )
    parser.add_argument(
        "--archive-only",
        action="store_true",
        help="archive.db만 마이그레이션",
    )
    parser.add_argument(
        "--pokervod-only",
        action="store_true",
        help="pokervod.db만 마이그레이션",
    )

    args = parser.parse_args()

    if args.dry_run:
        logger.info("=" * 50)
        logger.info("[DRY-RUN 모드] 실제 변경 없이 시뮬레이션합니다")
        logger.info("=" * 50)

    results = []

    # archive.db 마이그레이션
    if not args.pokervod_only:
        result = migrate_database(args.archive_db, args.dry_run)
        results.append(result)

    # pokervod.db 마이그레이션
    if not args.archive_only:
        result = migrate_database(args.pokervod_db, args.dry_run)
        results.append(result)

    # 결과 요약
    logger.info("\n" + "=" * 50)
    logger.info("마이그레이션 결과 요약")
    logger.info("=" * 50)

    for r in results:
        status = "✅" if r["success"] else "❌"
        logger.info(f"\n{status} {r['db_path']}")
        logger.info(f"   컬럼 추가: {r['columns_added']}")
        logger.info(f"   테이블 생성: {r['tables_created']}")
        logger.info(f"   인덱스 생성: {r['indexes_created']}")

    if args.dry_run:
        logger.info("\n[DRY-RUN 완료] 실제 변경 없음")

    # 실패한 경우 exit code 1
    if not all(r["success"] for r in results if Path(r["db_path"]).exists()):
        sys.exit(1)


if __name__ == "__main__":
    main()
