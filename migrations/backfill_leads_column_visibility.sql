-- Карточки, где видимые столбцы были настроены вручную (шестерёнка,
-- задача #46) ДО того, как появилось поле "Лиды" (задача #56), хранят
-- старый список столбцов без 'leads' - из-за этого столбец и понедельный
-- ввод лидов скрыты через .vcol-hidden, хотя на остальных карточках
-- (без ручной настройки) видны по умолчанию. Бэкфиллим 'leads' сразу
-- после 'cr' в сохранённый список, ничего больше не трогая.
--
-- На локальной базе затронута только id=66. На проде список id может
-- быть другим - перед применением проверить:
--   SELECT id, name, visible_columns FROM monitoring_campaigns
--   WHERE visible_columns IS NOT NULL AND visible_columns NOT LIKE '%leads%';
UPDATE monitoring_campaigns
SET visible_columns = '["impressions", "clicks", "ctr", "visits", "vtr", "bounce_rate", "time_on_site", "page_depth", "robotness", "pi", "conversions", "cr", "leads"]'
WHERE id = 66;
