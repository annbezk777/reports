-- Create SAPE accounts table
CREATE TABLE IF NOT EXISTS sape_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(255) NOT NULL,
    login VARCHAR(255) NOT NULL,
    api_token VARCHAR(500) NOT NULL,
    active BOOLEAN DEFAULT 1,
    last_sync DATETIME,
    created_at DATETIME NOT NULL
);

-- Create campaigns table
CREATE TABLE IF NOT EXISTS campaigns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    format_type VARCHAR(10),
    account_id INTEGER NOT NULL,
    active BOOLEAN DEFAULT 1,
    created_at DATETIME NOT NULL,
    FOREIGN KEY (account_id) REFERENCES sape_accounts(id)
);

-- Create report configs table
CREATE TABLE IF NOT EXISTS report_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    campaign_ids JSON NOT NULL,
    campaign_mode VARCHAR(20) DEFAULT 'separate',
    name VARCHAR(255),
    google_sheet_url VARCHAR(500) NOT NULL,
    worksheet_name VARCHAR(255),
    data_start_row INTEGER,
    date_column VARCHAR(5),
    impressions_column VARCHAR(5),
    reach_column VARCHAR(5),
    clicks_column VARCHAR(5),
    ctr_column VARCHAR(5),
    completes_column VARCHAR(5),
    spent_column VARCHAR(5),
    campaign_frequencies JSON,
    schedule_enabled BOOLEAN DEFAULT 1,
    schedule_days VARCHAR(50),
    schedule_time VARCHAR(10),
    last_update DATETIME,
    created_at DATETIME NOT NULL,
    active BOOLEAN DEFAULT 1,
    FOREIGN KEY (campaign_id) REFERENCES campaigns(id)
);

-- Create report logs table
CREATE TABLE IF NOT EXISTS report_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_config_id INTEGER NOT NULL,
    executed_at DATETIME NOT NULL,
    status VARCHAR(50) NOT NULL,
    error_message TEXT,
    metrics JSON,
    FOREIGN KEY (report_config_id) REFERENCES report_configs(id)
);

-- Insert accounts
INSERT INTO sape_accounts (name, login, api_token, active, created_at) VALUES
('Full Media PPL', 'full_media_ppl@sape.ru', '4e160b4d832182f06c669268a8835b448b4e0b0b6bfb54e6072925a6bcabc304', 1, datetime('now')),
('Full StargeIT', 'full-stargeit@sape.ru', '15ef0145b28c2678aa9275d331cc6856ef184d6099f785986feed5324d83e97b', 1, datetime('now')),
('Full Advelop', 'full_advelop@sape.ru', '19d5b488099189d49df4cf9357e65082baaf3f2d97a329db58ce2ce650b4d2b3', 1, datetime('now'));
