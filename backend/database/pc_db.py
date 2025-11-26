"""
PC 정보 DB 관리 모듈
"""
import uuid
import hashlib
from typing import Optional, Dict, Any, List
from datetime import datetime
from database.db import get_db

async def create_pc(hostname: str, os_info: str, agent_version: str, agent_token: str) -> str:
    """PC 등록 (agent_id 반환)"""
    agent_id = str(uuid.uuid4())
    # agent_token 해시 생성
    agent_token_hash = hashlib.sha256(agent_token.encode()).hexdigest()
    
    supabase = get_db()
    
    response = supabase.table('pc').insert({
        'id': agent_id,
        'host_name': hostname,
        'os': os_info,
        'agent_version': agent_version,
        'agent_token_hash': agent_token_hash,
        'poll_interval': 10
    }).execute()
    
    if response.data:
        return agent_id
    raise Exception(f"PC 등록 실패: {response}")

async def get_pc(agent_id: str) -> Optional[Dict[str, Any]]:
    """PC 정보 조회"""
    supabase = get_db()
    
    response = supabase.table('pc').select(
        'id, host_name, os, agent_version, agent_token_hash, last_check_in, poll_interval, created_at'
    ).eq('id', agent_id).execute()
    
    if response.data and len(response.data) > 0:
        return response.data[0]
    return None

async def update_pc_heartbeat(agent_id: str):
    """하트비트 업데이트 (last_check_in 갱신)"""
    supabase = get_db()
    
    supabase.table('pc').update({
        'last_check_in': datetime.now().isoformat()
    }).eq('id', agent_id).execute()

async def get_all_pcs() -> List[Dict[str, Any]]:
    """모든 PC 목록 조회"""
    supabase = get_db()
    
    response = supabase.table('pc').select(
        'id, host_name, os, agent_version, agent_token_hash, last_check_in, poll_interval, created_at'
    ).order('created_at', desc=True).execute()
    
    return response.data if response.data else []

