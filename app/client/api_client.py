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
        except requests.exceptions.HTTPError as e:
            status = getattr(e.response, 'status_code', 'unknown')
            # 410 Gone은 에이전트가 서버에서 제거되었음을 의미 (재등록 필요)
            if status == 410:
                print(f"에이전트가 서버에서 제거되었습니다. 재등록이 필요합니다. [{method} {endpoint}]")
                # 특별한 플래그를 반환하여 재등록을 유도
                return {'_needs_reregistration': True, 'status': 410}
            print(f"API 요청 실패 [{method} {endpoint}] HTTP {status}: {e}")
            return None
        except requests.exceptions.RequestException as e:
            print(f"API 요청 실패 [{method} {endpoint}]: {e}")
            return None

    def _set_auth(self, agent_token: Optional[str]):
        """인증 헤더 설정(토큰 있으면 추가, 없으면 제거)"""
        if agent_token:
            self.session.headers['Authorization'] = f'Bearer {agent_token}'
        else:
            self.session.headers.pop('Authorization', None)
    
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
        # 실제로는 서버에서 승인 시 자동으로 agent_id와 agent_token을 생성하므로
        # 여기서는 상태 확인 후 agent_id와 agent_token을 받아오는 방식
        
        # 등록 요청 조회로 상태 확인
        response = self._request('GET', f'/registration-requests/{request_id}')
        if response and response.get('status') == 'completed':
            # 등록 완료된 경우 agent_id 반환
            agent_id = response.get('agent_id')
            if not agent_id:
                # agent_id가 없으면 오류
                print(f"[오류] 등록 완료 응답에 agent_id가 없습니다: {response}")
                return None
            
            # agent_token은 등록 완료 시에만 서버에서 전달받음
            # 승인 API 응답에서 받은 토큰을 사용해야 하지만,
            # 현재 구조에서는 등록 요청 조회 API에서 토큰을 받을 수 없음
            # 따라서 등록 완료 시 서버에서 토큰을 가져오는 별도 API 호출 필요
            # 하지만 보안상 토큰은 등록 완료 시에만 한 번 전달되므로,
            # 여기서는 agent_id만 반환하고, 토큰은 별도로 가져와야 함
            # TODO: 등록 완료 시 토큰을 가져오는 별도 API 구현 필요
            return {
                'success': True,
                'agent_id': agent_id,
                'agent_token': None  # 토큰은 별도로 가져와야 함 (현재 구조에서는 불가능)
            }
        return None
    
    def send_heartbeat(self, agent_id: str, agent_token: str):
        """하트비트 전송
        Returns:
            True: 성공
            False: 실패
            dict with '_needs_reregistration': True: 재등록 필요 (410 Gone)
        """
        self._set_auth(agent_token)
        result = self._request('POST', f'/agents/{agent_id}/heartbeat')
        # 410 Gone이면 재등록 필요 플래그 반환
        if isinstance(result, dict) and result.get('_needs_reregistration'):
            return result  # 재등록 필요 플래그 반환
        return result is not None
    
    def poll_tasks(self, agent_id: str, agent_token: str, want_n: int = 1) -> Optional[Dict[str, Any]]:
        """작업 폴링"""
        self._set_auth(agent_token)
        payload = {'want_n': want_n}
        return self._request('POST', f'/agents/{agent_id}/tasks/poll', json=payload)
    
    def submit_result(self, agent_id: str, agent_token: str, result: Dict[str, Any]) -> bool:
        """작업 결과 제출"""
        self._set_auth(agent_token)
        response = self._request('POST', f'/agents/{agent_id}/tasks/results', json=result)
        return response is not None
    
    def get_agent_token(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """agent_id로 토큰 조회"""
        return self._request('GET', f'/agents/{agent_id}/token')
    
    def get_agent_config(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """agent_id로 설정 조회 (DB에서 가져옴)"""
        return self._request('GET', f'/agents/{agent_id}/config')

