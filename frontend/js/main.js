// OpsHub - 공통 JavaScript

// API 기본 URL 설정
// config.js가 먼저 로드되어 API_BASE_URL이 정의되어 있으면 사용
// 없으면 SERVER_HOST 사용, 그것도 없으면 기본값 사용
let API_BASE_URL;
if (typeof API_BASE_URL_FROM_CONFIG !== 'undefined') {
    API_BASE_URL = API_BASE_URL_FROM_CONFIG;
} else if (typeof SERVER_HOST !== 'undefined') {
    API_BASE_URL = `http://${SERVER_HOST}:${SERVER_PORT || 8000}/api`;
} else {
    API_BASE_URL = 'http://172.24.194.92:8000/api';
}

// API 통신 헬퍼
async function apiRequest(endpoint, options = {}) {
    try {
        const response = await fetch(`${API_BASE_URL}${endpoint}`, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        });

        if (!response.ok) {
            throw new Error(`API Error: ${response.status} ${response.statusText}`);
        }

        return await response.json();
    } catch (error) {
        console.error('API Request Error:', error);
        throw error;
    }
}

// 날짜 포맷팅
function formatDate(dateString) {
    if (!dateString) return '-';
    const date = new Date(dateString);
    return date.toLocaleString('ko-KR', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
}

// 상대 시간 표시 (예: "5분 전")
function formatRelativeTime(dateString) {
    if (!dateString) return '-';
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHour = Math.floor(diffMin / 60);
    const diffDay = Math.floor(diffHour / 24);

    if (diffSec < 60) return '방금 전';
    if (diffMin < 60) return `${diffMin}분 전`;
    if (diffHour < 24) return `${diffHour}시간 전`;
    if (diffDay < 7) return `${diffDay}일 전`;
    return formatDate(dateString);
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
