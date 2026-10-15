# Demo Script

Example questions to ask the agent (`python src/agent.py`), each with a validation
query to run in Databricks to confirm the answer. Tables are in `test_catalog.default`.

Data is randomized, so for the lineage demos first run the prep queries below to pick
real IDs, then substitute them into the prompts (replace `<ID>`).

## Prep — pick IDs before the demo

A customer that reached every layer (use for Demo 1):
```sql
SELECT c.customer_id
FROM test_catalog.default.raw_customers c
WHERE EXISTS (SELECT 1 FROM test_catalog.default.clean_orders s            WHERE s.customer_id = c.customer_id)
  AND EXISTS (SELECT 1 FROM test_catalog.default.customer_lifetime_value g WHERE g.customer_id = c.customer_id)
LIMIT 5;
```

An order that got stuck (in Bronze but dropped before Silver — use for Demo 2):
```sql
SELECT order_id, customer_id, product_id
FROM test_catalog.default.raw_orders
WHERE customer_id BETWEEN 900 AND 999   -- orphan customer, dropped at the Silver join
LIMIT 10;
```

---

## Demo 1 — Entity present across all layers

**Prompt:** `Is customer <ID> present in all layers?`

**Validate:**
```sql
SELECT
  (SELECT COUNT(*) FROM test_catalog.default.raw_customers           WHERE customer_id = <ID>) AS bronze,
  (SELECT COUNT(*) FROM test_catalog.default.clean_orders            WHERE customer_id = <ID>) AS silver,
  (SELECT COUNT(*) FROM test_catalog.default.customer_lifetime_value WHERE customer_id = <ID>) AS gold;
```
All three counts > 0 confirms a COMPLETE lineage.

## Demo 2 — Why is it missing / where did it get stuck

**Prompt:** `Where did order <ID> get stuck?`

**Validate (presence + the reason):**
```sql
SELECT
  o.order_id, o.customer_id, o.product_id, o.quantity, o.region, o.order_date,
  (SELECT COUNT(*) FROM test_catalog.default.raw_customers c WHERE c.customer_id = o.customer_id) AS customer_exists,
  (SELECT COUNT(*) FROM test_catalog.default.raw_products  p WHERE p.product_id  = o.product_id)  AS product_exists,
  (SELECT COUNT(*) FROM test_catalog.default.clean_orders  s WHERE s.order_id    = o.order_id)     AS in_silver
FROM test_catalog.default.raw_orders o
WHERE o.order_id = <ID>;
```
`in_silver = 0` with `customer_exists = 0` (or `product_exists = 0`) shows it was dropped by the INNER JOIN — stuck at Silver.

## Demo 3 — Track a product across layers

**Prompt:** `Track product <ID> across bronze, silver and gold.`

**Validate:**
```sql
SELECT
  (SELECT COUNT(*) FROM test_catalog.default.raw_products        WHERE product_id = <ID>) AS bronze,
  (SELECT COUNT(*) FROM test_catalog.default.clean_orders        WHERE product_id = <ID>) AS silver,
  (SELECT COUNT(*) FROM test_catalog.default.product_performance WHERE product_id = <ID>) AS gold;
```

## Demo 4 — Top customers (general analytics)

**Prompt:** `Who are the top 5 customers by lifetime value?`

**Validate:**
```sql
SELECT customer_id, customer_name, total_spent, total_orders
FROM test_catalog.default.customer_lifetime_value
ORDER BY total_spent DESC
LIMIT 5;
```

## Demo 5 — Layer counts and drop-off

**Prompt:** `How many orders are in Bronze versus Silver, and what percentage is filtered between them?`

**Validate:**
```sql
SELECT
  (SELECT COUNT(*) FROM test_catalog.default.raw_orders)   AS bronze_orders,
  (SELECT COUNT(*) FROM test_catalog.default.clean_orders) AS silver_orders,
  ROUND((1 - (SELECT COUNT(*) FROM test_catalog.default.clean_orders)
            / (SELECT COUNT(*) FROM test_catalog.default.raw_orders)) * 100, 1) AS pct_filtered;
```

## Demo 6 — Why orders are missing from revenue

**Prompt:** `Why might some orders be missing from the daily revenue report?`

**Validate (cancelled/returned are excluded from Gold):**
```sql
SELECT order_status, COUNT(*) AS orders
FROM test_catalog.default.clean_orders
GROUP BY order_status
ORDER BY orders DESC;
```

---

## Clean examples (one question, one validation query)

### Example 1 — Gold layer query

Ask the agent:
```
Who are the top 5 customers by total spending?
```

Validate in Databricks:
```sql
SELECT customer_name, total_spent, total_orders, avg_order_value
FROM test_catalog.default.customer_lifetime_value
ORDER BY total_spent DESC LIMIT 5;
```
Names and numbers should match.

### Example 2 — Missing data investigation

First, run this in Databricks to pick a real orphan order:
```sql
SELECT order_id, customer_id FROM test_catalog.default.raw_orders
WHERE customer_id NOT IN (SELECT customer_id FROM test_catalog.default.raw_customers)
LIMIT 1;
```

Note the `order_id` and `customer_id`. Then ask the agent:
```
Order {order_id} exists in raw_orders but not in clean_orders. Why?
```

Validate in Databricks (single query):
```sql
SELECT 'raw_orders' AS source, COUNT(*) AS found FROM test_catalog.default.raw_orders WHERE order_id = {order_id}
UNION ALL
SELECT 'raw_customers', COUNT(*) FROM test_catalog.default.raw_customers WHERE customer_id = {customer_id}
UNION ALL
SELECT 'clean_orders', COUNT(*) FROM test_catalog.default.clean_orders WHERE order_id = {order_id};
```
Result: raw_orders = 1, raw_customers = 0, clean_orders = 0. The customer doesn't exist, so the INNER JOIN dropped it — matches the agent's explanation.

### Example 3 — Cross-layer comparison

Ask the agent:
```
How many orders exist in each layer — bronze, silver, and gold — and what percentage gets filtered at each step?
```

Validate in Databricks (single query):
```sql
SELECT 'bronze' AS layer, COUNT(*) AS rows FROM test_catalog.default.raw_orders
UNION ALL
SELECT 'silver', COUNT(*) FROM test_catalog.default.clean_orders
UNION ALL
SELECT 'gold', SUM(total_orders) FROM test_catalog.default.daily_revenue;
```
