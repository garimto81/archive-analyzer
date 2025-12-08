"""NAS Auto Sync Web Monitoring

Issue #43: Docker 서버 배포 + GUI 모니터링
"""

from .app import app, create_app

__all__ = ["app", "create_app"]
