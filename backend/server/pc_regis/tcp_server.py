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
    update_heartbeat,
    get_registration_by_agent_id
)

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
            
            # 등록 요청 생성 (DB에 저장)
            request_id = await create_registration_request(hostname, os_info, agent_version)
            
            print(f"[TCP] 등록 요청 생성: request_id={request_id}")
            
            return {
                'success': True,
                'request_id': request_id,
                'message': '등록 요청이 접수되었습니다. 승인을 기다려주세요.',
                'status': 'pending'
            }
        except Exception as e:
            print(f"[TCP] 등록 요청 처리 오류: {e}")
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
            for key in ['created_at', 'approved_at', 'completed_at', 'last_heartbeat']:
                if request.get(key) and isinstance(request[key], datetime):
                    request[key] = request[key].isoformat()
        return request
    
    async def approve_registration(self, request_id: str) -> bool:
        """등록 요청 승인"""
        success = await approve_registration(request_id)
        if success:
            print(f"[TCP] 등록 요청 승인: request_id={request_id}")
        return success
    
    async def complete_registration(self, request_id: str, agent_id: str, agent_token: str = None) -> bool:
        """등록 완료 처리"""
        # agent_token이 없으면 생성
        if not agent_token:
            import secrets
            agent_token = secrets.token_urlsafe(32)
        
        success = await complete_registration(request_id, agent_id, agent_token)
        if success:
            print(f"[TCP] 등록 완료: request_id={request_id}, agent_id={agent_id}")
        return success
    
    async def update_heartbeat(self, agent_id: str) -> bool:
        """하트비트 업데이트"""
        return await update_heartbeat(agent_id)
    
    async def get_registration_by_agent_id(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """agent_id로 등록 요청 조회"""
        request = await get_registration_by_agent_id(agent_id)
        if request:
            # datetime 객체를 ISO 형식 문자열로 변환
            for key in ['created_at', 'approved_at', 'completed_at', 'last_heartbeat']:
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
            
            # TODO: DB에서 작업 큐 조회 (deployments 테이블)
            # 현재는 작업 없음 반환
            print(f"[TCP] 작업 폴링: agent_id={agent_id}")
            
            return {
                'success': True,
                'no_task': True,
                'message': '현재 작업이 없습니다'
            }
        except Exception as e:
            print(f"[TCP] 작업 폴링 처리 오류: {e}")
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
            
            # TODO: DB에 결과 저장 (deployment_results 테이블)
            print(f"[TCP] 작업 결과 수신: agent_id={agent_id}, task_id={task_id}, result={result_data}")
            
            return {
                'success': True,
                'message': '결과 제출 완료'
            }
        except Exception as e:
            print(f"[TCP] 작업 결과 처리 오류: {e}")
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
            
            # TODO: DB에 ACK 저장 (notification_receipts 테이블)
            print(f"[TCP] 공지 ACK 수신: agent_id={agent_id}, notification_id={notification_id}")
            
            return {
                'success': True,
                'message': 'ACK 수신 완료'
            }
        except Exception as e:
            print(f"[TCP] 공지 ACK 처리 오류: {e}")
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

