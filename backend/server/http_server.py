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
        import os
        workdir = Path(os.getcwd())  # 현재 작업 디렉토리
        
        # 프로젝트 루트 찾기
        # 현재 파일 위치 기준: backend/server/http_server.py -> backend -> 프로젝트 루트
        current_file = Path(__file__).resolve()
        # backend/server/http_server.py에서 backend 폴더 찾기
        backend_dir = current_file.parent.parent  # backend/server -> backend
        root_dir = backend_dir.parent  # backend -> 프로젝트 루트
        
        # 작업 디렉토리가 backend인 경우도 확인
        if workdir.name == 'backend':
            root_dir = workdir.parent
        
        # Docker 컨테이너 내부 경로 확인 (/app/frontend)
        docker_frontend = Path('/app/frontend')
        if docker_frontend.exists():
            # Docker 컨테이너 내부에서 실행 중
            self.frontend_dir = docker_frontend
            self.html_dir = docker_frontend / 'html'
            self.css_dir = docker_frontend / 'css'
            self.js_dir = docker_frontend / 'js'
            self.config_file = Path('/app/config.json')
            print(f"[HTTP] Docker 컨테이너 모드 감지: /app/frontend 사용")
        else:
            # 로컬 개발 환경
            self.frontend_dir = root_dir / 'frontend'
            self.html_dir = self.frontend_dir / 'html'
            self.css_dir = self.frontend_dir / 'css'
            self.js_dir = self.frontend_dir / 'js'
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
        # UDP 서버 참조 (공지 브로드캐스트용)
        self.udp_server = None
        
        # 라우트 설정
        self._setup_routes()
    
    def set_tcp_server(self, tcp_server):
        """TCP 서버 참조 설정"""
        self.tcp_server = tcp_server
    
    def set_udp_server(self, udp_server):
        """UDP 서버 참조 설정"""
        self.udp_server = udp_server
    
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
                # API 요청 로깅 (중복 방지)
                if request.path.startswith('/api/') and not request.path.startswith('/api/health'):
                    print(f"[HTTP] API 요청: {request.method} {request.path_qs}")
                
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
        self.app.router.add_post('/api/agents/{agent_id}/heartbeat', self._agent_heartbeat)
        
        # 공지 API
        self.app.router.add_get('/api/announcements', self._get_announcements)
        self.app.router.add_post('/api/announcements', self._create_announcement)
        self.app.router.add_get('/api/announcements/{announcement_id}', self._get_announcement)
        self.app.router.add_post('/api/announcements/{announcement_id}/expire', self._expire_announcement)
        self.app.router.add_get('/api/announcements/{announcement_id}/receipts', self._get_announcement_receipts)
    
    # HTML 페이지 서빙
    async def _serve_index(self, request: Request) -> Response:
        """대시보드 메인 페이지"""
        index_file = self.html_dir / 'index.html'
        print(f"[HTTP] index.html 찾기: {index_file}, exists: {index_file.exists()}")
        print(f"[HTTP] html_dir: {self.html_dir}, exists: {self.html_dir.exists()}")
        print(f"[HTTP] frontend_dir: {self.frontend_dir}, exists: {self.frontend_dir.exists()}")
        
        if index_file.exists():
            with open(index_file, 'r', encoding='utf-8') as f:
                return Response(text=f.read(), content_type='text/html')
        
        # 경로를 못 찾았을 때 대체 경로 시도
        # Docker 컨테이너 내부에서는 /app/frontend/html/index.html일 수 있음
        alt_paths = [
            Path('/app/frontend/html/index.html'),
            Path('/app/frontend/index.html'),
            self.frontend_dir / 'index.html',
            self.frontend_dir / 'html' / 'index.html',
        ]
        
        for alt_path in alt_paths:
            print(f"[HTTP] 대체 경로 시도: {alt_path}, exists: {alt_path.exists()}")
            if alt_path.exists():
                with open(alt_path, 'r', encoding='utf-8') as f:
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
            # UTF-8 BOM 처리 (utf-8-sig 사용)
            with open(self.config_file, 'r', encoding='utf-8-sig') as f:
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
        
        # 등록 완료된 경우 agent_token 재생성하여 반환 (등록 완료 시에만)
        if req.get('status') == 'completed' and req.get('agent_id'):
            import secrets
            from database.pc_db import get_pc, update_pc_token
            
            agent_id = req['agent_id']
            pc = await get_pc(agent_id)
            
            if pc:
                # 등록 완료 시 토큰을 재생성하여 반환 (보안상 한 번만 전달)
                # 이후에는 토큰을 반환하지 않음
                new_token = secrets.token_urlsafe(32)
                await update_pc_token(agent_id, new_token)
                print(f"[등록 조회] 등록 완료된 요청에 대해 새 토큰 생성: agent_id={agent_id}")
                
                # 응답에 토큰 포함
                req['agent_token'] = new_token
        
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
        import secrets
        from database.pc_db import create_pc, get_pc_by_hostname, get_pc
        
        req = await self.tcp_server.get_registration_request(request_id)
        if not req:
            return web.json_response({"error": "등록 요청을 찾을 수 없습니다"}, status=404)
        
        hostname = req['hostname']
        agent_token = None  # 등록 완료 시 생성한 토큰 저장용
        
        # 이미 completed 상태이고 agent_id가 있으면 그대로 사용
        if req.get('status') == 'completed' and req.get('agent_id'):
            agent_id = req['agent_id']
            print(f"[등록 승인] 이미 완료된 요청: agent_id={agent_id}")
            
            # pc 테이블에 있는지 확인
            pc_check = await get_pc(agent_id)
            if not pc_check:
                print(f"[등록 승인] pc 테이블에 없어서 생성: agent_id={agent_id}")
                agent_token = secrets.token_urlsafe(32)
                try:
                    await create_pc(hostname, req['os'], req.get('agent_version', '1.0.0'), agent_token, registration_request_id=request_id, status='active', agent_id=agent_id)
                except Exception as e:
                    print(f"[등록 승인] PC 테이블 생성 오류: {e}")
                    import traceback
                    traceback.print_exc()
        else:
            # 중복 체크: 같은 호스트명의 PC가 이미 등록되어 있는지 확인
            existing_pc = await get_pc_by_hostname(hostname)
            if existing_pc:
                # 이미 등록된 PC가 있으면 기존 agent_id 사용
                agent_id = existing_pc['id']
                # 기존 PC의 경우에도 새 토큰 생성 (재등록 시 토큰 갱신)
                agent_token = secrets.token_urlsafe(32)
                await update_pc_token(agent_id, agent_token)
                print(f"[등록 승인] 중복 방지: 호스트명 '{hostname}'은 이미 등록되어 있습니다. 기존 agent_id 사용: {agent_id}, 새 토큰 생성")
            else:
                # 새로 등록: 클라이언트가 등록 요청 시 받은 agent_id를 사용
                # 클라이언트가 등록 요청 응답에서 받은 agent_id를 사용하도록 함
                # 만약 agent_id가 없으면 새로 생성 (하지만 일반적으로는 클라이언트가 이미 받았음)
                agent_id = req.get('agent_id')
                if not agent_id:
                    # agent_id가 없으면 새로 생성 (하지만 이 경우는 거의 없어야 함)
                    import uuid
                    agent_id = str(uuid.uuid4())
                    print(f"[등록 승인] 경고: 등록 요청에 agent_id가 없어 새로 생성: {agent_id}")
                
                agent_token = secrets.token_urlsafe(32)
                print(f"[등록 승인] 새 PC 등록: hostname={hostname}, agent_id={agent_id}, request_id={request_id}")
                try:
                    # pc 테이블에 생성 (지정된 agent_id 사용)
                    created_agent_id = await create_pc(hostname, req['os'], req.get('agent_version', '1.0.0'), agent_token, registration_request_id=request_id, status='active', agent_id=agent_id)
                    print(f"[등록 승인] PC 테이블에 생성 완료: agent_id={created_agent_id}")
                    # create_pc가 중복 체크로 다른 agent_id를 반환할 수 있으므로 확인
                    if created_agent_id != agent_id:
                        print(f"[등록 승인] 경고: 생성된 agent_id가 다릅니다. 요청: {agent_id}, 생성: {created_agent_id}")
                        agent_id = created_agent_id
                except Exception as e:
                    print(f"[등록 승인] PC 테이블 생성 오류: {e}")
                    import traceback
                    traceback.print_exc()
                    return web.json_response({"error": f"PC 등록 실패: {str(e)}"}, status=500)
            
            # 등록 완료 처리 (registration_requests 테이블 업데이트 - 이력 추적용)
            # agent_token은 pc 테이블에만 저장되므로 registration_requests에는 전달하지 않음
            await self.tcp_server.complete_registration(request_id, agent_id)
        
        # pc 테이블에 반드시 있어야 함 (데이터 정합성 확인)
        pc_check = await get_pc(agent_id)
        if not pc_check:
            print(f"[등록 승인] 오류: pc 테이블에 agent_id가 없습니다. 재생성 시도: agent_id={agent_id}")
            try:
                agent_token = secrets.token_urlsafe(32)
                await create_pc(hostname, req['os'], req.get('agent_version', '1.0.0'), agent_token, registration_request_id=request_id, agent_id=agent_id)
                print(f"[등록 승인] PC 테이블 재생성 완료: agent_id={agent_id}")
            except Exception as e:
                print(f"[등록 승인] PC 테이블 재생성 실패: {e}")
                import traceback
                traceback.print_exc()
                return web.json_response({"error": "PC 등록 실패"}, status=500)
        
        # 등록 완료 정보 반환 (agent_id와 agent_token 포함)
        # agent_token은 등록 완료 시에만 한 번 전달 (보안상 이후에는 반환하지 않음)
        req = await self.tcp_server.get_registration_request(request_id)
        
        # 등록 완료 응답에 agent_id와 agent_token 포함
        # agent_token은 새로 등록한 경우에만 전달 (기존 등록은 토큰 재생성하지 않음)
        return web.json_response({
            "success": True,
            "message": "등록이 승인되었습니다",
            "agent_id": agent_id,
            "agent_token": agent_token,  # 등록 완료 시 생성한 토큰 전달 (새로 등록한 경우에만)
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
        """에이전트 목록 조회 (pc 테이블만 사용)"""
        try:
            from database.pc_db import get_all_pcs
            
            # pc 테이블만 조회 (정규화된 메인 테이블)
            pcs = await get_all_pcs()
            
            agents = []
            for pc in pcs:
                # 마지막 체크인 시간으로 온라인/오프라인 판단
                # 에이전트가 실행 중이면 하트비트를 정기적으로 전송하므로,
                # 마지막 하트비트가 10분 이내면 온라인으로 간주
                from datetime import datetime, timedelta, timezone
                status = 'offline'
                last_check_in = pc.get('last_check_in')
                
                if last_check_in:
                    try:
                        # ISO 8601 형식 파싱 (Z 또는 +00:00 처리)
                        if isinstance(last_check_in, str):
                            if last_check_in.endswith('Z'):
                                last_check_in = last_check_in[:-1] + '+00:00'
                            last_check = datetime.fromisoformat(last_check_in)
                            # 타임존이 없으면 UTC로 가정
                            if last_check.tzinfo is None:
                                last_check = last_check.replace(tzinfo=timezone.utc)
                            
                            # 현재 시간과 비교 (UTC 기준)
                            now_utc = datetime.now(timezone.utc)
                            time_diff = now_utc - last_check
                            
                            # 10분 이내면 온라인으로 판단 (에이전트가 실행 중이면 정기적으로 하트비트 전송)
                            if time_diff < timedelta(minutes=10):
                                status = 'online'
                            else:
                                # 10분 이상 지났으면 오프라인 (PC가 종료되었거나 에이전트가 실행되지 않음)
                                status = 'offline'
                    except Exception as e:
                        print(f"[HTTP] 날짜 파싱 오류 (agent_id={pc.get('id')}): {e}")
                        pass
                else:
                    # 하트비트가 한 번도 수신되지 않았으면 오프라인
                    status = 'offline'
                
                agents.append({
                    "id": pc.get('id'),
                    "host_id": pc.get('id'),
                    "host_name": pc.get('host_name'),
                    "hostname": pc.get('host_name'),
                    "os": pc.get('os'),
                    "agent_version": pc.get('agent_version'),
                    "status": status,
                    "last_check_in": last_check_in,  # ISO 8601 형식 유지
                    "created_at": pc.get('created_at')
                })
            
            return web.json_response(agents)
        except Exception as e:
            print(f"[ERROR] 에이전트 목록 조회 실패: {e}")
            import traceback
            traceback.print_exc()
            return web.json_response({"error": str(e)}, status=500)
    
    async def _get_system_status(self, request: Request) -> Response:
        """시스템 상태"""
        return web.json_response({
            "server": "running",
            "tcp_server": "running" if self.tcp_server else "stopped",
            "database": "connected"
        })
    
    async def _get_deployments(self, request: Request) -> Response:
        """배포 목록 조회"""
        from server.deployment_service import DeploymentService
        deployments = await DeploymentService.get_deployments()
        return web.json_response(deployments)
    
    async def _get_recent_deployments(self, request: Request) -> Response:
        """최근 배포 결과"""
        from server.deployment_service import DeploymentService
        deployments = await DeploymentService.get_deployments()
        recent = deployments[:5]  # 최근 5개
        return web.json_response(recent)
    
    async def _create_deployment(self, request: Request) -> Response:
        """배포 생성"""
        from server.deployment_service import DeploymentService
        from database.pc_db import get_pc
        
        try:
            data = await request.json()
            print(f"[HTTP] 배포 생성 요청 데이터: {data}")  # 디버깅용
        except Exception as e:
            print(f"[HTTP] 배포 생성 요청 파싱 오류: {e}")
            return web.json_response({
                "success": False,
                "error": f"요청 데이터 파싱 실패: {str(e)}"
            }, status=400)
        
        name = data.get('name', '')
        command = data.get('command', '')
        target_agents = data.get('target_agents', [])
        timeout = data.get('timeout', 300)
        target_type = data.get('target_type', 'selected')
        # 클라이언트에서 'admin' 또는 'admin_required' 둘 다 받을 수 있도록 수정
        admin_required = data.get('admin_required', False) or data.get('admin', False)
        
        if not name or not command:
            return web.json_response({
                "success": False,
                "error": "name과 command는 필수입니다"
            }, status=400)
        
        # 전체 에이전트 선택인 경우 모든 에이전트 가져오기
        if target_type == 'all':
            from database.pc_db import get_all_pcs
            all_pcs = await get_all_pcs()
            target_agents = [pc['id'] for pc in all_pcs]
            print(f"[HTTP] 전체 에이전트 선택: {len(target_agents)}개 에이전트")
        
        if not target_agents or not isinstance(target_agents, list) or len(target_agents) == 0:
            # target_type이 'tag'인 경우 target_agents가 없을 수 있음
            if target_type == 'tag':
                return web.json_response({
                    "success": False,
                    "error": "태그 기반 배포는 아직 지원하지 않습니다. 에이전트를 직접 선택해주세요."
                }, status=400)
            return web.json_response({
                "success": False,
                "error": "최소 하나 이상의 에이전트를 선택해주세요."
            }, status=400)
        
        # 에이전트 존재 여부 확인
        invalid_agents = []
        for agent_id in target_agents:
            pc = await get_pc(agent_id)
            if not pc:
                invalid_agents.append(agent_id)
        
        if invalid_agents:
            return web.json_response({
                "success": False,
                "error": f"존재하지 않는 에이전트 ID: {', '.join(invalid_agents)}"
            }, status=400)
        
        try:
            print(f"[HTTP] 배포 생성 파라미터: name={name}, command={command}, target_agents={target_agents}, timeout={timeout}, admin_required={admin_required}")
            result = await DeploymentService.create_deployment(
                name=name,
                command=command,
                target_agents=target_agents,
                timeout=timeout,
                admin_required=admin_required
            )
            
            if result.get('success'):
                print(f"[HTTP] 배포 생성 성공: deployment_id={result.get('deployment_id')}")
                return web.json_response(result)
            else:
                error_msg = result.get('error', '알 수 없는 오류')
                print(f"[HTTP] 배포 생성 실패: {error_msg}")
                return web.json_response({
                    "success": False,
                    "error": error_msg
                }, status=400)
        except Exception as e:
            print(f"[HTTP] 배포 생성 오류: {e}")
            import traceback
            traceback.print_exc()
            return web.json_response({
                "success": False,
                "error": f"배포 생성 실패: {str(e)}"
            }, status=500)
    
    async def _get_deployment(self, request: Request) -> Response:
        """배포 상세 조회"""
        from server.deployment_service import DeploymentService
        deployment_id = request.match_info['task_id']  # URL 파라미터 이름이 task_id
        
        # deployment_id 검증
        if not deployment_id or deployment_id == 'undefined' or deployment_id == '-':
            return web.json_response({
                "error": "유효하지 않은 배포 ID입니다"
            }, status=400)
        
        try:
            deployment = await DeploymentService.get_deployment(deployment_id)
            
            if not deployment:
                return web.json_response({"error": "배포를 찾을 수 없습니다"}, status=404)
            
            return web.json_response(deployment)
        except Exception as e:
            print(f"[HTTP] 배포 상세 조회 오류: {e}")
            import traceback
            traceback.print_exc()
            return web.json_response({
                "error": f"배포 조회 실패: {str(e)}"
            }, status=500)
    
    async def _get_deployment_results(self, request: Request) -> Response:
        """배포 결과 조회"""
        from server.deployment_service import DeploymentService
        deployment_id = request.match_info['task_id']
        results = await DeploymentService.get_deployment_results(deployment_id)
        return web.json_response(results)
    
    async def _pause_deployment(self, request: Request) -> Response:
        """배포 일시중지"""
        from server.deployment_service import DeploymentService
        deployment_id = request.match_info['task_id']
        success = await DeploymentService.pause_deployment(deployment_id)
        
        if success:
            return web.json_response({"success": True, "message": "배포가 일시중지되었습니다"})
        else:
            return web.json_response({"success": False, "error": "배포를 일시중지할 수 없습니다"}, status=400)
    
    async def _resume_deployment(self, request: Request) -> Response:
        """배포 재개"""
        from server.deployment_service import DeploymentService
        deployment_id = request.match_info['task_id']
        success = await DeploymentService.resume_deployment(deployment_id)
        
        if success:
            return web.json_response({"success": True, "message": "배포가 재개되었습니다"})
        else:
            return web.json_response({"success": False, "error": "배포를 재개할 수 없습니다"}, status=400)
    
    async def _get_deployment_log(self, request: Request) -> Response:
        """배포 로그 조회"""
        from server.deployment_service import DeploymentService
        request_id = request.match_info['request_id']
        
        # request_id는 task_id와 동일하다고 가정
        task_result = await DeploymentService.get_task_result(request_id)
        
        if not task_result:
            return web.json_response({"error": "작업을 찾을 수 없습니다"}, status=404)
        
        return web.json_response({
            "content": task_result.get('log_summary', ''),
            "exit_code": task_result.get('exit_code', -1),
            "status": task_result.get('status', 'unknown')
        })
    
    async def _get_agent_token(self, request: Request) -> Response:
        """
        에이전트 토큰 조회
        
        Note: agent_token은 pc 테이블에만 저장됨 (해시 형태)
        registration_requests에는 저장하지 않음
        보안상 실제 토큰은 등록 시에만 제공됨
        """
        from database.pc_db import get_pc
        
        agent_id = request.match_info['agent_id']
        
        # pc 테이블에서 조회 (agent_token_hash만 저장되어 있음)
        pc = await get_pc(agent_id)
        
        if not pc:
            return web.json_response({"error": "에이전트를 찾을 수 없습니다"}, status=404)
        
        # 보안상 실제 토큰은 반환하지 않음 (해시만 저장되어 있음)
        return web.json_response({
            "agent_id": agent_id,
            "message": "토큰은 등록 시에만 제공됩니다. 토큰 해시는 저장되어 있습니다."
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
                "poll_interval": pc_info.get('poll_interval', 30),
                "request_status_interval": 30,
                "auto_start": True,
                "version": pc_info.get('agent_version', '1.0.0')
            }
        })
    
    async def _agent_heartbeat(self, request: Request) -> Response:
        """
        에이전트 하트비트 수신 (HTTP)
        
        규칙: pc 테이블만 사용 (registration_requests는 참조하지 않음)
        - pc 테이블에 있으면 하트비트 업데이트
        - pc 테이블에 없으면 등록 미완료로 간주
        """
        from database.pc_db import update_pc_heartbeat, get_pc, get_pc_by_hostname
        
        agent_id = request.match_info['agent_id']
        
        # 요청 본문에서 호스트명 가져오기 (선택사항, agent_id 매칭 실패 시 사용)
        try:
            body = await request.json() if request.can_read_body else {}
            hostname = body.get('hostname')
        except:
            hostname = None
        
        # 1단계: agent_id로 pc 테이블에서 직접 조회 (가장 빠름)
        pc = await get_pc(agent_id)
        
        # 2단계: agent_id로 찾지 못했고 호스트명이 있으면 호스트명으로 조회
        if not pc and hostname:
            pc = await get_pc_by_hostname(hostname)
            if pc:
                correct_agent_id = pc['id']
                print(f"[HTTP] 하트비트: 잘못된 agent_id={agent_id}, 올바른 agent_id={correct_agent_id} (hostname={hostname})")
                agent_id = correct_agent_id
        
        # 3단계: 여전히 없으면 registration_requests에서 호스트명 찾아서 pc 테이블 조회 (마지막 수단)
        if not pc and self.tcp_server:
            registration = await self.tcp_server.get_registration_by_agent_id(agent_id)
            if registration:
                reg_hostname = registration.get('hostname')
                if reg_hostname:
                    pc = await get_pc_by_hostname(reg_hostname)
                    if pc:
                        correct_agent_id = pc['id']
                        print(f"[HTTP] 하트비트: 잘못된 agent_id={agent_id}, 올바른 agent_id={correct_agent_id} (hostname={reg_hostname})")
                        agent_id = correct_agent_id
        
        # 4단계: pc 테이블에 없으면 registration_requests에서 completed 상태인 경우 자동 생성 시도
        if not pc and self.tcp_server:
            registration = await self.tcp_server.get_registration_by_agent_id(agent_id)
            if registration and registration.get('status') == 'completed':
                print(f"[HTTP] 하트비트: pc 테이블에 없지만 registration_requests에 completed 상태 있음. 자동 생성 시도: agent_id={agent_id}")
                try:
                    import secrets
                    from database.pc_db import create_pc
                    reg_hostname = registration.get('hostname')
                    agent_token = secrets.token_urlsafe(32)  # 새 토큰 생성 (registration_requests에는 저장하지 않음)
                    created_agent_id = await create_pc(
                        reg_hostname,
                        registration.get('os', 'Unknown'),
                        registration.get('agent_version', '1.0.0'),
                        agent_token,
                        registration_request_id=registration.get('request_id'),
                        status='active'
                    )
                    print(f"[HTTP] 하트비트: pc 테이블에 자동 생성 완료: agent_id={created_agent_id}")
                    # 생성된 agent_id로 하트비트 업데이트
                    agent_id = created_agent_id
                    pc = await get_pc(agent_id)
                    await update_pc_heartbeat(agent_id)
                    return web.json_response({
                        "success": True,
                        "message": "하트비트 업데이트 완료 (자동 생성됨)"
                    })
                except Exception as e:
                    print(f"[HTTP] 하트비트: pc 테이블 자동 생성 실패: {e}")
                    import traceback
                    traceback.print_exc()
        
        # 5단계: 여전히 없으면 등록 미완료로 간주
        if not pc:
            print(f"[HTTP] 하트비트 실패: agent_id={agent_id}가 pc 테이블에 없습니다. 등록이 완료되지 않았을 수 있습니다.")
            return web.json_response({"error": "에이전트를 찾을 수 없습니다. 등록이 완료되지 않았을 수 있습니다."}, status=404)
        
        # 하트비트 업데이트
        try:
            await update_pc_heartbeat(agent_id)
            print(f"[HTTP] 하트비트 업데이트 완료: agent_id={agent_id}, host_name={pc.get('host_name')}")
            return web.json_response({
                "success": True,
                "message": "하트비트 업데이트 완료"
            })
        except Exception as e:
            print(f"[HTTP] 하트비트 업데이트 오류: {e}")
            import traceback
            traceback.print_exc()
            return web.json_response({
                "success": False,
                "error": str(e)
            }, status=500)
    
    # 공지 API 핸들러
    async def _get_announcements(self, request: Request) -> Response:
        """공지 목록 조회"""
        from server.announcement_service import AnnouncementService
        announcements = await AnnouncementService.get_announcements()
        return web.json_response(announcements)
    
    async def _create_announcement(self, request: Request) -> Response:
        """공지 생성 및 브로드캐스트"""
        from server.announcement_service import AnnouncementService
        
        if not self.udp_server:
            return web.json_response({"error": "UDP 서버가 실행되지 않았습니다"}, status=503)
        
        data = await request.json()
        
        title = data.get('title', '')
        content = data.get('content', '')
        priority = data.get('priority', 'normal')
        target_agents = data.get('target_agents', None)  # None이면 전체
        
        if not title or not content:
            return web.json_response({
                "success": False,
                "error": "title과 content는 필수입니다"
            }, status=400)
        
        # 공지 생성
        result = await AnnouncementService.create_announcement(
            title=title,
            content=content,
            priority=priority,
            target_agents=target_agents
        )
        
        if not result.get('success'):
            return web.json_response(result, status=400)
        
        announcement_id = result['announcement_id']
        
        # 공지 정보 조회
        announcement = await AnnouncementService.get_announcement(announcement_id)
        
        # UDP 브로드캐스트
        notification = {
            'type': 'announcement',
            'announcement_id': announcement_id,
            'title': title,
            'content': content,
            'priority': priority,
            'created_at': announcement.get('created_at') if announcement else None
        }
        
        await self.udp_server.broadcast_notification(notification)
        
        return web.json_response({
            "success": True,
            "announcement_id": announcement_id,
            "message": "공지가 생성되고 브로드캐스트되었습니다"
        })
    
    async def _get_announcement(self, request: Request) -> Response:
        """공지 조회"""
        from server.announcement_service import AnnouncementService
        announcement_id = request.match_info['announcement_id']
        announcement = await AnnouncementService.get_announcement(announcement_id)
        
        if not announcement:
            return web.json_response({"error": "공지를 찾을 수 없습니다"}, status=404)
        
        return web.json_response(announcement)
    
    async def _expire_announcement(self, request: Request) -> Response:
        """공지 만료 처리"""
        from server.announcement_service import AnnouncementService
        announcement_id = request.match_info['announcement_id']
        success = await AnnouncementService.expire_announcement(announcement_id)
        
        if success:
            return web.json_response({"success": True, "message": "공지가 만료되었습니다"})
        else:
            return web.json_response({"success": False, "error": "공지를 만료할 수 없습니다"}, status=400)
    
    async def _get_announcement_receipts(self, request: Request) -> Response:
        """공지 수신 기록 조회"""
        from server.announcement_service import AnnouncementService
        announcement_id = request.match_info['announcement_id']
        receipts = await AnnouncementService.get_receipts(announcement_id)
        return web.json_response(receipts)
    
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

