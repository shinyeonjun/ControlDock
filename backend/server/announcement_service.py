"""
공지 서비스 모듈
"""
from typing import Optional, Dict, Any, List
from database.announcement_db import (
    create_announcement,
    get_announcement,
    get_active_announcements,
    get_announcements,
    expire_announcement,
    record_announcement_receipt,
    get_announcement_receipts
)

class AnnouncementService:
    """공지 서비스"""
    
    @staticmethod
    async def create_announcement(
        title: str,
        content: str,
        priority: str = 'normal',
        target_agents: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """공지 생성"""
        try:
            announcement_id = await create_announcement(
                title=title,
                content=content,
                priority=priority,
                target_agents=target_agents
            )
            
            return {
                'success': True,
                'announcement_id': announcement_id,
                'message': '공지가 생성되었습니다'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    async def get_announcement(announcement_id: str) -> Optional[Dict[str, Any]]:
        """공지 조회"""
        return await get_announcement(announcement_id)
    
    @staticmethod
    async def get_active_announcements(target_agent_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """활성 공지 목록 조회"""
        return await get_active_announcements(target_agent_id)
    
    @staticmethod
    async def get_announcements() -> List[Dict[str, Any]]:
        """모든 공지 목록 조회"""
        return await get_announcements()
    
    @staticmethod
    async def expire_announcement(announcement_id: str) -> bool:
        """공지 만료 처리"""
        return await expire_announcement(announcement_id)
    
    @staticmethod
    async def record_receipt(announcement_id: str, agent_id: str) -> bool:
        """공지 수신 기록"""
        return await record_announcement_receipt(announcement_id, agent_id)
    
    @staticmethod
    async def get_receipts(announcement_id: str) -> List[Dict[str, Any]]:
        """공지 수신 기록 조회"""
        return await get_announcement_receipts(announcement_id)

