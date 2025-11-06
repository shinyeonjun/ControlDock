"""
PC 등록 TCP 서버 (포트 5500)
"""
import asyncio
import json
import struct
from typing import Optional, Dict, Any
from datetime import datetime
import uuid

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
        # 등록 요청 저장소 (메모리 기반, 향후 DB로 변경)
        self.registration_requests: Dict[str, Dict[str, Any]] = {}
    
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
                    
                    # 등록 요청 처리
                    response = await self._handle_registration_request(payload)
                    
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
            
            # 등록 요청 생성
            request_id = str(uuid.uuid4())
            
            # 등록 요청 저장 (메모리)
            registration_request = {
                'request_id': request_id,
                'hostname': hostname,
                'os': os_info,
                'agent_version': agent_version,
                'status': 'pending',
                'created_at': datetime.utcnow().isoformat(),
                'approved_at': None,
                'completed_at': None,
                'agent_id': None
            }
            
            self.registration_requests[request_id] = registration_request
            
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
    
    def get_registration_requests(self) -> list:
        """등록 요청 목록 조회"""
        return list(self.registration_requests.values())
    
    def get_registration_request(self, request_id: str) -> Optional[Dict[str, Any]]:
        """등록 요청 조회"""
        return self.registration_requests.get(request_id)
    
    def approve_registration(self, request_id: str) -> bool:
        """등록 요청 승인"""
        if request_id not in self.registration_requests:
            return False
        
        request = self.registration_requests[request_id]
        if request['status'] != 'pending':
            return False
        
        request['status'] = 'approved'
        request['approved_at'] = datetime.utcnow().isoformat()
        
        print(f"[TCP] 등록 요청 승인: request_id={request_id}")
        return True
    
    def complete_registration(self, request_id: str, agent_id: str, agent_token: str = None) -> bool:
        """등록 완료 처리"""
        if request_id not in self.registration_requests:
            return False
        
        request = self.registration_requests[request_id]
        if request['status'] != 'approved':
            return False
        
        # agent_token이 없으면 생성
        if not agent_token:
            import secrets
            agent_token = secrets.token_urlsafe(32)
        
        request['status'] = 'completed'
        request['completed_at'] = datetime.utcnow().isoformat()
        request['agent_id'] = agent_id
        request['agent_token'] = agent_token
        
        print(f"[TCP] 등록 완료: request_id={request_id}, agent_id={agent_id}")
        return True
    
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

