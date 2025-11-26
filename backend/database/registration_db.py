"""
등록 요청 DB 관리 모듈
"""
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime
from database.db import get_db

async def create_registration_request(hostname: str, os_info: str, agent_version: str) -> str:
    """등록 요청 생성"""
    request_id = str(uuid.uuid4())
    supabase = get_db()
    
    response = supabase.table('registration_requests').insert({
        'request_id': request_id,
        'hostname': hostname,
        'os': os_info,
        'agent_version': agent_version,
        'status': 'pending'
    }).execute()
    
    if response.data:
        return request_id
    raise Exception(f"등록 요청 생성 실패: {response}")

async def get_registration_request(request_id: str) -> Optional[Dict[str, Any]]:
    """등록 요청 조회"""
    supabase = get_db()
    
    response = supabase.table('registration_requests').select(
        'request_id, hostname, os, agent_version, status, agent_id, agent_token, '
        'created_at, approved_at, completed_at, last_heartbeat'
    ).eq('request_id', request_id).execute()
    
    if response.data and len(response.data) > 0:
        return response.data[0]
    return None

async def get_registration_requests() -> List[Dict[str, Any]]:
    """등록 요청 목록 조회"""
    supabase = get_db()
    
    response = supabase.table('registration_requests').select(
        'request_id, hostname, os, agent_version, status, agent_id, agent_token, '
        'created_at, approved_at, completed_at, last_heartbeat'
    ).order('created_at', desc=True).execute()
    
    return response.data if response.data else []

async def approve_registration(request_id: str) -> bool:
    """등록 요청 승인"""
    supabase = get_db()
    
    response = supabase.table('registration_requests').update({
        'status': 'approved',
        'approved_at': datetime.now().isoformat()
    }).eq('request_id', request_id).eq('status', 'pending').execute()
    
    return len(response.data) > 0 if response.data else False

async def complete_registration(request_id: str, agent_id: str, agent_token: str) -> bool:
    """등록 완료 처리"""
    supabase = get_db()
    
    response = supabase.table('registration_requests').update({
        'status': 'completed',
        'agent_id': agent_id,
        'agent_token': agent_token,
        'completed_at': datetime.now().isoformat()
    }).eq('request_id', request_id).eq('status', 'approved').execute()
    
    return len(response.data) > 0 if response.data else False

async def update_heartbeat(agent_id: str) -> bool:
    """하트비트 업데이트"""
    supabase = get_db()
    
    response = supabase.table('registration_requests').update({
        'last_heartbeat': datetime.now().isoformat()
    }).eq('agent_id', agent_id).eq('status', 'completed').execute()
    
    return len(response.data) > 0 if response.data else False

async def get_registration_by_agent_id(agent_id: str) -> Optional[Dict[str, Any]]:
    """agent_id로 등록 요청 조회"""
    supabase = get_db()
    
    response = supabase.table('registration_requests').select(
        'request_id, hostname, os, agent_version, status, agent_id, agent_token, '
        'created_at, approved_at, completed_at, last_heartbeat'
    ).eq('agent_id', agent_id).eq('status', 'completed').execute()
    
    if response.data and len(response.data) > 0:
        return response.data[0]
    return None

