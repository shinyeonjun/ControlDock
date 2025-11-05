// OpsHub - 공지 관리 JavaScript

let announcementsData = [];

// 공지 목록 로드
async function loadAnnouncements() {
    try {
        const announcements = await apiRequest('/announcements');
        announcementsData = announcements || [];
        updateAnnouncementsTable(announcementsData);
        updateAnnouncementStats(announcementsData);
    } catch (error) {
        console.error('공지 목록 로드 실패:', error);
        document.getElementById('announcements-table').innerHTML = 
            '<tr><td colspan="8" class="empty-state">데이터 로드를 실패했습니다</td></tr>';
    }
}

// 공지 테이블 업데이트
function updateAnnouncementsTable(announcements) {
    const tbody = document.getElementById('announcements-table');
    
    if (!announcements || announcements.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="empty-state">발송된 공지가 없습니다</td></tr>';
        return;
    }

    tbody.innerHTML = announcements.map(announcement => {
        const receiptRate = announcement.target_count > 0
            ? Math.round((announcement.received_count / announcement.target_count) * 100)
            : 0;

        return `
        <tr>
            <td><code>${announcement.announcement_id || '-'}</code></td>
            <td>${announcement.title || '-'}</td>
            <td>
                <span class="status-badge ${announcement.type === 'broadcast' ? 'running' : 'success'}">
                    ${announcement.type === 'broadcast' ? '브로드캐스트' : '멀티캐스트'}
                </span>
            </td>
            <td>${announcement.target_count || 0}</td>
            <td>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: ${receiptRate}%"></div>
                </div>
                <div class="progress-text">${receiptRate}% (${announcement.received_count || 0}/${announcement.target_count || 0})</div>
            </td>
            <td>${formatDate(announcement.sent_at)}</td>
            <td>
                <span class="status-badge ${announcement.status === 'sent' ? 'success' : 'pending'}">
                    ${announcement.status === 'sent' ? '발송 완료' : '대기'}
                </span>
            </td>
            <td>
                <div class="action-buttons">
                    <button class="action-btn primary" onclick="viewAnnouncementDetails('${announcement.announcement_id}')">상세</button>
                </div>
            </td>
        </tr>
    `;
    }).join('');
}

// 공지 통계 업데이트
function updateAnnouncementStats(announcements) {
    const total = announcements.length;
    const success = announcements.reduce((sum, a) => sum + (a.received_count || 0), 0);

    document.getElementById('total-announcements').textContent = total;
    document.getElementById('success-announcements').textContent = success;
}

// 공지 발송
async function sendAnnouncement(formData) {
    try {
        const response = await apiRequest('/announcements', {
            method: 'POST',
            body: JSON.stringify(formData)
        });

        showSuccess('공지가 성공적으로 발송되었습니다');
        closeModal('announcement-modal');
        document.getElementById('announcement-form').reset();
        loadAnnouncements();
        return response;
    } catch (error) {
        showError(`공지 발송 실패: ${error.message}`);
        throw error;
    }
}

// 공지 상세 보기
async function viewAnnouncementDetails(announcementId) {
    try {
        const announcement = await apiRequest(`/announcements/${announcementId}`);
        
        // 상세 정보 표시
        document.getElementById('detail-announcement-title').textContent = announcement.title || '-';
        document.getElementById('detail-announcement-content').textContent = announcement.content || '-';
        document.getElementById('detail-announcement-type').textContent = 
            announcement.type === 'broadcast' ? '브로드캐스트' : '멀티캐스트';
        document.getElementById('detail-announcement-targets').textContent = announcement.target_count || 0;
        document.getElementById('detail-announcement-success').textContent = announcement.received_count || 0;
        document.getElementById('detail-announcement-failed').textContent = 
            (announcement.target_count || 0) - (announcement.received_count || 0);
        
        const lossRate = announcement.target_count > 0
            ? ((announcement.target_count - announcement.received_count) / announcement.target_count * 100).toFixed(2)
            : 0;
        document.getElementById('detail-announcement-loss').textContent = `${lossRate}%`;
        document.getElementById('detail-announcement-time').textContent = formatDate(announcement.sent_at);

        openModal('announcement-detail-modal');
    } catch (error) {
        showError(`공지 상세 정보 로드 실패: ${error.message}`);
    }
}

// 페이지 로드 시 실행
document.addEventListener('DOMContentLoaded', () => {
    // 공지 목록 로드
    loadAnnouncements();

    // 10초마다 갱신
    setInterval(loadAnnouncements, 10000);

    // 새 공지 버튼
    document.getElementById('new-announcement-btn').addEventListener('click', () => {
        openModal('announcement-modal');
    });

    // 공지 모달 닫기
    document.getElementById('close-announcement-modal').addEventListener('click', () => {
        closeModal('announcement-modal');
    });

    document.getElementById('cancel-announcement').addEventListener('click', () => {
        closeModal('announcement-modal');
    });

    // 공지 발송 제출
    document.getElementById('submit-announcement').addEventListener('click', async () => {
        const formData = {
            title: document.getElementById('announcement-title').value,
            content: document.getElementById('announcement-content').value,
            type: document.getElementById('announcement-type').value,
            priority: document.getElementById('announcement-priority').value,
            show_tray: document.getElementById('announcement-tray').checked,
            save_log: document.getElementById('announcement-log').checked
        };

        if (formData.type === 'multicast') {
            const groups = document.getElementById('multicast-group').value;
            if (!groups) {
                showError('멀티캐스트 그룹을 입력하세요');
                return;
            }
            formData.multicast_groups = groups.split(',').map(g => g.trim());
        }

        if (!formData.title || !formData.content) {
            showError('제목과 내용을 입력하세요');
            return;
        }

        try {
            await sendAnnouncement(formData);
        } catch (error) {
            // 에러는 sendAnnouncement에서 이미 처리됨
        }
    });

    // 전송 방식 선택에 따른 UI 변경
    document.getElementById('announcement-type').addEventListener('change', (e) => {
        const multicastGroup = document.getElementById('multicast-group-group');
        if (e.target.value === 'multicast') {
            multicastGroup.style.display = 'block';
        } else {
            multicastGroup.style.display = 'none';
        }
    });

    // 상세 모달 닫기
    document.getElementById('close-announcement-detail-modal').addEventListener('click', () => {
        closeModal('announcement-detail-modal');
    });

    document.getElementById('close-announcement-detail').addEventListener('click', () => {
        closeModal('announcement-detail-modal');
    });
});
