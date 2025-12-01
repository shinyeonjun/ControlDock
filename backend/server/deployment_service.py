"""
배포 서비스 모듈
"""
from typing import Optional, Dict, Any, List
from database.deployment_db import (
    create_deployment,
    get_deployment,
    get_deployments,
    get_pending_task,
    assign_task,
    start_task,
    complete_task,
    pause_deployment,
    resume_deployment,
    get_deployment_results,
    get_task_result
)

class DeploymentService:
    """배포 서비스"""
    
    @staticmethod
    async def create_deployment(
        name: str,
        command: str,
        target_agents: List[str],
        timeout: int = 300,
        admin_required: bool = False
    ) -> Dict[str, Any]:
        """배포 생성"""
        try:
            deployment_id = await create_deployment(
                name=name,
                command=command,
                target_agents=target_agents,
                timeout=timeout,
                admin_required=admin_required
            )
            
            return {
                'success': True,
                'deployment_id': deployment_id,
                'message': '배포가 생성되었습니다'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    async def get_deployment(deployment_id: str) -> Optional[Dict[str, Any]]:
        """배포 조회"""
        return await get_deployment(deployment_id)
    
    @staticmethod
    async def get_deployments() -> List[Dict[str, Any]]:
        """배포 목록 조회"""
        return await get_deployments()
    
    @staticmethod
    async def poll_task(agent_id: str) -> Optional[Dict[str, Any]]:
        """에이전트의 대기 중인 작업 조회"""
        try:
            print(f"[DeploymentService] 작업 폴링 시작: agent_id={agent_id}")
            task = await get_pending_task(agent_id)
            
            if not task:
                print(f"[DeploymentService] 대기 중인 작업 없음: agent_id={agent_id}")
                return None
            
            print(f"[DeploymentService] 작업 발견: task_id={task.get('task_id')}, deployment_id={task.get('deployment_id')}")
            
            # 작업 할당 및 시작
            task_id = task['task_id']
            print(f"[DeploymentService] 작업 할당 시작: task_id={task_id}")
            await assign_task(task_id)
            print(f"[DeploymentService] 작업 시작: task_id={task_id}")
            await start_task(task_id)
            
            # 최신 작업 정보 조회
            updated_task = await get_task_result(task_id)
            
            if not updated_task:
                print(f"[DeploymentService] 작업 정보 조회 실패: task_id={task_id}")
                return None
            
            print(f"[DeploymentService] 작업 정보 조회 성공: task_id={task_id}, command={updated_task.get('command')}")
            
            return {
                'task_id': updated_task['task_id'],
                'deployment_id': updated_task['deployment_id'],
                'command': updated_task['command'],
                'timeout': updated_task.get('timeout', 300),
                'admin_required': updated_task.get('admin_required', False)
            }
        except Exception as e:
            print(f"[DeploymentService] 작업 폴링 오류: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    @staticmethod
    async def submit_result(
        agent_id: str,
        task_id: str,
        status: str,
        exit_code: int,
        log_summary: str
    ) -> bool:
        """작업 결과 제출"""
        try:
            success = await complete_task(
                task_id=task_id,
                status=status,
                exit_code=exit_code,
                log_summary=log_summary
            )
            return success
        except Exception as e:
            print(f"[DeploymentService] 결과 제출 오류: {e}")
            return False
    
    @staticmethod
    async def pause_deployment(deployment_id: str) -> bool:
        """배포 일시중지"""
        return await pause_deployment(deployment_id)
    
    @staticmethod
    async def resume_deployment(deployment_id: str) -> bool:
        """배포 재개"""
        return await resume_deployment(deployment_id)
    
    @staticmethod
    async def get_deployment_results(deployment_id: str) -> List[Dict[str, Any]]:
        """배포 결과 조회"""
        return await get_deployment_results(deployment_id)
    
    @staticmethod
    async def get_task_result(task_id: str) -> Optional[Dict[str, Any]]:
        """작업 결과 조회"""
        return await get_task_result(task_id)

