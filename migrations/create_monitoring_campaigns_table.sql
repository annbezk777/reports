-- Migration: Create monitoring_campaigns table
-- Date: 2026-10-12
-- Description: Create monitoring_campaigns table for campaign monitoring functionality

-- Create monitoring_campaigns table
CREATE TABLE IF NOT EXISTS monitoring_campaigns (
	id INTEGER NOT NULL,
	name VARCHAR(255) NOT NULL,
	account_id INTEGER NOT NULL,
	campaign_ids JSON NOT NULL,
	date_from DATE NOT NULL,
	date_to DATE NOT NULL,
	plan_impressions INTEGER,
	plan_clicks INTEGER,
	plan_visits INTEGER,
	plan_conversions INTEGER,
	plan_bounce_rate FLOAT,
	plan_page_depth FLOAT,
	plan_robotness FLOAT,
	metrika_counter_id VARCHAR(50),
	metrika_goal_id VARCHAR(50),
	utm_source VARCHAR(100),
	utm_campaign VARCHAR(100),
	manager VARCHAR(100),
	active BOOLEAN DEFAULT 1,
	archived BOOLEAN DEFAULT 0,
	last_sync DATETIME,
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
	plan_time_on_site REAL,
	plan_pi REAL,
	plan_ivt_impressions REAL,
	plan_givt_impressions REAL,
	plan_sivt REAL,
	plan_givt_clicks REAL,
	fact_impressions INTEGER,
	fact_clicks INTEGER,
	fact_visits INTEGER,
	fact_bounce_rate REAL,
	fact_time_on_site REAL,
	fact_page_depth REAL,
	fact_robotness REAL,
	google_sheet_url VARCHAR(500),
	fact_ivt_impressions REAL,
	fact_givt_impressions REAL,
	fact_sivt_impressions REAL,
	fact_givt_clicks REAL,
	plan_vtr REAL,
	fact_vtr FLOAT,
	PRIMARY KEY (id),
	FOREIGN KEY(account_id) REFERENCES sape_accounts (id)
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_monitoring_campaigns_account_id ON monitoring_campaigns(account_id);
CREATE INDEX IF NOT EXISTS idx_monitoring_campaigns_active ON monitoring_campaigns(active);
CREATE INDEX IF NOT EXISTS idx_monitoring_campaigns_archived ON monitoring_campaigns(archived);
CREATE INDEX IF NOT EXISTS idx_monitoring_campaigns_manager ON monitoring_campaigns(manager);
CREATE INDEX IF NOT EXISTS idx_monitoring_campaigns_date_from ON monitoring_campaigns(date_from);
CREATE INDEX IF NOT EXISTS idx_monitoring_campaigns_date_to ON monitoring_campaigns(date_to);

-- Verify table was created
SELECT 'Table monitoring_campaigns created successfully. Columns: ' || COUNT(*)
FROM pragma_table_info('monitoring_campaigns');
