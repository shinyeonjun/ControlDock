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
        
        # app/config.json 경로 찾기 (app 폴더)
        self.app_config_file = self._find_app_config()
        
        # 루트 config.json 경로 찾기 (프로젝트 루트)
        self.root_config_file = self._find_root_config()
        
        # 기본 설정값
        # 주의: 실제 서버 IP로 변경하거나 config.json 파일에서 설정하세요
        self.default_config = {
            'server_url': 'http://172.29.44.72:8000',
            'server_host': '172.29.44.72',  # TCP 서버 호스트
            'server_tcp_port': 5500,  # TCP 서버 포트
            'agent_id': None,  # agent_token은 서버에서 가져옴
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
        
        # 1. 배포판 설정 로드 (EXE 옆 또는 루트 config.json)
        # 이것을 베이스로 사용
        base_config_path = None
        if self.app_config_file and self.app_config_file.exists():
            base_config_path = self.app_config_file
        elif self.root_config_file and self.root_config_file.exists():
            base_config_path = self.root_config_file
            
        if base_config_path:
            try:
                print(f"배포판 설정 로드: {base_config_path}")
                with open(base_config_path, 'r', encoding='utf-8') as f:
                    base_conf = json.load(f)
                    self._merge_config(config, base_conf)
            except Exception as e:
                print(f"배포판 설정 로드 실패: {e}")

        # 2. 사용자 설정 로드 (%APPDATA%\OpsHub\config.json)
        # 이것이 최우선 순위 (사용자 커스텀)
        if self.config_file.exists():
            try:
                print(f"사용자 설정 로드 (%APPDATA%): {self.config_file}")
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    user_conf = json.load(f)
                    self._merge_config(config, user_conf)
            except Exception as e:
                print(f"사용자 설정 로드 실패: {e}")
        else:
            # 사용자 설정 파일이 없으면 현재 설정으로 생성
            print(f"사용자 설정 파일 생성: {self.config_file}")
            self._save_config_to_file(config)
            
        return config
    
    def _merge_config(self, target: dict, source: dict):
        """설정 병합 (server 섹션 처리 포함)"""
        # 서버 설정 병합
        if 'server' in source:
            server = source['server']
            host = server.get('host')
            http_port = server.get('http_port', 8000)
            tcp_port = server.get('tcp_port', target.get('server_tcp_port', 5500))
            
            if host:
                target['server_host'] = host
                target['server_tcp_port'] = tcp_port
                target['server_url'] = f"http://{host}:{http_port}"
                print(f"  -> 서버 설정 갱신: {host}:{http_port} (TCP:{tcp_port})")
        
        # 에이전트 설정 병합
        if 'agent' in source:
            agent = source['agent']
            if 'poll_interval' in agent:
                target['poll_interval'] = agent['poll_interval']
            if 'request_status_interval' in agent:
                target['request_status_interval'] = agent['request_status_interval']
            if 'auto_start' in agent:
                target['auto_start'] = agent['auto_start']
            if 'version' in agent:
                target['version'] = agent['version']
        
        # 기타 최상위 키 병합 (agent_id 등)
        for key, value in source.items():
            if key not in ['server', 'agent', 'frontend']:
                target[key] = value

    def _save_config_to_file(self, config_data: dict):
        """설정을 파일로 저장"""
        try:
            # 저장할 구조 생성
            save_data = {
                'agent_id': config_data.get('agent_id'),
                'server': {
                    'host': config_data.get('server_host'),
                    'http_port': 8000, # 기본값 가정
                    'tcp_port': config_data.get('server_tcp_port')
                },
                'agent': {
                    'poll_interval': config_data.get('poll_interval'),
                    'request_status_interval': config_data.get('request_status_interval'),
                    'auto_start': config_data.get('auto_start'),
                    'version': config_data.get('version')
                }
            }
            
            # URL에서 포트 추출 시도
            try:
                url_parts = config_data.get('server_url', '').split(':')
                if len(url_parts) >= 3:
                    save_data['server']['http_port'] = int(url_parts[2].split('/')[0])
            except:
                pass
                
            # 기타 필요한 필드 추가
            if 'registration_request_id' in config_data:
                save_data['registration_request_id'] = config_data['registration_request_id']
            if 'should_register_startup' in config_data:
                save_data['should_register_startup'] = config_data['should_register_startup']

            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=2, ensure_ascii=False)
            print(f"설정 저장 완료: {self.config_file}")
        except Exception as e:
            print(f"설정 저장 실패: {e}")

    def get(self, key: str, default=None):
        """설정값 가져오기"""
        return self._config.get(key, default)
    
    def set(self, key: str, value):
        """설정값 설정 및 저장"""
        self._config[key] = value
        self._save_config_to_file(self._config)
        
    @property
    def agent_id(self) -> Optional[str]:
        return self.get('agent_id')
    
    @agent_id.setter
    def agent_id(self, value: str):
        self.set('agent_id', value)
        
    def get_agent_token(self) -> Optional[str]:
        """에이전트 토큰 가져오기 (서버에서 가져옴, 캐싱됨)"""
        if hasattr(self, '_cached_token'):
            return self._cached_token
        return None
        
    def set_agent_token(self, token: str):
        """에이전트 토큰 설정 (메모리 캐싱만)"""
        self._cached_token = token
        
    @property
    def server_url(self) -> str:
        return self.get('server_url', 'http://172.29.44.72:8000')
    
    @property
    def poll_interval(self) -> int:
        return self.get('poll_interval', 10)
    
    @property
    def request_status_interval(self) -> int:
        return self.get('request_status_interval', 30)
    
    @property
    def server_host(self) -> str:
        return self.get('server_host', '172.29.44.72')
    
    @property
    def server_tcp_port(self) -> int:
        return self.get('server_tcp_port', 5500)
