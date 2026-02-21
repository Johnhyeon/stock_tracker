-- Phase 1: DB 테이블 마이그레이션 (trader → expert)
-- 실행 전 백업 권장: pg_dump -U postgres investment_tracker > backup.sql

BEGIN;

-- 테이블 이름 변경
ALTER TABLE trader_mentions RENAME TO expert_mentions;
ALTER TABLE trader_stats RENAME TO expert_stats;

-- 인덱스 이름 변경
ALTER INDEX ix_trader_mentions_stock_name RENAME TO ix_expert_mentions_stock_name;
ALTER INDEX ix_trader_mentions_stock_code RENAME TO ix_expert_mentions_stock_code;
ALTER INDEX ix_trader_mentions_date RENAME TO ix_expert_mentions_date;
ALTER INDEX ix_trader_stats_stock_code RENAME TO ix_expert_stats_stock_code;
ALTER INDEX ix_trader_stats_date RENAME TO ix_expert_stats_date;
ALTER INDEX uq_trader_stats_code_date RENAME TO uq_expert_stats_code_date;

-- AlertType enum 값 변경 (notification_logs 테이블 내 기존 데이터)
UPDATE notification_logs SET alert_type = 'expert_new_mention' WHERE alert_type = 'trader_new_mention';
UPDATE notification_logs SET alert_type = 'expert_cross_check' WHERE alert_type = 'trader_cross_check';

COMMIT;
