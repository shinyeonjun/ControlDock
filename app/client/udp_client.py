"""
UDP 클라이언트 (하트비트 전송 + 공지 수신)
"""
import socket
import json
import threading
from typing import Optional, Callable, Dict, Any

class UDPClient:
    """UDP 클라이언트 (하트비트 전송 + 공지 수신)"""
    
    def __init__(self, server_host: str, heartbeat_port: int = 5501, notification_port: int = 5502):
        """
        UDP 클라이언트 초기화
        
        Args:
            server_host: 서버 호스트 주소
            heartbeat_port: 하트비트 전송 포트 (기본값: 5501)
            notification_port: 공지 수신 포트 (기본값: 5502)
        """
        self.server_host = server_host
        self.heartbeat_port = heartbeat_port
        self.notification_port = notification_port
        
        self.heartbeat_sock: Optional[socket.socket] = None
        self.notification_sock: Optional[socket.socket] = None
        
        self.running = False
        self.notification_thread: Optional[threading.Thread] = None
        
        # 공지 수신 콜백
        self.notification_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    
    def set_notification_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """공지 수신 콜백 설정"""
        self.notification_callback = callback
    
    def send_heartbeat(self, agent_id: str) -> bool:
        """하트비트 전송"""
        try:
            if not self.heartbeat_sock:
                self.heartbeat_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                # UDP 소켓 옵션 설정
                self.heartbeat_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            
            payload = {
                'agent_id': agent_id
            }
            
            data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
            bytes_sent = self.heartbeat_sock.sendto(data, (self.server_host, self.heartbeat_port))
            
            print(f"[UDP] 하트비트 전송 완료: agent_id={agent_id}, 서버={self.server_host}:{self.heartbeat_port}, 전송 바이트={bytes_sent}")
            print(f"[UDP] 전송 데이터: {data[:100]}...")
            return True
        except Exception as e:
            print(f"[UDP] 하트비트 전송 오류: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _listen_notifications(self):
        """공지 수신 스레드"""
        try:
            print(f"[UDP] 공지 수신 스레드 시작: 포트={self.notification_port}")
            self.notification_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            
            # 소켓 옵션 설정
            self.notification_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            # 브로드캐스트 수신을 위해 SO_BROADCAST 옵션 설정
            self.notification_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            
            # Windows에서 브로드캐스트 수신을 위한 추가 설정
            try:
                # SO_REUSEPORT는 Windows에서 지원되지 않지만 시도
                self.notification_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except (AttributeError, OSError):
                # Windows에서는 SO_REUSEPORT가 없을 수 있음 (정상)
                pass
            
            try:
                # 모든 인터페이스에 바인딩 (0.0.0.0)
                self.notification_sock.bind(('0.0.0.0', self.notification_port))
                bound_addr = self.notification_sock.getsockname()
                print(f"[UDP] ✅ 공지 수신 소켓 바인딩 완료: {bound_addr}")
                print(f"[UDP] 소켓 정보: family={self.notification_sock.family}, type={self.notification_sock.type}")
            except OSError as e:
                print(f"[UDP] ❌ 공지 수신 소켓 바인딩 실패: {e}")
                print(f"[UDP] 포트 {self.notification_port}가 이미 사용 중이거나 권한이 없을 수 있습니다.")
                import traceback
                traceback.print_exc()
                return
            
            self.notification_sock.settimeout(1.0)  # 1초 타임아웃 (루프 종료 확인용)
            
            print(f"[UDP] ✅ 공지 수신 시작: 포트={self.notification_port}, 대기 중...")
            print(f"[UDP] 브로드캐스트 수신 준비 완료 (SO_BROADCAST 활성화)")
            
            packet_count = 0
            while self.running:
                try:
                    data, addr = self.notification_sock.recvfrom(4096)
                    packet_count += 1
                    print(f"[UDP] ✅ UDP 패킷 수신 (#{packet_count}): {len(data)} bytes from {addr[0]}:{addr[1]}")
                    print(f"[UDP] 수신 데이터 (처음 100바이트): {data[:100]}")
                    
                    # JSON 디코딩
                    try:
                        notification = json.loads(data.decode('utf-8'))
                        print(f"[UDP] ✅ 공지 데이터 파싱 완료:")
                        print(f"[UDP]   - type: {notification.get('type')}")
                        print(f"[UDP]   - title: {notification.get('title', 'Unknown')}")
                        print(f"[UDP]   - announcement_id: {notification.get('announcement_id', 'Unknown')}")
                    except json.JSONDecodeError as e:
                        print(f"[UDP] ❌ 공지 JSON 디코딩 오류: {e}")
                        print(f"[UDP] 원본 데이터: {data[:200]}")
                        continue
                    
                    # 공지 타입 확인
                    if notification.get('type') == 'announcement':
                        print(f"[UDP] ✅ 공지 수신 확인: {notification.get('title', 'Unknown')} from {addr}")
                        
                        # 콜백 호출
                        if self.notification_callback:
                            try:
                                print(f"[UDP] 공지 콜백 호출 시작...")
                                self.notification_callback(notification)
                                print(f"[UDP] ✅ 공지 콜백 호출 완료")
                            except Exception as e:
                                print(f"[UDP] ❌ 공지 콜백 오류: {e}")
                                import traceback
                                traceback.print_exc()
                        else:
                            print(f"[UDP] ⚠️ 경고: 공지 콜백이 설정되지 않았습니다")
                    else:
                        print(f"[UDP] ⚠️ 알 수 없는 메시지 타입: {notification.get('type')}")
                        print(f"[UDP] 전체 notification: {notification}")
                    
                except socket.timeout:
                    # 타임아웃은 정상 (루프 종료 확인용)
                    # 주기적으로 상태 로그 출력 (너무 자주 출력하지 않도록)
                    if packet_count == 0 and self.running:
                        # 아직 패킷을 받지 못한 경우에만 로그 출력
                        pass
                    continue
                except Exception as e:
                    if self.running:
                        print(f"[UDP] ❌ 공지 수신 오류: {e}")
                        import traceback
                        traceback.print_exc()
            
        except Exception as e:
            print(f"[UDP] 공지 수신 스레드 오류: {e}")
            import traceback
            traceback.print_exc()
        finally:
            if self.notification_sock:
                self.notification_sock.close()
                self.notification_sock = None
            print("[UDP] 공지 수신 종료")
    
    def start(self):
        """UDP 클라이언트 시작 (공지 수신 시작)"""
        if self.running:
            print("[UDP] UDP 클라이언트가 이미 실행 중입니다")
            return
        
        print(f"[UDP] UDP 클라이언트 시작 중... (공지 포트: {self.notification_port})")
        self.running = True
        self.notification_thread = threading.Thread(target=self._listen_notifications, daemon=True)
        self.notification_thread.start()
        print("[UDP] UDP 클라이언트 시작 완료 (공지 수신 스레드 시작됨)")
    
    def stop(self):
        """UDP 클라이언트 중지"""
        if not self.running:
            return
        
        self.running = False
        
        if self.notification_sock:
            self.notification_sock.close()
            self.notification_sock = None
        
        if self.notification_thread:
            self.notification_thread.join(timeout=2)
        
        if self.heartbeat_sock:
            self.heartbeat_sock.close()
            self.heartbeat_sock = None
        
        print("[UDP] UDP 클라이언트 중지")

