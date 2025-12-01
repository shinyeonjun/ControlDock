"""
메인 에이전트 로직
"""
import time
import threading
import subprocess
import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from config.config import Config
from client.api_client import APIClient
from client.udp_client import UDPClient
from client.tcp_client import TCPClient
from core.registration import RegistrationManager
from core.announcement_handler import AnnouncementHandler
from utils.system_info import SystemInfo

class Agent:
    """메인 에이전트 클래스"""
    
    def __init__(self, config: Config, tray_icon=None, startup_callback=None):
        self.config = config
        self.client = APIClient(config)
        self.registration = RegistrationManager(config, self.client)
        self.tray_icon = tray_icon
        self.running = False
        self.thread = None
        self.status = 'unknown'  # 'online', 'offline', 'pending', 'unknown'
        
        # UDP 클라이언트 및 공지 핸들러 초기화
        self.udp_client: Optional[UDPClient] = None
        self.announcement_handler: Optional[AnnouncementHandler] = None
        self.tcp_client: Optional[TCPClient] = None
        
        # 트레이 아이콘에 상태 콜백 등록
        if self.tray_icon:
            self.tray_icon.agent_status_callback = self.get_status
        
        # RegistrationManager에 시작 프로그램 등록 콜백 전달
        if startup_callback and hasattr(self.registration, 'set_startup_callback'):
            self.registration.set_startup_callback(startup_callback)
    
    def start(self):
        """에이전트 시작"""
        if self.running:
            print("에이전트가 이미 실행 중입니다.")
            return
        
        print("에이전트 시작...")
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
    
    def stop(self):
        """에이전트 중지"""
        print("에이전트 중지...")
        self.running = False
        
        # UDP 클라이언트 중지
        if self.udp_client:
            self.udp_client.stop()
        
        if self.thread:
            self.thread.join(timeout=5)
    
    def _run(self):
        """메인 실행 루프"""
        # 등록 요청이 있으면 먼저 처리 (등록 상태와 관계없이)
        if self.registration.request_id:
            print(f"등록 요청 대기 중... (Request ID: {self.registration.request_id})")
            self.status = 'pending'
            self._update_tray_status()
            self._handle_registration()
            return
        
        # 등록 확인
        if not self.registration.is_registered():
            # 등록 요청이 없는 경우에만 새로 요청
            print("등록되지 않은 에이전트입니다. 등록 요청을 시작합니다...")
            self.status = 'pending'
            self._update_tray_status()
            self._handle_registration()
            return
        
        # 등록된 에이전트: 하트비트 및 작업 폴링
        agent_id = self.config.agent_id
        
        if not agent_id:
            print("에이전트 ID가 없습니다.")
            self.status = 'offline'
            self._update_tray_status()
            return
        
        # UDP 클라이언트 및 공지 핸들러 초기화
        self._init_udp_and_announcement(agent_id)
        
        # 서버에서 설정 동기화 (DB에서 최신 설정 가져오기)
        self._sync_config_from_server(agent_id)
        
        # agent_token을 서버에서 가져오기
        agent_token = self._get_agent_token_from_server(agent_id)
        if not agent_token:
            print("서버에서 에이전트 토큰을 가져올 수 없습니다.")
            self.status = 'offline'
            self._update_tray_status()
            return
        
        # 메인 루프 실행
        self._run_main_loop(agent_id, agent_token)
    
    def _init_udp_and_announcement(self, agent_id: str):
        """UDP 클라이언트 및 공지 핸들러 초기화"""
        try:
            print(f"[에이전트] UDP 클라이언트 초기화 시작: agent_id={agent_id}")
            print(f"[에이전트] 서버 호스트: {self.config.server_host}, TCP 포트: {self.config.server_tcp_port}")
            
            # TCP 클라이언트 생성 (ACK 전송용)
            self.tcp_client = TCPClient(
                host=self.config.server_host,
                port=self.config.server_tcp_port
            )
            print("[에이전트] TCP 클라이언트 생성 완료")
            
            # UDP 클라이언트 생성
            self.udp_client = UDPClient(
                server_host=self.config.server_host,
                heartbeat_port=5501,
                notification_port=5502
            )
            print(f"[에이전트] UDP 클라이언트 생성 완료: 서버={self.config.server_host}:5501")
            
            # 공지 핸들러 생성
            self.announcement_handler = AnnouncementHandler(
                config=self.config,
                tcp_client=self.tcp_client
            )
            
            # 공지 수신 콜백 설정
            self.udp_client.set_notification_callback(
                self.announcement_handler.handle_notification
            )
            
            # UDP 클라이언트 시작 (공지 수신 시작)
            self.udp_client.start()
            
            print("[에이전트] UDP 클라이언트 및 공지 핸들러 초기화 완료")
        except Exception as e:
            print(f"[에이전트] UDP/공지 초기화 오류: {e}")
            import traceback
            traceback.print_exc()
    
    def _run_main_loop(self, agent_id: str, agent_token: str):
        """등록된 에이전트의 메인 실행 루프 (하트비트 및 작업 폴링)"""
        print(f"에이전트 실행 중... (ID: {agent_id})")
        self.status = 'online'
        self._update_tray_status()
        
        # UDP 클라이언트가 없으면 자동 초기화
        if not self.udp_client:
            print(f"[에이전트] UDP 클라이언트가 없어서 자동 초기화합니다.")
            self._init_udp_and_announcement(agent_id)
        
        while self.running:
            try:
                # 하트비트 전송 (UDP)
                if self.udp_client:
                    heartbeat_udp_success = self.udp_client.send_heartbeat(agent_id)
                    if not heartbeat_udp_success:
                        print(f"[에이전트] UDP 하트비트 전송 실패")
                else:
                    # UDP 클라이언트가 여전히 없으면 재시도
                    print(f"[에이전트] UDP 클라이언트가 없어서 재초기화 시도합니다.")
                    self._init_udp_and_announcement(agent_id)
                
                # 하트비트 전송 및 상태 반영 (HTTP - 기존 방식 유지)
                heartbeat_result = self._send_heartbeat(agent_id, agent_token)
                # 410 Gone 응답이면 재등록 필요
                if isinstance(heartbeat_result, dict) and heartbeat_result.get('_needs_reregistration'):
                    print("서버에서 에이전트를 찾을 수 없습니다. 재등록을 시작합니다...")
                    # agent_id 초기화 (토큰은 메모리 캐시만 있으므로 자동으로 사라짐)
                    self.config.agent_id = None
                    self.config.set('agent_id', None)
                    if hasattr(self.config, '_cached_token'):
                        delattr(self.config, '_cached_token')
                    # registration_request_id도 초기화
                    self.registration.request_id = None
                    self.config.set('registration_request_id', None)
                    # 재등록 루프로 이동
                    self._run()
                    return
                
                heartbeat_success = bool(heartbeat_result)
                
                # 에이전트가 실행 중이면 항상 온라인으로 표시
                # (하트비트 전송 실패는 네트워크 문제일 수 있지만, 에이전트 자체는 실행 중)
                self.status = 'online'
                self._update_tray_status()
                
                # 작업 폴링 (TCP)
                self._poll_tasks_tcp(agent_id)
                # 폴링 간격 대기 (하트비트 전송 주기)
                time.sleep(self.config.poll_interval)
                
            except Exception as e:
                print(f"에이전트 실행 오류: {e}")
                import traceback
                traceback.print_exc()
                # 에러가 발생해도 에이전트는 실행 중이므로 온라인 상태 유지
                # (네트워크 오류 등 일시적 문제일 수 있음)
                self.status = 'online'
                self._update_tray_status()
                time.sleep(self.config.poll_interval)
    
    def _handle_registration(self):
        """등록 처리"""
        # 등록 요청
        request_id = self.registration.request_registration()
        if not request_id:
            print("등록 요청 실패")
            self.status = 'offline'
            self._update_tray_status()
            return
        
        print(f"등록 요청 완료. 승인 대기 중... (Request ID: {request_id})")
        self.status = 'pending'
        self._update_tray_status()
        
        # 승인 대기 (폴링)
        # 폴링 간격을 최소 10초로 설정 (너무 길지 않게)
        interval = max(self.config.request_status_interval, 10)
        print(f"등록 승인 대기 중... (확인 간격: {interval}초)")
        print(f"서버에서 승인되면 자동으로 연결됩니다.")
        
        consecutive_errors = 0
        max_consecutive_errors = 5  # 연속 5번 실패하면 로그 출력
        check_count = 0
        
        while self.running:
            try:
                check_count += 1
                status = self.registration.check_status()
                
                # 상태 확인 성공 시 에러 카운터 리셋
                if status is not None:
                    consecutive_errors = 0
                    if check_count % 6 == 0:  # 6번마다 한 번씩 상태 로그 출력 (약 1분마다)
                        print(f"[등록 상태] 승인 대기 중... (확인 횟수: {check_count}, 상태: {status})")
                else:
                    consecutive_errors += 1
                    if consecutive_errors >= max_consecutive_errors:
                        print(f"[경고] 등록 상태 확인 실패 ({consecutive_errors}회 연속). 네트워크 문제일 수 있습니다. 계속 재시도합니다...")
                        consecutive_errors = 0  # 로그 출력 후 리셋
                    # status가 None이면 pending으로 간주하고 계속 재시도
                    status = 'pending'
                
                if status == 'approved':
                    print("=" * 50)
                    print("✓ 등록이 승인되었습니다! 등록 완료 중...")
                    print("=" * 50)
                    result = self.registration.complete_registration()
                    if result:
                        print("✓ 등록 완료! 서버에 연결합니다...")
                        # 서비스 설치 확인은 메인 스레드에서 실행되도록 콜백 사용
                        # (complete_registration 내부에서 콜백이 호출됨)
                        
                        # 등록 완료 후 request_id 클리어하여 재등록 방지
                        self.registration.request_id = None
                        if hasattr(self.config, 'set'):
                            self.config.set('registration_request_id', None)
                        
                        # 등록 완료 후 메인 루프로 직접 진입
                        agent_id = self.config.agent_id
                        agent_token = self.config.get_agent_token()
                        
                        if agent_id and agent_token:
                            print(f"✓ 에이전트 연결 시작: agent_id={agent_id}")
                            # UDP 클라이언트 및 공지 핸들러 초기화
                            self._init_udp_and_announcement(agent_id)
                            # 메인 루프 실행
                            self._run_main_loop(agent_id, agent_token)
                            return
                        else:
                            print("✗ 에이전트 ID 또는 토큰이 저장되지 않았습니다. 재시작이 필요합니다.")
                            self.status = 'offline'
                            self._update_tray_status()
                            break
                    else:
                        print("✗ 등록 완료 실패")
                        self.status = 'offline'
                        self._update_tray_status()
                        break
                
                elif status == 'rejected':
                    print("=" * 50)
                    print("✗ 등록 요청이 거부되었습니다.")
                    print("=" * 50)
                    self.status = 'offline'
                    self._update_tray_status()
                    break
                
                elif status == 'completed':
                    print("=" * 50)
                    print("✓ 이미 등록이 완료되었습니다. agent_id와 agent_token을 받아옵니다...")
                    print("=" * 50)
                    # completed 상태이지만 agent_id와 agent_token이 없을 수 있으므로
                    # complete_registration()을 호출하여 받아옴
                    result = self.registration.complete_registration()
                    if result:
                        print("✓ 등록 정보를 받아왔습니다! 서버에 연결합니다...")
                        # request_id 클리어
                        self.registration.request_id = None
                        if hasattr(self.config, 'set'):
                            self.config.set('registration_request_id', None)
                        
                        # 등록 완료 후 메인 루프로 직접 진입
                        agent_id = self.config.agent_id
                        agent_token = self.config.get_agent_token()
                        
                        if agent_id and agent_token:
                            print(f"✓ 에이전트 연결 시작: agent_id={agent_id}")
                            # UDP 클라이언트 및 공지 핸들러 초기화
                            self._init_udp_and_announcement(agent_id)
                            # 메인 루프 실행
                            self._run_main_loop(agent_id, agent_token)
                            return
                        else:
                            print("✗ 에이전트 ID 또는 토큰이 저장되지 않았습니다. 재시작이 필요합니다.")
                            self.status = 'offline'
                            self._update_tray_status()
                            break
                    else:
                        print("✗ 등록 정보를 받아오는데 실패했습니다.")
                        self.status = 'offline'
                        self._update_tray_status()
                        break
                
                elif status == 'pending':
                    # 대기 중이면 간격을 두고 다시 확인
                    pass
                
                # 대기 중 (간격을 두고 다시 확인)
                time.sleep(interval)
                
            except Exception as e:
                print(f"등록 상태 확인 오류: {e}")
                # 오류 발생 시 더 긴 간격으로 재시도
                time.sleep(interval * 2)
    
    def _send_heartbeat(self, agent_id: str, agent_token: str):
        """하트비트 전송
        Returns:
            True: 성공
            False: 실패
            dict with '_needs_reregistration': True: 재등록 필요
        """
        result = self.client.send_heartbeat(agent_id, agent_token)
        # 410 Gone 응답이면 재등록 필요
        if isinstance(result, dict) and result.get('_needs_reregistration'):
            print(f"[{datetime.now()}] 하트비트 전송 실패 - 서버에서 에이전트를 찾을 수 없음. 재등록이 필요합니다.")
            return result  # 재등록 필요 플래그 반환
        if result:
            print(f"[{datetime.now()}] 하트비트 전송 성공")
        return result
    
    def _update_tray_status(self):
        """트레이 아이콘 상태 업데이트"""
        if self.tray_icon:
            self.tray_icon.update_status(self.status)
    
    def get_status(self) -> str:
        """현재 상태 반환"""
        return self.status
    
    def _sync_config_from_server(self, agent_id: str):
        """서버에서 설정 동기화 (DB에서 최신 설정 가져오기)"""
        try:
            response = self.client.get_agent_config(agent_id)
            if response and response.get('success'):
                server_config = response.get('config', {})
                
                # 서버에서 가져온 설정으로 업데이트 (로컬 파일에는 저장하지 않음)
                # poll_interval 등은 메모리에서만 사용
                if 'poll_interval' in server_config:
                    self.config._config['poll_interval'] = server_config['poll_interval']
                    print(f"설정 동기화: poll_interval={server_config['poll_interval']}")
                
                if 'request_status_interval' in server_config:
                    self.config._config['request_status_interval'] = server_config['request_status_interval']
                
                if 'version' in server_config:
                    self.config._config['version'] = server_config['version']
                
                print("서버에서 설정 동기화 완료")
        except Exception as e:
            print(f"서버에서 설정 동기화 실패: {e} (기본값 사용)")
    
    def _get_agent_token_from_server(self, agent_id: str) -> Optional[str]:
        """서버에서 agent_token 가져오기 (캐싱)"""
        # 메모리에 캐싱된 토큰이 있으면 사용
        cached_token = self.config.get_agent_token()
        if cached_token:
            return cached_token
        
        # 서버에서 토큰 가져오기
        try:
            response = self.client.get_agent_token(agent_id)
            if response and response.get('success'):
                token = response.get('agent_token')
                if token:
                    # 메모리에 캐싱
                    self.config.set_agent_token(token)
                    return token
        except Exception as e:
            print(f"서버에서 토큰 가져오기 실패: {e}")
        
        return None
    
    def _poll_tasks_tcp(self, agent_id: str):
        """작업 폴링 (TCP)"""
        if not self.tcp_client:
            return
        
        response = self.tcp_client.poll_tasks(agent_id)
        
        if response and response.get('success'):
            if 'task' in response:
                task = response['task']
                print(f"[작업] 작업 수신: task_id={task.get('task_id')}")
                self._execute_task(task)
            elif response.get('no_task'):
                # 작업 없음
                pass
        elif response and response.get('re_register'):
            # 재등록 필요
            print("[작업] 서버에서 재등록이 필요합니다")
            self.config.agent_id = None
            self.config.set('agent_id', None)
            self._run()
    
    def _execute_task(self, task: Dict[str, Any]):
        """작업 실행"""
        task_id = task.get('task_id')
        command = task.get('command')
        timeout = task.get('timeout', 300)
        admin_required = task.get('admin_required', False)
        
        if not command:
            print("작업에 명령이 없습니다.")
            return
        
        print(f"작업 실행 시작: {task_id}")
        print(f"명령: {command}")
        
        # 작업 실행
        request_id = str(uuid.uuid4())
        started_at = datetime.utcnow()
        
        try:
            # PowerShell 또는 명령 실행
            if command.startswith('powershell') or command.endswith('.ps1'):
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=timeout
                )
            else:
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=timeout
                )
            
            completed_at = datetime.utcnow()
            duration = (completed_at - started_at).total_seconds()
            
            # 결과 준비
            status = 'success' if result.returncode == 0 else 'failed'
            log_summary = result.stdout[:1000] + result.stderr[:1000]  # 최대 2000자
            
            result_data = {
                'request_id': request_id,
                'task_id': task_id,
                'agent_id': self.config.agent_id,
                'status': status,
                'exit_code': result.returncode,
                'log_summary': log_summary,
                'started_at': started_at.isoformat() + 'Z',
                'completed_at': completed_at.isoformat() + 'Z'
            }
            
            # 결과 제출 (TCP)
            if self.tcp_client:
                response = self.tcp_client.submit_result(
                    self.config.agent_id,
                    task_id,
                    result_data
                )
                
                if response and response.get('success'):
                    print(f"[작업] 결과 제출 성공: {task_id}")
                else:
                    print(f"[작업] 결과 제출 실패: {task_id}")
            else:
                print(f"[작업] TCP 클라이언트가 없어 결과를 제출할 수 없습니다: {task_id}")
                
        except subprocess.TimeoutExpired:
            print(f"작업 타임아웃: {task_id}")
            completed_at = datetime.utcnow()
            result_data = {
                'request_id': request_id,
                'task_id': task_id,
                'agent_id': self.config.agent_id,
                'status': 'timeout',
                'exit_code': -1,
                'log_summary': f'작업이 타임아웃되었습니다 ({timeout}초)',
                'started_at': started_at.isoformat() + 'Z',
                'completed_at': completed_at.isoformat() + 'Z'
            }
            if self.tcp_client:
                self.tcp_client.submit_result(
                    self.config.agent_id,
                    task_id,
                    result_data
                )
        except Exception as e:
            print(f"작업 실행 오류: {e}")
            completed_at = datetime.utcnow()
            result_data = {
                'request_id': request_id,
                'task_id': task_id,
                'agent_id': self.config.agent_id,
                'status': 'failed',
                'exit_code': -1,
                'log_summary': str(e),
                'started_at': started_at.isoformat() + 'Z',
                'completed_at': completed_at.isoformat() + 'Z'
            }
            if self.tcp_client:
                self.tcp_client.submit_result(
                    self.config.agent_id,
                    task_id,
                    result_data
                )

