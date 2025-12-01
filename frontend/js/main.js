// OpsHub - 공통 JavaScript

// API 기본 URL 가져오기 (config.json에서 로드)
function getApiBaseUrl() {
    // config.json이 로드되었으면 사용, 아니면 재시도
    if (typeof API_BASE_URL_FROM_CONFIG !== 'undefined' && API_BASE_URL_FROM_CONFIG) {
        return API_BASE_URL_FROM_CONFIG;
    }
    
    // SERVER_HOST가 있으면 조합
    if (typeof SERVER_HOST !== 'undefined' && SERVER_HOST) {
        const port = typeof SERVER_PORT !== 'undefined' ? SERVER_PORT : 8000;
        return `http://${SERVER_HOST}:${port}/api`;
    }
    
    // 아직 로드되지 않았으면 기본값 (config.json이 로드될 때까지)
    console.warn('config.json이 아직 로드되지 않았습니다. 기본값을 사용합니다.');
    return null;
}

// API 통신 헬퍼
async function apiRequest(endpoint, options = {}) {
    // 설정이 로드될 때까지 대기 (최대 3초)
    let apiBaseUrl = getApiBaseUrl();
    let retries = 30; // 3초 동안 100ms마다 재시도
    
    while (!apiBaseUrl && retries > 0) {
        await new Promise(resolve => setTimeout(resolve, 100));
        apiBaseUrl = getApiBaseUrl();
        retries--;
    }
    
    if (!apiBaseUrl) {
        throw new Error('API 서버 설정을 가져올 수 없습니다. config.json을 확인하세요.');
    }
    
    try {
        const url = `${apiBaseUrl}${endpoint}`;
        console.log(`API 요청: ${url}`);
        
        const response = await fetch(url, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        });

        if (!response.ok) {
            throw new Error(`API Error: ${response.status} ${response.statusText}`);
        }

        const data = await response.json();
        console.log(`API 응답: ${endpoint}`, data);
        return data;
    } catch (error) {
        console.error('API Request Error:', error);
        throw error;
    }
}

// 날짜 포맷팅
function formatDate(dateString) {
    if (!dateString) return '-';
    try {
        const date = new Date(dateString);
        // 유효한 날짜인지 확인
        if (isNaN(date.getTime())) return '-';
        return date.toLocaleString('ko-KR', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false
        });
    } catch (e) {
        console.error('날짜 포맷팅 오류:', e, dateString);
        return '-';
    }
}

// 상대 시간 표시 (예: "5분 전")
function formatRelativeTime(dateString) {
    if (!dateString) return '-';
    try {
        const date = new Date(dateString);
        // 유효한 날짜인지 확인
        if (isNaN(date.getTime())) return '-';
        
        const now = new Date();
        const diffMs = now - date;
        
        // 미래 시간이면 현재 시간 표시
        if (diffMs < 0) return '방금 전';
        
        const diffSec = Math.floor(diffMs / 1000);
        const diffMin = Math.floor(diffSec / 60);
        const diffHour = Math.floor(diffMin / 60);
        const diffDay = Math.floor(diffHour / 24);

        if (diffSec < 60) return '방금 전';
        if (diffMin < 60) return `${diffMin}분 전`;
        if (diffHour < 24) return `${diffHour}시간 전`;
        if (diffDay < 7) return `${diffDay}일 전`;
        return formatDate(dateString);
    } catch (e) {
        console.error('상대 시간 포맷팅 오류:', e, dateString);
        return '-';
    }
}

// 모달 제어
function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.add('active');
    }
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.remove('active');
    }
}

// 모달 외부 클릭 시 닫기
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.modal').forEach(modal => {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.classList.remove('active');
            }
        });
    });
});

// 에러 메시지 표시
function showError(message) {
    alert(`오류: ${message}`);
}

// 성공 메시지 표시
function showSuccess(message) {
    alert(`성공: ${message}`);
}

// 로딩 상태 표시
function setLoading(element, isLoading) {
    if (isLoading) {
        element.innerHTML = '<tr><td colspan="999" class="empty-state">데이터 로딩 중...</td></tr>';
    }
}
