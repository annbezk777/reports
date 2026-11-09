-- Унификация 5 статусных полей в Dropdown Badge (Выполнение/Отвал/Тип
-- размещения/Тип клиента/Статус БДМ): tri-state "Выполнение" заменяет
-- старый bool completed, плюс новое поле "Тип клиента".
ALTER TABLE monitoring_campaigns ADD COLUMN completion_status VARCHAR(20);
ALTER TABLE monitoring_campaigns ADD COLUMN client_type VARCHAR(20);

-- Backfill completion_status из старого completed bool, только для уже
-- завершённых (frozen) карточек, где он был задан.
UPDATE monitoring_campaigns SET completion_status = 'completed' WHERE frozen = 1 AND completed = 1;
UPDATE monitoring_campaigns SET completion_status = 'not_completed' WHERE frozen = 1 AND completed = 0;
