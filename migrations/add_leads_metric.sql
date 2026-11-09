-- Задача #56: новая метрика "Лиды" после CR - ручной ввод, общая таблица
-- (план/факт) и понедельная динамика (факт по неделям).
ALTER TABLE monitoring_campaigns ADD COLUMN plan_leads INTEGER;
ALTER TABLE monitoring_campaigns ADD COLUMN fact_leads INTEGER;
ALTER TABLE monitoring_weekly_stats ADD COLUMN leads INTEGER;
