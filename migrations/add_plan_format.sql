-- Задача #20: явный формат медиаплана (CPM/CPC), чтобы "% выполнения
-- показов" честно игнорировался для CPC-кампаний, вместо хрупкой
-- эвристики "план показов пустой = CPC".
ALTER TABLE monitoring_campaigns ADD COLUMN plan_format VARCHAR(10);
