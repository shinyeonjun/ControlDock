"""
PC 정보 DB 관리 모듈
"""
import uuid
import hashlib
from typing import Optional, Dict, Any, List
from datetime import datetime
from database.db import get_db

async def get_pc_by_hostname(hostname: str) -> Optional[Dict[str, Any]]:
    """호스트명으로 PC 정보 조회"""
    supabase = get_db()
    
    response = supabase.table('pc').select(
        'id, host_name, os, agent_version, agent_token_hash, last_check_in, poll_interval, created_at, updated_at, status, registration_request_id'
    ).eq('host_name', hostname).execute()
    
    if response.data and len(response.data) > 0:
        return response.data[0]
    return None

async def create_pc(hostname: str, os_info: str, agent_version: str, agent_token: str, registration_request_id: str = None, status: str = 'active', agent_id: str = None) -> str:
    """
    PC 등록 (agent_id 반환, 중복 체크 포함)
    
    Args:
        hostname: 호스트명
        os_info: OS 정보
        agent_version: 에이전트 버전
        agent_token: 에이전트 토큰 (해시로 저장됨)
        registration_request_id: 연결된 registration_requests의 request_id (선택사항)
        status: 상태 (기본값: 'active')
        agent_id: 지정할 agent_id (선택사항, 없으면 새로 생성)
    
    Returns:
        agent_id: 생성된 또는 기존의 agent_id
    """
    supabase = get_db()
    
    # 중복 체크: 같은 호스트명의 PC가 이미 등록되어 있는지 확인
    existing_pc = await get_pc_by_hostname(hostname)
    if existing_pc:
        # 이미 등록된 PC가 있으면 기존 agent_id 반환 (업데이트는 하지 않음)
        print(f"[PC DB] 중복 등록 방지: 호스트명 '{hostname}'은 이미 등록되어 있습니다. (agent_id: {existing_pc['id']})")
        return existing_pc['id']
    
    # agent_id가 지정되지 않았으면 새로 생성
    if not agent_id:
        agent_id = str(uuid.uuid4())
    # agent_token 해시 생성
    agent_token_hash = hashlib.sha256(agent_token.encode()).hexdigest()
    
    # UTC 타임존 사용
    from datetime import timezone
    now_utc = datetime.now(timezone.utc)
    
    insert_data = {
        'id': agent_id,
        'host_name': hostname,
        'os': os_info,
        'agent_version': agent_version,
        'agent_token_hash': agent_token_hash,
        'poll_interval': 30,
        'status': status,
        'last_check_in': now_utc.isoformat()  # 등록 시점에 하트비트 설정
    }
    
    if registration_request_id:
        insert_data['registration_request_id'] = registration_request_id
    
    try:
        print(f"[PC DB] PC 생성 시도: agent_id={agent_id}, hostname={hostname}, registration_request_id={registration_request_id}")
        response = supabase.table('pc').insert(insert_data).execute()
        
        if response.data:
            print(f"[PC DB] PC 생성 성공: agent_id={agent_id}")
            return agent_id
        else:
            print(f"[PC DB] PC 생성 실패: response.data가 없음")
            raise Exception(f"PC 등록 실패: response.data가 없습니다")
    except Exception as e:
        print(f"[PC DB] PC 생성 오류: {e}")
        print(f"[PC DB] insert_data: {insert_data}")
        import traceback
        traceback.print_exc()
        raise Exception(f"PC 등록 실패: {str(e)}")

async def get_pc(agent_id: str) -> Optional[Dict[str, Any]]:
    """PC 정보 조회 (agent_id로)"""
    supabase = get_db()
    
    response = supabase.table('pc').select(
        'id, host_name, os, agent_version, agent_token_hash, last_check_in, poll_interval, created_at, updated_at, status, registration_request_id'
    ).eq('id', agent_id).execute()
    
    if response.data and len(response.data) > 0:
        return response.data[0]
    return None

async def update_pc_heartbeat(agent_id: str):
    """하트비트 업데이트 (last_check_in 갱신)"""
    supabase = get_db()
    
    # UTC 타임존 사용 (ISO 8601 형식)
    from datetime import timezone
    now_utc = datetime.now(timezone.utc)
    
    supabase.table('pc').update({
        'last_check_in': now_utc.isoformat()
    }).eq('id', agent_id).execute()

async def update_pc_token(agent_id: str, agent_token: str):
    """PC 토큰 업데이트 (토큰 재생성 시 사용)"""
    supabase = get_db()
    
    # agent_token 해시 생성
    agent_token_hash = hashlib.sha256(agent_token.encode()).hexdigest()
    
    supabase.table('pc').update({
        'agent_token_hash': agent_token_hash
    }).eq('id', agent_id).execute()

async def get_all_pcs() -> List[Dict[str, Any]]:
    """모든 PC 목록 조회 (active 상태만)"""
    supabase = get_db()
    
    response = supabase.table('pc').select(
        'id, host_name, os, agent_version, agent_token_hash, last_check_in, poll_interval, created_at, updated_at, status, registration_request_id'
    ).eq('status', 'active').order('created_at', desc=True).execute()
    
    return response.data if response.data else []

