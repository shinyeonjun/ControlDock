#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WSL 포트 포워딩 자동 설정 스크립트
Windows 호스트 IP와 WSL IP를 자동으로 감지하고 포트 포워딩을 설정합니다.
"""

import json
import os
import subprocess
import sys
import re
from pathlib import Path


def is_admin():
    """관리자 권한 확인"""
    try:
        return os.getuid() == 0
    except AttributeError:
        # Windows
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0


def get_wsl_ip():
    """WSL IP 주소 가져오기"""
    try:
        result = subprocess.run(
            ['wsl', 'hostname', '-I'],
            capture_output=True,
            text=True,
            check=True
        )
        ip = result.stdout.strip().split()[0]  # 첫 번째 IP만 사용
        return ip
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("[오류] WSL IP 주소를 가져올 수 없습니다.")
        print("WSL이 실행 중인지 확인하세요.")
        return None


def get_windows_host_ip():
    """Windows 호스트 IP 주소 가져오기 (192.168.0.x 우선, 그 다음 192.168.x.x)"""
    try:
        result = subprocess.run(
            ['ipconfig'],
            capture_output=True,
            text=True,
            check=True
        )
        
        # IPv4 주소 찾기
        ipv4_pattern = r'IPv4.*?:\s*(\d+\.\d+\.\d+\.\d+)'
        matches = re.findall(ipv4_pattern, result.stdout)
        
        # 1순위: 192.168.0.x (Wi-Fi)
        for ip in matches:
            if ip.startswith('192.168.0.'):
                return ip
        
        # 2순위: 192.168.x.x (이더넷)
        for ip in matches:
            if ip.startswith('192.168.'):
                return ip
        
        # 3순위: 172.x.x.x
        for ip in matches:
            if ip.startswith('172.'):
                return ip
        
        # 그 외 첫 번째 IP
        if matches:
            return matches[0]
        
        return None
    except subprocess.CalledProcessError:
        print("[경고] Windows 호스트 IP를 자동으로 찾을 수 없습니다.")
        return None


def setup_port_forwarding(wsl_ip, ports):
    """포트 포워딩 설정"""
    print("\n[4단계] 포트 포워딩 설정 중...\n")
    
    # 기존 포트 포워딩 삭제
    for port in ports:
        subprocess.run(
            ['netsh', 'interface', 'portproxy', 'delete', 'v4tov4',
             f'listenport={port}', 'listenaddress=0.0.0.0'],
            capture_output=True
        )
    
    # 새 포트 포워딩 추가
    success_count = 0
    for port in ports:
        result = subprocess.run(
            ['netsh', 'interface', 'portproxy', 'add', 'v4tov4',
             f'listenport={port}', 'listenaddress=0.0.0.0',
             f'connectport={port}', f'connectaddress={wsl_ip}'],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print(f"[완료] 포트 {port} 포워딩 설정 완료")
            success_count += 1
        else:
            print(f"[오류] 포트 {port} 포워딩 설정 실패")
    
    return success_count == len(ports)


def check_docker_running():
    """Docker가 실행 중인지 확인"""
    try:
        result = subprocess.run(
            ['docker', 'ps'],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False


def check_docker_container_running(project_dir):
    """Docker 컨테이너가 실행 중인지 확인"""
    try:
        os.chdir(project_dir)
        result = subprocess.run(
            ['docker-compose', 'ps'],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return 'ophub-server' in result.stdout and 'Up' in result.stdout
        return False
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False
    finally:
        # 원래 디렉토리로 복귀
        try:
            os.chdir(Path(__file__).parent)
        except:
            pass


def manage_docker_container(project_dir, host_ip):
    """Docker 컨테이너 관리"""
    print("\n[3단계] Docker 컨테이너 상태 확인 중...\n")
    
    # Docker 실행 확인
    if not check_docker_running():
        print("[경고] Docker가 실행되지 않았거나 docker 명령어를 찾을 수 없습니다.")
        print("Docker Desktop을 실행한 후 다시 시도하세요.")
        return
    
    backend_dir = Path(project_dir) / "backend"
    if not backend_dir.exists():
        print("[정보] backend 디렉토리를 찾을 수 없습니다.")
        return
    
    # 컨테이너 상태 확인
    if check_docker_container_running(str(backend_dir)):
        print("[확인] Docker 컨테이너가 실행 중입니다.")
        print()
        restart = input("[선택사항] Docker 컨테이너를 재시작하여 새 설정을 적용하시겠습니까? (Y/N): ").strip().upper()
        if restart == 'Y':
            print()
            print("[재시작] Docker 컨테이너 재시작 중...")
            try:
                os.chdir(backend_dir)
                result = subprocess.run(
                    ['docker-compose', 'restart', 'ophub-server'],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode == 0:
                    print("[완료] Docker 컨테이너 재시작 완료")
                    import time
                    time.sleep(2)
                    print()
                    print("[확인] Docker 컨테이너 로그:")
                    subprocess.run(['docker-compose', 'logs', '--tail=10', 'ophub-server'])
                else:
                    print("[경고] Docker 컨테이너 재시작 실패")
            except Exception as e:
                print(f"[경고] Docker 컨테이너 재시작 중 오류: {e}")
            finally:
                os.chdir(project_dir)
    else:
        print("[정보] Docker 컨테이너가 실행되지 않았습니다.")
        print()
        start = input("Docker 컨테이너를 시작하시겠습니까? (Y/N): ").strip().upper()
        if start == 'Y':
            print()
            print("[시작] Docker 컨테이너 시작 중...")
            try:
                os.chdir(backend_dir)
                result = subprocess.run(
                    ['docker-compose', 'up', '-d'],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                if result.returncode == 0:
                    print("[완료] Docker 컨테이너 시작 완료")
                    import time
                    time.sleep(3)
                    print()
                    print("[확인] Docker 컨테이너 로그:")
                    subprocess.run(['docker-compose', 'logs', '--tail=20', 'ophub-server'])
                else:
                    print("[경고] Docker 컨테이너 시작 실패")
            except Exception as e:
                print(f"[경고] Docker 컨테이너 시작 중 오류: {e}")
            finally:
                os.chdir(project_dir)
        else:
            print("[정보] Docker 컨테이너를 시작하려면 다음 명령어를 실행하세요:")
            print("  cd backend")
            print("  docker-compose up -d")


def update_config_json(config_path, host_ip, is_client=False):
    """config.json 파일 업데이트"""
    try:
        # 기존 config.json 읽기
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        else:
            # 기본 구조 생성
            if is_client:
                config = {
                    "server": {
                        "host": "",
                        "tcp_port": 5500,
                        "http_port": 8000
                    },
                    "agent": {}
                }
            else:
                config = {
                    "server": {
                        "host": "",
                        "http_port": 8000,
                        "tcp_port": 5500
                    },
                    "frontend": {
                        "api_base_url": ""
                    }
                }
        
        # server 섹션이 없으면 생성
        if 'server' not in config:
            config['server'] = {}
        
        # 값 업데이트
        config['server']['host'] = host_ip
        config['server']['tcp_port'] = 5500
        config['server']['http_port'] = 8000
        
        # 클라이언트가 아닌 경우 frontend도 업데이트
        if not is_client:
            if 'frontend' not in config:
                config['frontend'] = {}
            config['frontend']['api_base_url'] = f"http://{host_ip}:8000/api"
        
        # 파일 저장
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        return True
    except Exception as e:
        print(f"[경고] {config_path} 업데이트 실패: {e}")
        return False


def main():
    """메인 함수 - OpsHub 자동 설정"""
    print("=" * 40)
    print("OpsHub 자동 설정")
    print("=" * 40)
    print()
    
    # 1단계: Windows 호스트 IP 주소 자동 감지
    print("[1단계] Windows 호스트 IP 주소 자동 감지 중...\n")
    host_ip = get_windows_host_ip()
    if not host_ip:
        print("[경고] Windows 호스트 IP를 자동으로 찾을 수 없습니다.")
        print("\n현재 네트워크 어댑터의 IP 주소:")
        subprocess.run(['ipconfig'])
        print("\n수동으로 IP를 입력하세요 (예: 192.168.0.14):")
        host_ip = input("Windows 호스트 IP 주소: ").strip()
        if not host_ip:
            print("[오류] IP 주소를 입력하지 않았습니다.")
            input("Press Enter to exit...")
            sys.exit(1)
    print(f"[확인] Windows 호스트 IP 주소: {host_ip}\n")
    
    # 2단계: config.json 파일 업데이트
    print("[2단계] config.json 파일 업데이트 중...\n")
    
    # 프로젝트 루트 경로
    project_root = Path(__file__).parent
    config_file = project_root / "config.json"
    app_config_file = project_root / "app" / "config.json"

    # config.json 업데이트
    if update_config_json(config_file, host_ip):
        print("[완료] config.json 업데이트 완료")
    else:
        print("[경고] config.json 업데이트 실패")

    # app/config.json 업데이트
    if app_config_file.exists():
        if update_config_json(app_config_file, host_ip):
            print("[완료] app\\config.json 업데이트 완료")
        else:
            print("[경고] app\\config.json 업데이트 실패")
    else:
        print("[정보] app\\config.json 파일이 없습니다. (건너뜀)")

    # %APPDATA%\OpsHub\config.json 업데이트 (클라이언트 설정)
    appdata_dir = os.environ.get("APPDATA")
    if appdata_dir:
        client_dir = Path(appdata_dir) / "OpsHub"
        try:
            client_dir.mkdir(parents=True, exist_ok=True)
            client_config_file = client_dir / "config.json"
            if update_config_json(client_config_file, host_ip, is_client=True):
                print("[완료] 클라이언트 config.json 업데이트 완료")
            else:
                print("[경고] 클라이언트 config.json 업데이트 실패")
        except Exception as e:
            print(f"[경고] 클라이언트 config.json 디렉터리 생성/업데이트 실패: {e}")
    else:
        print("[정보] APPDATA 환경변수를 찾을 수 없습니다. 클라이언트 config.json 업데이트를 건너뜁니다.")
    
    # 3단계: Docker 컨테이너 관리
    manage_docker_container(str(project_root), host_ip)
    
    # 4단계: 포트 포워딩 설정 (선택사항 - 관리자 권한 필요)
    print("\n[4단계] WSL 포트 포워딩 설정 (선택사항)...\n")
    if is_admin():
        wsl_ip = get_wsl_ip()
        if wsl_ip:
            print(f"[확인] WSL IP 주소: {wsl_ip}\n")
            setup = input("포트 포워딩을 설정하시겠습니까? (Y/N): ").strip().upper()
            if setup == 'Y':
                ports = [5500, 8000, 5501, 5502]
                # 기존 포트 포워딩 삭제
                print("\n기존 포트 포워딩 삭제 중...")
                for port in ports:
                    subprocess.run(
                        ['netsh', 'interface', 'portproxy', 'delete', 'v4tov4',
                         f'listenport={port}', 'listenaddress=0.0.0.0'],
                        capture_output=True
                    )
                # 새 포트 포워딩 설정
                if setup_port_forwarding(wsl_ip, ports):
                    print("\n현재 설정된 포트 포워딩:")
                    subprocess.run(['netsh', 'interface', 'portproxy', 'show', 'all'])
                else:
                    print("\n[경고] 일부 포트 포워딩 설정에 실패했습니다.")
        else:
            print("[정보] WSL IP를 가져올 수 없어 포트 포워딩을 건너뜁니다.")
    else:
        print("[정보] 포트 포워딩 설정은 관리자 권한이 필요합니다.")
        print("       관리자 권한으로 실행하면 포트 포워딩을 설정할 수 있습니다.")
    
    # 결과 출력
    print("\n" + "=" * 40)
    print("설정 완료!")
    print("=" * 40)
    print()
    print("현재 설정:")
    print(f"  - Windows 호스트 IP: {host_ip}")
    print(f"  - HTTP 서버: http://{host_ip}:8000")
    print(f"  - TCP 서버: {host_ip}:5500")
    print(f"  - UDP 하트비트: {host_ip}:5501")
    print(f"  - UDP 공지: {host_ip}:5502")
    print()
    print("업데이트된 파일:")
    print(f"  - {config_file}")
    if app_config_file.exists():
        print(f"  - {app_config_file}")
    appdata_dir = os.environ.get("APPDATA")
    if appdata_dir:
        client_config_file = Path(appdata_dir) / "OpsHub" / "config.json"
        if client_config_file.exists():
            print(f"  - {client_config_file}")
    print()
    print("참고: 네트워크가 변경되면 이 스크립트(setup.py)를 다시 실행하세요.")
    print("       클라이언트를 실행하기 전에 설정이 완료되었는지 확인하세요.")
    print()
    input("Press Enter to exit...")


if __name__ == "__main__":
    main()
