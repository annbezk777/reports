-- Migration: Create adriver_file_uploads table (Постклик archive)
-- Date: 2026-10-26
-- Description: Archive of every Adriver/Sizmek Excel file uploaded via a
-- monitoring's Excel upload - keeps the file itself plus who uploaded it
-- and when, instead of parsing and discarding it like before.

CREATE TABLE IF NOT EXISTS adriver_file_uploads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    monitoring_id INTEGER NOT NULL REFERENCES monitoring_campaigns(id),
    filename VARCHAR(255) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    uploaded_by VARCHAR(255),
    uploaded_at DATETIME,
    impressions INTEGER,
    clicks INTEGER,
    data_as_of_date DATE
);
