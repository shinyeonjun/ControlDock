"""
TCP 클라이언트 (등록 요청 전송)
"""
import socket
import json
import struct
from typing import Optional, Dict, Any

class TCPClient:
    """TCP 클라이언트"""
    
    def __init__(self, host: str, port: int = 5500):
        """
        TCP 클라이언트 초기화
        
        Args:
            host: 서버 호스트 주소 (config.json에서 설정)
            port: 서버 포트 (기본값: 5500)
        """
        if not host:
            raise ValueError("host는 필수입니다. config.json에서 설정하세요.")
        self.host = host
        self.port = port
    
    def send_registration_request(self, hostname: str, os_info: str, agent_version: str) -> Optional[Dict[str, Any]]:
        """등록 요청 전송"""
        print(f"[TCP] 등록 요청 전송 시작: {self.host}:{self.port}")
        print(f"[TCP] 호스트명: {hostname}, OS: {os_info}")
        
        try:
            # TCP 연결
            print(f"[TCP] 서버에 연결 시도 중... ({self.host}:{self.port})")
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            
            try:
                sock.connect((self.host, self.port))
                print(f"[TCP] 서버 연결 성공!")
            except socket.timeout:
                error_msg = f"서버 연결 타임아웃 ({self.host}:{self.port})"
                print(f"[TCP] 오류: {error_msg}")
                print(f"[TCP] 가능한 원인:")
                print(f"  1. 서버가 실행 중이지 않음")
                print(f"  2. 서버 IP 주소가 잘못됨")
                print(f"  3. 방화벽이 포트 {self.port}를 막고 있음")
                print(f"  4. 네트워크 연결 문제")
                sock.close()
                return None
            except socket.gaierror as e:
                error_msg = f"호스트 이름을 확인할 수 없음: {self.host}"
                print(f"[TCP] 오류: {error_msg}")
                print(f"[TCP] 가능한 원인:")
                print(f"  1. 서버 IP 주소가 잘못됨: {self.host}")
                print(f"  2. DNS 문제 (호스트 이름 사용 시)")
                print(f"  3. 네트워크 연결 문제")
                sock.close()
                return None
            except ConnectionRefusedError:
                error_msg = f"연결 거부됨 ({self.host}:{self.port})"
                print(f"[TCP] 오류: {error_msg}")
                print(f"[TCP] 가능한 원인:")
                print(f"  1. 서버가 실행 중이지 않음")
                print(f"  2. 서버의 방화벽이 포트 {self.port}를 막고 있음")
                print(f"  3. 서버가 다른 포트에서 실행 중")
                sock.close()
                return None
            except OSError as e:
                error_msg = f"네트워크 오류: {e}"
                print(f"[TCP] 오류: {error_msg}")
                print(f"[TCP] 가능한 원인:")
                print(f"  1. 방화벽이 포트 {self.port}를 막고 있음")
                print(f"  2. 네트워크 연결 문제")
                print(f"  3. 서버에 접근할 수 없음")
                sock.close()
                return None
            
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
            print(f"[TCP] 등록 요청 데이터 전송 중... ({len(json_data)} bytes)")
            sock.sendall(message)
            print(f"[TCP] 데이터 전송 완료")
            
            # 응답 수신
            # 길이 읽기
            print(f"[TCP] 서버 응답 대기 중...")
            length_bytes = sock.recv(4)
            if len(length_bytes) < 4:
                raise ValueError("응답 길이를 읽을 수 없습니다")
            
            length = struct.unpack('>I', length_bytes)[0]
            print(f"[TCP] 응답 길이: {length} bytes")
            
            # 데이터 읽기
            response_data = b''
            while len(response_data) < length:
                chunk = sock.recv(length - len(response_data))
                if not chunk:
                    raise ValueError("응답 데이터를 읽을 수 없습니다")
                response_data += chunk
            
            # JSON 디코딩
            try:
                response = json.loads(response_data.decode('utf-8'))
                print(f"[TCP] 응답 수신 완료: {response}")
            except json.JSONDecodeError as e:
                print(f"[TCP] JSON 디코딩 오류: {e}")
                print(f"[TCP] 응답 데이터 (raw): {response_data}")
                raise ValueError(f"서버 응답을 파싱할 수 없습니다: {e}")
            
            sock.close()
            return response
            
        except socket.timeout:
            error_msg = f"서버 응답 타임아웃"
            print(f"[TCP] 오류: {error_msg}")
            print(f"[TCP] 서버가 응답하지 않습니다")
            return None
        except Exception as e:
            error_msg = f"TCP 통신 오류: {e}"
            print(f"[TCP] 오류: {error_msg}")
            import traceback
            print(f"[TCP] 상세 오류:")
            traceback.print_exc()
            return None
    
    def poll_tasks(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """작업 폴링 (TCP)"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            
            try:
                sock.connect((self.host, self.port))
            except Exception as e:
                print(f"[TCP] 작업 폴링 연결 실패: {e}")
                sock.close()
                return None
            
            # 요청 데이터 준비
            payload = {
                'type': 'poll',
                'agent_id': agent_id
            }
            
            # JSON 인코딩
            json_data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
            
            # 프레이밍: [길이(4바이트)][데이터]
            length = len(json_data).to_bytes(4, 'big')
            message = length + json_data
            
            # 전송
            sock.sendall(message)
            
            # 응답 수신
            length_bytes = sock.recv(4)
            if len(length_bytes) < 4:
                sock.close()
                return None
            
            length = struct.unpack('>I', length_bytes)[0]
            
            # 데이터 읽기
            response_data = b''
            while len(response_data) < length:
                chunk = sock.recv(length - len(response_data))
                if not chunk:
                    sock.close()
                    return None
                response_data += chunk
            
            # JSON 디코딩
            response = json.loads(response_data.decode('utf-8'))
            
            sock.close()
            return response
            
        except Exception as e:
            print(f"[TCP] 작업 폴링 오류: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def submit_result(self, agent_id: str, task_id: str, result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """작업 결과 제출 (TCP)"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            
            try:
                sock.connect((self.host, self.port))
            except Exception as e:
                print(f"[TCP] 결과 제출 연결 실패: {e}")
                sock.close()
                return None
            
            # 요청 데이터 준비
            payload = {
                'type': 'result',
                'agent_id': agent_id,
                'task_id': task_id,
                'result': result
            }
            
            # JSON 인코딩
            json_data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
            
            # 프레이밍: [길이(4바이트)][데이터]
            length = len(json_data).to_bytes(4, 'big')
            message = length + json_data
            
            # 전송
            sock.sendall(message)
            
            # 응답 수신
            length_bytes = sock.recv(4)
            if len(length_bytes) < 4:
                sock.close()
                return None
            
            length = struct.unpack('>I', length_bytes)[0]
            
            # 데이터 읽기
            response_data = b''
            while len(response_data) < length:
                chunk = sock.recv(length - len(response_data))
                if not chunk:
                    sock.close()
                    return None
                response_data += chunk
            
            # JSON 디코딩
            response = json.loads(response_data.decode('utf-8'))
            
            sock.close()
            return response
            
        except Exception as e:
            print(f"[TCP] 결과 제출 오류: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def send_notification_ack(self, agent_id: str, notification_id: str) -> Optional[Dict[str, Any]]:
        """공지 수신 ACK 전송"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            
            try:
                sock.connect((self.host, self.port))
            except Exception as e:
                print(f"[TCP] ACK 전송 연결 실패: {e}")
                sock.close()
                return None
            
            # 요청 데이터 준비
            payload = {
                'type': 'notification_ack',
                'agent_id': agent_id,
                'notification_id': notification_id
            }
            
            # JSON 인코딩
            json_data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
            
            # 프레이밍: [길이(4바이트)][데이터]
            length = len(json_data).to_bytes(4, 'big')
            message = length + json_data
            
            # 전송
            sock.sendall(message)
            
            # 응답 수신
            length_bytes = sock.recv(4)
            if len(length_bytes) < 4:
                sock.close()
                return None
            
            length = struct.unpack('>I', length_bytes)[0]
            
            # 데이터 읽기
            response_data = b''
            while len(response_data) < length:
                chunk = sock.recv(length - len(response_data))
                if not chunk:
                    sock.close()
                    return None
                response_data += chunk
            
            # JSON 디코딩
            response = json.loads(response_data.decode('utf-8'))
            
            sock.close()
            return response
            
        except Exception as e:
            print(f"[TCP] ACK 전송 오류: {e}")
            return None

