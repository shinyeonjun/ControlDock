"""
UDP 서버 (하트비트 + 공지)
포트 5501: 하트비트 수신
포트 5502: 공지 전송
"""
import asyncio
import json
from typing import Optional, Dict, Any
from datetime import datetime
from database.registration_db import update_heartbeat, get_registration_by_agent_id

class UDPServer:
    """UDP 서버 (하트비트 수신 + 공지 전송)"""
    
    def __init__(self, heartbeat_port: int = 5501, notification_port: int = 5502):
        import os
        from dotenv import load_dotenv
        
        load_dotenv()
        
        self.heartbeat_port = heartbeat_port or int(os.getenv('UDP_HEARTBEAT_PORT', '5501'))
        self.notification_port = notification_port or int(os.getenv('UDP_NOTIFICATION_PORT', '5502'))
        self.host = '0.0.0.0'
        
        self.heartbeat_transport: Optional[asyncio.DatagramTransport] = None
        self.notification_transport: Optional[asyncio.DatagramTransport] = None
        
        # 공지 전송을 위한 연결된 에이전트 목록 (UDP는 연결이 없으므로 브로드캐스트 사용)
        self.connected_agents = set()  # (host, port) 튜플 세트
    
    def heartbeat_datagram_received(self, data: bytes, addr: tuple):
        """하트비트 UDP 패킷 수신 처리"""
        try:
            # JSON 디코딩
            payload = json.loads(data.decode('utf-8'))
            agent_id = payload.get('agent_id')
            
            if not agent_id:
                print(f"[UDP] 하트비트 수신 실패: agent_id 없음 (from {addr})")
                return
            
            # 하트비트 업데이트
            asyncio.create_task(self._update_heartbeat_async(agent_id))
            
            # 연결된 에이전트로 등록 (공지 전송용)
            self.connected_agents.add(addr)
            
            print(f"[UDP] 하트비트 수신: agent_id={agent_id} (from {addr[0]}:{addr[1]})")
            
        except json.JSONDecodeError as e:
            print(f"[UDP] 하트비트 JSON 디코딩 오류: {e} (from {addr})")
        except Exception as e:
            print(f"[UDP] 하트비트 처리 오류: {e} (from {addr})")
    
    async def _update_heartbeat_async(self, agent_id: str):
        """비동기 하트비트 업데이트"""
        try:
            # 에이전트 존재 확인
            agent_request = await get_registration_by_agent_id(agent_id)
            if not agent_request:
                print(f"[UDP] 하트비트 업데이트 실패: 에이전트를 찾을 수 없음 (agent_id={agent_id})")
                return
            
            # 하트비트 업데이트
            await update_heartbeat(agent_id)
        except Exception as e:
            print(f"[UDP] 하트비트 업데이트 오류: {e}")
    
    def error_received(self, exc: Exception):
        """UDP 에러 처리"""
        print(f"[UDP] 에러 발생: {exc}")
    
    async def start(self):
        """UDP 서버 시작"""
        import socket
        loop = asyncio.get_event_loop()
        
        # 하트비트 수신 서버 (포트 5501)
        sock_heartbeat = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock_heartbeat.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock_heartbeat.bind((self.host, self.heartbeat_port))
        
        self.heartbeat_transport, _ = await loop.create_datagram_endpoint(
            lambda: HeartbeatProtocol(self),
            sock=sock_heartbeat
        )
        print(f"[UDP] 하트비트 서버 시작: {self.host}:{self.heartbeat_port}")
        
        # 공지 전송 서버 (포트 5502) - 브로드캐스트 활성화
        sock_notification = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock_notification.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock_notification.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)  # 브로드캐스트 활성화
        sock_notification.bind((self.host, self.notification_port))
        
        self.notification_transport, _ = await loop.create_datagram_endpoint(
            lambda: NotificationProtocol(self),
            sock=sock_notification
        )
        print(f"[UDP] 공지 서버 시작: {self.host}:{self.notification_port} (브로드캐스트 활성화)")
    
    async def stop(self):
        """UDP 서버 중지"""
        if self.heartbeat_transport:
            self.heartbeat_transport.close()
        if self.notification_transport:
            self.notification_transport.close()
        print("[UDP] UDP 서버 종료")
    
    async def broadcast_notification(self, notification: Dict[str, Any]):
        """공지 브로드캐스트 전송"""
        if not self.notification_transport:
            print("[UDP] 공지 서버가 실행되지 않았습니다")
            return
        
        try:
            notification_json = json.dumps(notification, ensure_ascii=False).encode('utf-8')
            
            # 브로드캐스트 주소 사용 (255.255.255.255)
            # Docker 네트워크에서는 서브넷 브로드캐스트도 고려할 수 있지만,
            # 일단 전체 브로드캐스트 사용
            broadcast_addr = ('255.255.255.255', self.notification_port)
            self.notification_transport.sendto(notification_json, broadcast_addr)
            
            # 연결된 에이전트에도 개별 전송 (백업)
            if self.connected_agents:
                for addr in self.connected_agents:
                    try:
                        self.notification_transport.sendto(notification_json, addr)
                    except Exception as e:
                        print(f"[UDP] 개별 전송 실패 {addr}: {e}")
                
                print(f"[UDP] 공지 브로드캐스트: 전체 네트워크 + {len(self.connected_agents)}개 에이전트에 전송")
            else:
                print(f"[UDP] 공지 브로드캐스트: 전체 네트워크에 전송")
        except Exception as e:
            print(f"[UDP] 공지 브로드캐스트 오류: {e}")


class HeartbeatProtocol(asyncio.DatagramProtocol):
    """하트비트 UDP 프로토콜"""
    
    def __init__(self, server: UDPServer):
        self.server = server
    
    def datagram_received(self, data: bytes, addr: tuple):
        """데이터그램 수신"""
        self.server.heartbeat_datagram_received(data, addr)
    
    def error_received(self, exc: Exception):
        """에러 수신"""
        self.server.error_received(exc)


class NotificationProtocol(asyncio.DatagramProtocol):
    """공지 UDP 프로토콜"""
    
    def __init__(self, server: UDPServer):
        self.server = server
    
    def datagram_received(self, data: bytes, addr: tuple):
        """데이터그램 수신 (공지 서버는 주로 전송용이지만 수신도 가능)"""
        # 공지 서버는 주로 전송용이지만, 필요시 수신도 처리 가능
        pass
    
    def error_received(self, exc: Exception):
        """에러 수신"""
        self.server.error_received(exc)

