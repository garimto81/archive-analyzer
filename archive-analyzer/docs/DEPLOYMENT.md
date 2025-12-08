# NAS Auto Sync 배포 가이드

Issue #43: Docker 서버 배포 + GUI 모니터링 + Windows 앱 패키징

## 목차

1. [Docker 배포](#docker-배포)
2. [Windows 앱 설치](#windows-앱-설치)
3. [Web 모니터링](#web-모니터링)
4. [설정](#설정)

---

## Docker 배포

### 빠른 시작

```bash
# 1. 이미지 빌드
docker build -f Dockerfile.monitor -t nas-sync-monitor .

# 2. 컨테이너 실행
docker run -d \
  --name nas-sync-monitor \
  -p 8080:8080 \
  -v ./data:/app/data \
  nas-sync-monitor
```

### docker-compose 사용

```bash
# 전체 서비스 시작 (Web + Sync 데몬)
docker-compose -f docker-compose.monitor.yml up -d

# 로그 확인
docker-compose -f docker-compose.monitor.yml logs -f

# 서비스 중지
docker-compose -f docker-compose.monitor.yml down
```

### 환경변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `ARCHIVE_DB` | `/app/data/output/archive.db` | Archive DB 경로 |
| `POKERVOD_DB` | `/app/data/pokervod.db` | Pokervod DB 경로 |
| `NAS_MOUNT_PATH` | `/nas` | NAS 마운트 경로 |
| `SYNC_INTERVAL` | `1800` | 동기화 간격 (초) |
| `WEB_PORT` | `8080` | 웹 서버 포트 |
| `LOG_LEVEL` | `INFO` | 로그 레벨 |

### NAS 마운트 (CIFS/SMB)

호스트에서 NAS를 마운트하고 컨테이너에 바인드:

```bash
# 호스트에서 NAS 마운트
sudo mount -t cifs //10.10.100.122/docker/GGPNAs/ARCHIVE /mnt/nas \
  -o username=GGP,password=*****

# docker-compose.monitor.yml 수정
volumes:
  - /mnt/nas:/nas:ro
```

### 실행 모드

```bash
# Web 서버만
docker run nas-sync-monitor web

# 동기화 데몬만
docker run nas-sync-monitor sync

# 경로 추적 모드
docker run nas-sync-monitor track

# 정합성 검증 (1회)
docker run nas-sync-monitor reconcile

# Web + Sync (기본)
docker run nas-sync-monitor all
```

---

## Windows 앱 설치

### 방법 1: 소스에서 빌드

```powershell
# 1. 의존성 설치
pip install -e ".[web,tray]"
pip install pyinstaller

# 2. 빌드 실행
python scripts/build_installer.py

# 3. 실행 파일 확인
dist/NASAutoSync/NASAutoSync.exe
```

### 방법 2: 설치 프로그램 생성

[Inno Setup](https://jrsoftware.org/isinfo.php) 설치 후:

```powershell
# 빌드 스크립트 생성
python scripts/build_installer.py --inno

# 설치 프로그램 생성
iscc installer/setup.iss

# 결과물
dist/NASAutoSync_Setup_v1.0.0.exe
```

### 시스템 트레이 앱 기능

- **Start/Stop**: 서비스 시작/중지
- **Open Dashboard**: 웹 대시보드 열기 (브라우저)
- **Settings**: 설정 변경
  - DB 경로
  - NAS 마운트 경로
  - 동기화 간격
  - 웹 포트
  - Windows 시작 시 자동 실행

### 설정 파일 위치

```
%APPDATA%\NASAutoSync\config.json
```

---

## Web 모니터링

### 접속

```
http://localhost:8080
```

### 기능

| 기능 | 설명 |
|------|------|
| **Dashboard** | 전체 상태 요약 |
| **File History** | 파일 변경 이력 (생성/이동/삭제) |
| **Live Logs** | 실시간 로그 스트리밍 (WebSocket) |
| **Manual Sync** | 수동 동기화 트리거 |
| **Reconcile** | DB vs NAS 정합성 검증 |

### API 엔드포인트

| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/health` | GET | 헬스 체크 |
| `/api/status` | GET | 서비스 상태 |
| `/api/stats` | GET | DB 통계 |
| `/api/history` | GET | 파일 변경 이력 |
| `/api/logs` | GET | 최근 로그 |
| `/api/sync` | POST | 동기화 트리거 |
| `/api/reconcile` | POST | 정합성 검증 |
| `/ws/logs` | WebSocket | 실시간 로그 |

---

## 설정

### Docker 환경

`.env` 파일 생성:

```env
# SMB/NAS 설정
SMB_SERVER=10.10.100.122
SMB_SHARE=docker
SMB_USERNAME=GGP
SMB_PASSWORD=your_password

# 경로
HOST_DATA_DIR=./data
NAS_MOUNT_PATH=/mnt/nas

# 동기화
SYNC_INTERVAL=1800

# 웹
WEB_PORT=8080
LOG_LEVEL=INFO
```

### Windows 앱 설정

설정 GUI에서 변경하거나 직접 `config.json` 수정:

```json
{
  "archive_db": "D:/data/archive.db",
  "pokervod_db": "D:/AI/claude01/shared-data/pokervod.db",
  "nas_mount_path": "Z:/GGPNAs/ARCHIVE",
  "sync_interval": 1800,
  "web_port": 8080,
  "auto_start": true,
  "minimize_to_tray": true
}
```

---

## 문제 해결

### Docker: NAS 연결 실패

```bash
# 호스트에서 마운트 확인
ls /mnt/nas

# 컨테이너 내부 확인
docker exec -it nas-sync-monitor ls /nas
```

### Windows: 서비스 시작 실패

1. 로그 확인: `%APPDATA%\NASAutoSync\logs\`
2. DB 경로 확인
3. 포트 충돌 확인: `netstat -an | findstr 8080`

### Web: WebSocket 연결 끊김

- 방화벽 설정 확인
- 프록시 WebSocket 지원 확인
- 브라우저 콘솔 오류 확인

---

## 참조

- Issue #41: NAS 경로 변경 실시간 감지
- Issue #43: Docker + GUI + 패키징
- [FastAPI 문서](https://fastapi.tiangolo.com/)
- [PyInstaller 문서](https://pyinstaller.org/)
