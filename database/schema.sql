-- 확장
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ===== Enum 타입 =====
DO $$ BEGIN
  CREATE TYPE deploy_status    AS ENUM ('pending','running','paused','completed','failed');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE deploy_target    AS ENUM ('all','online','selected','tag','group');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE result_status    AS ENUM ('success','failed','timeout');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE notif_method     AS ENUM ('broadcast','multicast');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE notif_status     AS ENUM ('pending','sent');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- ===== PC(Agents) =====
CREATE TABLE IF NOT EXISTS pc (
  id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  host_name        VARCHAR(255) NOT NULL,
  os               VARCHAR(100),
  agent_version    VARCHAR(50),
  agent_token_hash VARCHAR(255),
  last_check_in    TIMESTAMPTZ,
  poll_interval    INT DEFAULT 10,
  created_at       TIMESTAMPTZ DEFAULT now()
);

-- ===== Deployments =====
CREATE TABLE IF NOT EXISTS deployments (
  id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  release_name  VARCHAR(255),
  category      VARCHAR(100),
  command       TEXT NOT NULL,
  target_type   deploy_target NOT NULL,
  target_number INT,
  status        deploy_status NOT NULL DEFAULT 'pending',
  progress      INT DEFAULT 0,      -- (선택) 저장형 진행률
  success_count INT DEFAULT 0,      -- (선택) 저장형 카운터
  failed_count  INT DEFAULT 0,      -- (선택) 저장형 카운터
  started_at    TIMESTAMPTZ,
  completed_at  TIMESTAMPTZ,
  created_at    TIMESTAMPTZ DEFAULT now(),
  CONSTRAINT deployments_status_time_chk CHECK (
    (status='pending'   AND started_at IS NULL AND completed_at IS NULL) OR
    (status='running'   AND started_at IS NOT NULL AND completed_at IS NULL) OR
    (status IN ('paused','completed','failed') AND started_at IS NOT NULL)
  )
);

-- 상태 전이 타임스탬프 자동 세팅(간단 트리거)
CREATE OR REPLACE FUNCTION tr_deploy_ts()
RETURNS TRIGGER AS $$
BEGIN
  IF NEW.status='running' AND OLD.status IS DISTINCT FROM 'running' THEN
    NEW.started_at := COALESCE(NEW.started_at, now());
  END IF;
  IF NEW.status IN ('completed','failed') AND (OLD.status IS DISTINCT FROM NEW.status) THEN
    NEW.completed_at := COALESCE(NEW.completed_at, now());
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_deploy_ts ON deployments;
CREATE TRIGGER trg_deploy_ts BEFORE UPDATE ON deployments
FOR EACH ROW EXECUTE FUNCTION tr_deploy_ts();

-- ===== Deployment Results (Exactly-Once) =====
CREATE TABLE IF NOT EXISTS deployment_results (
  request_id         UUID PRIMARY KEY,                -- 에이전트가 생성
  deployment_id      UUID NOT NULL REFERENCES deployments(id) ON DELETE CASCADE,
  agent_id           UUID NOT NULL REFERENCES pc(id) ON DELETE CASCADE,
  status             result_status NOT NULL,
  exit_code          INT,
  log_summary        TEXT,
  log_storage_url    TEXT,
  started_at         TIMESTAMPTZ NOT NULL,
  completed_at       TIMESTAMPTZ NOT NULL,
  server_received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (completed_at >= started_at)
);

-- ===== Notification(공지) =====
CREATE TABLE IF NOT EXISTS notification (
  id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  title               VARCHAR(255) NOT NULL,
  content             TEXT NOT NULL,
  transmission_method notif_method NOT NULL,
  target_number       INT,
  reception_rate      INT,
  status              notif_status DEFAULT 'pending',
  sent_at             TIMESTAMPTZ,
  created_at          TIMESTAMPTZ DEFAULT now()
);

-- ===== Notification Receipts =====
CREATE TABLE IF NOT EXISTS notification_receipts (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  notification_id UUID NOT NULL REFERENCES notification(id) ON DELETE CASCADE,
  agent_id        UUID NOT NULL REFERENCES pc(id) ON DELETE CASCADE,
  received_at     TIMESTAMPTZ DEFAULT now(),
  UNIQUE(notification_id, agent_id)   -- 중복 수신 방지
);
-- 인덱스
CREATE INDEX IF NOT EXISTS idx_pc_last_check_in ON pc(last_check_in);
CREATE INDEX IF NOT EXISTS idx_pc_host_trgm     ON pc USING gin (host_name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_dep_status_ctime ON deployments(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_res_deploy_recv  ON deployment_results(deployment_id, server_received_at DESC);
CREATE INDEX IF NOT EXISTS idx_res_deploy_agent ON deployment_results(deployment_id, agent_id);
CREATE INDEX IF NOT EXISTS idx_receipts_pair    ON notification_receipts(notification_id, agent_id);

-- 동적 온라인 판정(폴링주기 반영)
CREATE OR REPLACE VIEW pc_with_status AS
SELECT
  p.*,
  CASE
    WHEN p.last_check_in IS NOT NULL
     AND now() - p.last_check_in <= make_interval(secs => COALESCE(p.poll_interval,10) * 3)
    THEN 'online' ELSE 'offline'
  END AS status
FROM pc p;

-- 배포별 최신 결과(에이전트당 1건)
CREATE OR REPLACE VIEW deployment_latest_result AS
WITH latest AS (
  SELECT DISTINCT ON (deployment_id, agent_id)
         deployment_id, agent_id, status, exit_code, server_received_at
  FROM deployment_results
  ORDER BY deployment_id, agent_id, server_received_at DESC
)
SELECT * FROM latest;

-- 배포 대시보드 집계(뷰 기반 진행률)
CREATE OR REPLACE VIEW deployments_with_counts AS
SELECT
  d.*,
  COALESCE(d.target_number, 0) AS total_targets,
  COALESCE(a.completed_count, 0) AS completed_count,
  COALESCE(a.success_count, 0)   AS success_count,
  COALESCE(a.failed_count, 0)    AS failed_count,
  CASE
    WHEN COALESCE(d.target_number,0)=0 THEN 0
    ELSE ROUND((COALESCE(a.completed_count,0)::numeric / d.target_number) * 100)::int
  END AS progress_pct
FROM deployments d
LEFT JOIN (
  SELECT
    deployment_id,
    COUNT(*)                                           AS completed_count,
    COUNT(*) FILTER (WHERE status='success')           AS success_count,
    COUNT(*) FILTER (WHERE status IN ('failed','timeout')) AS failed_count
  FROM deployment_latest_result
  GROUP BY deployment_id
) a ON a.deployment_id = d.id;

-- 공지 수신 집계
CREATE OR REPLACE VIEW notification_stats AS
SELECT
  n.*,
  (SELECT COUNT(*) FROM notification_receipts r WHERE r.notification_id = n.id) AS received_count
FROM notification n;
