-- Rollback for 0001_initial: drop everything it created, in reverse order.
DROP TABLE IF EXISTS runs;
DROP TABLE IF EXISTS events;
DROP TABLE IF EXISTS kv;
