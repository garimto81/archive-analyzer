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
    """DB 통계 조회"""
    if not Path(db_path).exists():
        return {"error": f"DB not found: {db_path}"}

    conn = sqlite3.connect(db_path)
    try:
        stats = {}

        # 전체 파일 수
        cursor = conn.execute("SELECT COUNT(*) FROM files")
        stats["total_files"] = cursor.fetchone()[0]

        # 상태별 파일 수
        cursor = conn.execute(
            """SELECT COALESCE(status, 'unknown'), COUNT(*)
               FROM files GROUP BY status"""
        )
        stats["by_status"] = dict(cursor.fetchall())

        # 파일 타입별
        cursor = conn.execute(
            """SELECT file_type, COUNT(*)
               FROM files GROUP BY file_type
               ORDER BY COUNT(*) DESC LIMIT 10"""
        )
        stats["by_type"] = dict(cursor.fetchall())

        # 최근 동기화 파일
        cursor = conn.execute(
            """SELECT path, filename, updated_at
               FROM files
               ORDER BY updated_at DESC LIMIT 5"""
        )
        stats["recent_files"] = [
            {"path": r[0], "filename": r[1], "updated_at": r[2]}
            for r in cursor.fetchall()
        ]

        # DB 파일 크기
        stats["db_size_mb"] = round(Path(db_path).stat().st_size / (1024 * 1024), 2)

        return stats

    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()


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

    logger.info(f"Web 모니터링 서버 시작: http://{state.config.host}:{state.config.port}")

    yield

    # Shutdown
    state.is_running = False
    logger.info("Web 모니터링 서버 종료")


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

    if templates_dir.exists():
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
    """내장 대시보드 HTML (템플릿 파일 없을 때)"""
    html = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NAS Auto Sync Monitor</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
    <style>
        .log-container { height: 400px; overflow-y: auto; font-family: monospace; font-size: 12px; }
        .status-dot { width: 12px; height: 12px; border-radius: 50%; display: inline-block; }
        .status-running { background-color: #22c55e; animation: pulse 2s infinite; }
        .status-stopped { background-color: #ef4444; }
        .status-syncing { background-color: #eab308; animation: pulse 1s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
    </style>
</head>
<body class="bg-gray-900 text-gray-100 min-h-screen">
    <div class="container mx-auto px-4 py-8">
        <!-- Header -->
        <div class="flex justify-between items-center mb-8">
            <h1 class="text-3xl font-bold">NAS Auto Sync Monitor</h1>
            <div id="status-indicator" class="flex items-center gap-2">
                <span class="status-dot status-running"></span>
                <span>Running</span>
            </div>
        </div>

        <!-- Stats Grid -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
            <!-- Archive DB -->
            <div class="bg-gray-800 rounded-lg p-6">
                <h2 class="text-xl font-semibold mb-4">Archive DB</h2>
                <div id="archive-stats" hx-get="/api/stats" hx-trigger="load, every 30s" hx-target="#archive-stats">
                    <p class="text-gray-400">Loading...</p>
                </div>
            </div>

            <!-- Pokervod DB -->
            <div class="bg-gray-800 rounded-lg p-6">
                <h2 class="text-xl font-semibold mb-4">Pokervod DB</h2>
                <div id="pokervod-stats">
                    <p class="text-gray-400">Loading...</p>
                </div>
            </div>

            <!-- Actions -->
            <div class="bg-gray-800 rounded-lg p-6">
                <h2 class="text-xl font-semibold mb-4">Actions</h2>
                <div class="space-y-3">
                    <button onclick="triggerSync()" class="w-full bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded">
                        Manual Sync
                    </button>
                    <button onclick="triggerReconcile(true)" class="w-full bg-yellow-600 hover:bg-yellow-700 px-4 py-2 rounded">
                        Reconcile (Dry Run)
                    </button>
                    <button onclick="triggerReconcile(false)" class="w-full bg-red-600 hover:bg-red-700 px-4 py-2 rounded">
                        Reconcile (Execute)
                    </button>
                </div>
            </div>
        </div>

        <!-- File History -->
        <div class="bg-gray-800 rounded-lg p-6 mb-8">
            <h2 class="text-xl font-semibold mb-4">File History (Recent Changes)</h2>
            <div id="file-history" class="overflow-x-auto">
                <table class="w-full text-sm">
                    <thead>
                        <tr class="text-left border-b border-gray-700">
                            <th class="pb-2">Event</th>
                            <th class="pb-2">File</th>
                            <th class="pb-2">Path</th>
                            <th class="pb-2">Time</th>
                        </tr>
                    </thead>
                    <tbody id="history-body">
                        <tr><td colspan="4" class="text-gray-400 py-4">Loading...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Live Logs -->
        <div class="bg-gray-800 rounded-lg p-6">
            <div class="flex justify-between items-center mb-4">
                <h2 class="text-xl font-semibold">Live Logs</h2>
                <button onclick="clearLogs()" class="text-sm bg-gray-700 hover:bg-gray-600 px-3 py-1 rounded">
                    Clear
                </button>
            </div>
            <div id="log-container" class="log-container bg-gray-950 rounded p-4 text-green-400">
                <div id="logs"></div>
            </div>
        </div>
    </div>

    <script>
        // WebSocket for live logs
        let ws;
        function connectWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${protocol}//${window.location.host}/ws/logs`);

            ws.onmessage = (event) => {
                const logsDiv = document.getElementById('logs');
                const line = document.createElement('div');
                line.textContent = event.data;
                logsDiv.appendChild(line);

                // Auto-scroll
                const container = document.getElementById('log-container');
                container.scrollTop = container.scrollHeight;
            };

            ws.onclose = () => {
                setTimeout(connectWebSocket, 3000);
            };
        }
        connectWebSocket();

        // Load stats
        async function loadStats() {
            try {
                const res = await fetch('/api/stats');
                const data = await res.json();

                document.getElementById('archive-stats').innerHTML = formatStats(data.archive);
                document.getElementById('pokervod-stats').innerHTML = formatStats(data.pokervod);
            } catch (e) {
                console.error('Stats load error:', e);
            }
        }

        function formatStats(stats) {
            if (stats.error) return `<p class="text-red-400">${stats.error}</p>`;
            return `
                <div class="space-y-2">
                    <p>Total Files: <span class="font-bold text-blue-400">${stats.total_files || 0}</span></p>
                    <p>DB Size: <span class="text-gray-400">${stats.db_size_mb || 0} MB</span></p>
                    <div class="text-sm text-gray-400">
                        ${Object.entries(stats.by_status || {}).map(([k, v]) => `${k}: ${v}`).join(', ')}
                    </div>
                </div>
            `;
        }

        // Load history
        async function loadHistory() {
            try {
                const res = await fetch('/api/history?limit=20');
                const data = await res.json();

                const tbody = document.getElementById('history-body');
                if (!data.history || data.history.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="4" class="text-gray-400 py-4">No history</td></tr>';
                    return;
                }

                tbody.innerHTML = data.history.map(h => `
                    <tr class="border-b border-gray-700">
                        <td class="py-2">
                            <span class="px-2 py-1 rounded text-xs ${getEventClass(h.event_type)}">
                                ${h.event_type}
                            </span>
                        </td>
                        <td class="py-2">${h.filename || '-'}</td>
                        <td class="py-2 text-gray-400 text-xs">${h.new_path || h.old_path || '-'}</td>
                        <td class="py-2 text-gray-400 text-xs">${h.detected_at || '-'}</td>
                    </tr>
                `).join('');
            } catch (e) {
                console.error('History load error:', e);
            }
        }

        function getEventClass(event) {
            switch(event) {
                case 'created': return 'bg-green-600';
                case 'deleted': return 'bg-red-600';
                case 'moved': return 'bg-yellow-600';
                case 'modified': return 'bg-blue-600';
                default: return 'bg-gray-600';
            }
        }

        // Actions
        async function triggerSync() {
            if (!confirm('동기화를 시작하시겠습니까?')) return;
            try {
                const res = await fetch('/api/sync', { method: 'POST' });
                const data = await res.json();
                alert(data.message || data.error);
            } catch (e) {
                alert('Error: ' + e.message);
            }
        }

        async function triggerReconcile(dryRun) {
            const msg = dryRun ? '정합성 검증 (Dry Run)' : '정합성 검증 (실제 실행 - 삭제된 파일 마킹)';
            if (!confirm(`${msg}을 시작하시겠습니까?`)) return;
            try {
                const res = await fetch(`/api/reconcile?dry_run=${dryRun}`, { method: 'POST' });
                const data = await res.json();
                alert(data.message || data.error);
            } catch (e) {
                alert('Error: ' + e.message);
            }
        }

        function clearLogs() {
            document.getElementById('logs').innerHTML = '';
        }

        // Polling
        loadStats();
        loadHistory();
        setInterval(loadStats, 30000);
        setInterval(loadHistory, 60000);

        // Status check
        async function checkStatus() {
            try {
                const res = await fetch('/api/status');
                const data = await res.json();
                const indicator = document.getElementById('status-indicator');
                const dot = indicator.querySelector('.status-dot');

                if (data.sync_in_progress) {
                    dot.className = 'status-dot status-syncing';
                    indicator.querySelector('span:last-child').textContent = 'Syncing...';
                } else if (data.is_running) {
                    dot.className = 'status-dot status-running';
                    indicator.querySelector('span:last-child').textContent = 'Running';
                } else {
                    dot.className = 'status-dot status-stopped';
                    indicator.querySelector('span:last-child').textContent = 'Stopped';
                }
            } catch (e) {
                console.error('Status check error:', e);
            }
        }
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
