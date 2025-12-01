"""
PC 등록 TCP 서버 (포트 5500)
"""
import asyncio
import json
import struct
from typing import Optional, Dict, Any
from datetime import datetime
import uuid
from database.registration_db import (
    create_registration_request,
    get_registration_request,
    get_registration_requests,
    approve_registration,
    complete_registration,
    get_registration_by_agent_id
)
from server.deployment_service import DeploymentService
from server.announcement_service import AnnouncementService

class TCPRegistrationServer:
    """PC 등록 TCP 서버"""
    
    def __init__(self, host: str = None, port: int = None):
        import os
        from dotenv import load_dotenv
        
        load_dotenv()
        
        # 환경 변수 또는 파라미터로 설정
        self.host = host or os.getenv('TCP_HOST', '0.0.0.0')
        self.port = port or int(os.getenv('TCP_PORT', '5500'))
        self.server: Optional[asyncio.Server] = None
    
    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """클라이언트 연결 처리"""
        client_addr = writer.get_extra_info('peername')
        print(f"[TCP] 클라이언트 연결: {client_addr}")
        
        try:
            while True:
                # 메시지 읽기 (프레이밍 프로토콜)
                try:
                    # 길이 읽기 (4바이트, big-endian)
                    length_bytes = await reader.readexactly(4)
                    length = struct.unpack('>I', length_bytes)[0]
                    
                    if length > 1024 * 1024:  # 1MB 제한
                        print(f"[TCP] 메시지가 너무 큽니다: {length}바이트")
                        break
                    
                    # 메시지 데이터 읽기
                    message_data = await reader.readexactly(length)
                    
                    # JSON 디코딩
                    payload = json.loads(message_data.decode('utf-8'))
                    
                    # 메시지 타입에 따라 처리
                    msg_type = payload.get('type', 'registration')
                    
                    if msg_type == 'registration':
                        response = await self._handle_registration_request(payload)
                    elif msg_type == 'poll':
                        response = await self._handle_poll_request(payload)
                    elif msg_type == 'result':
                        response = await self._handle_result_submission(payload)
                    elif msg_type == 'notification_ack':
                        response = await self._handle_notification_ack(payload)
                    else:
                        response = {
                            'success': False,
                            'error': f'Unknown message type: {msg_type}'
                        }
                    
                    # 응답 전송
                    response_json = json.dumps(response, ensure_ascii=False).encode('utf-8')
                    response_length = len(response_json).to_bytes(4, 'big')
                    
                    writer.write(response_length + response_json)
                    await writer.drain()
                    
                except asyncio.IncompleteReadError:
                    break
                except json.JSONDecodeError as e:
                    print(f"[TCP] JSON 디코딩 오류: {e}")
                    error_response = json.dumps({
                        'success': False,
                        'error': 'Invalid JSON format'
                    }, ensure_ascii=False).encode('utf-8')
                    error_length = len(error_response).to_bytes(4, 'big')
                    writer.write(error_length + error_response)
                    await writer.drain()
                    break
                except Exception as e:
                    print(f"[TCP] 메시지 처리 오류: {e}")
                    error_response = json.dumps({
                        'success': False,
                        'error': str(e)
                    }, ensure_ascii=False).encode('utf-8')
                    error_length = len(error_response).to_bytes(4, 'big')
                    writer.write(error_length + error_response)
                    await writer.drain()
                    break
                    
        except Exception as e:
            print(f"[TCP] 클라이언트 처리 오류: {e}")
        finally:
            writer.close()
            await writer.wait_closed()
            print(f"[TCP] 클라이언트 연결 종료: {client_addr}")
    
    async def _handle_registration_request(self, payload: dict) -> dict:
        """등록 요청 처리"""
        try:
            hostname = payload.get('hostname')
            os_info = payload.get('os')
            agent_version = payload.get('agent_version', '1.0.0')
            
            if not hostname or not os_info:
                return {
                    'success': False,
                    'error': 'hostname과 os는 필수입니다'
                }
            
            print(f"[TCP] 등록 요청 수신: hostname={hostname}, os={os_info}, version={agent_version}")
            
            # 중복 체크: 이미 등록된 PC가 있는지 확인
            from database.pc_db import get_pc_by_hostname, update_pc_token
            import secrets
            existing_pc = await get_pc_by_hostname(hostname)
            if existing_pc:
                # 이미 등록된 PC가 있으면 기존 정보 반환
                # 클라이언트가 토큰을 사용할 수 있도록 새 토큰 생성 (기존 토큰은 해시로만 저장되어 있어서 반환 불가)
                agent_id = existing_pc['id']
                new_token = secrets.token_urlsafe(32)
                
                # 새 토큰을 DB에 저장 (해시로)
                await update_pc_token(agent_id, new_token)
                
                print(f"[TCP] 중복 등록 방지: 호스트명 '{hostname}'은 이미 등록되어 있습니다. (agent_id: {agent_id})")
                return {
                    'success': True,
                    'request_id': None,
                    'message': f'이미 등록된 PC입니다. (agent_id: {agent_id})',
                    'status': 'already_registered',
                    'agent_id': agent_id,
                    'agent_token': new_token  # 새 토큰 반환
                }
            
            # 등록 요청 생성 (DB에 저장, 중복 체크 포함)
            request_id = await create_registration_request(hostname, os_info, agent_version)
            
            # 중복 체크 결과 확인
            existing_req = await get_registration_request(request_id)
            if existing_req and existing_req.get('status') == 'completed':
                # 이미 완료된 요청이면 완료 상태 반환
                print(f"[TCP] 이미 완료된 등록 요청: request_id={request_id}")
                return {
                    'success': True,
                    'request_id': request_id,
                    'message': '이미 등록 완료된 PC입니다.',
                    'status': 'completed',
                    'agent_id': existing_req.get('agent_id')
                }
            
            # agent_id 생성 (클라이언트에 반환용, DB에는 저장하지 않음)
            # payload에서 agent_id가 있으면 사용, 없으면 생성
            # 주의: agent_id는 등록 완료 시점에 pc 테이블이 생성된 후에만
            # registration_requests.agent_id에 저장됨 (Foreign Key 제약 때문)
            agent_id = payload.get('agent_id')
            if not agent_id:
                agent_id = str(uuid.uuid4())
            
            print(f"[TCP] 등록 요청 생성: request_id={request_id}, agent_id={agent_id} (임시)")
            
            return {
                'success': True,
                'request_id': request_id,
                'agent_id': agent_id,  # 클라이언트에 반환 (하트비트 매칭용)
                'message': '등록 요청이 접수되었습니다. 승인을 기다려주세요.',
                'status': 'pending'
            }
        except Exception as e:
            print(f"[TCP] 등록 요청 처리 오류: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'error': str(e)
            }
    
    async def get_registration_requests(self) -> list:
        """등록 요청 목록 조회"""
        requests = await get_registration_requests()
        # datetime 객체를 ISO 형식 문자열로 변환
        for req in requests:
            for key in ['created_at', 'approved_at', 'completed_at', 'last_heartbeat']:
                if req.get(key) and isinstance(req[key], datetime):
                    req[key] = req[key].isoformat()
        return requests
    
    async def get_registration_request(self, request_id: str) -> Optional[Dict[str, Any]]:
        """등록 요청 조회"""
        request = await get_registration_request(request_id)
        if request:
            # datetime 객체를 ISO 형식 문자열로 변환
            for key in ['created_at', 'approved_at', 'completed_at', 'rejected_at']:
                if request.get(key) and isinstance(request[key], datetime):
                    request[key] = request[key].isoformat()
        return request
    
    async def approve_registration(self, request_id: str) -> bool:
        """등록 요청 승인"""
        success = await approve_registration(request_id)
        if success:
            print(f"[TCP] 등록 요청 승인: request_id={request_id}")
        return success
    
    async def complete_registration(self, request_id: str, agent_id: str) -> bool:
        """
        등록 완료 처리
        
        Note: agent_token은 pc 테이블에만 저장됨 (registration_requests에는 저장하지 않음)
        """
        success = await complete_registration(request_id, agent_id)
        if success:
            print(f"[TCP] 등록 완료: request_id={request_id}, agent_id={agent_id}")
        return success
    
    # 하트비트 업데이트는 pc_db.py의 update_pc_heartbeat만 사용
    # registration_requests 테이블에는 하트비트 정보를 저장하지 않음
    
    async def get_registration_by_agent_id(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """agent_id로 등록 요청 조회"""
        request = await get_registration_by_agent_id(agent_id)
        if request:
            # datetime 객체를 ISO 형식 문자열로 변환
            for key in ['created_at', 'approved_at', 'completed_at', 'rejected_at']:
                if request.get(key) and isinstance(request[key], datetime):
                    request[key] = request[key].isoformat()
        return request
    
    async def _handle_poll_request(self, payload: dict) -> dict:
        """작업 폴링 요청 처리"""
        try:
            agent_id = payload.get('agent_id')
            if not agent_id:
                return {
                    'success': False,
                    'error': 'agent_id는 필수입니다'
                }
            
            # 에이전트 등록 확인
            agent_request = await get_registration_by_agent_id(agent_id)
            if not agent_request:
                return {
                    'success': False,
                    'error': '에이전트를 찾을 수 없습니다. 재등록이 필요합니다.',
                    're_register': True
                }
            
            # 배포 서비스를 통해 작업 조회
            task = await DeploymentService.poll_task(agent_id)
            
            if task:
                print(f"[TCP] 작업 할당: agent_id={agent_id}, task_id={task['task_id']}")
                return {
                    'success': True,
                    'task': {
                        'task_id': task['task_id'],
                        'deployment_id': task['deployment_id'],
                        'command': task['command'],
                        'timeout': task['timeout'],
                        'admin_required': task.get('admin_required', False)
                    }
                }
            else:
                print(f"[TCP] 작업 없음: agent_id={agent_id}")
                return {
                    'success': True,
                    'no_task': True,
                    'message': '현재 작업이 없습니다'
                }
        except Exception as e:
            print(f"[TCP] 작업 폴링 처리 오류: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _handle_result_submission(self, payload: dict) -> dict:
        """작업 결과 제출 처리"""
        try:
            agent_id = payload.get('agent_id')
            task_id = payload.get('task_id')
            result_data = payload.get('result', {})
            
            if not agent_id or not task_id:
                return {
                    'success': False,
                    'error': 'agent_id와 task_id는 필수입니다'
                }
            
            # 에이전트 등록 확인
            agent_request = await get_registration_by_agent_id(agent_id)
            if not agent_request:
                return {
                    'success': False,
                    'error': '에이전트를 찾을 수 없습니다'
                }
            
            # 결과 데이터 파싱
            status = result_data.get('status', 'failed')  # success, failed, timeout
            exit_code = result_data.get('exit_code', -1)
            log_summary = result_data.get('log_summary', '')
            
            # 배포 서비스를 통해 결과 저장
            success = await DeploymentService.submit_result(
                agent_id=agent_id,
                task_id=task_id,
                status=status,
                exit_code=exit_code,
                log_summary=log_summary
            )
            
            if success:
                print(f"[TCP] 작업 결과 저장 완료: agent_id={agent_id}, task_id={task_id}, status={status}")
                return {
                    'success': True,
                    'message': '결과 제출 완료'
                }
            else:
                return {
                    'success': False,
                    'error': '결과 저장 실패'
                }
        except Exception as e:
            print(f"[TCP] 작업 결과 처리 오류: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _handle_notification_ack(self, payload: dict) -> dict:
        """공지 ACK 처리"""
        try:
            agent_id = payload.get('agent_id')
            notification_id = payload.get('notification_id')
            
            if not agent_id or not notification_id:
                return {
                    'success': False,
                    'error': 'agent_id와 notification_id는 필수입니다'
                }
            
            # 공지 서비스를 통해 수신 기록 저장
            success = await AnnouncementService.record_receipt(
                announcement_id=notification_id,
                agent_id=agent_id
            )
            
            if success:
                print(f"[TCP] 공지 ACK 저장 완료: agent_id={agent_id}, notification_id={notification_id}")
                return {
                    'success': True,
                    'message': 'ACK 수신 완료'
                }
            else:
                return {
                    'success': False,
                    'error': 'ACK 저장 실패'
                }
        except Exception as e:
            print(f"[TCP] 공지 ACK 처리 오류: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'error': str(e)
            }
    
    async def start(self):
        """TCP 서버 시작"""
        self.server = await asyncio.start_server(
            self.handle_client,
            self.host,
            self.port
        )
        
        addr = self.server.sockets[0].getsockname()
        print(f"[TCP] PC 등록 서버 시작: {addr[0]}:{addr[1]}")
        
        async with self.server:
            await self.server.serve_forever()
    
    async def stop(self):
        """TCP 서버 중지"""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            print("[TCP] PC 등록 서버 종료")

