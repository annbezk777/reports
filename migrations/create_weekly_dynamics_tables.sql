-- Migration: weekly dynamics feature (task #22)
-- adriver_daily_stats: per-day Adriver numbers parsed from uploaded Excel files,
--   needed since SAPE/TargetAds/Weborama all support querying an arbitrary
--   date range directly, but Adriver only exists as whatever file was last
--   uploaded - this gives it the same "any date range" shape.
-- monitoring_weekly_stats: one Mon-Sun week's frozen fact numbers per monitoring,
--   computed once a week (Monday, for the week that just ended).

CREATE TABLE IF NOT EXISTS adriver_daily_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    monitoring_id INTEGER NOT NULL REFERENCES monitoring_campaigns(id),
    upload_id INTEGER REFERENCES adriver_file_uploads(id),
    date DATE NOT NULL,
    impressions INTEGER,
    clicks INTEGER,
    ivt_impressions_percent FLOAT,
    givt_impressions_percent FLOAT,
    sivt_impressions_percent FLOAT,
    givt_clicks_percent FLOAT,
    UNIQUE (monitoring_id, date)
);

CREATE TABLE IF NOT EXISTS monitoring_weekly_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    monitoring_id INTEGER NOT NULL REFERENCES monitoring_campaigns(id),
    week_start DATE NOT NULL,
    week_end DATE NOT NULL,
    impressions INTEGER,
    clicks INTEGER,
    ctr FLOAT,
    visits INTEGER,
    vtr FLOAT,
    bounce_rate FLOAT,
    time_on_site FLOAT,
    page_depth FLOAT,
    robotness FLOAT,
    pi FLOAT,
    conversions INTEGER,
    cr FLOAT,
    ivt_impressions_percent FLOAT,
    givt_impressions_percent FLOAT,
    sivt_impressions_percent FLOAT,
    givt_clicks_percent FLOAT,
    adriver_impressions INTEGER,
    adriver_clicks INTEGER,
    weborama_impressions INTEGER,
    weborama_clicks INTEGER,
    computed_at DATETIME,
    UNIQUE (monitoring_id, week_start)
);
