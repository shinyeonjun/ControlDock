"""
OpsHub 메인 서버
순수 HTTP/TCP/UDP 서버 기반 (FastAPI 제거)
"""
import asyncio
import os
import json
from pathlib import Path
from dotenv import load_dotenv
from server.http_server import HTTPServer
from server.pc_regis.tcp_server import TCPRegistrationServer
from server.udp_server import UDPServer
from database.db import init_db, close_db

# 서버 인스턴스
http_server: HTTPServer = None
tcp_server: TCPRegistrationServer = None
udp_server: UDPServer = None

async def main():
    """메인 함수 - 모든 서버 시작"""
    global http_server, tcp_server, udp_server
    
    load_dotenv()
    
    print("=" * 50)
    print("OpsHub 서버 시작 중...")
    print("=" * 50)
    
    # DB 초기화
    print("\n[DB] 데이터베이스 초기화 중...")
    await init_db()
    print("[DB] 데이터베이스 초기화 완료")
    
    # 설정 파일 읽기
    root_config_file = Path(__file__).parent.parent / 'config.json'
    http_host = '0.0.0.0'
    http_port = 8000
    tcp_host = '0.0.0.0'
    tcp_port = 5500
    udp_heartbeat_port = 5501
    udp_notification_port = 5502
    
    if root_config_file.exists():
        try:
            with open(root_config_file, 'r', encoding='utf-8') as f:
                root_config = json.load(f)
                if 'server' in root_config:
                    server = root_config['server']
                    http_port = server.get('http_port', 8000)
                    tcp_port = server.get('tcp_port', 5500)
        except Exception as e:
            print(f"[설정] 설정 파일 로드 실패: {e}, 기본값 사용")
    
    # 환경변수 우선 사용
    http_host = os.getenv('HTTP_HOST', http_host)
    http_port = int(os.getenv('HTTP_PORT', str(http_port)))
    tcp_host = os.getenv('TCP_HOST', tcp_host)
    tcp_port = int(os.getenv('TCP_PORT', str(tcp_port)))
    udp_heartbeat_port = int(os.getenv('UDP_HEARTBEAT_PORT', str(udp_heartbeat_port)))
    udp_notification_port = int(os.getenv('UDP_NOTIFICATION_PORT', str(udp_notification_port)))
    
    # 서버 인스턴스 생성
    print("\n[HTTP] HTTP 서버 생성 중...")
    http_server = HTTPServer(host=http_host, port=http_port)
    
    print("\n[TCP] TCP 서버 생성 중...")
    tcp_server = TCPRegistrationServer(host=tcp_host, port=tcp_port)
    
    print("\n[UDP] UDP 서버 생성 중...")
    udp_server = UDPServer(
        heartbeat_port=udp_heartbeat_port,
        notification_port=udp_notification_port
    )
    
    # HTTP 서버에 TCP 서버 참조 설정
    http_server.set_tcp_server(tcp_server)
    
    # 모든 서버 시작
    print("\n" + "=" * 50)
    print("서버 시작 중...")
    print("=" * 50)
    
    # HTTP 서버 시작
    await http_server.start()
    
    # UDP 서버 시작
    await udp_server.start()
    
    # TCP 서버를 백그라운드 태스크로 시작
    tcp_task = asyncio.create_task(tcp_server.start())
    
    print("\n" + "=" * 50)
    print("모든 서버가 시작되었습니다!")
    print(f"  - HTTP 서버: http://{http_host}:{http_port}")
    print(f"  - TCP 서버: {tcp_host}:{tcp_port}")
    print(f"  - UDP 하트비트: {http_host}:{udp_heartbeat_port}")
    print(f"  - UDP 공지: {http_host}:{udp_notification_port}")
    print("=" * 50)
    print("\n종료하려면 Ctrl+C를 누르세요.\n")
    
    # 모든 서버가 실행 중인 상태로 유지
    try:
        await tcp_task
    except asyncio.CancelledError:
        pass

async def shutdown():
    """서버 종료"""
    global http_server, tcp_server, udp_server
    
    print("\n" + "=" * 50)
    print("서버 종료 중...")
    print("=" * 50)
    
    if http_server:
        await http_server.stop()
    
    if tcp_server:
        await tcp_server.stop()
    
    if udp_server:
        await udp_server.stop()
    
    # DB 연결 종료
    await close_db()
    
    print("서버 종료 완료")

async def run_server():
    """서버 실행 래퍼"""
    try:
        await main()
    except KeyboardInterrupt:
        print("\n\n키보드 인터럽트 감지")
    except Exception as e:
        print(f"\n\n서버 오류: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await shutdown()

if __name__ == "__main__":
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        print("\n서버 종료 중...")
