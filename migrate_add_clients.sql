-- Create clients table
CREATE TABLE IF NOT EXISTS clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    account_id INTEGER NOT NULL,
    active BOOLEAN DEFAULT 1,
    created_at DATETIME NOT NULL,
    FOREIGN KEY (account_id) REFERENCES sape_accounts(id)
);

-- Add client_id column to campaigns
ALTER TABLE campaigns ADD COLUMN client_id INTEGER REFERENCES clients(id);

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_campaigns_client_id ON campaigns(client_id);
CREATE INDEX IF NOT EXISTS idx_clients_account_id ON clients(account_id);
