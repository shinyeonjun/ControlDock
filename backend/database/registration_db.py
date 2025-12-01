"""
등록 요청 DB 관리 모듈
"""
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime
from database.db import get_db

async def get_registration_by_hostname(hostname: str, status: str = None) -> Optional[Dict[str, Any]]:
    """호스트명으로 등록 요청 조회"""
    supabase = get_db()
    
    query = supabase.table('registration_requests').select(
        'request_id, hostname, os, agent_version, status, agent_id, '
        'created_at, approved_at, completed_at, rejected_at'
    ).eq('hostname', hostname)
    
    if status:
        query = query.eq('status', status)
    
    response = query.order('created_at', desc=True).limit(1).execute()
    
    if response.data and len(response.data) > 0:
        return response.data[0]
    return None

async def create_registration_request(hostname: str, os_info: str, agent_version: str) -> str:
    """등록 요청 생성 (중복 체크 포함)"""
    supabase = get_db()
    
    # 중복 체크: 같은 호스트명의 pending/completed 요청이 있는지 확인
    existing_pending = await get_registration_by_hostname(hostname, 'pending')
    if existing_pending:
        # pending 요청이 있으면 기존 요청 ID 반환
        print(f"[등록 요청] 중복 방지: 호스트명 '{hostname}'의 대기 중인 등록 요청이 있습니다. (request_id: {existing_pending['request_id']})")
        return existing_pending['request_id']
    
    existing_completed = await get_registration_by_hostname(hostname, 'completed')
    if existing_completed:
        # completed 요청이 있으면 이미 등록된 것으로 간주
        print(f"[등록 요청] 중복 방지: 호스트명 '{hostname}'은 이미 등록 완료되었습니다. (request_id: {existing_completed['request_id']}, agent_id: {existing_completed.get('agent_id')})")
        return existing_completed['request_id']
    
    request_id = str(uuid.uuid4())
    
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
        'request_id, hostname, os, agent_version, status, agent_id, '
        'created_at, approved_at, completed_at, rejected_at'
    ).eq('request_id', request_id).execute()
    
    if response.data and len(response.data) > 0:
        return response.data[0]
    return None

async def get_registration_requests() -> List[Dict[str, Any]]:
    """등록 요청 목록 조회"""
    supabase = get_db()
    
    response = supabase.table('registration_requests').select(
        'request_id, hostname, os, agent_version, status, agent_id, '
        'created_at, approved_at, completed_at, rejected_at'
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

async def complete_registration(request_id: str, agent_id: str) -> bool:
    """
    등록 완료 처리
    
    Args:
        request_id: 등록 요청 ID
        agent_id: 연결된 PC의 agent_id (pc 테이블의 id)
    
    Note:
        agent_token은 pc 테이블에만 저장됨 (registration_requests에는 저장하지 않음)
    """
    supabase = get_db()
    
    response = supabase.table('registration_requests').update({
        'status': 'completed',
        'agent_id': agent_id,  # Foreign Key to pc 테이블
        'completed_at': datetime.now().isoformat()
    }).eq('request_id', request_id).eq('status', 'approved').execute()
    
    return len(response.data) > 0 if response.data else False

# 하트비트 업데이트는 pc_db.py의 update_pc_heartbeat만 사용
# registration_requests 테이블에는 하트비트 정보를 저장하지 않음

# 주의: update_registration_agent_id 함수는 제거됨
# agent_id는 등록 완료 시점(complete_registration)에만 저장됨
# 등록 요청 생성 시점에는 agent_id를 저장하지 않음 (Foreign Key 제약 때문)

async def get_registration_by_agent_id(agent_id: str) -> Optional[Dict[str, Any]]:
    """
    agent_id로 등록 요청 조회 (모든 상태)
    
    Note:
        이 함수는 하트비트 매칭용으로만 사용 (호스트명 찾기)
        실제 하트비트는 pc 테이블에서만 업데이트됨
    """
    supabase = get_db()
    
    response = supabase.table('registration_requests').select(
        'request_id, hostname, os, agent_version, status, agent_id, '
        'created_at, approved_at, completed_at, rejected_at'
    ).eq('agent_id', agent_id).order('created_at', desc=True).limit(1).execute()
    
    if response.data and len(response.data) > 0:
        return response.data[0]
    return None

