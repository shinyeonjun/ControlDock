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
from core.registration import RegistrationManager
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
        if self.thread:
            self.thread.join(timeout=5)
    
    def _run(self):
        """메인 실행 루프"""
        # 등록 확인
        if not self.registration.is_registered():
            # 이미 등록 요청이 있는 경우 (TCP로 이미 전송한 경우)
            if self.registration.request_id:
                print(f"등록 요청 대기 중... (Request ID: {self.registration.request_id})")
                self.status = 'pending'
                self._update_tray_status()
                self._handle_registration()
                return
            else:
                # 등록 요청이 없는 경우에만 새로 요청
                print("등록되지 않은 에이전트입니다. 등록 요청을 시작합니다...")
                self.status = 'pending'
                self._update_tray_status()
                self._handle_registration()
                return
        
        # 등록된 에이전트: 하트비트 및 작업 폴링
        agent_id = self.config.agent_id
        agent_token = self.config.get_agent_token()
        
        if not agent_id or not agent_token:
            print("에이전트 ID 또는 토큰이 없습니다.")
            self.status = 'offline'
            self._update_tray_status()
            return
        
        # 메인 루프 실행
        self._run_main_loop(agent_id, agent_token)
    
    def _run_main_loop(self, agent_id: str, agent_token: str):
        """등록된 에이전트의 메인 실행 루프 (하트비트 및 작업 폴링)"""
        print(f"에이전트 실행 중... (ID: {agent_id})")
        self.status = 'online'
        self._update_tray_status()
        
        while self.running:
            try:
                # 하트비트 전송 및 상태 반영
                self.status = 'online' if self._send_heartbeat(agent_id, agent_token) else 'offline'
                self._update_tray_status()
                # 작업 폴링
                self._poll_tasks(agent_id, agent_token)
                # 폴링 간격 대기
                time.sleep(self.config.poll_interval)
                
            except Exception as e:
                print(f"에이전트 실행 오류: {e}")
                self.status = 'offline'
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
        # 폴링 간격을 최소 30초로 설정 (너무 자주 요청하지 않도록)
        interval = max(self.config.request_status_interval, 30)
        print(f"등록 승인 대기 중... (확인 간격: {interval}초)")
        
        while self.running:
            try:
                status = self.registration.check_status()
                
                if status == 'approved':
                    print("등록이 승인되었습니다. 등록 완료 중...")
                    result = self.registration.complete_registration()
                    if result:
                        print("등록 완료!")
                        # 서비스 설치 확인은 메인 스레드에서 실행되도록 콜백 사용
                        # (complete_registration 내부에서 콜백이 호출됨)
                        
                        # 등록 완료 후 request_id 클리어하여 재등록 방지
                        self.registration.request_id = None
                        if hasattr(self.config, 'set'):
                            self.config.set('registration_request_id', None)
                        
                        # 등록 완료 후 메인 루프로 직접 진입 (재귀 호출 대신)
                        # agent_id와 agent_token이 제대로 저장되었는지 확인
                        agent_id = self.config.agent_id
                        agent_token = self.config.get_agent_token()
                        
                        if agent_id and agent_token:
                            # 메인 루프 실행
                            self._run_main_loop(agent_id, agent_token)
                            return
                        else:
                            print("에이전트 ID 또는 토큰이 저장되지 않았습니다. 재시작이 필요합니다.")
                            self.status = 'offline'
                            self._update_tray_status()
                            break
                    else:
                        print("등록 완료 실패")
                        self.status = 'offline'
                        self._update_tray_status()
                        break
                
                elif status == 'rejected':
                    print("등록 요청이 거부되었습니다.")
                    self.status = 'offline'
                    self._update_tray_status()
                    break
                
                elif status == 'completed':
                    print("이미 등록이 완료되었습니다. agent_id와 agent_token을 받아옵니다...")
                    # completed 상태이지만 agent_id와 agent_token이 없을 수 있으므로
                    # complete_registration()을 호출하여 받아옴
                    result = self.registration.complete_registration()
                    if result:
                        print("등록 정보를 받아왔습니다!")
                        # request_id 클리어
                        self.registration.request_id = None
                        if hasattr(self.config, 'set'):
                            self.config.set('registration_request_id', None)
                        
                        # 등록 완료 후 메인 루프로 직접 진입
                        agent_id = self.config.agent_id
                        agent_token = self.config.get_agent_token()
                        
                        if agent_id and agent_token:
                            # 메인 루프 실행
                            self._run_main_loop(agent_id, agent_token)
                            return
                        else:
                            print("에이전트 ID 또는 토큰이 저장되지 않았습니다. 재시작이 필요합니다.")
                            self.status = 'offline'
                            self._update_tray_status()
                            break
                    else:
                        print("등록 정보를 받아오는데 실패했습니다.")
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
    
    def _send_heartbeat(self, agent_id: str, agent_token: str) -> bool:
        """하트비트 전송"""
        success = self.client.send_heartbeat(agent_id, agent_token)
        if success:
            print(f"[{datetime.now()}] 하트비트 전송 성공")
        else:
            print(f"[{datetime.now()}] 하트비트 전송 실패")
        return success
    
    def _update_tray_status(self):
        """트레이 아이콘 상태 업데이트"""
        if self.tray_icon:
            self.tray_icon.update_status(self.status)
    
    def get_status(self) -> str:
        """현재 상태 반환"""
        return self.status
    
    def _poll_tasks(self, agent_id: str, agent_token: str):
        """작업 폴링"""
        response = self.client.poll_tasks(agent_id, agent_token, want_n=1)
        
        if response and 'task' in response:
            task = response['task']
            print(f"작업 수신: {task.get('task_id')}")
            self._execute_task(task)
        elif response and response.get('no_task'):
            # 작업 없음
            pass
    
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
            
            # 결과 제출
            success = self.client.submit_result(
                self.config.agent_id,
                self.config.get_agent_token(),
                result_data
            )
            
            if success:
                print(f"작업 결과 제출 성공: {task_id}")
            else:
                print(f"작업 결과 제출 실패: {task_id}")
                
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
            self.client.submit_result(
                self.config.agent_id,
                self.config.get_agent_token(),
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
            self.client.submit_result(
                self.config.agent_id,
                self.config.get_agent_token(),
                result_data
            )

