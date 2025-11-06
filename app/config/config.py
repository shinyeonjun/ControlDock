"""
OpsHub Agent 설정 관리
"""
import os
import sys
import json
from pathlib import Path
from typing import Optional

class Config:
    """에이전트 설정 관리 클래스"""
    
    def __init__(self, config_dir: Optional[Path] = None):
        if config_dir is None:
            # 기본 설정 디렉토리: %APPDATA%\OpsHub
            self.config_dir = Path(os.getenv('APPDATA', '')) / 'OpsHub'
        else:
            self.config_dir = Path(config_dir)
        
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = self.config_dir / 'config.json'
        self.agent_token_file = self.config_dir / 'agent_token.txt'
        
        # app/config.json 경로 찾기 (app 폴더)
        self.app_config_file = self._find_app_config()
        
        # 루트 config.json 경로 찾기 (프로젝트 루트)
        self.root_config_file = self._find_root_config()
        
        # 기본 설정값
        # 주의: 실제 서버 IP로 변경하거나 config.json 파일에서 설정하세요
        self.default_config = {
            'server_url': 'http://172.31.72.62:8000',
            'server_host': '172.31.72.62',  # TCP 서버 호스트
            'server_tcp_port': 5500,  # TCP 서버 포트
            'agent_id': None,
            'agent_token': None,
            'poll_interval': 10,  # 초
            'request_status_interval': 30,  # 승인 요청 상태 확인 주기 (초)
            'auto_start': True,
            'version': '1.0.0'
        }
        
        self._config = self._load_config()
    
    def _find_app_config(self) -> Optional[Path]:
        """app 폴더의 config.json 찾기"""
        # PyInstaller로 빌드된 exe인 경우
        if getattr(sys, 'frozen', False):
            # exe 파일이 있는 디렉토리에서 config.json 찾기
            exe_dir = Path(sys.executable).parent
            app_config = exe_dir / 'config.json'
            if app_config.exists():
                return app_config
        
        # 개발 모드: 현재 파일 위치에서 상위로 올라가면서 config.json 찾기
        current = Path(__file__).resolve()
        # app/config/config.py -> app -> app/config.json
        app_config = current.parent.parent / 'config.json'
        if app_config.exists():
            return app_config
        return None
    
    def _find_root_config(self) -> Optional[Path]:
        """프로젝트 루트의 config.json 찾기"""
        # 현재 파일 위치에서 상위로 올라가면서 config.json 찾기
        current = Path(__file__).resolve()
        # app/config/config.py -> app -> 프로젝트 루트
        root = current.parent.parent.parent / 'config.json'
        if root.exists():
            return root
        return None
    
    def _load_config(self) -> dict:
        """설정 파일 로드"""
        config = self.default_config.copy()
        
        # 루트 config.json을 단일 소스(true source)로 사용
        # - 개발 환경: 루트 config.json 우선
        # - 동결(EXE) 환경: exe 옆 config.json(app_config_file) 우선
        try:
            prefer_root = not getattr(sys, 'frozen', False)
            loaded_from = None
            cfg_path = None
            if prefer_root and self.root_config_file and self.root_config_file.exists():
                cfg_path = self.root_config_file
                loaded_from = 'root'
            elif self.app_config_file and self.app_config_file.exists():
                cfg_path = self.app_config_file
                loaded_from = 'app'
            
            if cfg_path:
                print(f"설정 파일 로드 중({loaded_from}): {cfg_path}")
                with open(cfg_path, 'r', encoding='utf-8') as f:
                    merged = json.load(f)
                    # 서버 설정
                    if 'server' in merged:
                        server = merged['server']
                        host = server.get('host', config['server_host'])
                        http_port = server.get('http_port', 8000)
                        tcp_port = server.get('tcp_port', config['server_tcp_port'])
                        config['server_host'] = host
                        config['server_tcp_port'] = tcp_port
                        config['server_url'] = f"http://{host}:{http_port}"
                        print(f"서버 설정 로드: {config['server_host']}:{http_port} (TCP:{config['server_tcp_port']})")
                    # 에이전트 설정
                    if 'agent' in merged:
                        agent = merged['agent']
                        if 'poll_interval' in agent:
                            config['poll_interval'] = agent['poll_interval']
                        if 'request_status_interval' in agent:
                            config['request_status_interval'] = agent['request_status_interval']
                        if 'auto_start' in agent:
                            config['auto_start'] = agent['auto_start']
                        if 'version' in agent:
                            config['version'] = agent['version']
                        print(f"에이전트 설정 로드: poll_interval={config['poll_interval']}, version={config['version']}")
            else:
                print("루트/앱 config.json을 찾지 못했습니다. 기본값을 사용합니다.")
        except Exception as e:
            print(f"설정 파일 로드 실패: {e}")
        
        # 3. 로컬 config.json에서 설정 읽기 (사용자별 설정만 - agent_id, token 등)
        # 서버 설정(server_host, server_url)은 app/config.json을 우선시
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    local_config = json.load(f)
                    # 서버 설정은 제외하고 나머지만 업데이트
                    # 서버 설정은 app/config.json에서 관리
                    if 'server_host' in local_config:
                        del local_config['server_host']
                    if 'server_url' in local_config:
                        del local_config['server_url']
                    if 'server_tcp_port' in local_config:
                        del local_config['server_tcp_port']
                    # 나머지 설정만 업데이트 (agent_id, token 등 사용자별 설정)
                    config.update(local_config)
                    print(f"로컬 설정 파일 로드 완료: {self.config_file}")
            except Exception as e:
                print(f"로컬 설정 파일 로드 실패: {e}")
        else:
            # config.json이 없으면 기본값으로 파일 생성 (EXE 실행 시 자동 생성)
            try:
                self.save_config()
                print(f"설정 파일이 생성되었습니다: {self.config_file}")
            except Exception as e:
                print(f"설정 파일 자동 생성 실패: {e}")
        
        return config
    
    def save_config(self):
        """설정 파일 저장"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"설정 파일 저장 실패: {e}")
    
    def get(self, key: str, default=None):
        """설정값 가져오기"""
        return self._config.get(key, default)
    
    def set(self, key: str, value):
        """설정값 설정"""
        self._config[key] = value
        self.save_config()
    
    def get_agent_token(self) -> Optional[str]:
        """에이전트 토큰 가져오기 (파일에서)"""
        if self.agent_token_file.exists():
            try:
                with open(self.agent_token_file, 'r', encoding='utf-8') as f:
                    return f.read().strip()
            except Exception:
                pass
        return self._config.get('agent_token')
    
    def save_agent_token(self, token: str):
        """에이전트 토큰 저장"""
        try:
            with open(self.agent_token_file, 'w', encoding='utf-8') as f:
                f.write(token)
            self.set('agent_token', token)
        except Exception as e:
            print(f"토큰 저장 실패: {e}")
    
    @property
    def server_url(self) -> str:
        return self.get('server_url', 'http://172.31.72.62:8000')
    
    @property
    def agent_id(self) -> Optional[str]:
        return self.get('agent_id')
    
    @agent_id.setter
    def agent_id(self, value: str):
        self.set('agent_id', value)
    
    @property
    def poll_interval(self) -> int:
        return self.get('poll_interval', 10)
    
    @property
    def request_status_interval(self) -> int:
        return self.get('request_status_interval', 30)
    
    @property
    def server_host(self) -> str:
        return self.get('server_host', '172.31.72.62')
    
    @property
    def server_tcp_port(self) -> int:
        return self.get('server_tcp_port', 5500)


