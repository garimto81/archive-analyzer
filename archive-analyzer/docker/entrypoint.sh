#!/bin/bash
# NAS Auto Sync Service Entrypoint
# Issue #43: Docker 서버 배포 + GUI 모니터링

set -e

# 로그 함수
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# 환경변수 출력
log "=== NAS Auto Sync Service ==="
log "ARCHIVE_DB: $ARCHIVE_DB"
log "POKERVOD_DB: $POKERVOD_DB"
log "NAS_MOUNT_PATH: $NAS_MOUNT_PATH"
log "SYNC_INTERVAL: $SYNC_INTERVAL"
log "WEB_PORT: $WEB_PORT"
log "============================="

# 데이터 디렉토리 확인
mkdir -p /app/data/output /app/logs

# 명령어 처리
case "$1" in
    web)
        log "Starting Web Monitoring Server on port $WEB_PORT..."
        exec python -m uvicorn archive_analyzer.web.app:app \
            --host 0.0.0.0 \
            --port "$WEB_PORT"
        ;;

    sync)
        log "Starting NAS Auto Sync Daemon..."
        exec python -m archive_analyzer.nas_auto_sync \
            --interval "$SYNC_INTERVAL" \
            --archive-db "$ARCHIVE_DB" \
            --pokervod-db "$POKERVOD_DB"
        ;;

    track)
        log "Starting NAS Path Tracker..."
        exec python -m archive_analyzer.nas_auto_sync \
            --track \
            --nas-mount "$NAS_MOUNT_PATH" \
            --archive-db "$ARCHIVE_DB" \
            --pokervod-db "$POKERVOD_DB"
        ;;

    reconcile)
        log "Running Reconciliation..."
        exec python -m archive_analyzer.nas_auto_sync \
            --reconcile \
            --nas-mount "$NAS_MOUNT_PATH" \
            --archive-db "$ARCHIVE_DB" \
            --pokervod-db "$POKERVOD_DB"
        ;;

    all)
        log "Starting Web Server + Sync Daemon..."
        # 백그라운드로 sync 데몬 실행
        python -m archive_analyzer.nas_auto_sync \
            --interval "$SYNC_INTERVAL" \
            --archive-db "$ARCHIVE_DB" \
            --pokervod-db "$POKERVOD_DB" &

        # 포그라운드로 웹 서버 실행
        exec python -m uvicorn archive_analyzer.web.app:app \
            --host 0.0.0.0 \
            --port "$WEB_PORT"
        ;;

    *)
        # 커스텀 명령어 실행
        exec "$@"
        ;;
esac
