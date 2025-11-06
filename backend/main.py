"""
OpsHub 메인 서버
FastAPI + Uvicorn 기반
"""
import asyncio
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from contextlib import asynccontextmanager
from typing import List, Dict, Any
from pathlib import Path
from server.pc_regis.tcp_server import TCPRegistrationServer

# TCP 서버 인스턴스
tcp_server: TCPRegistrationServer = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 생명주기 관리"""
    global tcp_server
    
    # 시작 시 TCP 서버 시작
    print("서버 시작 중...")
    import os
    import json
    from pathlib import Path
    from dotenv import load_dotenv
    load_dotenv()
    
    # 루트 config.json에서 설정 읽기
    # backend/main.py -> backend -> 프로젝트 루트
    root_config_file = Path(__file__).parent.parent / 'config.json'
    tcp_host = '0.0.0.0'
    tcp_port = 5500
    
    if root_config_file.exists():
        try:
            with open(root_config_file, 'r', encoding='utf-8') as f:
                root_config = json.load(f)
                if 'server' in root_config:
                    server = root_config['server']
                    # TCP 서버는 항상 0.0.0.0으로 바인딩 (모든 네트워크 인터페이스에서 접근 가능)
                    # config.json의 host는 클라이언트가 접속할 서버 IP이지, 서버 바인딩 주소가 아님
                    # tcp_host는 0.0.0.0으로 유지
                    tcp_port = server.get('tcp_port', 5500)
        except Exception as e:
            print(f"루트 설정 파일 로드 실패: {e}, 환경변수 사용")
    
    # 환경변수가 있으면 우선 사용
    tcp_host = os.getenv('TCP_HOST', tcp_host)
    tcp_port = int(os.getenv('TCP_PORT', str(tcp_port)))
    
    tcp_server = TCPRegistrationServer(host=tcp_host, port=tcp_port)
    
    # 백그라운드 태스크로 TCP 서버 실행
    tcp_task = asyncio.create_task(tcp_server.start())
    
    yield
    
    # 종료 시 TCP 서버 중지
    print("서버 종료 중...")
    if tcp_server:
        await tcp_server.stop()
        tcp_task.cancel()
        try:
            await tcp_task
        except asyncio.CancelledError:
            pass

# FastAPI 앱 생성
app = FastAPI(
    title="OpsHub Server",
    description="OpsHub PC 원격 관리 서버",
    version="1.0.0",
    lifespan=lifespan
)

# CORS 설정 (프론트엔드 접근 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 개발용, 프로덕션에서는 특정 도메인만 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 프론트엔드 정적 파일 경로 설정
# backend/main.py -> backend -> 프로젝트 루트 -> frontend
root_dir = Path(__file__).parent.parent
frontend_dir = root_dir / 'frontend'
html_dir = frontend_dir / 'html'
css_dir = frontend_dir / 'css'
js_dir = frontend_dir / 'js'
config_file = root_dir / 'config.json'

# 정적 파일 마운트
if css_dir.exists():
    app.mount("/css", StaticFiles(directory=str(css_dir)), name="css")
if js_dir.exists():
    app.mount("/js", StaticFiles(directory=str(js_dir)), name="js")

@app.get("/config.json")
async def get_config():
    """루트 config.json 파일 서빙"""
    if config_file.exists():
        return FileResponse(str(config_file))
    raise HTTPException(status_code=404, detail="config.json not found")

@app.get("/", response_class=HTMLResponse)
async def root():
    """루트 엔드포인트 - 대시보드 메인 페이지"""
    index_file = html_dir / 'index.html'
    if index_file.exists():
        with open(index_file, 'r', encoding='utf-8') as f:
            return f.read()
    return HTMLResponse(content="<h1>OpsHub Server</h1><p>Index file not found</p>", status_code=404)

@app.get("/index.html", response_class=HTMLResponse)
async def index():
    """대시보드 메인 페이지"""
    index_file = html_dir / 'index.html'
    if index_file.exists():
        with open(index_file, 'r', encoding='utf-8') as f:
            return f.read()
    raise HTTPException(status_code=404, detail="Page not found")

@app.get("/agents.html", response_class=HTMLResponse)
async def agents():
    """에이전트 페이지"""
    agents_file = html_dir / 'agents.html'
    if agents_file.exists():
        with open(agents_file, 'r', encoding='utf-8') as f:
            return f.read()
    raise HTTPException(status_code=404, detail="Page not found")

@app.get("/deployments.html", response_class=HTMLResponse)
async def deployments():
    """배포 페이지"""
    deployments_file = html_dir / 'deployments.html'
    if deployments_file.exists():
        with open(deployments_file, 'r', encoding='utf-8') as f:
            return f.read()
    raise HTTPException(status_code=404, detail="Page not found")

@app.get("/announcements.html", response_class=HTMLResponse)
async def announcements():
    """공지 페이지"""
    announcements_file = html_dir / 'announcements.html'
    if announcements_file.exists():
        with open(announcements_file, 'r', encoding='utf-8') as f:
            return f.read()
    raise HTTPException(status_code=404, detail="Page not found")

@app.get("/health")
async def health():
    """헬스 체크"""
    return {
        "status": "healthy",
        "tcp_server": "running" if tcp_server else "stopped"
    }

# 등록 요청 API
@app.get("/api/registration-requests")
async def get_registration_requests() -> List[Dict[str, Any]]:
    """등록 요청 목록 조회"""
    if not tcp_server:
        raise HTTPException(status_code=503, detail="TCP 서버가 실행되지 않았습니다")
    
    requests = tcp_server.get_registration_requests()
    return requests

@app.get("/api/registration-requests/{request_id}")
async def get_registration_request(request_id: str) -> Dict[str, Any]:
    """등록 요청 조회"""
    if not tcp_server:
        raise HTTPException(status_code=503, detail="TCP 서버가 실행되지 않았습니다")
    
    request = tcp_server.get_registration_request(request_id)
    if not request:
        raise HTTPException(status_code=404, detail="등록 요청을 찾을 수 없습니다")
    
    return request

@app.post("/api/registration-requests/{request_id}/approve")
async def approve_registration(request_id: str) -> Dict[str, Any]:
    """등록 요청 승인"""
    if not tcp_server:
        raise HTTPException(status_code=503, detail="TCP 서버가 실행되지 않았습니다")
    
    success = tcp_server.approve_registration(request_id)
    if not success:
        raise HTTPException(status_code=400, detail="등록 요청을 승인할 수 없습니다")
    
    # 승인 후 즉시 등록 완료 처리 (테스트용)
    # 실제로는 클라이언트가 상세 정보를 보내면 완료 처리
    import uuid
    import secrets
    agent_id = str(uuid.uuid4())
    agent_token = secrets.token_urlsafe(32)
    tcp_server.complete_registration(request_id, agent_id, agent_token)
    
    request = tcp_server.get_registration_request(request_id)
    return {
        "success": True,
        "message": "등록이 승인되었습니다",
        "request": request
    }

# 대시보드 API
@app.get("/api/stats")
async def get_stats() -> Dict[str, Any]:
    """대시보드 통계 데이터"""
    if not tcp_server:
        raise HTTPException(status_code=503, detail="TCP 서버가 실행되지 않았습니다")
    
    # 등록된 에이전트 수 (completed 상태)
    requests = tcp_server.get_registration_requests()
    completed_requests = [r for r in requests if r.get('status') == 'completed']
    pending_requests = [r for r in requests if r.get('status') == 'pending']
    
    return {
        "totalAgents": len(completed_requests),
        "onlineAgents": len(completed_requests),  # 일단 등록된 수 = 온라인 수
        "offlineAgents": 0,
        "pendingRegistrations": len(pending_requests),
        "totalDeployments": 0,
        "successfulDeployments": 0,
        "failedDeployments": 0
    }

@app.get("/api/agents/recent")
async def get_recent_agents() -> List[Dict[str, Any]]:
    """최근 에이전트 활동"""
    if not tcp_server:
        raise HTTPException(status_code=503, detail="TCP 서버가 실행되지 않았습니다")
    
    requests = tcp_server.get_registration_requests()
    completed_requests = [r for r in requests if r.get('status') == 'completed']
    
    # 최근 5개만 반환
    recent = sorted(completed_requests, key=lambda x: x.get('completed_at', ''), reverse=True)[:5]
    
    return recent

@app.get("/api/deployments/recent")
async def get_recent_deployments() -> List[Dict[str, Any]]:
    """최근 배포 결과 (임시 - 아직 구현 안됨)"""
    return []

@app.get("/api/system/status")
async def get_system_status() -> Dict[str, Any]:
    """시스템 상태"""
    return {
        "server": "running",
        "tcp_server": "running" if tcp_server else "stopped",
        "database": "connected"  # 임시
    }

def main():
    """메인 함수"""
    import os
    import json
    from pathlib import Path
    from dotenv import load_dotenv
    
    load_dotenv()
    
    # 루트 config.json에서 설정 읽기
    # backend/main.py -> backend -> 프로젝트 루트
    root_config_file = Path(__file__).parent.parent / 'config.json'
    host = '0.0.0.0'
    port = 8000
    tcp_host = '0.0.0.0'
    tcp_port = 5500
    
    if root_config_file.exists():
        try:
            with open(root_config_file, 'r', encoding='utf-8') as f:
                root_config = json.load(f)
                if 'server' in root_config:
                    server = root_config['server']
                    host = server.get('host', '0.0.0.0')
                    port = server.get('http_port', 8000)
                    # TCP 서버는 항상 0.0.0.0으로 바인딩
                    # config.json의 host는 클라이언트 접속용 IP이므로 서버 바인딩에는 사용하지 않음
                    tcp_host = '0.0.0.0'
                    tcp_port = server.get('tcp_port', 5500)
        except Exception as e:
            print(f"루트 설정 파일 로드 실패: {e}, 환경변수 사용")
    
    # 환경변수가 있으면 우선 사용
    host = os.getenv('HOST', host)
    port = int(os.getenv('PORT', str(port)))
    tcp_host = os.getenv('TCP_HOST', tcp_host)
    tcp_port = int(os.getenv('TCP_PORT', str(tcp_port)))
    
    print(f"서버 시작: HTTP {host}:{port}, TCP {tcp_host}:{tcp_port}")
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=True,
        log_level="info"
    )

if __name__ == "__main__":
    main()

