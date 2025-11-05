// OpsHub - 대시보드 JavaScript

// 대시보드 데이터 로드
async function loadDashboardData() {
    try {
        // 통계 데이터
        const stats = await apiRequest('/stats');
        updateStats(stats);

        // 최근 에이전트 활동
        const recentAgents = await apiRequest('/agents/recent');
        updateRecentAgents(recentAgents);

        // 최근 배포 결과
        const recentDeployments = await apiRequest('/deployments/recent');
        updateRecentDeployments(recentDeployments);

        // 시스템 상태
        const systemStatus = await apiRequest('/system/status');
        updateSystemStatus(systemStatus);
    } catch (error) {
        console.error('대시보드 데이터 로드 실패:', error);
    }
}

// 통계 업데이트
function updateStats(stats) {
    if (!stats) return;

    document.getElementById('total-agents').textContent = stats.totalAgents || 0;
    document.getElementById('online-agents').textContent = stats.onlineAgents || 0;
    document.getElementById('offline-agents').textContent = stats.offlineAgents || 0;
    document.getElementById('total-deployments').textContent = stats.totalDeployments || 0;
    document.getElementById('success-deployments').textContent = stats.successDeployments || 0;
    document.getElementById('failed-deployments').textContent = stats.failedDeployments || 0;
    document.getElementById('running-commands').textContent = stats.runningCommands || 0;
    document.getElementById('pending-commands').textContent = stats.pendingCommands || 0;
    document.getElementById('recent-announcements').textContent = stats.recentAnnouncements || 0;
}

// 최근 에이전트 활동 업데이트
function updateRecentAgents(agents) {
    const tbody = document.getElementById('recent-agents-table');
    if (!agents || agents.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="empty-state">최근 활동이 없습니다</td></tr>';
        return;
    }

    tbody.innerHTML = agents.slice(0, 5).map(agent => `
        <tr>
            <td>${agent.host_name || agent.hostname || '-'}</td>
            <td>
                <span class="status-badge ${agent.status === 'online' ? 'online' : 'offline'}">
                    <span class="status-dot ${agent.status === 'online' ? 'online' : 'offline'}"></span>
                    ${agent.status === 'online' ? '온라인' : '오프라인'}
                </span>
            </td>
            <td>${formatRelativeTime(agent.last_check_in || agent.lastCheckin)}</td>
            <td>${agent.os || '-'}</td>
        </tr>
    `).join('');
}

// 최근 배포 결과 업데이트
function updateRecentDeployments(deployments) {
    const tbody = document.getElementById('recent-deployments-table');
    if (!deployments || deployments.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="empty-state">최근 배포가 없습니다</td></tr>';
        return;
    }

    tbody.innerHTML = deployments.slice(0, 5).map(deployment => `
        <tr>
            <td>${deployment.name || deployment.task_id || '-'}</td>
            <td>
                <span class="status-badge ${deployment.status === 'completed' ? 'completed' : deployment.status === 'running' ? 'running' : 'failed'}">
                    ${deployment.status === 'completed' ? '완료' : deployment.status === 'running' ? '실행 중' : '실패'}
                </span>
            </td>
            <td>${deployment.success_count || 0}/${deployment.total_count || 0}</td>
            <td>${formatRelativeTime(deployment.completed_at || deployment.created_at)}</td>
        </tr>
    `).join('');
}

// 시스템 상태 업데이트
function updateSystemStatus(status) {
    if (!status) return;

    document.getElementById('tcp-connections').textContent = status.tcpConnections || 0;
    document.getElementById('udp-received').textContent = status.udpReceived || 0;
}

// 페이지 로드 시 실행
document.addEventListener('DOMContentLoaded', () => {
    loadDashboardData();
    
    // 5초마다 데이터 갱신
    // 15초마다 대시보드 데이터 갱신 (너무 자주 요청하지 않도록)
    setInterval(loadDashboardData, 15000);
});
