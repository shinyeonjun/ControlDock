# OpsHub 데이터베이스 스키마 (최소 구성 버전)

## 개요
3개 핵심 테이블 + 2개 보완 테이블로 구성된 간소화된 스키마입니다.

## 테이블 구조

### 핵심 3개 테이블

#### 1. agents (에이전트/PC)
Windows PC 에이전트 정보를 저장합니다.

**주요 필드:**
- `id`: UUID (PK)
- `host_name`: 호스트명
- `os`: 운영체제
- `agent_version`: 에이전트 버전
- `agent_token_hash`: 에이전트 토큰 해시
- `last_check_in`: 마지막 하트비트 시간
- `poll_interval`: 폴링 주기 (초, 기본값 10)
- `status`: 계산된 상태 (online/offline) - GENERATED 컬럼
  - `poll_interval × 3` 기준으로 동적 계산
- `created_at`: 등록 시간

#### 2. deployments (배포/릴리스)
배포 작업을 저장합니다.

**주요 필드:**
- `id`: UUID (PK)
- `release_name`: 배포 이름
- `category`: 작업 유형 (powershell/command/install)
- `command`: 실행할 명령/스크립트
- `target_type`: 대상 선택 방식 (all/online/selected/tag)
- `target_number`: 대상 수
- `status`: 배포 상태 (pending/running/completed/failed)
- `progress`: 진행률 (%)
- `success_count`: 성공 수
- `failed_count`: 실패 수
- `started_at`: 시작 시간
- `completed_at`: 완료 시간
- `created_at`: 생성 시간

#### 3. notifications (공지)
공지 정보를 저장합니다.

**주요 필드:**
- `id`: UUID (PK)
- `title`: 공지 제목
- `content`: 공지 내용
- `transmission_method`: 전송 방식 (broadcast/multicast)
- `target_number`: 대상 수
- `reception_rate`: 수신률 (%)
- `status`: 공지 상태 (pending/sent)
- `sent_at`: 발송 시간
- `created_at`: 생성 시간

### 보완 테이블 2개

#### 4. deployment_results (배포 결과)
배포 실행 결과를 저장합니다. **Exactly-Once 보장 필수**

**주요 필드:**
- `request_id`: UUID (PK) - 클라이언트가 생성한 고유 ID
- `deployment_id`: UUID (FK) - 배포 작업 ID
- `agent_id`: UUID (FK) - 에이전트 ID
- `status`: 실행 결과 (success/failed/timeout)
- `exit_code`: 종료 코드
- `log_summary`: 로그 요약
- `log_storage_url`: 전체 로그 저장소 URL
- `started_at`: 시작 시간 (에이전트 시간)
- `completed_at`: 완료 시간 (에이전트 시간)
- `server_received_at`: 서버 수신 시각

**제약조건:**
- `UNIQUE(request_id)`: Exactly-Once 보장

#### 5. notification_receipts (공지 수신 기록)
공지 수신 여부를 추적합니다.

**주요 필드:**
- `id`: UUID (PK)
- `notification_id`: UUID (FK) - 공지 ID
- `agent_id`: UUID (FK) - 에이전트 ID
- `received_at`: 수신 시간

**제약조건:**
- `UNIQUE(notification_id, agent_id)`: 중복 수신 방지

## 핵심 기능 유지

✅ **Exactly-Once 보장**: `deployment_results.request_id`는 클라이언트 생성 필수

✅ **진행률 자동 계산**: 트리거로 `deployments.progress`, `success_count`, `failed_count` 자동 업데이트

✅ **수신률 자동 계산**: 트리거로 `notifications.reception_rate` 자동 업데이트

✅ **온라인 상태 계산**: `agents.status`는 GENERATED 컬럼으로 동적 계산

## 장단점 비교

### 장점
- ✅ 단순함: 3개 핵심 테이블로 이해하기 쉬움
- ✅ 빠른 시작: MVP에 적합
- ✅ 핵심 기능 유지: Exactly-Once, 자동 계산 등

### 단점 (vs 완전 버전)
- ❌ 재시도 추적 어려움: `attempt_no` 없음
- ❌ 배포 대상 정규화 부족: `target_agents` 배열 대신 선택 필요
- ❌ 아티팩트 관리 없음: 설치 파일 관리 기능 없음
- ❌ 공지 대상 정규화 부족: 멀티캐스트 그룹 관리 제한적
- ❌ 히스토리 추적 제한: 마지막 결과만 (전체 시도 기록 없음)

## 사용 예시

### 배포 생성 및 결과 기록
```sql
-- 1. 배포 생성
INSERT INTO deployments (release_name, category, command, target_type, target_number)
VALUES ('Notepad++ 설치', 'powershell', 'Install-Package NotepadPlusPlus', 'all', 10);

-- 2. 결과 기록 (Exactly-Once)
INSERT INTO deployment_results (
    request_id,  -- 클라이언트가 생성한 UUID
    deployment_id,
    agent_id,
    status,
    started_at,
    completed_at
)
VALUES (
    'client-uuid',
    'deployment-uuid',
    'agent-uuid',
    'success',
    '2024-01-01 10:00:00+00',
    '2024-01-01 10:05:00+00'
)
ON CONFLICT (request_id) DO NOTHING;
```

### 공지 발송 및 수신 기록
```sql
-- 1. 공지 생성
INSERT INTO notifications (title, content, target_number)
VALUES ('유지보수 공지', '오늘 20:00 유지보수 예정', 10);

-- 2. 수신 기록
INSERT INTO notification_receipts (notification_id, agent_id)
VALUES ('notification-uuid', 'agent-uuid')
ON CONFLICT (notification_id, agent_id) DO NOTHING;
```

## 선택 가이드

**최소 버전 선택 시:**
- MVP 프로토타입
- 소규모 환경 (100대 이하)
- 빠른 개발 우선

**완전 버전 선택 시:**
- 프로덕션 환경
- 대규모 환경 (1000대 이상)
- 재시도, 아티팩트 관리 등 고급 기능 필요


