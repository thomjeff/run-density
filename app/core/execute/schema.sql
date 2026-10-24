CREATE TABLE IF NOT EXISTS execute_plans (
    plan_id UUID PRIMARY KEY,
    revision INTEGER NOT NULL,
    calendar_date DATE NOT NULL,
    weekday_code TEXT,
    name TEXT NOT NULL DEFAULT '',
    source_run_id TEXT NOT NULL DEFAULT '',
    archived BOOLEAN NOT NULL DEFAULT FALSE,
    imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    manifest JSONB NOT NULL DEFAULT '{}'::jsonb,
    locations JSONB NOT NULL DEFAULT '{}'::jsonb,
    courses JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS execute_active (
    lock SMALLINT PRIMARY KEY DEFAULT 1 CHECK (lock = 1),
    plan_id UUID REFERENCES execute_plans (plan_id)
);

INSERT INTO execute_active (lock, plan_id)
VALUES (1, NULL)
ON CONFLICT (lock) DO NOTHING;

CREATE TABLE IF NOT EXISTS execute_blobs (
    plan_id UUID NOT NULL REFERENCES execute_plans (plan_id),
    kind TEXT NOT NULL,
    day TEXT NOT NULL DEFAULT '',
    payload JSONB NOT NULL,
    PRIMARY KEY (plan_id, kind, day)
);
