-- Post-close verdicts on a "Завершить месяц" card: completed (set by
-- whoever closes the month) and churned (set separately by account-manager
-- role, only while the card is frozen).
ALTER TABLE monitoring_campaigns ADD COLUMN completed BOOLEAN;
ALTER TABLE monitoring_campaigns ADD COLUMN churned BOOLEAN;
