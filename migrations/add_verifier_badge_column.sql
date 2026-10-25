-- Migration: Add verifier_badge column to monitoring_campaigns table
-- Date: 2026-10-25
-- Description: Single-letter badge (W/S/T/A) parsed from the Asana task's
-- "Верификатор:" free-text note - shown on monitoring/report cards.

ALTER TABLE monitoring_campaigns ADD COLUMN verifier_badge VARCHAR(1);
