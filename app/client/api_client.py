"""
서버 통신 API 클라이언트
"""
import requests
from typing import Optional, Dict, Any
from config.config import Config

class APIClient:
    """서버 API 클라이언트"""
    
    def __init__(self, config: Config):
        self.config = config
        self.base_url = config.server_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': f'OpsHub-Agent/{config.get("version", "1.0.0")}'
        })
    
    def _request(self, method: str, endpoint: str, **kwargs) -> Optional[Dict[str, Any]]:
        """API 요청 헬퍼"""
        url = f"{self.base_url}/api{endpoint}"
        
        try:
            response = self.session.request(method, url, timeout=10, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"API 요청 실패 [{method} {endpoint}]: {e}")
            return None
    
    def register_request(self, system_info: Dict[str, str]) -> Optional[Dict[str, Any]]:
        """PC 등록 승인 요청"""
        payload = {
            'hostname': system_info['hostname'],
            'os': system_info['os'],
            'agent_version': self.config.get('version', '1.0.0')
        }
        return self._request('POST', '/agents/register-request', json=payload)
    
    def check_registration_status(self, request_id: str) -> Optional[Dict[str, Any]]:
        """등록 요청 상태 확인"""
        # 기존 엔드포인트 사용: /api/registration-requests/{request_id}
        response = self._request('GET', f'/registration-requests/{request_id}')
        if response:
            # 응답 형식을 맞춰서 반환
            return {
                'success': True,
                'status': response.get('status', 'pending'),
                'request': response
            }
        return None
    
    def complete_registration(self, request_id: str, system_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """등록 완료 (상세 정보 전송)"""
        # 승인된 후 등록 완료는 별도 API가 필요하지만, 
        # 현재는 승인 시 자동으로 완료 처리되므로 여기서는 상태 확인만
        # 실제로는 서버에서 승인 시 자동으로 agent_id를 생성하므로
        # 여기서는 상태 확인 후 agent_id를 받아오는 방식으로 수정 필요
        response = self._request('GET', f'/registration-requests/{request_id}')
        if response and response.get('status') == 'completed':
            # 등록 완료된 경우 agent_id 반환
            return {
                'success': True,
                'agent_id': response.get('agent_id'),
                'agent_token': None  # 토큰은 별도로 받아야 할 수 있음
            }
        return None
    
    def send_heartbeat(self, agent_id: str, agent_token: str) -> bool:
        """하트비트 전송"""
        self.session.headers['Authorization'] = f'Bearer {agent_token}'
        result = self._request('POST', f'/agents/{agent_id}/heartbeat')
        return result is not None
    
    def poll_tasks(self, agent_id: str, agent_token: str, want_n: int = 1) -> Optional[Dict[str, Any]]:
        """작업 폴링"""
        self.session.headers['Authorization'] = f'Bearer {agent_token}'
        payload = {'want_n': want_n}
        return self._request('POST', f'/agents/{agent_id}/tasks/poll', json=payload)
    
    def submit_result(self, agent_id: str, agent_token: str, result: Dict[str, Any]) -> bool:
        """작업 결과 제출"""
        self.session.headers['Authorization'] = f'Bearer {agent_token}'
        response = self._request('POST', f'/agents/{agent_id}/tasks/results', json=result)
        return response is not None

