"""
데이터베이스 연결 모듈
Supabase 클라이언트 사용
"""
import os
from typing import Optional
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

# Supabase 클라이언트
_supabase: Optional[Client] = None

async def init_db():
    """Supabase 클라이언트 초기화"""
    global _supabase
    if _supabase is None:
        try:
            supabase_url = os.getenv('SUPABASE_URL')
            supabase_key = os.getenv('SUPABASE_KEY')
            
            if not supabase_url or not supabase_key:
                raise ValueError("SUPABASE_URL과 SUPABASE_KEY 환경 변수가 필요합니다.")
            
            _supabase = create_client(supabase_url, supabase_key)
            print(f"Supabase 클라이언트 초기화 완료: {supabase_url}")
        except Exception as e:
            print(f"Supabase 클라이언트 초기화 실패: {e}")
            raise
    return _supabase

async def close_db():
    """Supabase 클라이언트 종료"""
    global _supabase
    _supabase = None
    print("Supabase 클라이언트 종료")

def get_db() -> Client:
    """Supabase 클라이언트 가져오기"""
    global _supabase
    if _supabase is None:
        import os
        from supabase import create_client
        
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_KEY')
        
        if not supabase_url or not supabase_key:
            raise ValueError("SUPABASE_URL과 SUPABASE_KEY 환경 변수가 필요합니다.")
        
        _supabase = create_client(supabase_url, supabase_key)
    return _supabase

