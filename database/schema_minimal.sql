-- =========================================================
-- OpsHub mini schema (PC, deployments, deployment_results,
--                     notification, notification_receipts)
-- PostgreSQL 13+ 권장
-- =========================================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ---------------------------
-- 1) PC (agents)
-- ---------------------------
CREATE TABLE IF NOT EXISTS pc (
  id               uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  host_name        varchar(255) NOT NULL,
  os               varchar(100),
  agent_version    varchar(50),
  agent_token_hash varchar(255),
  last_check_in    timestamptz,
  poll_interval    int DEFAULT 10,
  created_at       timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_pc_last_check_in ON pc(last_check_in);
CREATE INDEX IF NOT EXISTS idx_pc_host_trgm ON pc USING gin (host_name gin_trgm_ops);

-- ---------------------------
-- 2) deployments
-- ---------------------------
CREATE TABLE IF NOT EXISTS deployments (
  id            uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  release_name  varchar(255),
  category      varchar(100),
  command       text NOT NULL,
  target_type   varchar(20) NOT NULL CHECK (target_type IN ('all','online','selected','tag','group')),
  target_number int,                                  -- 대상 총 수 (UI에서 계산해 넣거나 고정)
  status        varchar(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','running','paused','completed','failed')),
  progress      int DEFAULT 0,                         -- 선택: 저장형 진행률(뷰로도 제공)
  success_count int DEFAULT 0,                         -- 선택: 저장형 카운터
  failed_count  int DEFAULT 0,                         -- 선택: 저장형 카운터
  started_at    timestamptz,
  completed_at  timestamptz,
  created_at    timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_deployments_status_created ON deployments(status, created_at DESC);

-- ---------------------------
-- 3) deployment_results (Exactly-Once: request_id 전역 UNIQUE)
-- ---------------------------
CREATE TABLE IF NOT EXISTS deployment_results (
  request_id         uuid PRIMARY KEY,                -- 클라이언트(에이전트)가 생성
  deployment_id      uuid NOT NULL REFERENCES deployments(id) ON DELETE CASCADE,
  agent_id           uuid NOT NULL REFERENCES pc(id) ON DELETE CASCADE,
  status             varchar(20) NOT NULL CHECK (status IN ('success','failed','timeout')),
  exit_code          int,
  log_summary        text,
  log_storage_url    varchar(2048),
  started_at         timestamptz NOT NULL,
  completed_at       timestamptz NOT NULL,
  server_received_at timestamptz NOT NULL DEFAULT now(),
  CHECK (completed_at >= started_at)
);

CREATE INDEX IF NOT EXISTS idx_results_deploy_received ON deployment_results(deployment_id, server_received_at DESC);
CREATE INDEX IF NOT EXISTS idx_results_deploy_agent   ON deployment_results(deployment_id, agent_id);

-- ---------------------------
-- 4) notification (공지)
-- ---------------------------
CREATE TABLE IF NOT EXISTS notification (
  id                  uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  title               varchar(255) NOT NULL,
  content             text NOT NULL,
  transmission_method varchar(20) NOT NULL CHECK (transmission_method IN ('broadcast','multicast')),
  target_number       int,
  reception_rate      int,
  status              varchar(20) DEFAULT 'pending' CHECK (status IN ('pending','sent')),
  sent_at             timestamptz,
  created_at          timestamptz DEFAULT now()
);

-- ---------------------------
-- 5) notification_receipts (공지 수신 로그)
-- ---------------------------
CREATE TABLE IF NOT EXISTS notification_receipts (
  id              uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  notification_id uuid NOT NULL REFERENCES notification(id) ON DELETE CASCADE,
  agent_id        uuid NOT NULL REFERENCES pc(id) ON DELETE CASCADE,
  received_at     timestamptz DEFAULT now(),
  UNIQUE(notification_id, agent_id)    -- 중복 수신 방지
);

CREATE INDEX IF NOT EXISTS idx_receipts_notif_agent ON notification_receipts(notification_id, agent_id);

-- =========================================================
-- Views (계산형 상태/집계: 중복·경계 안전)
-- =========================================================

-- A) PC 온라인/오프라인 계산(동적 임계값: poll_interval * 3)
CREATE OR REPLACE VIEW pc_with_status AS
SELECT
  p.*,
  CASE
    WHEN p.last_check_in IS NOT NULL
     AND now() - p.last_check_in <= make_interval(secs => COALESCE(p.poll_interval,10) * 3)
    THEN 'online' ELSE 'offline'
  END AS status
FROM pc p;

-- B) 배포별 "에이전트 최신 결과" (중복 방지용)
CREATE OR REPLACE VIEW deployment_latest_result AS
WITH latest AS (
  SELECT DISTINCT ON (deployment_id, agent_id)
         deployment_id, agent_id, status, exit_code, server_received_at
  FROM deployment_results
  ORDER BY deployment_id, agent_id, server_received_at DESC
)
SELECT * FROM latest;

-- C) 배포 대시보드 집계
--  - 분모: deployments.target_number (대상 수)
--  - 분자: 최신 결과 기준 완료/성공/실패 건수
CREATE OR REPLACE VIEW deployments_with_counts AS
SELECT
  d.*,
  COALESCE(d.target_number, 0) AS total_targets,
  COALESCE(a.completed_count, 0) AS completed_count,
  COALESCE(a.success_count, 0)   AS success_count,
  COALESCE(a.failed_count, 0)    AS failed_count,
  CASE
    WHEN COALESCE(d.target_number,0) = 0 THEN 0
    ELSE ROUND((COALESCE(a.completed_count,0)::numeric / d.target_number) * 100)::int
  END AS progress_pct
FROM deployments d
LEFT JOIN (
  SELECT
    deployment_id,
    COUNT(*)                                           AS completed_count,
    COUNT(*) FILTER (WHERE status = 'success')         AS success_count,
    COUNT(*) FILTER (WHERE status IN ('failed','timeout')) AS failed_count
  FROM deployment_latest_result
  GROUP BY deployment_id
) a ON a.deployment_id = d.id;

-- D) 공지 수신 집계
CREATE OR REPLACE VIEW notification_stats AS
SELECT
  n.*,
  (SELECT COUNT(*) FROM notification_receipts r WHERE r.notification_id = n.id) AS received_count
FROM notification n;

-- =========================================================
-- Upsert 패턴(Exactly-Once 수신 예시)
-- =========================================================
-- INSERT INTO deployment_results(request_id, deployment_id, agent_id, status, exit_code,
--                                log_summary, log_storage_url, started_at, completed_at)
-- VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
-- ON CONFLICT (request_id) DO NOTHING;
