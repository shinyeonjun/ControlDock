"""
UDP 서버 (하트비트 + 공지)
포트 5501: 하트비트 수신
포트 5502: 공지 전송
"""
import asyncio
import json
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
from database.registration_db import get_registration_by_agent_id

class UDPServer:
    """UDP 서버 (하트비트 수신 + 공지 전송)"""
    
    def __init__(self, heartbeat_port: int = 5501, notification_port: int = 5502):
        import os
        from dotenv import load_dotenv
        from pathlib import Path
        
        load_dotenv()
        
        self.heartbeat_port = heartbeat_port or int(os.getenv('UDP_HEARTBEAT_PORT', '5501'))
        self.notification_port = notification_port or int(os.getenv('UDP_NOTIFICATION_PORT', '5502'))
        self.host = '0.0.0.0'
        
        self.heartbeat_transport: Optional[asyncio.DatagramTransport] = None
        self.notification_transport: Optional[asyncio.DatagramTransport] = None
        
        # 공지 전송을 위한 연결된 에이전트 목록 (UDP는 연결이 없으므로 브로드캐스트 사용)
        self.connected_agents = set()  # (host, port) 튜플 세트
        
        # Windows 호스트 IP (config.json에서 읽기)
        self.host_ip = None
        self._load_host_ip()
    
    def _load_host_ip(self):
        """config.json에서 Windows 호스트 IP 자동 로드"""
        try:
            # Docker 컨테이너 내부 경로 확인
            config_path = Path('/app/config.json')
            if not config_path.exists():
                # 로컬 개발 환경
                current_file = Path(__file__).resolve()
                backend_dir = current_file.parent.parent
                root_dir = backend_dir.parent
                config_path = root_dir / 'config.json'
            
            print(f"[UDP] 🔍 config.json 경로 확인: {config_path}")
            print(f"[UDP] 파일 존재 여부: {config_path.exists()}")
            
            if config_path.exists():
                import json
                with open(config_path, 'r', encoding='utf-8-sig') as f:
                    config = json.load(f)
                    print(f"[UDP] ✅ config.json 로드 완료")
                    print(f"[UDP] config 내용: {json.dumps(config, indent=2, ensure_ascii=False)}")
                    
                    # 여러 형식 시도
                    host_ip = None
                    
                    # 1. server.host (가장 직접적)
                    if 'server' in config and 'host' in config['server']:
                        host_ip = config['server']['host']
                        print(f"[UDP] ✅ server.host에서 IP 발견: {host_ip}")
                    
                    # 2. server.api_base_url
                    if not host_ip and 'server' in config and 'api_base_url' in config['server']:
                        api_url = config['server']['api_base_url']
                        if '://' in api_url:
                            host_ip = api_url.split('://')[1].split(':')[0]
                        else:
                            host_ip = api_url.split(':')[0]
                        print(f"[UDP] ✅ server.api_base_url에서 IP 발견: {host_ip}")
                    
                    # 3. frontend.api_base_url
                    if not host_ip and 'frontend' in config and 'api_base_url' in config['frontend']:
                        api_url = config['frontend']['api_base_url']
                        if '://' in api_url:
                            host_ip = api_url.split('://')[1].split(':')[0]
                        else:
                            host_ip = api_url.split(':')[0]
                        print(f"[UDP] ✅ frontend.api_base_url에서 IP 발견: {host_ip}")
                    
                    # 4. server_url (루트 레벨)
                    if not host_ip and 'server_url' in config:
                        api_url = config['server_url']
                        if '://' in api_url:
                            host_ip = api_url.split('://')[1].split(':')[0]
                        else:
                            host_ip = api_url.split(':')[0]
                        print(f"[UDP] ✅ server_url에서 IP 발견: {host_ip}")
                    
                    if host_ip:
                        self.host_ip = host_ip
                        print(f"[UDP] ✅✅✅ Windows 호스트 IP 로드 성공: {self.host_ip}")
                    else:
                        print(f"[UDP] ❌❌❌ 경고: config.json에서 서버 IP를 찾을 수 없습니다!")
                        print(f"[UDP] config 구조: {list(config.keys())}")
                        if 'server' in config:
                            print(f"[UDP] server 섹션: {list(config['server'].keys())}")
                        if 'frontend' in config:
                            print(f"[UDP] frontend 섹션: {list(config['frontend'].keys())}")
            else:
                print(f"[UDP] ❌❌❌ 경고: config.json 파일을 찾을 수 없습니다: {config_path}")
                print(f"[UDP] 현재 작업 디렉토리: {Path.cwd()}")
        except Exception as e:
            print(f"[UDP] ❌❌❌ Windows 호스트 IP 로드 실패: {e}")
            import traceback
            traceback.print_exc()
    
    def heartbeat_datagram_received(self, data: bytes, addr: tuple):
        """하트비트 UDP 패킷 수신 처리"""
        try:
            print(f"[UDP] 패킷 수신: {len(data)} bytes from {addr[0]}:{addr[1]}")
            # JSON 디코딩
            payload = json.loads(data.decode('utf-8'))
            agent_id = payload.get('agent_id')
            
            if not agent_id:
                print(f"[UDP] 하트비트 수신 실패: agent_id 없음 (from {addr}), payload={payload}")
                return
            
            print(f"[UDP] 하트비트 수신: agent_id={agent_id} (from {addr[0]}:{addr[1]})")
            
            # 하트비트 업데이트
            asyncio.create_task(self._update_heartbeat_async(agent_id))
            
            # 연결된 에이전트로 등록 (공지 전송용)
            # 하트비트는 5501 포트로 오지만, 공지는 5502 포트로 보내야 함
            # Docker 게이트웨이 IP(172.x.0.1)인 경우 Windows 호스트 IP로 변환
            client_ip = addr[0]
            original_ip = client_ip
            
            # Docker 게이트웨이 IP 감지 및 변환
            if client_ip.startswith('172.'):
                if self.host_ip:
                    # Docker 게이트웨이 IP인 경우 Windows 호스트 IP 사용
                    client_ip = self.host_ip
                    print(f"[UDP] 🔄 Docker 게이트웨이 IP 변환: {original_ip} -> Windows 호스트 IP: {client_ip}")
                else:
                    print(f"[UDP] ⚠️ 경고: Docker 게이트웨이 IP 감지 ({client_ip})했지만 Windows 호스트 IP가 로드되지 않았습니다!")
                    print(f"[UDP] ⚠️ config.json에서 서버 IP를 확인하세요!")
            else:
                # 이미 Windows 호스트 IP인 경우
                print(f"[UDP] 클라이언트 IP가 Windows 호스트 IP입니다: {client_ip}")
            
            notification_addr = (client_ip, self.notification_port)  # 포트를 5502로 변경
            self.connected_agents.add(notification_addr)
            print(f"[UDP] ✅ 에이전트 등록 완료:")
            print(f"[UDP]   - 하트비트 주소: {addr}")
            print(f"[UDP]   - 공지 주소: {notification_addr}")
            print(f"[UDP]   - Windows 호스트 IP: {self.host_ip}")
            
        except json.JSONDecodeError as e:
            print(f"[UDP] 하트비트 JSON 디코딩 오류: {e} (from {addr}), raw_data={data[:100]}")
            import traceback
            traceback.print_exc()
        except Exception as e:
            print(f"[UDP] 하트비트 처리 오류: {e} (from {addr})")
            import traceback
            traceback.print_exc()
    
    async def _update_heartbeat_async(self, agent_id: str):
        """
        비동기 하트비트 업데이트 (UDP)
        
        규칙: pc 테이블만 사용 (registration_requests는 참조하지 않음)
        - pc 테이블에 있으면 하트비트 업데이트
        - pc 테이블에 없으면 등록 미완료로 간주
        """
        try:
            from database.pc_db import update_pc_heartbeat, get_pc, get_pc_by_hostname
            from database.registration_db import get_registration_by_agent_id
            
            # 1단계: agent_id로 pc 테이블에서 직접 조회
            pc = await get_pc(agent_id)
            
            # 2단계: 없으면 registration_requests에서 호스트명 찾아서 pc 테이블 조회
            if not pc:
                registration = await get_registration_by_agent_id(agent_id)
                if registration:
                    hostname = registration.get('hostname')
                    if hostname:
                        pc = await get_pc_by_hostname(hostname)
                        if pc:
                            correct_agent_id = pc['id']
                            print(f"[UDP] 하트비트: 잘못된 agent_id={agent_id}, 올바른 agent_id={correct_agent_id} (hostname={hostname})")
                            agent_id = correct_agent_id
            
            # 3단계: pc 테이블에 있으면 하트비트 업데이트
            if pc:
                await update_pc_heartbeat(agent_id)
                print(f"[UDP] 하트비트 업데이트 완료: agent_id={agent_id}, host_name={pc.get('host_name')}")
            else:
                # 4단계: pc 테이블에 없으면 registration_requests에서 completed 상태인 경우 자동 생성 시도
                registration = await get_registration_by_agent_id(agent_id)
                if registration and registration.get('status') == 'completed':
                    print(f"[UDP] 하트비트: pc 테이블에 없지만 registration_requests에 completed 상태 있음. 자동 생성 시도: agent_id={agent_id}")
                    try:
                        import secrets
                        from database.pc_db import create_pc
                        hostname = registration.get('hostname')
                        agent_token = secrets.token_urlsafe(32)  # 새 토큰 생성 (registration_requests에는 저장하지 않음)
                        created_agent_id = await create_pc(
                            hostname,
                            registration.get('os', 'Unknown'),
                            registration.get('agent_version', '1.0.0'),
                            agent_token,
                            registration_request_id=registration.get('request_id'),
                            status='active'
                        )
                        print(f"[UDP] 하트비트: pc 테이블에 자동 생성 완료: agent_id={created_agent_id}")
                        # 생성 후 하트비트 업데이트
                        await update_pc_heartbeat(created_agent_id)
                    except Exception as e:
                        print(f"[UDP] 하트비트: pc 테이블 자동 생성 실패: {e}")
                        import traceback
                        traceback.print_exc()
                else:
                    # 등록 미완료로 간주
                    print(f"[UDP] 경고: agent_id={agent_id}가 pc 테이블에 없습니다. 등록이 완료되지 않았을 수 있습니다.")
        except Exception as e:
            print(f"[UDP] 하트비트 업데이트 오류: {e}")
            import traceback
            traceback.print_exc()
    
    def error_received(self, exc: Exception):
        """UDP 에러 처리"""
        print(f"[UDP] 에러 발생: {exc}")
    
    async def start(self):
        """UDP 서버 시작"""
        import socket
        loop = asyncio.get_event_loop()
        
        # Windows 호스트 IP 로드 상태 확인
        if self.host_ip:
            print(f"[UDP] ✅ Windows 호스트 IP: {self.host_ip} (공지 전송 시 사용됨)")
        else:
            print(f"[UDP] ⚠️ 경고: Windows 호스트 IP가 로드되지 않았습니다!")
            print(f"[UDP] Docker 게이트웨이 IP로만 전송됩니다. config.json을 확인하세요.")
        
        # 하트비트 수신 서버 (포트 5501)
        sock_heartbeat = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock_heartbeat.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # WSL2에서 UDP 수신을 위해 SO_REUSEPORT 시도 (지원되는 경우)
        try:
            sock_heartbeat.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except AttributeError:
            # Windows에서는 SO_REUSEPORT가 없을 수 있음
            pass
        
        sock_heartbeat.bind((self.host, self.heartbeat_port))
        
        # 바인딩 확인
        bound_addr = sock_heartbeat.getsockname()
        print(f"[UDP] 하트비트 서버 소켓 바인딩 완료: {bound_addr}")
        print(f"[UDP] 하트비트 서버 리스닝 중: {self.host}:{self.heartbeat_port}")
        print(f"[UDP] UDP 패킷 수신 대기 중... (클라이언트에서 전송 시 로그가 나타납니다)")
        
        self.heartbeat_transport, _ = await loop.create_datagram_endpoint(
            lambda: HeartbeatProtocol(self),
            sock=sock_heartbeat
        )
        print(f"[UDP] 하트비트 서버 시작 완료: {self.host}:{self.heartbeat_port}")
        
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
        """공지 브로드캐스트 전송 (UDP만 사용)"""
        if not self.notification_transport:
            print("[UDP] 공지 서버가 실행되지 않았습니다")
            return
        
        try:
            notification_json = json.dumps(notification, ensure_ascii=False).encode('utf-8')
            
            # 연결된 에이전트에 개별 전송 (우선순위)
            success_count = 0
            if self.connected_agents:
                print(f"[UDP] 연결된 에이전트 목록: {list(self.connected_agents)}")
                print(f"[UDP] Windows 호스트 IP: {self.host_ip}")
                for addr in self.connected_agents:
                    try:
                        print(f"[UDP] 공지 전송 시도: {addr[0]}:{addr[1]}")
                        self.notification_transport.sendto(notification_json, addr)
                        success_count += 1
                        print(f"[UDP] ✅ 개별 전송 성공: {addr}")
                    except Exception as e:
                        print(f"[UDP] ❌ 개별 전송 실패 {addr}: {e}")
                        import traceback
                        traceback.print_exc()
            
            # 브로드캐스트 전송 (전체 네트워크)
            try:
                # 전체 브로드캐스트 주소
                broadcast_addr = ('255.255.255.255', self.notification_port)
                self.notification_transport.sendto(notification_json, broadcast_addr)
                print(f"[UDP] 브로드캐스트 전송: {broadcast_addr}")
                
                # Windows 호스트 IP가 있으면 해당 서브넷 브로드캐스트도 시도
                if self.host_ip:
                    try:
                        # 192.168.0.255 형식의 서브넷 브로드캐스트
                        host_parts = self.host_ip.split('.')
                        if len(host_parts) == 4:
                            subnet_broadcast = f"{host_parts[0]}.{host_parts[1]}.{host_parts[2]}.255"
                            subnet_addr = (subnet_broadcast, self.notification_port)
                            self.notification_transport.sendto(notification_json, subnet_addr)
                            print(f"[UDP] Windows 호스트 서브넷 브로드캐스트 전송: {subnet_addr}")
                    except Exception as e:
                        print(f"[UDP] Windows 호스트 서브넷 브로드캐스트 시도 실패: {e}")
                
                # Docker 서브넷 브로드캐스트도 시도 (Docker 네트워크용)
                import socket
                try:
                    # 서버의 네트워크 인터페이스 확인
                    hostname = socket.gethostname()
                    local_ip = socket.gethostbyname(hostname)
                    if local_ip.startswith('172.'):
                        # 172.x.x.255 형식의 서브넷 브로드캐스트
                        subnet_parts = local_ip.split('.')
                        subnet_broadcast = f"{subnet_parts[0]}.{subnet_parts[1]}.{subnet_parts[2]}.255"
                        subnet_addr = (subnet_broadcast, self.notification_port)
                        self.notification_transport.sendto(notification_json, subnet_addr)
                        print(f"[UDP] Docker 서브넷 브로드캐스트 전송: {subnet_addr}")
                except Exception as e:
                    print(f"[UDP] Docker 서브넷 브로드캐스트 시도 실패: {e}")
                    
            except Exception as e:
                print(f"[UDP] 브로드캐스트 전송 오류: {e}")
            
            if self.connected_agents:
                print(f"[UDP] 공지 전송 완료: 브로드캐스트 + {success_count}/{len(self.connected_agents)}개 에이전트에 개별 전송")
            else:
                print(f"[UDP] 공지 전송 완료: 브로드캐스트만 전송 (등록된 에이전트 없음)")
        except Exception as e:
            print(f"[UDP] 공지 브로드캐스트 오류: {e}")
            import traceback
            traceback.print_exc()


class HeartbeatProtocol(asyncio.DatagramProtocol):
    """하트비트 UDP 프로토콜"""
    
    def __init__(self, server: UDPServer):
        self.server = server
        self.packet_count = 0
    
    def connection_made(self, transport):
        """연결 생성 (UDP는 연결이 없지만, transport가 준비되면 호출됨)"""
        sockname = transport.get_extra_info('sockname')
        print(f"[UDP] HeartbeatProtocol 준비 완료: {sockname}")
    
    def datagram_received(self, data: bytes, addr: tuple):
        """데이터그램 수신"""
        self.packet_count += 1
        print(f"[UDP] HeartbeatProtocol.datagram_received 호출됨 (#{self.packet_count}): {len(data)} bytes from {addr}")
        self.server.heartbeat_datagram_received(data, addr)
    
    def error_received(self, exc: Exception):
        """에러 수신"""
        print(f"[UDP] HeartbeatProtocol 에러 수신: {exc}")
        import traceback
        traceback.print_exc()
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

