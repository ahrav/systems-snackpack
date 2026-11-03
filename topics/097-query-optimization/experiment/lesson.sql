DROP TABLE IF EXISTS lesson_customers;
CREATE TEMP TABLE lesson_customers AS
SELECT i AS id, i % 100 AS a, i % 100 AS b
FROM generate_series(1, 10000) AS g(i);
ANALYZE lesson_customers;
EXPLAIN (ANALYZE, BUFFERS, TIMING OFF)
SELECT * FROM lesson_customers WHERE a = 1 AND b = 1;
CREATE STATISTICS pg_temp.lesson_ab (dependencies)
ON a, b FROM lesson_customers;
ANALYZE lesson_customers;
EXPLAIN (ANALYZE, BUFFERS, TIMING OFF)
SELECT * FROM lesson_customers WHERE a = 1 AND b = 1;
