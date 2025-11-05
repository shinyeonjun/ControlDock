# OpsHub 데이터베이스 스키마 (개선판)

## 개요
PostgreSQL 기반 데이터베이스 스키마로 설계되었습니다.

## ✅ 주요 개선 사항

### 치명도 높은 6가지 수정
1. **Exactly-Once 보장**: `request_id` 기본값 제거, 클라이언트 생성 필수
2. **중복 집계 방지**: `deployment_targets` 테이블로 마지막 결과만 집계
3. **타깃 선택 모델 개선**: `deployment_targets` 테이블로 정규화
4. **아티팩트 관리**: `artifacts` 테이블 추가
5. **agents.status 파생값**: 저장 대신 뷰로 계산
6. **로그 저장 전략**: 전체 로그는 오브젝트 스토리지, DB에는 URL만

### 개선 사항 8가지
1. **스케줄/유지보수 창**: maintenance_rule 필드 추가 (v2 확장용)
2. **토큰 보안**: 해시 저장 + 만료시간
3. **카운터 최적화**: `deployment_targets` 기반으로 계산
4. **인덱스 정교화**: trigram 인덱스, 복합 인덱스 추가
5. **파티션 전략**: 향후 확장용 (주석 참고)
6. **멀티캐스트 그룹**: `agent_groups`, `agent_group_members` 테이블 추가
7. **무결성 검증**: 시간 검증 CHECK 제약조건
8. **배포 상태 전이**: 트리거로 자동 타임스탬프 설정

### ✅ 필수 수정 5가지 (최신)
1. **온라인 판정 임계값 동적화**: `poll_interval × 3` 기준으로 동적 계산
2. **배포 상태 체크 엄격화**: `completed/failed` 상태 시 `completed_at IS NOT NULL` 필수
3. **결과 시간 신뢰원 분리**: `server_received_at`, `server_processed_at` 추가 (시계 오차 보정)
4. **인덱스 정교화**: `deployment_targets(task_id, status)`, `(task_id, host_id)` 복합 인덱스
5. **로그 저장 무결성**: `log_storage_url`과 `log_size_bytes` 동시 NULL/NOT NULL 체크

### ✅ 권장 개선 7가지 (최신)
1. **재시도 의미 정리**: `attempt_no`는 서버가 시도 지시할 때 증가
2. **공지 대상 모델 명확화**: `announcement_targets` 테이블 추가
3. **Artifacts 검색성**: `metadata` JSONB GIN 인덱스 추가
4. **토큰 수명 정책**: 기본 TTL 90일, 만료 시 재등록 플로우
5. **카운터 정확성**: 물질화 뷰 고려 (대규모 배포 시)
6. **파티셔닝 계획**: 월별/해시 파티션 예시 주석
7. **보안 트리비얼**: 토큰 로깅 마스킹, bootstrap_token 만료 삭제 배치

## 테이블 구조

### 1. agents (에이전트)
Windows PC 에이전트 정보를 저장합니다.

**주요 필드:**
- `host_id`: UUID (PK) - 고유 호스트 ID
- `hostname`: 호스트명
- `os`: 운영체제 정보
- `agent_version`: 에이전트 버전
- `bootstrap_token_hash`: 부트스트랩 토큰 해시 (평문 저장 안 함)
- `agent_token_hash`: 에이전트 토큰 해시 (평문 저장 안 함)
- `agent_token_expires_at`: 토큰 만료시간
- `last_checkin`: 마지막 하트비트 시간
- `poll_interval`: 폴링 주기 (초)
- `maintenance_window_start/end`: 유지보수 시간대 (v1)
- `maintenance_rule`: 유지보수 규칙 (cron/rrule, v2 확장용)
- `tags`: 태그 배열 (예: ['개발부', 'Windows11'])

**✅ 개선:**
- `status` 컬럼 제거 → `agents_with_status` 뷰로 계산
- 토큰 해시 저장 + 만료시간
- hostname LIKE 검색을 위한 trigram 인덱스

**인덱스:**
- last_checkin, hostname (trigram), tags (GIN)

### 2. agent_groups (에이전트 그룹) ✅ 신규
멀티캐스트 공지 그룹 관리를 위한 테이블입니다.

**주요 필드:**
- `group_name`: VARCHAR(255) (PK) - 그룹 이름
- `description`: 그룹 설명
- `created_at`: 생성 시간

### 3. agent_group_members (에이전트 그룹 멤버) ✅ 신규
에이전트와 그룹의 다대다 관계 테이블입니다.

**주요 필드:**
- `host_id`: UUID (FK) - 에이전트 ID
- `group_name`: VARCHAR(255) (FK) - 그룹 이름
- `joined_at`: 가입 시간

### 4. artifacts (아티팩트) ✅ 신규
설치 파일 및 스크립트 번들을 관리하는 테이블입니다.

**주요 필드:**
- `artifact_id`: UUID (PK)
- `name`: 아티팩트 이름
- `version`: 버전
- `size_bytes`: 파일 크기 (바이트)
- `sha256`: SHA-256 해시 (UNIQUE)
- `storage_url`: 오브젝트 스토리지 URL
- `metadata`: JSONB 메타데이터
- `created_at`: 생성 시간
- `created_by`: 업로드한 관리자

**인덱스:**
- name, sha256, created_at

### 5. deployments (배포 작업)
원격 명령 실행 작업을 저장합니다.

**주요 필드:**
- `task_id`: UUID (PK)
- `name`: 작업명
- `artifact_id`: UUID (FK) - 아티팩트 ID (선택적)
- `type`: powershell/command/install
- `command`: 실행할 명령/스크립트
- `timeout`: 타임아웃 (초)
- `admin_required`: 관리자 권한 필요 여부
- `target_type`: all/online/selected/tag/group
- `target_tag`: 태그 기준 선택
- `target_group`: 그룹 기준 선택 (agent_groups 참조)
- `schedule_type`: now/scheduled
- `status`: pending/running/paused/completed/failed
- `total_count`: 전체 대상 수 (deployment_targets 기준)
- `completed_count`: 완료된 수
- `success_count`: 성공 수
- `failed_count`: 실패 수
- `started_at`: 실행 시작 시간 (상태 전이 시 자동 설정)
- `completed_at`: 완료 시간 (상태 전이 시 자동 설정)

**✅ 개선:**
- `target_agents` 배열 제거 → `deployment_targets` 테이블로 정규화
- 배포 상태 전이 검증 (CHECK 제약조건)
- 아티팩트 FK 추가

**인덱스:**
- status, created_at, schedule_time, artifact_id

### 6. deployment_targets (배포 대상) ✅ 신규 - 치명도 높음
배포 대상 에이전트를 미리 기록하고, 마지막 결과만 참조하는 테이블입니다.

**주요 필드:**
- `target_id`: UUID (PK)
- `task_id`: UUID (FK) - 배포 작업 ID
- `host_id`: UUID (FK) - 에이전트 ID
- `status`: pending/running/completed/failed/skipped
- `last_result_id`: UUID (FK) - 마지막 결과 ID (deployment_results 참조)
- `attempt_no`: 재시도 횟수
- `assigned_at`: 할당 시간
- `started_at`: 시작 시간
- `completed_at`: 완료 시간

**제약조건:**
- `UNIQUE(task_id, host_id)`: 한 에이전트당 배포 1건만

**✅ 치명도 높음:**
- 마지막 결과만 집계하여 중복 집계 방지
- 진행률/성공률의 기준이 됨

**인덱스:**
- task_id, host_id, status, last_result_id

### 7. deployment_results (배포 결과) ✅ 수정
각 에이전트별 배포 실행 결과 히스토리를 저장합니다.

**주요 필드:**
- `request_id`: UUID (PK) - ✅ 치명도 높음: 기본값 제거, 클라이언트 생성 필수
- `task_id`: 배포 작업 ID (FK)
- `host_id`: 에이전트 ID (FK)
- `status`: success/failed/timeout
- `exit_code`: 종료 코드
- `log_summary`: 로그 요약 (최대 10KB 권장)
- `log_storage_url`: ✅ 치명도 높음: 전체 로그는 오브젝트 스토리지 URL
- `log_size_bytes`: 로그 크기
- `duration_sec`: ✅ 개선: 실행 시간 (초, 자동 계산 가능)
- `started_at`: 시작 시간 (NOT NULL) - 에이전트 시간
- `completed_at`: 완료 시간 (NOT NULL) - 에이전트 시간
- `server_received_at`: ✅ 필수 수정: 서버 수신 시각 (시계 오차 보정용)
- `server_processed_at`: ✅ 필수 수정: 서버 처리 시각

**제약조건:**
- `UNIQUE(request_id)`: ✅ 치명도 높음: 전역 고유 제약조건 (Exactly-Once)
- `CHECK (completed_at >= started_at)`: ✅ 개선: 시간 검증
- `CHECK (로그 무결성)`: ✅ 필수 수정: `log_storage_url`과 `log_size_bytes` 동시 NULL/NOT NULL

**✅ 치명도 높음:**
- Exactly-Once 보장: `request_id`는 에이전트가 생성 (기본값 없음)
- 히스토리 기록용: 마지막 결과는 `deployment_targets.last_result_id`에서 참조

**인덱스:**
- (task_id, completed_at DESC), host_id, status, request_id

### 8. announcements (공지)
브로드캐스트/멀티캐스트 공지 정보를 저장합니다.

**주요 필드:**
- `announcement_id`: UUID (PK)
- `title`: 공지 제목
- `content`: 공지 내용
- `type`: broadcast/multicast
- `multicast_groups`: 멀티캐스트 그룹 배열
- `priority`: normal/high/urgent
- `target_count`: 대상 수
- `received_count`: 수신 성공 수
- `status`: pending/sent

**인덱스:**
- status, sent_at, type

### 8. announcements (공지)
브로드캐스트/멀티캐스트 공지 정보를 저장합니다.

**주요 필드:**
- `announcement_id`: UUID (PK)
- `title`: 공지 제목
- `content`: 공지 내용
- `type`: broadcast/multicast
- `multicast_groups`: 멀티캐스트 그룹 배열
- `target_count`: 대상 수 (announcement_targets 기준)
- `received_count`: 수신 성공 수

### 9. announcement_targets (공지 대상) ✅ 신규 - 권장 개선
송신 시점에 대상 확정하여 기록 (수신/유실률 분석 및 재송신 용이)

**주요 필드:**
- `target_id`: UUID (PK)
- `announcement_id`: UUID (FK)
- `host_id`: UUID (FK)
- `status`: pending/sent/received/failed
- `assigned_at`: 할당 시간
- `sent_at`: 발송 시간
- `received_at`: 수신 시간

**제약조건:**
- `UNIQUE(announcement_id, host_id)`: 중복 할당 방지

**인덱스:**
- announcement_id, host_id, status

### 10. announcement_receipts (공지 수신 기록)
공지 수신 여부를 추적합니다.

**주요 필드:**
- `receipt_id`: UUID (PK)
- `announcement_id`: 공지 ID (FK)
- `host_id`: 에이전트 ID (FK)
- `received_at`: 수신 시간

**제약조건:**
- `UNIQUE(announcement_id, host_id)`: 중복 수신 방지

**인덱스:**
- announcement_id, host_id, received_at

### 11. agent_policies (에이전트 정책)
에이전트별 정책 설정을 저장합니다.

**주요 필드:**
- `policy_id`: UUID (PK)
- `host_id`: 에이전트 ID (FK)
- `policy_name`: 정책 이름
- `policy_value`: 정책 값

## 뷰 (Views)

### agents_with_status ✅ 신규
에이전트 정보 + 계산된 상태 (online/offline)

**✅ 필수 수정:** `poll_interval × 3` 기준으로 동적 임계값 사용

### agents_status_summary ✅ 수정
에이전트 상태 요약 (온라인/오프라인 수) - 상태는 계산값, 동적 임계값 적용

### deployments_summary
배포 통계 요약

### announcements_summary
공지 통계 요약 (24시간 내)

## 트리거 (Triggers)

1. **update_agents_updated_at**: agents 테이블의 updated_at 자동 업데이트
2. **update_deployment_status_timestamps_trigger**: ✅ 신규 - 배포 상태 전이 시 타임스탬프 자동 설정
3. **update_deployment_progress_trigger**: ✅ 수정 - deployment_targets 기준으로 진행률 최적화 계산
4. **update_deployment_target_on_result_trigger**: ✅ 신규 - deployment_results 삽입 시 deployment_targets 업데이트
5. **update_announcement_receipt_count_trigger**: 공지 수신 기록 시 수신률 자동 계산

## 함수 (Functions)

1. **update_updated_at_column()**: updated_at 컬럼 자동 업데이트
2. **update_deployment_status_timestamps()**: ✅ 신규 - 배포 상태 전이 시 타임스탬프 자동 설정
3. **update_deployment_progress_optimized()**: ✅ 수정 - deployment_targets 기반으로 진행률 최적화 계산
4. **update_deployment_target_on_result()**: ✅ 신규 - deployment_results 삽입 시 deployment_targets 업데이트

**✅ 제거:**
- `update_agent_status()`: 상태는 뷰로 계산하므로 제거

## 사용 예시

### 에이전트 등록
```sql
INSERT INTO agents (hostname, os, agent_version, bootstrap_token)
VALUES ('PC-001', 'Windows 11', '1.0.0', 'token123');
```

### 하트비트 업데이트
```sql
UPDATE agents 
SET last_checkin = CURRENT_TIMESTAMP 
WHERE host_id = '...';
```

### 배포 생성 및 대상 설정
```sql
-- 1. 배포 생성
INSERT INTO deployments (name, type, command, target_type, artifact_id)
VALUES ('Notepad++ 설치', 'powershell', 'Install-Package NotepadPlusPlus', 'all', '...');

-- 2. 배포 대상 설정 (target_type이 'all'이면 모든 에이전트, 'selected'면 선택한 에이전트)
INSERT INTO deployment_targets (task_id, host_id, status)
SELECT 'task-uuid', host_id, 'pending'
FROM agents
WHERE status = 'online'; -- 또는 WHERE host_id = ANY(...)
```

### 배포 결과 기록 (Exactly-Once)
```sql
-- ✅ 중요: request_id는 클라이언트(에이전트)가 생성한 값
INSERT INTO deployment_results (
    request_id,  -- 클라이언트가 생성한 UUID
    task_id, 
    host_id, 
    status, 
    exit_code, 
    log_summary,
    log_storage_url,
    started_at,
    completed_at
)
VALUES (
    'client-generated-uuid',  -- 에이전트가 생성한 UUID
    '...', 
    '...', 
    'success', 
    0, 
    '설치 완료',
    'https://storage.example.com/logs/...',  -- 오브젝트 스토리지 URL
    '2024-01-01 10:00:00+00',
    '2024-01-01 10:05:00+00'
)
ON CONFLICT (request_id) DO NOTHING;  -- 중복 방지
```

### 에이전트 상태 조회 (계산된 값)
```sql
-- 뷰를 사용하여 계산된 상태 조회
SELECT * FROM agents_with_status;

-- 요약 통계
SELECT * FROM agents_status_summary;
```

## 주의사항

1. **✅ Exactly-Once 보장**: 
   - `request_id`는 **클라이언트(에이전트)가 생성**해야 함 (기본값 없음)
   - `UNIQUE(request_id)` 제약조건으로 중복 보고 방지
   - `ON CONFLICT (request_id) DO NOTHING` 패턴 사용 권장

2. **✅ 중복 집계 방지**:
   - `deployment_targets` 테이블의 `UNIQUE(task_id, host_id)` 제약조건으로 한 에이전트당 배포 1건만
   - `last_result_id`로 마지막 결과만 참조

3. **✅ 온라인 상태 계산**: 
   - `agents.status` 컬럼 제거 → `agents_with_status` 뷰로 계산
   - `last_checkin`이 30초 이내면 온라인으로 간주

4. **✅ 배포 진행률**: 
   - `deployment_targets` 테이블 기준으로 계산 (더 정확하고 빠름)
   - 트리거로 자동 계산되어 실시간 반영

5. **✅ 로그 저장 전략**:
   - 전체 로그는 오브젝트 스토리지에 저장
   - DB에는 `log_storage_url`만 저장
   - `log_summary`는 최대 10KB 권장

6. **✅ 배포 상태 전이**:
   - `running` 진입 시 `started_at` 자동 설정
   - `completed/failed` 진입 시 `completed_at` 자동 설정 (✅ 필수: NOT NULL 필수)
   - CHECK 제약조건으로 상태 전이 검증

7. **✅ 온라인 판정 임계값**:
   - 30초 고정 대신 `poll_interval × 3` 동적 기준 사용
   - 에이전트별 폴링 주기 다를 때 오탐 방지

8. **✅ 결과 시간 신뢰원 분리**:
   - `started_at`/`completed_at`: 에이전트 시간 (시계 오차 가능)
   - `server_received_at`/`server_processed_at`: 서버 시간 (리포팅/SLI 기준)

9. **✅ 로그 저장 무결성**:
   - `log_storage_url`과 `log_size_bytes` 동시 NULL 또는 동시 NOT NULL
   - CHECK 제약조건으로 무결성 보장

10. **✅ 재시도 의미 정리**:
    - `attempt_no`는 서버가 시도 지시할 때 증가 (결과 도착 시가 아님)

11. **✅ 공지 대상 모델 명확화**:
    - `announcement_targets` 테이블로 송신 시점 대상 확정
    - 수신/유실률 분석 및 재송신 용이

12. **공지 수신률**: 트리거로 자동 계산되어 실시간 반영

