// OpsHub - 에이전트 관리 JavaScript

let agentsData = [];
let registrationRequestsData = [];

// 등록 요청 목록 로드
async function loadRegistrationRequests() {
    try {
        console.log('등록 요청 목록 로드 시작...');
        const requests = await apiRequest('/registration-requests');
        console.log('등록 요청 목록 응답:', requests);
        
        registrationRequestsData = requests || [];
        console.log(`등록 요청 데이터: 총 ${registrationRequestsData.length}개`);
        
        // pending 상태만 필터링
        const pendingRequests = registrationRequestsData.filter(r => r.status === 'pending');
        console.log(`대기 중인 등록 요청: ${pendingRequests.length}개`);
        
        if (pendingRequests.length > 0) {
            console.log('등록 요청 카드 표시');
            document.getElementById('registration-requests-card').style.display = 'block';
            document.getElementById('pending-requests-count').textContent = pendingRequests.length;
            updateRegistrationRequestsTable(pendingRequests);
        } else {
            console.log('등록 요청이 없어서 카드 숨김');
            document.getElementById('registration-requests-card').style.display = 'none';
        }
    } catch (error) {
        console.error('등록 요청 목록 로드 실패:', error);
    }
}

// 등록 요청 테이블 업데이트
function updateRegistrationRequestsTable(requests) {
    const tbody = document.getElementById('registration-requests-table');
    
    if (!requests || requests.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="empty-state">등록 요청이 없습니다</td></tr>';
        return;
    }
    
    tbody.innerHTML = requests.map(request => `
        <tr>
            <td>${request.hostname || '-'}</td>
            <td>${request.os || '-'}</td>
            <td>${request.agent_version || '-'}</td>
            <td>${formatRelativeTime(request.created_at)}</td>
            <td>
                <span class="status-badge pending">
                    대기 중
                </span>
            </td>
            <td>
                <div class="action-buttons">
                    <button class="action-btn primary" onclick="approveRegistration('${request.request_id}')">승인</button>
                    <button class="action-btn" onclick="rejectRegistration('${request.request_id}')">거부</button>
                </div>
            </td>
        </tr>
    `).join('');
}

// 등록 요청 승인
async function approveRegistration(requestId) {
    if (!confirm('이 PC 등록 요청을 승인하시겠습니까?')) {
        return;
    }
    
    try {
        const response = await apiRequest(`/registration-requests/${requestId}/approve`, {
            method: 'POST'
        });
        
        if (response && response.success) {
            showSuccess('등록이 승인되었습니다');
            loadRegistrationRequests();
            loadAgents(); // 에이전트 목록 새로고침
        } else {
            showError('등록 승인 실패');
        }
    } catch (error) {
        showError(`등록 승인 실패: ${error.message}`);
    }
}

// 등록 요청 거부
async function rejectRegistration(requestId) {
    if (!confirm('이 PC 등록 요청을 거부하시겠습니까?')) {
        return;
    }
    
    try {
        // TODO: 거부 API 구현
        showError('거부 기능은 아직 구현되지 않았습니다');
    } catch (error) {
        showError(`등록 거부 실패: ${error.message}`);
    }
}

// 에이전트 목록 로드
async function loadAgents() {
    try {
        // 등록 완료된 요청들을 에이전트로 표시
        const completedRequests = registrationRequestsData.filter(r => r.status === 'completed');
        
        // 임시로 등록 완료된 요청을 에이전트로 변환
        agentsData = completedRequests.map(request => ({
            id: request.agent_id,
            host_id: request.agent_id,
            host_name: request.hostname,
            hostname: request.hostname,
            os: request.os,
            agent_version: request.agent_version,
            status: 'online',
            created_at: request.completed_at || request.created_at,
            last_check_in: new Date().toISOString()
        }));
        
        updateAgentsTable(agentsData);
        updateFilterStats(agentsData);
    } catch (error) {
        console.error('에이전트 목록 로드 실패:', error);
        document.getElementById('agents-table').innerHTML = 
            '<tr><td colspan="8" class="empty-state">데이터 로드를 실패했습니다</td></tr>';
    }
}

// 에이전트 테이블 업데이트
function updateAgentsTable(agents) {
    const tbody = document.getElementById('agents-table');
    
    if (!agents || agents.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="empty-state">등록된 에이전트가 없습니다</td></tr>';
        return;
    }

    tbody.innerHTML = agents.map(agent => `
        <tr>
            <td>
                <span class="status-badge ${agent.status === 'online' ? 'online' : 'offline'}">
                    <span class="status-dot ${agent.status === 'online' ? 'online' : 'offline'}"></span>
                    ${agent.status === 'online' ? '온라인' : '오프라인'}
                </span>
            </td>
            <td>${agent.host_name || agent.hostname || '-'}</td>
            <td><code>${agent.id || agent.host_id || '-'}</code></td>
            <td>${agent.os || '-'}</td>
            <td>${agent.agent_version || '-'}</td>
            <td>${formatRelativeTime(agent.last_check_in || agent.last_checkin)}</td>
            <td>${formatDate(agent.created_at || agent.registered_at)}</td>
            <td>
                <div class="action-buttons">
                    <button class="action-btn" onclick="viewAgentDetails('${agent.host_id}')">상세</button>
                </div>
            </td>
        </tr>
    `).join('');
}

// 필터 통계 업데이트
function updateFilterStats(agents) {
    const online = agents.filter(a => a.status === 'online').length;
    const offline = agents.filter(a => a.status === 'offline').length;
    const total = agents.length;

    document.getElementById('filtered-online').textContent = online;
    document.getElementById('filtered-offline').textContent = offline;
    document.getElementById('filtered-total').textContent = total;
}


// 에이전트 상세 보기
function viewAgentDetails(hostId) {
    const agent = agentsData.find(a => (a.id || a.host_id) === hostId);
    if (!agent) {
        showError('에이전트를 찾을 수 없습니다');
        return;
    }

    // 상세 정보를 모달이나 새 페이지에 표시
    const hostname = agent.host_name || agent.hostname;
    const lastCheckin = agent.last_check_in || agent.last_checkin;
    alert(`에이전트 상세 정보:\n호스트명: ${hostname}\nOS: ${agent.os}\n상태: ${agent.status}\n마지막 체크인: ${formatDate(lastCheckin)}`);
}

// 필터 적용
function applyFilters() {
    const statusFilter = document.getElementById('status-filter').value;
    const osFilter = document.getElementById('os-filter').value;
    const searchTerm = document.getElementById('agent-search').value.toLowerCase();

    let filtered = agentsData;

    // 상태 필터
    if (statusFilter !== 'all') {
        filtered = filtered.filter(a => a.status === statusFilter);
    }

    // OS 필터
    if (osFilter !== 'all') {
        filtered = filtered.filter(a => a.os && a.os.includes(osFilter));
    }

    // 검색 필터
    if (searchTerm) {
        filtered = filtered.filter(a => 
            ((a.host_name || a.hostname) && (a.host_name || a.hostname).toLowerCase().includes(searchTerm)) ||
            ((a.id || a.host_id) && (a.id || a.host_id).toString().toLowerCase().includes(searchTerm))
        );
    }

    updateAgentsTable(filtered);
    updateFilterStats(filtered);
}

// 페이지 로드 시 실행
document.addEventListener('DOMContentLoaded', () => {
    // 등록 요청 목록 로드
    loadRegistrationRequests();
    
    // 에이전트 목록 로드
    loadAgents();

    // 10초마다 등록 요청 갱신 (너무 자주 요청하지 않도록)
    setInterval(loadRegistrationRequests, 10000);
    
    // 30초마다 에이전트 목록 갱신
    setInterval(loadAgents, 30000);


    // 필터 이벤트
    document.getElementById('status-filter').addEventListener('change', applyFilters);
    document.getElementById('os-filter').addEventListener('change', applyFilters);
    document.getElementById('agent-search').addEventListener('input', applyFilters);

    // 전송 방식 선택에 따른 UI 변경
    document.getElementById('announcement-type')?.addEventListener('change', (e) => {
        const multicastGroup = document.getElementById('multicast-group-group');
        if (e.target.value === 'multicast') {
            multicastGroup.style.display = 'block';
        } else {
            multicastGroup.style.display = 'none';
        }
    });
});
