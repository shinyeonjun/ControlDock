"""
배포 작업 DB 관리 모듈
"""
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime
from database.db import get_db

async def create_deployment(
    name: str,
    command: str,
    target_agents: List[str],
    timeout: int = 300,
    admin_required: bool = False
) -> str:
    """배포 작업 생성"""
    deployment_id = str(uuid.uuid4())
    supabase = get_db()
    
    response = supabase.table('deployments').insert({
        'deployment_id': deployment_id,
        'name': name,
        'command': command,
        'target_agents': target_agents,
        'timeout': timeout,
        'admin_required': admin_required,
        'status': 'running',  # 생성 시 즉시 running 상태로 시작 (다이어그램 기준)
        'created_at': datetime.now().isoformat(),
        'started_at': datetime.now().isoformat()  # 시작 시간 기록
    }).execute()
    
    if response.data:
        # 각 타겟 에이전트에 대해 작업 생성
        print(f"[배포 생성] 작업 생성 시작: deployment_id={deployment_id}, target_agents={len(target_agents)}개")
        for agent_id in target_agents:
            task_id = str(uuid.uuid4())
            try:
                task_response = supabase.table('tasks').insert({
                    'task_id': task_id,
                    'deployment_id': deployment_id,
                    'agent_id': agent_id,
                    'command': command,
                    'timeout': timeout,
                    'admin_required': admin_required,
                    'status': 'pending',  # pending, assigned, running, completed, failed, timeout
                    'created_at': datetime.now().isoformat()
                }).execute()
                print(f"[배포 생성] 작업 생성 성공: task_id={task_id}, agent_id={agent_id}")
            except Exception as e:
                print(f"[배포 생성] 작업 생성 실패: task_id={task_id}, agent_id={agent_id}, 오류={e}")
                import traceback
                traceback.print_exc()
        
        print(f"[배포 생성] 모든 작업 생성 완료: deployment_id={deployment_id}")
        return deployment_id
    raise Exception(f"배포 생성 실패: {response}")

async def get_deployment(deployment_id: str) -> Optional[Dict[str, Any]]:
    """배포 조회 (통계 정보 포함)"""
    supabase = get_db()
    
    response = supabase.table('deployments').select(
        'deployment_id, name, command, target_agents, timeout, admin_required, '
        'status, created_at, started_at, completed_at'
    ).eq('deployment_id', deployment_id).execute()
    
    if response.data and len(response.data) > 0:
        deployment = response.data[0]
        target_agents = deployment.get('target_agents', [])
        
        # 총 작업 수 (target_agents 수)
        total_count = len(target_agents) if isinstance(target_agents, list) else 0
        
        # 완료된 작업 수 (completed 또는 failed 상태)
        tasks_response = supabase.table('tasks').select('status').eq('deployment_id', deployment_id).execute()
        tasks = tasks_response.data if tasks_response.data else []
        
        completed_count = sum(1 for task in tasks if task['status'] in ['completed', 'failed'])
        success_count = sum(1 for task in tasks if task['status'] == 'completed')
        failed_count = sum(1 for task in tasks if task['status'] == 'failed')
        
        # 통계 정보 추가
        deployment['total_count'] = total_count
        deployment['completed_count'] = completed_count
        deployment['success_count'] = success_count
        deployment['failed_count'] = failed_count
        deployment['type'] = 'powershell'  # 기본값
        
        return deployment
    return None

async def get_deployments() -> List[Dict[str, Any]]:
    """배포 목록 조회 (통계 정보 포함)"""
    supabase = get_db()
    
    response = supabase.table('deployments').select(
        'deployment_id, name, command, target_agents, timeout, admin_required, '
        'status, created_at, started_at, completed_at'
    ).order('created_at', desc=True).execute()
    
    deployments = response.data if response.data else []
    
    # 각 배포에 통계 정보 추가
    for deployment in deployments:
        deployment_id = deployment['deployment_id']
        target_agents = deployment.get('target_agents', [])
        
        # 총 작업 수 (target_agents 수)
        total_count = len(target_agents) if isinstance(target_agents, list) else 0
        
        # 완료된 작업 수 (completed 또는 failed 상태)
        tasks_response = supabase.table('tasks').select('status').eq('deployment_id', deployment_id).execute()
        tasks = tasks_response.data if tasks_response.data else []
        
        completed_count = sum(1 for task in tasks if task['status'] in ['completed', 'failed'])
        success_count = sum(1 for task in tasks if task['status'] == 'completed')
        failed_count = sum(1 for task in tasks if task['status'] == 'failed')
        
        # 프론트엔드 호환성을 위해 task_id도 추가 (deployment_id 사용)
        deployment['task_id'] = deployment_id
        deployment['total_count'] = total_count
        deployment['completed_count'] = completed_count
        deployment['success_count'] = success_count
        deployment['failed_count'] = failed_count
        deployment['type'] = 'powershell'  # 기본값 (나중에 확장 가능)
    
    return deployments

async def get_pending_task(agent_id: str) -> Optional[Dict[str, Any]]:
    """에이전트의 대기 중인 작업 조회 (가장 오래된 것부터)"""
    supabase = get_db()
    
    print(f"[작업 조회] 대기 중인 작업 검색: agent_id={agent_id}")
    
    # 배포가 paused가 아니고, 작업 상태가 pending인 것만 조회
    response = supabase.table('tasks').select(
        'task_id, deployment_id, agent_id, command, timeout, admin_required, '
        'status, created_at'
    ).eq('agent_id', agent_id).eq('status', 'pending').order('created_at', desc=False).limit(1).execute()
    
    if response.data and len(response.data) > 0:
        task = response.data[0]
        print(f"[작업 조회] 대기 중인 작업 발견: task_id={task['task_id']}, deployment_id={task['deployment_id']}")
        
        # 배포 상태 확인 (running 상태만 작업 할당 가능)
        deployment = await get_deployment(task['deployment_id'])
        if deployment:
            print(f"[작업 조회] 배포 상태 확인: deployment_id={task['deployment_id']}, status={deployment['status']}")
            if deployment['status'] == 'running':
                print(f"[작업 조회] 작업 반환: task_id={task['task_id']}")
                return task
            else:
                print(f"[작업 조회] 배포가 running 상태가 아님: status={deployment['status']}")
        else:
            print(f"[작업 조회] 배포를 찾을 수 없음: deployment_id={task['deployment_id']}")
    else:
        print(f"[작업 조회] 대기 중인 작업 없음: agent_id={agent_id}")
    
    return None

async def assign_task(task_id: str) -> bool:
    """작업 할당 (pending -> assigned)"""
    supabase = get_db()
    
    response = supabase.table('tasks').update({
        'status': 'assigned',
        'assigned_at': datetime.now().isoformat()
    }).eq('task_id', task_id).eq('status', 'pending').execute()
    
    return len(response.data) > 0 if response.data else False

async def start_task(task_id: str) -> bool:
    """작업 시작 (assigned -> running)"""
    supabase = get_db()
    
    response = supabase.table('tasks').update({
        'status': 'running',
        'started_at': datetime.now().isoformat()
    }).eq('task_id', task_id).eq('status', 'assigned').execute()
    
    return len(response.data) > 0 if response.data else False

async def complete_task(
    task_id: str,
    status: str,  # 'completed', 'failed', 'timeout', 'success' (클라이언트에서 보낼 수 있음)
    exit_code: int,
    log_summary: str
) -> bool:
    """작업 완료"""
    supabase = get_db()
    
    # 클라이언트에서 'success'로 보낼 수 있으므로 'completed'로 변환
    if status == 'success':
        status = 'completed'
    
    response = supabase.table('tasks').update({
        'status': status,
        'exit_code': exit_code,
        'log_summary': log_summary,
        'completed_at': datetime.now().isoformat()
    }).eq('task_id', task_id).execute()
    
    if len(response.data) > 0 if response.data else False:
        # 배포 상태 업데이트 (모든 작업이 완료되었는지 확인)
        task = supabase.table('tasks').select('deployment_id').eq('task_id', task_id).execute()
        if task.data and len(task.data) > 0:
            deployment_id = task.data[0]['deployment_id']
            await _update_deployment_status(deployment_id)
            print(f"[배포 상태] 배포 상태 업데이트 완료: deployment_id={deployment_id}")
        
        return True
    return False

async def _update_deployment_status(deployment_id: str):
    """배포 상태 업데이트 (모든 작업 완료 여부 확인)"""
    supabase = get_db()
    
    # 배포의 모든 작업 조회
    tasks_response = supabase.table('tasks').select('status').eq('deployment_id', deployment_id).execute()
    
    if not tasks_response.data:
        print(f"[배포 상태] 작업이 없음: deployment_id={deployment_id}")
        return
    
    tasks = tasks_response.data
    total_tasks = len(tasks)
    completed_tasks = [task for task in tasks if task['status'] in ['completed', 'failed', 'timeout']]
    completed_count = len(completed_tasks)
    
    print(f"[배포 상태] 작업 상태 확인: deployment_id={deployment_id}, 전체={total_tasks}, 완료={completed_count}")
    
    all_completed = completed_count == total_tasks
    
    if all_completed:
        # 모든 작업 완료
        failed_count = sum(1 for task in tasks if task['status'] in ['failed', 'timeout'])
        deployment_status = 'failed' if failed_count > 0 else 'completed'
        
        print(f"[배포 상태] 배포 완료: deployment_id={deployment_id}, status={deployment_status}, 실패={failed_count}")
        
        supabase.table('deployments').update({
            'status': deployment_status,
            'completed_at': datetime.now().isoformat()
        }).eq('deployment_id', deployment_id).execute()

async def pause_deployment(deployment_id: str) -> bool:
    """배포 일시중지"""
    supabase = get_db()
    
    response = supabase.table('deployments').update({
        'status': 'paused'
    }).eq('deployment_id', deployment_id).eq('status', 'running').execute()
    
    return len(response.data) > 0 if response.data else False

async def resume_deployment(deployment_id: str) -> bool:
    """배포 재개"""
    supabase = get_db()
    
    response = supabase.table('deployments').update({
        'status': 'running'
    }).eq('deployment_id', deployment_id).eq('status', 'paused').execute()
    
    return len(response.data) > 0 if response.data else False

async def get_deployment_results(deployment_id: str) -> List[Dict[str, Any]]:
    """배포 결과 조회"""
    supabase = get_db()
    
    response = supabase.table('tasks').select(
        'task_id, agent_id, status, exit_code, log_summary, '
        'created_at, assigned_at, started_at, completed_at'
    ).eq('deployment_id', deployment_id).order('created_at', desc=True).execute()
    
    tasks = response.data if response.data else []
    
    # 각 작업에 호스트명 추가
    for task in tasks:
        agent_id = task.get('agent_id')
        if agent_id:
            # pc 테이블에서 호스트명 조회
            pc_response = supabase.table('pc').select('host_name').eq('id', agent_id).execute()
            if pc_response.data and len(pc_response.data) > 0:
                task['hostname'] = pc_response.data[0].get('host_name', '-')
            else:
                task['hostname'] = '-'
        else:
            task['hostname'] = '-'
        
        # request_id는 task_id와 동일 (프론트엔드 호환성)
        task['request_id'] = task.get('task_id')
        
        # 소요 시간 계산
        if task.get('started_at') and task.get('completed_at'):
            from datetime import datetime
            try:
                started = datetime.fromisoformat(task['started_at'].replace('Z', '+00:00'))
                completed = datetime.fromisoformat(task['completed_at'].replace('Z', '+00:00'))
                duration = (completed - started).total_seconds()
                task['duration'] = int(duration)
            except:
                task['duration'] = None
        else:
            task['duration'] = None
    
    return tasks

async def get_task_result(task_id: str) -> Optional[Dict[str, Any]]:
    """작업 결과 조회"""
    supabase = get_db()
    
    response = supabase.table('tasks').select(
        'task_id, deployment_id, agent_id, command, timeout, admin_required, status, exit_code, log_summary, '
        'created_at, assigned_at, started_at, completed_at'
    ).eq('task_id', task_id).execute()
    
    if response.data and len(response.data) > 0:
        return response.data[0]
    return None

