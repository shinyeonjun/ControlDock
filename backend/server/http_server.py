"""
HTTP 서버 (웹 UI용)
aiohttp 기반 순수 HTTP 서버
"""
import json
from pathlib import Path
from typing import Dict, Any, Optional
from aiohttp import web
from aiohttp.web import Request, Response
from aiohttp.web_runner import AppRunner, TCPSite
import asyncio

class HTTPServer:
    """HTTP 서버 (웹 UI 전용)"""
    
    def __init__(self, host: str = '0.0.0.0', port: int = 8000):
        self.host = host
        self.port = port
        self.app = web.Application()
        self.runner: Optional[AppRunner] = None
        self.site: Optional[TCPSite] = None
        
        # 정적 파일 경로 설정
        # Docker 컨테이너 내부에서는 /app이 WORKDIR
        # docker-compose.yml에서 ../frontend:/app/frontend로 마운트됨
        import os
        workdir = Path(os.getcwd())  # 현재 작업 디렉토리 (/app)
        
        # frontend 디렉토리 경로 (Docker 컨테이너 내부: /app/frontend)
        self.frontend_dir = workdir / 'frontend'
        self.html_dir = self.frontend_dir / 'html'
        self.css_dir = self.frontend_dir / 'css'
        self.js_dir = self.frontend_dir / 'js'
        
        # config.json 경로 (프로젝트 루트)
        root_dir = workdir.parent  # /app의 부모는 /이지만, 실제로는 프로젝트 루트
        self.config_file = root_dir / 'config.json'
        
        # config.json이 없으면 workdir에서 찾기
        if not self.config_file.exists():
            self.config_file = workdir / 'config.json'
        
        # 디버깅용 경로 출력
        print(f"[DEBUG] workdir: {workdir}")
        print(f"[DEBUG] frontend_dir: {self.frontend_dir}, exists: {self.frontend_dir.exists()}")
        print(f"[DEBUG] css_dir: {self.css_dir}, exists: {self.css_dir.exists()}")
        print(f"[DEBUG] js_dir: {self.js_dir}, exists: {self.js_dir.exists()}")
        
        # TCP 서버 참조 (API에서 사용)
        self.tcp_server = None
        
        # 라우트 설정
        self._setup_routes()
    
    def set_tcp_server(self, tcp_server):
        """TCP 서버 참조 설정"""
        self.tcp_server = tcp_server
    
    def _setup_routes(self):
        """라우트 설정"""
        # CORS 미들웨어 추가
        async def cors_middleware(app, handler):
            async def middleware_handler(request):
                if request.method == 'OPTIONS':
                    return Response(
                        headers={
                            'Access-Control-Allow-Origin': '*',
                            'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                            'Access-Control-Allow-Headers': 'Content-Type',
                        }
                    )
                response = await handler(request)
                response.headers['Access-Control-Allow-Origin'] = '*'
                response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
                response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
                return response
            return middleware_handler
        
        self.app.middlewares.append(cors_middleware)
        
        # 정적 파일 서빙 (디렉토리가 존재할 때만)
        if self.css_dir.exists():
            self.app.router.add_static('/css', path=str(self.css_dir), name='css')
        else:
            print(f"[WARNING] CSS 디렉토리를 찾을 수 없습니다: {self.css_dir}")
        
        if self.js_dir.exists():
            self.app.router.add_static('/js', path=str(self.js_dir), name='js')
        else:
            print(f"[WARNING] JS 디렉토리를 찾을 수 없습니다: {self.js_dir}")
        
        # HTML 페이지
        self.app.router.add_get('/', self._serve_index)
        self.app.router.add_get('/index.html', self._serve_index)
        self.app.router.add_get('/agents.html', self._serve_agents)
        self.app.router.add_get('/deployments.html', self._serve_deployments)
        self.app.router.add_get('/announcements.html', self._serve_announcements)
        
        # 설정 파일
        self.app.router.add_get('/config.json', self._serve_config)
        self.app.router.add_get('/favicon.ico', self._serve_favicon)
        
        # 헬스 체크
        self.app.router.add_get('/health', self._health_check)
        
        # API 라우트
        self.app.router.add_get('/api/registration-requests', self._get_registration_requests)
        self.app.router.add_get('/api/registration-requests/{request_id}', self._get_registration_request)
        self.app.router.add_post('/api/registration-requests/{request_id}/approve', self._approve_registration)
        
        self.app.router.add_get('/api/stats', self._get_stats)
        self.app.router.add_get('/api/agents/recent', self._get_recent_agents)
        self.app.router.add_get('/api/agents', self._get_agents)
        self.app.router.add_get('/api/system/status', self._get_system_status)
        
        self.app.router.add_get('/api/deployments', self._get_deployments)
        self.app.router.add_get('/api/deployments/recent', self._get_recent_deployments)
        self.app.router.add_post('/api/deployments', self._create_deployment)
        self.app.router.add_get('/api/deployments/{task_id}', self._get_deployment)
        self.app.router.add_get('/api/deployments/{task_id}/results', self._get_deployment_results)
        self.app.router.add_post('/api/deployments/{task_id}/pause', self._pause_deployment)
        self.app.router.add_post('/api/deployments/{task_id}/resume', self._resume_deployment)
        self.app.router.add_get('/api/deployments/results/{request_id}/log', self._get_deployment_log)
        
        self.app.router.add_get('/api/agents/{agent_id}/token', self._get_agent_token)
        self.app.router.add_get('/api/agents/{agent_id}/config', self._get_agent_config)
    
    # HTML 페이지 서빙
    async def _serve_index(self, request: Request) -> Response:
        """대시보드 메인 페이지"""
        index_file = self.html_dir / 'index.html'
        if index_file.exists():
            with open(index_file, 'r', encoding='utf-8') as f:
                return Response(text=f.read(), content_type='text/html')
        return Response(text="<h1>OpsHub Server</h1><p>Index file not found</p>", status=404)
    
    async def _serve_agents(self, request: Request) -> Response:
        """에이전트 페이지"""
        agents_file = self.html_dir / 'agents.html'
        if agents_file.exists():
            with open(agents_file, 'r', encoding='utf-8') as f:
                return Response(text=f.read(), content_type='text/html')
        return Response(text="Page not found", status=404)
    
    async def _serve_deployments(self, request: Request) -> Response:
        """배포 페이지"""
        deployments_file = self.html_dir / 'deployments.html'
        if deployments_file.exists():
            with open(deployments_file, 'r', encoding='utf-8') as f:
                return Response(text=f.read(), content_type='text/html')
        return Response(text="Page not found", status=404)
    
    async def _serve_announcements(self, request: Request) -> Response:
        """공지 페이지"""
        announcements_file = self.html_dir / 'announcements.html'
        if announcements_file.exists():
            with open(announcements_file, 'r', encoding='utf-8') as f:
                return Response(text=f.read(), content_type='text/html')
        return Response(text="Page not found", status=404)
    
    async def _serve_config(self, request: Request) -> Response:
        """config.json 파일 서빙"""
        if self.config_file.exists():
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return Response(text=f.read(), content_type='application/json')
        return Response(text='{"error": "config.json not found"}', status=404)
    
    async def _serve_favicon(self, request: Request) -> Response:
        """favicon.ico 요청 처리"""
        return Response(status=204)  # No Content
    
    async def _health_check(self, request: Request) -> Response:
        """헬스 체크"""
        return web.json_response({
            "status": "healthy",
            "tcp_server": "running" if self.tcp_server else "stopped"
        })
    
    # API 핸들러
    async def _get_registration_requests(self, request: Request) -> Response:
        """등록 요청 목록 조회"""
        if not self.tcp_server:
            return web.json_response({"error": "TCP 서버가 실행되지 않았습니다"}, status=503)
        
        requests = await self.tcp_server.get_registration_requests()
        return web.json_response(requests)
    
    async def _get_registration_request(self, request: Request) -> Response:
        """등록 요청 조회"""
        if not self.tcp_server:
            return web.json_response({"error": "TCP 서버가 실행되지 않았습니다"}, status=503)
        
        request_id = request.match_info['request_id']
        req = await self.tcp_server.get_registration_request(request_id)
        if not req:
            return web.json_response({"error": "등록 요청을 찾을 수 없습니다"}, status=404)
        
        return web.json_response(req)
    
    async def _approve_registration(self, request: Request) -> Response:
        """등록 요청 승인"""
        if not self.tcp_server:
            return web.json_response({"error": "TCP 서버가 실행되지 않았습니다"}, status=503)
        
        request_id = request.match_info['request_id']
        success = await self.tcp_server.approve_registration(request_id)
        
        if not success:
            return web.json_response({"error": "등록 요청을 승인할 수 없습니다"}, status=400)
        
        # 승인 후 즉시 등록 완료 처리
        import uuid
        import secrets
        from database.pc_db import create_pc
        
        req = await self.tcp_server.get_registration_request(request_id)
        if not req:
            return web.json_response({"error": "등록 요청을 찾을 수 없습니다"}, status=404)
        
        agent_id = str(uuid.uuid4())
        agent_token = secrets.token_urlsafe(32)
        await create_pc(req['hostname'], req['os'], req.get('agent_version', '1.0.0'), agent_token)
        
        await self.tcp_server.complete_registration(request_id, agent_id, agent_token)
        
        req = await self.tcp_server.get_registration_request(request_id)
        return web.json_response({
            "success": True,
            "message": "등록이 승인되었습니다",
            "request": req
        })
    
    async def _get_stats(self, request: Request) -> Response:
        """대시보드 통계 데이터"""
        if not self.tcp_server:
            return web.json_response({"error": "TCP 서버가 실행되지 않았습니다"}, status=503)
        
        requests = await self.tcp_server.get_registration_requests()
        completed_requests = [r for r in requests if r.get('status') == 'completed']
        pending_requests = [r for r in requests if r.get('status') == 'pending']
        
        return web.json_response({
            "totalAgents": len(completed_requests),
            "onlineAgents": len(completed_requests),
            "offlineAgents": 0,
            "pendingRegistrations": len(pending_requests),
            "totalDeployments": 0,
            "successfulDeployments": 0,
            "failedDeployments": 0
        })
    
    async def _get_recent_agents(self, request: Request) -> Response:
        """최근 에이전트 활동"""
        if not self.tcp_server:
            return web.json_response({"error": "TCP 서버가 실행되지 않았습니다"}, status=503)
        
        requests = await self.tcp_server.get_registration_requests()
        completed_requests = [r for r in requests if r.get('status') == 'completed']
        recent = sorted(completed_requests, key=lambda x: x.get('completed_at', ''), reverse=True)[:5]
        
        return web.json_response(recent)
    
    async def _get_agents(self, request: Request) -> Response:
        """에이전트 목록 조회"""
        if not self.tcp_server:
            return web.json_response({"error": "TCP 서버가 실행되지 않았습니다"}, status=503)
        
        requests = await self.tcp_server.get_registration_requests()
        completed_requests = [r for r in requests if r.get('status') == 'completed']
        
        agents = []
        for req in completed_requests:
            agents.append({
                "host_id": req.get('agent_id'),
                "hostname": req.get('hostname'),
                "status": "online"
            })
        
        return web.json_response(agents)
    
    async def _get_system_status(self, request: Request) -> Response:
        """시스템 상태"""
        return web.json_response({
            "server": "running",
            "tcp_server": "running" if self.tcp_server else "stopped",
            "database": "connected"
        })
    
    async def _get_deployments(self, request: Request) -> Response:
        """배포 목록 조회"""
        return web.json_response([])
    
    async def _get_recent_deployments(self, request: Request) -> Response:
        """최근 배포 결과"""
        return web.json_response([])
    
    async def _create_deployment(self, request: Request) -> Response:
        """배포 생성"""
        data = await request.json()
        import uuid
        task_id = str(uuid.uuid4())
        return web.json_response({
            "success": True,
            "task_id": task_id,
            "message": "배포가 생성되었습니다 (임시)"
        })
    
    async def _get_deployment(self, request: Request) -> Response:
        """배포 상세 조회"""
        return web.json_response({"error": "배포를 찾을 수 없습니다"}, status=404)
    
    async def _get_deployment_results(self, request: Request) -> Response:
        """배포 결과 조회"""
        return web.json_response([])
    
    async def _pause_deployment(self, request: Request) -> Response:
        """배포 일시중지"""
        return web.json_response({"success": True, "message": "배포가 일시중지되었습니다 (임시)"})
    
    async def _resume_deployment(self, request: Request) -> Response:
        """배포 재개"""
        return web.json_response({"success": True, "message": "배포가 재개되었습니다 (임시)"})
    
    async def _get_deployment_log(self, request: Request) -> Response:
        """배포 로그 조회"""
        return web.json_response({"content": "로그가 없습니다 (임시)"})
    
    async def _get_agent_token(self, request: Request) -> Response:
        """에이전트 토큰 조회"""
        if not self.tcp_server:
            return web.json_response({"error": "TCP 서버가 실행되지 않았습니다"}, status=503)
        
        agent_id = request.match_info['agent_id']
        agent_request = await self.tcp_server.get_registration_by_agent_id(agent_id)
        
        if not agent_request:
            return web.json_response({"error": "에이전트를 찾을 수 없습니다"}, status=404)
        
        return web.json_response({
            "success": True,
            "agent_token": agent_request.get('agent_token')
        })
    
    async def _get_agent_config(self, request: Request) -> Response:
        """에이전트 설정 조회"""
        from database.pc_db import get_pc
        
        agent_id = request.match_info['agent_id']
        pc_info = await get_pc(agent_id)
        
        if not pc_info:
            return web.json_response({"error": "에이전트를 찾을 수 없습니다"}, status=404)
        
        return web.json_response({
            "success": True,
            "config": {
                "poll_interval": pc_info.get('poll_interval', 10),
                "request_status_interval": 30,
                "auto_start": True,
                "version": pc_info.get('agent_version', '1.0.0')
            }
        })
    
    async def start(self):
        """HTTP 서버 시작"""
        self.runner = AppRunner(self.app)
        await self.runner.setup()
        self.site = TCPSite(self.runner, self.host, self.port)
        await self.site.start()
        print(f"[HTTP] 웹 서버 시작: {self.host}:{self.port}")
    
    async def stop(self):
        """HTTP 서버 중지"""
        if self.site:
            await self.site.stop()
        if self.runner:
            await self.runner.cleanup()
        print("[HTTP] 웹 서버 종료")

