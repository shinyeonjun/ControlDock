"""
공지 DB 관리 모듈
"""
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime
from database.db import get_db

async def create_announcement(
    title: str,
    content: str,
    priority: str = 'normal',  # low, normal, high, urgent
    target_agents: Optional[List[str]] = None  # None이면 전체
) -> str:
    """공지 생성"""
    announcement_id = str(uuid.uuid4())
    supabase = get_db()
    
    response = supabase.table('announcements').insert({
        'announcement_id': announcement_id,
        'title': title,
        'content': content,
        'priority': priority,
        'target_agents': target_agents,  # None이면 전체 대상
        'status': 'active',  # active, expired
        'created_at': datetime.now().isoformat(),
        'expires_at': None  # 만료 시간 (선택사항)
    }).execute()
    
    if response.data:
        return announcement_id
    raise Exception(f"공지 생성 실패: {response}")

async def get_announcement(announcement_id: str) -> Optional[Dict[str, Any]]:
    """공지 조회 (대상 수, 수신 수 포함)"""
    supabase = get_db()
    
    response = supabase.table('announcements').select(
        'announcement_id, title, content, priority, target_agents, '
        'status, created_at, expires_at'
    ).eq('announcement_id', announcement_id).execute()
    
    if not response.data or len(response.data) == 0:
        return None
    
    ann = response.data[0]
    
    # 전체 에이전트 수 조회
    from database.pc_db import get_all_pcs
    all_pcs = await get_all_pcs()
    total_agents_count = len(all_pcs)
    
    # 수신 기록 수 조회
    receipts_response = supabase.table('announcement_receipts').select(
        'receipt_id'
    ).eq('announcement_id', announcement_id).execute()
    
    received_count = len(receipts_response.data) if receipts_response.data else 0
    
    # 대상 수 계산
    target_agents = ann.get('target_agents')
    if target_agents is None or (isinstance(target_agents, list) and len(target_agents) == 0):
        target_count = total_agents_count
    else:
        target_count = len(target_agents) if isinstance(target_agents, list) else 0
    
    # 상태 변환
    status = ann.get('status', 'active')
    display_status = 'sent' if status == 'active' else 'expired'
    
    # 통계 추가
    return {
        **ann,
        'target_count': target_count,
        'received_count': received_count,
        'sent_at': ann.get('created_at'),
        'status': display_status
    }

async def get_active_announcements(target_agent_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """활성 공지 목록 조회"""
    supabase = get_db()
    
    query = supabase.table('announcements').select(
        'announcement_id, title, content, priority, target_agents, '
        'status, created_at, expires_at'
    ).eq('status', 'active')
    
    # 만료 시간 확인
    now = datetime.now().isoformat()
    query = query.or_(f'expires_at.is.null,expires_at.gt.{now}')
    
    response = query.order('created_at', desc=True).execute()
    
    if not response.data:
        return []
    
    announcements = response.data
    
    # 타겟 에이전트 필터링
    if target_agent_id:
        filtered = []
        for ann in announcements:
            target_agents = ann.get('target_agents')
            # target_agents가 None이거나 빈 리스트면 전체 대상
            if not target_agents or len(target_agents) == 0 or target_agent_id in target_agents:
                filtered.append(ann)
        return filtered
    
    return announcements

async def get_announcements() -> List[Dict[str, Any]]:
    """모든 공지 목록 조회 (대상 수, 수신 수 포함)"""
    supabase = get_db()
    
    # 공지 목록 조회
    response = supabase.table('announcements').select(
        'announcement_id, title, content, priority, target_agents, '
        'status, created_at, expires_at'
    ).order('created_at', desc=True).execute()
    
    if not response.data:
        return []
    
    announcements = response.data
    
    # 전체 에이전트 수 조회 (대상 계산용)
    from database.pc_db import get_all_pcs
    all_pcs = await get_all_pcs()
    total_agents_count = len(all_pcs)
    
    # 각 공지에 대해 수신 기록 수 조회 및 통계 계산
    enriched_announcements = []
    for ann in announcements:
        announcement_id = ann['announcement_id']
        
        # 수신 기록 수 조회
        receipts_response = supabase.table('announcement_receipts').select(
            'receipt_id'
        ).eq('announcement_id', announcement_id).execute()
        
        received_count = len(receipts_response.data) if receipts_response.data else 0
        
        # 대상 수 계산
        target_agents = ann.get('target_agents')
        if target_agents is None or (isinstance(target_agents, list) and len(target_agents) == 0):
            # 전체 대상
            target_count = total_agents_count
        else:
            # 특정 에이전트 대상
            target_count = len(target_agents) if isinstance(target_agents, list) else 0
        
        # 상태 변환 (active -> sent, expired -> expired)
        status = ann.get('status', 'active')
        display_status = 'sent' if status == 'active' else 'expired'
        
        # 발송 시간 (created_at 사용)
        sent_at = ann.get('created_at')
        
        # 공지 정보에 통계 추가
        enriched_ann = {
            **ann,
            'target_count': target_count,
            'received_count': received_count,
            'sent_at': sent_at,
            'status': display_status
        }
        
        enriched_announcements.append(enriched_ann)
    
    return enriched_announcements

async def expire_announcement(announcement_id: str) -> bool:
    """공지 만료 처리"""
    supabase = get_db()
    
    response = supabase.table('announcements').update({
        'status': 'expired'
    }).eq('announcement_id', announcement_id).eq('status', 'active').execute()
    
    return len(response.data) > 0 if response.data else False

async def record_announcement_receipt(
    announcement_id: str,
    agent_id: str
) -> bool:
    """공지 수신 기록 (멱등성 보장)"""
    supabase = get_db()
    
    # 중복 체크 (멱등성 보장)
    existing = supabase.table('announcement_receipts').select('receipt_id').eq(
        'announcement_id', announcement_id
    ).eq('agent_id', agent_id).execute()
    
    if existing.data and len(existing.data) > 0:
        # 이미 수신 기록이 있으면 성공으로 반환 (멱등성)
        print(f"[공지] 중복 ACK 무시: announcement_id={announcement_id}, agent_id={agent_id}")
        return True
    
    # 새 수신 기록 저장
    receipt_id = str(uuid.uuid4())
    response = supabase.table('announcement_receipts').insert({
        'receipt_id': receipt_id,
        'announcement_id': announcement_id,
        'agent_id': agent_id,
        'received_at': datetime.now().isoformat()
    }).execute()
    
    return len(response.data) > 0 if response.data else False

async def get_announcement_receipts(announcement_id: str) -> List[Dict[str, Any]]:
    """공지 수신 기록 조회"""
    supabase = get_db()
    
    response = supabase.table('announcement_receipts').select(
        'receipt_id, announcement_id, agent_id, received_at'
    ).eq('announcement_id', announcement_id).order('received_at', desc=True).execute()
    
    return response.data if response.data else []

