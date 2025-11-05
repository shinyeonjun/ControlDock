"""
TCP 클라이언트 (등록 요청 전송)
"""
import socket
import json
import struct
from typing import Optional, Dict, Any

class TCPClient:
    """TCP 클라이언트"""
    
    def __init__(self, host: str = '172.24.194.92', port: int = 5500):
        self.host = host
        self.port = port
    
    def send_registration_request(self, hostname: str, os_info: str, agent_version: str) -> Optional[Dict[str, Any]]:
        """등록 요청 전송"""
        try:
            # TCP 연결
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            sock.connect((self.host, self.port))
            
            # 요청 데이터 준비
            payload = {
                'hostname': hostname,
                'os': os_info,
                'agent_version': agent_version
            }
            
            # JSON 인코딩
            json_data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
            
            # 프레이밍: [길이(4바이트)][데이터]
            length = len(json_data).to_bytes(4, 'big')
            message = length + json_data
            
            # 전송
            sock.sendall(message)
            
            # 응답 수신
            # 길이 읽기
            length_bytes = sock.recv(4)
            if len(length_bytes) < 4:
                raise ValueError("응답 길이를 읽을 수 없습니다")
            
            length = struct.unpack('>I', length_bytes)[0]
            
            # 데이터 읽기
            response_data = b''
            while len(response_data) < length:
                chunk = sock.recv(length - len(response_data))
                if not chunk:
                    raise ValueError("응답 데이터를 읽을 수 없습니다")
                response_data += chunk
            
            # JSON 디코딩
            response = json.loads(response_data.decode('utf-8'))
            
            sock.close()
            return response
            
        except Exception as e:
            print(f"TCP 클라이언트 오류: {e}")
            return None

