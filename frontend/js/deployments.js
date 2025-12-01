// OpsHub - 배포 관리 JavaScript

let deploymentsData = [];

// 배포 목록 로드
async function loadDeployments() {
    try {
        const deployments = await apiRequest('/deployments');
        deploymentsData = deployments || [];
        updateDeploymentsTable(deploymentsData);
        updateDeploymentStats(deploymentsData);
    } catch (error) {
        console.error('배포 목록 로드 실패:', error);
        document.getElementById('deployments-table').innerHTML = 
            '<tr><td colspan="9" class="empty-state">데이터 로드를 실패했습니다</td></tr>';
    }
}

// 배포 테이블 업데이트
function updateDeploymentsTable(deployments) {
    const tbody = document.getElementById('deployments-table');
    
    if (!deployments || deployments.length === 0) {
        tbody.innerHTML = '<tr><td colspan="9" class="empty-state">배포가 없습니다</td></tr>';
        return;
    }

    tbody.innerHTML = deployments.map(deployment => {
        const progress = deployment.total_count > 0 
            ? Math.round((deployment.completed_count / deployment.total_count) * 100) 
            : 0;

        const deploymentId = deployment.deployment_id || deployment.task_id || '-';
        
        return `
        <tr>
            <td><code>${deploymentId.substring(0, 8)}...</code></td>
            <td>${deployment.name || '-'}</td>
            <td>${deployment.type || '-'}</td>
            <td>${deployment.total_count || 0}</td>
            <td>
                <span class="status-badge ${deployment.status === 'completed' ? 'completed' : deployment.status === 'running' ? 'running' : deployment.status === 'paused' ? 'paused' : 'pending'}">
                    ${deployment.status === 'completed' ? '완료' : 
                      deployment.status === 'running' ? '실행 중' : 
                      deployment.status === 'paused' ? '일시중지' : 
                      '대기'}
                </span>
            </td>
            <td>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: ${progress}%"></div>
                </div>
                <div class="progress-text">${progress}% (${deployment.completed_count || 0}/${deployment.total_count || 0})</div>
            </td>
            <td>
                <span class="success-count">${deployment.success_count || 0}</span> / 
                <span class="failed-count">${deployment.failed_count || 0}</span>
            </td>
            <td>${formatDate(deployment.created_at)}</td>
            <td>
                <div class="action-buttons">
                    <button class="action-btn primary" onclick="viewDeploymentDetails('${deploymentId}')">상세</button>
                    ${deployment.status === 'running' ? 
                        `<button class="action-btn" onclick="pauseDeployment('${deploymentId}')">일시중지</button>` : 
                        deployment.status === 'paused' ? 
                        `<button class="action-btn" onclick="resumeDeployment('${deploymentId}')">재개</button>` : 
                        ''}
                </div>
            </td>
        </tr>
    `;
    }).join('');
}

// 배포 통계 업데이트
function updateDeploymentStats(deployments) {
    const running = deployments.filter(d => d.status === 'running').length;
    const success = deployments.filter(d => d.status === 'completed').reduce((sum, d) => sum + (d.success_count || 0), 0);
    const failed = deployments.filter(d => d.status === 'completed').reduce((sum, d) => sum + (d.failed_count || 0), 0);

    document.getElementById('running-deployments').textContent = running;
    document.getElementById('success-deployments-count').textContent = success;
    document.getElementById('failed-deployments-count').textContent = failed;
}

// 배포 생성
async function createDeployment(formData) {
    try {
        const response = await apiRequest('/deployments', {
            method: 'POST',
            body: JSON.stringify(formData)
        });

        showSuccess('배포가 성공적으로 생성되었습니다');
        closeModal('deployment-modal');
        document.getElementById('deployment-form').reset();
        loadDeployments();
        return response;
    } catch (error) {
        showError(`배포 생성 실패: ${error.message}`);
        throw error;
    }
}

// 배포 상세 보기
async function viewDeploymentDetails(deploymentId) {
    try {
        if (!deploymentId || deploymentId === 'undefined' || deploymentId === '-') {
            showError('배포 ID가 유효하지 않습니다.');
            return;
        }
        
        const deployment = await apiRequest(`/deployments/${deploymentId}`);
        const results = await apiRequest(`/deployments/${deploymentId}/results`);
        
        // 상세 정보 표시
        const displayDeploymentId = deployment.deployment_id || deployment.task_id || deploymentId || '-';
        document.getElementById('detail-task-id').textContent = displayDeploymentId;
        
        // 배포 이름 표시 (있는 경우)
        const detailNameEl = document.getElementById('detail-name');
        if (detailNameEl) {
            detailNameEl.textContent = deployment.name || '-';
        }
        
        // 상태 표시
        const statusBadge = deployment.status === 'completed' ? 'completed' : 
                           deployment.status === 'running' ? 'running' : 
                           deployment.status === 'paused' ? 'paused' : 
                           deployment.status === 'failed' ? 'failed' : 'pending';
        document.getElementById('detail-status').innerHTML = `
            <span class="status-badge ${statusBadge}">
                ${deployment.status === 'completed' ? '완료' : 
                  deployment.status === 'running' ? '실행 중' : 
                  deployment.status === 'paused' ? '일시중지' : 
                  deployment.status === 'failed' ? '실패' : '대기'}
            </span>
        `;
        
        // 진행률 계산 및 표시
        const totalCount = deployment.total_count || 0;
        const completedCount = deployment.completed_count || 0;
        const progress = totalCount > 0 
            ? Math.round((completedCount / totalCount) * 100) 
            : 0;
        
        // 진행률 텍스트
        const progressText = `${progress}% (${completedCount}/${totalCount})`;
        const progressEl = document.getElementById('detail-progress');
        if (progressEl) {
            progressEl.innerHTML = `
                <div class="progress-bar" style="margin-bottom: 5px;">
                    <div class="progress-fill" style="width: ${progress}%; background-color: ${progress === 100 ? '#4CAF50' : '#2196F3'};"></div>
                </div>
                <div class="progress-text">${progressText}</div>
            `;
        }
        
        // 성공/실패 표시
        const successCount = deployment.success_count || 0;
        const failedCount = deployment.failed_count || 0;
        const successFailEl = document.getElementById('detail-success-fail');
        if (successFailEl) {
            successFailEl.innerHTML = `
                <span class="success-count" style="color: #4CAF50; font-weight: bold;">성공: ${successCount}</span> / 
                <span class="failed-count" style="color: #F44336; font-weight: bold;">실패: ${failedCount}</span>
            `;
        }
        
        // 명령어 표시 (있는 경우)
        const detailCommandEl = document.getElementById('detail-command');
        const detailCommandContainer = document.getElementById('detail-command-container');
        if (detailCommandEl && deployment.command) {
            detailCommandEl.textContent = deployment.command;
            if (detailCommandContainer) {
                detailCommandContainer.style.display = 'block';
            }
        } else if (detailCommandContainer) {
            detailCommandContainer.style.display = 'none';
        }

        // 배포 상태에 따라 버튼 표시/숨김
        const pauseBtn = document.getElementById('pause-deployment');
        const resumeBtn = document.getElementById('resume-deployment');
        
        if (deployment.status === 'completed' || deployment.status === 'failed') {
            // 완료된 배포는 버튼 숨김
            if (pauseBtn) pauseBtn.style.display = 'none';
            if (resumeBtn) resumeBtn.style.display = 'none';
        } else if (deployment.status === 'running') {
            // 실행 중인 배포는 일시중지 버튼만 표시
            if (pauseBtn) pauseBtn.style.display = 'inline-block';
            if (resumeBtn) resumeBtn.style.display = 'none';
        } else if (deployment.status === 'paused') {
            // 일시중지된 배포는 재개 버튼만 표시
            if (pauseBtn) pauseBtn.style.display = 'none';
            if (resumeBtn) resumeBtn.style.display = 'inline-block';
        } else {
            // 기타 상태는 모두 숨김
            if (pauseBtn) pauseBtn.style.display = 'none';
            if (resumeBtn) resumeBtn.style.display = 'none';
        }

        // 결과 테이블 업데이트
        updateResultsTable(results);

        openModal('deployment-detail-modal');
    } catch (error) {
        showError(`배포 상세 정보 로드 실패: ${error.message}`);
    }
}

// 결과 테이블 업데이트
function updateResultsTable(results) {
    const tbody = document.getElementById('deployment-results-table');
    
    if (!results || results.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="empty-state">결과가 없습니다</td></tr>';
        return;
    }

    tbody.innerHTML = results.map(result => {
        // request_id 또는 task_id 사용 (둘 다 있을 수 있음)
        const logId = result.request_id || result.task_id;
        
        return `
        <tr>
            <td>${result.hostname || result.host_id || '-'}</td>
            <td>
                <span class="status-badge ${result.status === 'success' || result.status === 'completed' ? 'success' : 'failed'}">
                    ${result.status === 'success' || result.status === 'completed' ? '성공' : '실패'}
                </span>
            </td>
            <td>${result.exit_code !== undefined && result.exit_code !== null ? result.exit_code : '-'}</td>
            <td>${result.duration ? `${result.duration}초` : '-'}</td>
            <td>${result.log_summary ? result.log_summary.substring(0, 100) + '...' : '-'}</td>
            <td>
                ${logId && logId !== 'undefined' ? 
                    `<button class="action-btn" onclick="viewLog('${logId}')">로그 보기</button>` : 
                    '<span>-</span>'}
            </td>
        </tr>
    `;
    }).join('');
}

// 로그 보기
async function viewLog(requestId) {
    try {
        if (!requestId || requestId === 'undefined' || requestId === '-') {
            showError('유효하지 않은 작업 ID입니다.');
            return;
        }
        
        const log = await apiRequest(`/deployments/results/${requestId}/log`);
        document.getElementById('log-content').textContent = log.content || '로그가 없습니다';
        document.getElementById('log-detail-section').style.display = 'block';
    } catch (error) {
        showError(`로그 로드 실패: ${error.message}`);
    }
}

// 배포 일시중지
async function pauseDeployment(deploymentId) {
    try {
        if (!deploymentId || deploymentId === 'undefined' || deploymentId === '-') {
            showError('배포 ID가 유효하지 않습니다.');
            return;
        }
        await apiRequest(`/deployments/${deploymentId}/pause`, {
            method: 'POST'
        });
        showSuccess('배포가 일시중지되었습니다');
        loadDeployments();
    } catch (error) {
        showError(`일시중지 실패: ${error.message}`);
    }
}

// 배포 재개
async function resumeDeployment(deploymentId) {
    try {
        if (!deploymentId || deploymentId === 'undefined' || deploymentId === '-') {
            showError('배포 ID가 유효하지 않습니다.');
            return;
        }
        await apiRequest(`/deployments/${deploymentId}/resume`, {
            method: 'POST'
        });
        showSuccess('배포가 재개되었습니다');
        loadDeployments();
    } catch (error) {
        showError(`재개 실패: ${error.message}`);
    }
}

// 에이전트 목록 로드 (배포 생성 시)
async function loadAgentsForSelection() {
    try {
        const agents = await apiRequest('/agents');
        const selector = document.getElementById('agent-selector');
        if (!agents || agents.length === 0) {
            selector.innerHTML = '<p class="empty-state">등록된 에이전트가 없습니다</p>';
            return;
        }

        selector.innerHTML = agents.map(agent => `
            <label>
                <input type="checkbox" name="selected-agents" value="${agent.host_id}">
                ${agent.hostname} (${agent.host_id}) - ${agent.status === 'online' ? '온라인' : '오프라인'}
            </label>
        `).join('');
    } catch (error) {
        console.error('에이전트 목록 로드 실패:', error);
    }
}

// 페이지 로드 시 실행
document.addEventListener('DOMContentLoaded', () => {
    // 배포 목록 로드
    loadDeployments();

    // 5초마다 갱신
    setInterval(loadDeployments, 5000);

    // 새 배포 버튼
    document.getElementById('new-deployment-btn').addEventListener('click', () => {
        loadAgentsForSelection();
        openModal('deployment-modal');
    });

    // 배포 모달 닫기
    document.getElementById('close-deployment-modal').addEventListener('click', () => {
        closeModal('deployment-modal');
    });

    document.getElementById('cancel-deployment').addEventListener('click', () => {
        closeModal('deployment-modal');
    });

    // 배포 상세 모달 닫기
    document.getElementById('close-detail-modal').addEventListener('click', () => {
        closeModal('deployment-detail-modal');
    });

    document.getElementById('close-detail').addEventListener('click', () => {
        closeModal('deployment-detail-modal');
    });

    // 배포 생성 제출
    document.getElementById('submit-deployment').addEventListener('click', async () => {
        const formData = {
            name: document.getElementById('deployment-name').value,
            type: document.getElementById('deployment-type').value,
            command: document.getElementById('deployment-command').value,
            timeout: parseInt(document.getElementById('deployment-timeout').value),
            admin: document.getElementById('deployment-admin').checked,
            target_type: document.getElementById('target-type').value,
            schedule_type: document.getElementById('schedule-type').value
        };

        // 대상 선택
        if (formData.target_type === 'selected') {
            const selected = Array.from(document.querySelectorAll('input[name="selected-agents"]:checked'))
                .map(cb => cb.value);
            formData.target_agents = selected;
            
            if (!formData.target_agents || formData.target_agents.length === 0) {
                showError('최소 하나 이상의 에이전트를 선택해주세요.');
                return;
            }
        } else if (formData.target_type === 'all') {
            // 전체 에이전트 선택 - 서버에서 처리하도록 target_agents는 보내지 않음
            // 서버에서 모든 에이전트를 가져와서 처리
            formData.target_agents = [];  // 빈 배열로 보내면 서버에서 전체 에이전트 처리
        } else if (formData.target_type === 'tag') {
            formData.target_tag = document.getElementById('target-tag').value;
            showError('태그 기반 배포는 아직 지원하지 않습니다. 에이전트를 직접 선택해주세요.');
            return;
        } else {
            showError('대상 선택 방식을 선택해주세요.');
            return;
        }

        // 일정 설정
        if (formData.schedule_type === 'scheduled') {
            formData.schedule_time = document.getElementById('schedule-time').value;
        }

        if (!formData.name || !formData.command) {
            showError('작업명과 명령을 입력하세요');
            return;
        }

        // admin 필드를 admin_required로 변환 (서버 호환성)
        if (formData.admin !== undefined) {
            formData.admin_required = formData.admin;
            delete formData.admin;
        }

        console.log('배포 생성 요청 데이터:', formData);

        try {
            await createDeployment(formData);
        } catch (error) {
            // 에러는 createDeployment에서 이미 처리됨
        }
    });

    // 대상 선택 방식 변경
    document.getElementById('target-type').addEventListener('change', (e) => {
        const agentsGroup = document.getElementById('target-agents-group');
        const tagGroup = document.getElementById('target-tag-group');
        
        agentsGroup.style.display = 'none';
        tagGroup.style.display = 'none';
        
        if (e.target.value === 'selected') {
            agentsGroup.style.display = 'block';
            loadAgentsForSelection();
        } else if (e.target.value === 'tag') {
            tagGroup.style.display = 'block';
        }
    });

    // 일정 선택 방식 변경
    document.getElementById('schedule-type').addEventListener('change', (e) => {
        const timeGroup = document.getElementById('schedule-time-group');
        timeGroup.style.display = e.target.value === 'scheduled' ? 'block' : 'none';
    });

    // 상세 모달 닫기
    document.getElementById('close-detail-modal').addEventListener('click', () => {
        closeModal('deployment-detail-modal');
    });

    document.getElementById('close-detail').addEventListener('click', () => {
        closeModal('deployment-detail-modal');
    });

    // 일시중지/재개 버튼
    document.getElementById('pause-deployment')?.addEventListener('click', () => {
        const taskId = document.getElementById('detail-task-id').textContent;
        pauseDeployment(taskId);
    });

    document.getElementById('resume-deployment')?.addEventListener('click', () => {
        const taskId = document.getElementById('detail-task-id').textContent;
        resumeDeployment(taskId);
    });
});
