-- Задача #43: решение сейлза (пролонгация/отказ от сотрудничества/на паузе)
-- по карточке, приближающейся к завершению, + свободный комментарий.
ALTER TABLE monitoring_campaigns ADD COLUMN sales_status VARCHAR(20);
ALTER TABLE monitoring_campaigns ADD COLUMN sales_comment TEXT;
ALTER TABLE monitoring_campaigns ADD COLUMN sales_status_updated_at DATETIME;
ALTER TABLE monitoring_campaigns ADD COLUMN sales_status_updated_by VARCHAR(255);

-- Задача #44: тип размещения для завершённых РК (постоянный/тест/флайт).
ALTER TABLE monitoring_campaigns ADD COLUMN placement_type VARCHAR(20);
