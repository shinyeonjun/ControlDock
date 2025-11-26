# ControlDock (OpsHub)

Windows PC 원격 관리 시스템 - 네트워크 프로그래밍 기반의 분산 관리 플랫폼

## 📋 프로젝트 개요

ControlDock은 Windows PC를 원격으로 관리하기 위한 클라이언트-서버 시스템입니다. 웹 기반 대시보드를 통해 여러 PC를 중앙에서 관리하고, 에이전트 프로그램을 통해 원격 명령 실행, 상태 모니터링, 배포 관리 등을 수행할 수 있습니다.

### 주요 특징

- 🌐 **웹 기반 대시보드**: 브라우저에서 모든 PC를 중앙 관리
- 🔐 **안전한 등록 프로세스**: 관리자 승인 기반 PC 등록 시스템
- 📡 **다중 프로토콜 지원**: HTTP (웹 UI), TCP (에이전트 통신), UDP (브로드캐스트)
- 🖥️ **Windows 서비스 지원**: 백그라운드에서 자동 실행
- 📦 **EXE 배포**: PyInstaller로 빌드된 독립 실행 파일
- 🗄️ **Supabase 연동**: 클라우드 데이터베이스 사용

## 🏗️ 아키텍처

```
┌─────────────────┐         ┌──────────────────┐         ┌──────────────┐
│  Web Dashboard  │ ─HTTP─> │   HTTP Server    │         │   Supabase   │
│   (Frontend)    │         │   (Port 8000)   │ ──────> │  Database    │
└─────────────────┘         └──────────────────┘         └──────────────┘
                                      │
                                      │ TCP (Port 5500)
                                      │ UDP (Port 5501, 5502)
                                      │
                            ┌─────────┴─────────┐
                            │  TCP/UDP Server  │
                            │  (Registration) │
                            └─────────┬─────────┘
                                      │
                            ┌─────────┴─────────┐
                            │  Agent (Windows)  │
                            │  OpsHubAgent.exe │
                            └──────────────────┘
```

### 프로토콜 사용

- **HTTP (Port 8000)**: 웹 대시보드 및 REST API
- **TCP (Port 5500)**: PC 등록 및 에이전트 통신
- **UDP (Port 5501, 5502)**: 하트비트 및 브로드캐스트 알림

## 📁 프로젝트 구조

```
ControlDock/
├── backend/                 # 서버 애플리케이션
│   ├── server/
│   │   ├── http_server.py   # HTTP 서버 (웹 UI)
│   │   ├── udp_server.py    # UDP 서버 (브로드캐스트)
│   │   └── pc_regis/
│   │       └── tcp_server.py # TCP 서버 (에이전트 통신)
│   ├── database/            # 데이터베이스 레이어
│   │   ├── db.py           # Supabase 연결
│   │   ├── pc_db.py        # PC 정보 관리
│   │   └── registration_db.py # 등록 요청 관리
│   ├── main.py             # 서버 메인 엔트리포인트
│   ├── requirements.txt     # Python 의존성
│   ├── Dockerfile          # Docker 이미지 정의
│   └── docker-compose.yml   # Docker Compose 설정
│
├── app/                    # Windows 에이전트 애플리케이션
│   ├── config/             # 설정 관리
│   │   └── config.py       # 설정 로드/저장 (%APPDATA% 우선)
│   ├── client/             # 서버 통신 클라이언트
│   │   ├── api_client.py   # HTTP API 클라이언트
│   │   └── tcp_client.py   # TCP 클라이언트
│   ├── core/               # 핵심 로직
│   │   ├── agent.py        # 메인 에이전트
│   │   └── registration.py # 등록 관리
│   ├── gui/                # GUI 컴포넌트
│   │   ├── tray_icon.py    # 시스템 트레이 아이콘
│   │   └── registration_dialog.py # 등록 승인 다이얼로그
│   ├── service/            # Windows 서비스
│   │   └── windows_service.py
│   ├── utils/               # 유틸리티
│   │   └── system_info.py  # 시스템 정보 수집
│   ├── main.py             # 메인 엔트리포인트
│   ├── requirements.txt    # Python 의존성
│   ├── build.bat           # EXE 빌드 스크립트
│   └── OpsHubAgent.spec    # PyInstaller 스펙
│
├── frontend/               # 웹 대시보드
│   ├── html/               # HTML 파일
│   │   ├── index.html      # 메인 대시보드
│   │   ├── agents.html     # 에이전트 관리
│   │   ├── deployments.html # 배포 관리
│   │   └── announcements.html # 공지사항
│   ├── css/                # 스타일시트
│   └── js/                 # JavaScript
│       ├── config.js       # 설정
│       ├── dashboard.js    # 대시보드 로직
│       ├── agents.js       # 에이전트 관리
│       └── deployments.js  # 배포 관리
│
├── config.json             # 프로젝트 루트 설정 파일
└── README.md               # 이 파일
```

## 🚀 시작하기

### 사전 요구사항

- Python 3.11 이상
- Supabase 계정 및 프로젝트
- Docker (선택사항, 서버 배포용)
- Windows 10/11 (에이전트 실행 환경)

### 1. 저장소 클론

```bash
git clone https://github.com/shinyeonjun/ControlDock.git
cd ControlDock
```

### 2. 환경 설정

#### 백엔드 설정

1. `backend/` 디렉토리에 `.env` 파일 생성:

```bash
cd backend
cp .env.example .env  # .env.example이 있다면
```

2. `.env` 파일에 Supabase 정보 입력:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
```

#### 프론트엔드 설정

`config.json` 파일 수정:

```json
{
  "server": {
    "host": "172.29.44.72",
    "http_port": 8000,
    "tcp_port": 5500
  },
  "frontend": {
    "api_base_url": "http://172.29.44.72:8000/api"
  }
}
```

### 3. 백엔드 서버 실행

#### 방법 1: Docker 사용 (권장)

```bash
cd backend
docker-compose up -d
```

#### 방법 2: 직접 실행

```bash
cd backend

# 가상환경 생성 및 활성화
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# 의존성 설치
pip install -r requirements.txt

# 서버 실행
python main.py
```

서버가 다음 포트에서 실행됩니다:
- HTTP: `http://0.0.0.0:8000`
- TCP: `0.0.0.0:5500`
- UDP: `0.0.0.0:5501`, `5502`

### 4. 에이전트 빌드 및 배포

#### 개발 모드 실행

```bash
cd app

# 가상환경 활성화
venv\Scripts\activate  # Windows

# 의존성 설치
pip install -r requirements.txt

# 실행
python main.py
```

#### EXE 빌드

```bash
cd app
build.bat
```

빌드된 EXE 파일: `app/dist/OpsHubAgent.exe`

#### 에이전트 설정

에이전트는 다음 순서로 설정 파일을 읽습니다:

1. **최우선**: `%APPDATA%\OpsHub\config.json` (사용자 설정)
2. **기본값**: EXE 옆 `config.json` (배포 시 설정)

`%APPDATA%\OpsHub\config.json` 예시:

```json
{
  "agent_id": "your-agent-id",
  "server": {
    "host": "172.29.44.72",
    "http_port": 8000,
    "tcp_port": 5500
  },
  "agent": {
    "poll_interval": 10,
    "request_status_interval": 30,
    "auto_start": true
  }
}
```

## 📖 사용 방법

### 웹 대시보드 접속

브라우저에서 `http://172.29.44.72:8000` 접속

### PC 등록 프로세스

1. **에이전트 실행**: `OpsHubAgent.exe` 실행
2. **등록 승인**: 첫 실행 시 등록 승인 다이얼로그 표시
3. **서버 전송**: 등록 요청이 TCP 서버로 전송됨
4. **대시보드 승인**: 웹 대시보드에서 등록 요청 승인
5. **등록 완료**: 에이전트가 자동으로 등록 완료 처리

### Windows 서비스로 실행

```bash
# 서비스 설치
python app/main.py --install

# 서비스 시작
python app/main.py --start

# 서비스 중지
python app/main.py --stop

# 서비스 제거
python app/main.py --remove
```

또는 Windows 서비스 관리자에서 "OpsHub Agent Service" 관리

## 🔧 설정

### 서버 설정

`config.json` (프로젝트 루트):

```json
{
  "server": {
    "host": "0.0.0.0",      # 서버 바인딩 주소
    "http_port": 8000,      # HTTP 서버 포트
    "tcp_port": 5500        # TCP 서버 포트
  }
}
```

환경 변수로도 설정 가능 (`backend/.env`):

```env
HTTP_HOST=0.0.0.0
HTTP_PORT=8000
TCP_HOST=0.0.0.0
TCP_PORT=5500
UDP_HEARTBEAT_PORT=5501
UDP_NOTIFICATION_PORT=5502
```

### 에이전트 설정

에이전트 설정은 `%APPDATA%\OpsHub\config.json`에서 관리됩니다.

## 🗄️ 데이터베이스 스키마

Supabase를 사용하며, 다음 테이블이 필요합니다:

- `registration_requests`: PC 등록 요청
- `pcs`: 등록된 PC 정보
- `agents`: 에이전트 정보
- `tasks`: 원격 실행 작업
- `deployments`: 배포 관리

자세한 스키마는 `backend/database/` 디렉토리의 코드를 참조하세요.

## 🛠️ 개발

### 기술 스택

**백엔드:**
- Python 3.11+
- aiohttp (비동기 HTTP 서버)
- asyncio (비동기 TCP/UDP 서버)
- Supabase (데이터베이스)

**프론트엔드:**
- 순수 HTML/CSS/JavaScript
- Fetch API

**에이전트:**
- Python 3.11+
- PyQt6 (GUI)
- pystray (시스템 트레이)
- pywin32 (Windows 서비스)
- PyInstaller (EXE 빌드)

### 빌드 및 배포

#### 서버 Docker 이미지 빌드

```bash
cd backend
docker build -t controldock-server .
docker run -p 8000:8000 -p 5500:5500 -p 5501:5501/udp -p 5502:5502/udp controldock-server
```

#### 에이전트 EXE 빌드

```bash
cd app
build.bat
```

빌드된 파일: `app/dist/OpsHubAgent.exe`

## 📝 API 문서

### HTTP API (Port 8000)

- `GET /api/agents` - 에이전트 목록 조회
- `GET /api/agents/{agent_id}` - 에이전트 상세 정보
- `POST /api/registration/{request_id}/approve` - 등록 승인
- `GET /api/tasks` - 작업 목록 조회
- `POST /api/tasks` - 작업 생성

### TCP API (Port 5500)

- 등록 요청 전송
- 하트비트 전송
- 작업 결과 전송

## 🐛 문제 해결

### 에이전트가 서버에 연결되지 않음

1. `%APPDATA%\OpsHub\config.json` 확인
2. 서버 IP 주소가 올바른지 확인
3. 방화벽 설정 확인 (TCP 5500 포트)

### 서버가 시작되지 않음

1. 포트가 이미 사용 중인지 확인
2. `.env` 파일의 Supabase 설정 확인
3. Docker 로그 확인: `docker-compose logs`

### EXE 빌드 오류

- PyInstaller 경고 (`js` 모듈 없음)는 무시해도 됩니다
- 실행 중인 에이전트 프로세스 종료 후 빌드

## 📄 라이선스

이 프로젝트의 라이선스 정보를 여기에 추가하세요.

## 👥 기여자

- [shinyeonjun](https://github.com/shinyeonjun)

## 🔗 관련 링크

- [Supabase 문서](https://supabase.com/docs)
- [aiohttp 문서](https://docs.aiohttp.org/)
- [PyInstaller 문서](https://pyinstaller.org/)

---

**참고**: 이 프로젝트는 네트워크 프로그래밍 과제로 개발되었으며, 웹 포스팅을 제외한 모든 통신은 TCP/UDP를 사용합니다.

