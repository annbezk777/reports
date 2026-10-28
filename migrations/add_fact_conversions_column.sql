-- Migration: Add fact_conversions column to monitoring_campaigns table
-- Description: Manual-entry fact конверсии, counterpart to the existing plan_conversions,
-- used to calculate CR (Conversion Rate) = конверсии / визиты * 100

ALTER TABLE monitoring_campaigns ADD COLUMN fact_conversions INTEGER;
