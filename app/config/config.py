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
        
        # 1. app/config.json에서 서버 설정 읽기 (우선순위 높음)
        if self.app_config_file and self.app_config_file.exists():
            try:
                print(f"app 설정 파일 로드 중: {self.app_config_file}")
                with open(self.app_config_file, 'r', encoding='utf-8') as f:
                    app_config = json.load(f)
                    # 서버 설정 병합
                    if 'server' in app_config:
                        server = app_config['server']
                        config['server_host'] = server.get('host', config['server_host'])
                        config['server_tcp_port'] = server.get('tcp_port', config['server_tcp_port'])
                        config['server_url'] = f"http://{server.get('host', config['server_host'])}:{server.get('http_port', 8000)}"
                        print(f"서버 설정 로드: {config['server_host']}:{config['server_tcp_port']} (URL: {config['server_url']})")
                    # 에이전트 설정 병합
                    if 'agent' in app_config:
                        agent = app_config['agent']
                        config['poll_interval'] = agent.get('poll_interval', config['poll_interval'])
                        config['request_status_interval'] = agent.get('request_status_interval', config['request_status_interval'])
                        config['auto_start'] = agent.get('auto_start', config['auto_start'])
                        config['version'] = agent.get('version', config['version'])
                        print(f"에이전트 설정 로드: poll_interval={config['poll_interval']}, version={config['version']}")
            except Exception as e:
                print(f"app 설정 파일 로드 실패: {e}")
        else:
            print("app/config.json 파일을 찾을 수 없습니다. 기본값을 사용합니다.")
        
        # 2. 루트 config.json에서 서버 설정 읽기 (app/config.json에서 설정하지 않은 경우에만)
        # app/config.json이 없거나 서버 설정이 없는 경우에만 루트 설정 사용
        if self.root_config_file and self.root_config_file.exists():
            # app/config.json에서 서버 설정을 읽지 못한 경우에만 루트 설정 사용
            if not self.app_config_file or not self.app_config_file.exists():
                try:
                    with open(self.root_config_file, 'r', encoding='utf-8') as f:
                        root_config = json.load(f)
                        # 서버 설정 병합 (아직 설정되지 않은 경우)
                        if 'server' in root_config and config.get('server_host') == self.default_config['server_host']:
                            server = root_config['server']
                            config['server_host'] = server.get('host', config['server_host'])
                            config['server_tcp_port'] = server.get('tcp_port', config['server_tcp_port'])
                            config['server_url'] = f"http://{server.get('host', config['server_host'])}:{server.get('http_port', 8000)}"
                        # 에이전트 설정 병합 (아직 설정되지 않은 경우)
                        if 'agent' in root_config:
                            agent = root_config['agent']
                            if config.get('poll_interval') == self.default_config['poll_interval']:
                                config['poll_interval'] = agent.get('poll_interval', config['poll_interval'])
                            if config.get('request_status_interval') == self.default_config['request_status_interval']:
                                config['request_status_interval'] = agent.get('request_status_interval', config['request_status_interval'])
                            if config.get('auto_start') == self.default_config['auto_start']:
                                config['auto_start'] = agent.get('auto_start', config['auto_start'])
                            if config.get('version') == self.default_config['version']:
                                config['version'] = agent.get('version', config['version'])
                except Exception as e:
                    print(f"루트 설정 파일 로드 실패: {e}")
        
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


