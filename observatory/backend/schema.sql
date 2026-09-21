CREATE EXTENSION IF NOT EXISTS postgis;
CREATE TABLE IF NOT EXISTS events (
 id text PRIMARY KEY, time bigint NOT NULL, updated bigint NOT NULL,
 geom geography(Point,4326) NOT NULL, record jsonb NOT NULL
);
CREATE INDEX IF NOT EXISTS events_geom_idx ON events USING gist(geom);
CREATE INDEX IF NOT EXISTS events_time_idx ON events(time);
CREATE TABLE IF NOT EXISTS event_revisions (
 event_id text NOT NULL, updated bigint NOT NULL, record jsonb NOT NULL,
 PRIMARY KEY(event_id,updated)
);
CREATE TABLE IF NOT EXISTS assets (
 id text PRIMARY KEY, kind text NOT NULL, geom geography(Point,4326) NOT NULL, record jsonb NOT NULL
);
CREATE INDEX IF NOT EXISTS assets_geom_idx ON assets USING gist(geom);
CREATE TABLE IF NOT EXISTS feed_health (
 id text PRIMARY KEY, last_success timestamptz, last_attempt timestamptz NOT NULL DEFAULT now(), error text
);
CREATE TABLE IF NOT EXISTS ai_budget (
 month text PRIMARY KEY, reserved_usd numeric NOT NULL DEFAULT 0
);
