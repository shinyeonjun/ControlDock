# OpsHub Agent

Windows PC용 원격 관리 에이전트 프로그램입니다.

## 기능

- PC 등록 승인 요청
- 승인 대기 및 상태 확인
- 등록 완료 후 하트비트 전송
- 작업 폴링 및 실행
- Windows 서비스로 백그라운드 실행

## 설치

### 1. 의존성 설치

```bash
pip install -r requirements.txt
```

### 2. 서비스 설치

```bash
python main.py --install
```

### 3. 서비스 시작

```bash
python main.py --start
```

또는 Windows 서비스 관리자에서 "OpsHub Agent Service"를 시작하세요.

## 사용 방법

### 콘솔 모드 (디버깅용)

```bash
python main.py
```

### 서비스 모드

```bash
# 서비스 설치
python main.py --install

# 서비스 시작
python main.py --start

# 서비스 중지
python main.py --stop

# 서비스 제거
python main.py --remove
```

## 프로젝트 구조

```
app/
├── config/          # 설정 관리
│   ├── __init__.py
│   └── config.py
├── client/          # 서버 통신
│   ├── __init__.py
│   └── api_client.py
├── core/            # 핵심 로직
│   ├── __init__.py
│   ├── agent.py
│   └── registration.py
├── service/         # Windows 서비스
│   ├── __init__.py
│   └── windows_service.py
├── utils/           # 유틸리티
│   ├── __init__.py
│   └── system_info.py
├── main.py          # 메인 엔트리포인트
├── requirements.txt
└── README.md
```

## 등록 프로세스

1. 에이전트 시작 시 등록 여부 확인
2. 미등록 시 서버에 등록 승인 요청 전송
3. 주기적으로 승인 상태 확인 (폴링)
4. 대시보드에서 승인 확인
5. 승인되면 상세 PC 정보 전송 및 등록 완료
6. agent_id와 agent_token 저장
7. 정상적인 하트비트 및 작업 폴링 시작

## 설정

설정 파일 위치: `%APPDATA%\OpsHub\config.json`

```json
{
  "server_url": "http://localhost:8000",
  "agent_id": null,
  "agent_token": null,
  "poll_interval": 10,
  "request_status_interval": 30,
  "auto_start": true,
  "version": "1.0.0"
}
```

## EXE 빌드

PyInstaller를 사용하여 EXE 파일로 빌드할 수 있습니다:

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name OpsHubAgent main.py
```


