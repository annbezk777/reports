-- "Завершить месяц" feature: static monthly history + rollover.
-- See docs/plan validated-stargazing-cerf.md for the full design.

ALTER TABLE monitoring_campaigns ADD COLUMN frozen BOOLEAN DEFAULT 0;
ALTER TABLE monitoring_campaigns ADD COLUMN frozen_at DATETIME;
ALTER TABLE monitoring_campaigns ADD COLUMN frozen_period VARCHAR(7);
ALTER TABLE monitoring_campaigns ADD COLUMN rolled_from_id INTEGER REFERENCES monitoring_campaigns(id);
ALTER TABLE monitoring_campaigns ADD COLUMN rolled_to_id INTEGER REFERENCES monitoring_campaigns(id);

ALTER TABLE report_configs ADD COLUMN frozen BOOLEAN DEFAULT 0;
ALTER TABLE report_configs ADD COLUMN frozen_at DATETIME;
ALTER TABLE report_configs ADD COLUMN frozen_period VARCHAR(7);
ALTER TABLE report_configs ADD COLUMN rolled_from_id INTEGER REFERENCES report_configs(id);
ALTER TABLE report_configs ADD COLUMN rolled_to_id INTEGER REFERENCES report_configs(id);
