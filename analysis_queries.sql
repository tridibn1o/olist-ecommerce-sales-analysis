-- Olist Brazilian E-commerce: analysis queries (SQLite syntax)
-- Tables: orders, order_items, products, customers, category_translation
-- Only delivered orders are used. Revenue = SUM(price), freight excluded.

-- 0. Dataset size
SELECT COUNT(*) AS total_orders FROM orders;
SELECT COUNT(*) AS delivered_orders FROM orders WHERE order_status = 'delivered';

-- 1. Revenue by category (top 10) and share of total
WITH cat AS (
    SELECT COALESCE(t.product_category_name_english, p.product_category_name, 'unknown') AS category,
           SUM(oi.price) AS revenue
    FROM order_items oi
    JOIN orders o   ON o.order_id = oi.order_id
    JOIN products p ON p.product_id = oi.product_id
    LEFT JOIN category_translation t ON t.product_category_name = p.product_category_name
    WHERE o.order_status = 'delivered'
    GROUP BY category
)
SELECT category,
       ROUND(revenue, 2) AS revenue,
       ROUND(100.0 * revenue / SUM(revenue) OVER (), 2) AS pct_of_total
FROM cat
ORDER BY revenue DESC
LIMIT 10;

-- 2. Top 3 sellers within each of the top categories (window function)
WITH seller_cat AS (
    SELECT COALESCE(t.product_category_name_english, p.product_category_name, 'unknown') AS category,
           oi.seller_id,
           SUM(oi.price) AS revenue
    FROM order_items oi
    JOIN orders o   ON o.order_id = oi.order_id
    JOIN products p ON p.product_id = oi.product_id
    LEFT JOIN category_translation t ON t.product_category_name = p.product_category_name
    WHERE o.order_status = 'delivered'
    GROUP BY category, oi.seller_id
),
ranked AS (
    SELECT *, RANK() OVER (PARTITION BY category ORDER BY revenue DESC) AS rnk
    FROM seller_cat
)
SELECT category, seller_id, ROUND(revenue, 2) AS revenue, rnk
FROM ranked
WHERE rnk <= 3
ORDER BY category, rnk;

-- 3. Monthly revenue and month-over-month growth (LAG)
--    Jan 2017 to Aug 2018 only: 2016 and Sep-Oct 2018 are sparse or incomplete in the dataset.
WITH monthly AS (
    SELECT strftime('%Y-%m', o.order_purchase_timestamp) AS month,
           SUM(oi.price) AS revenue
    FROM orders o
    JOIN order_items oi ON oi.order_id = o.order_id
    WHERE o.order_status = 'delivered'
      AND o.order_purchase_timestamp >= '2017-01-01'
      AND o.order_purchase_timestamp <  '2018-09-01'   -- complete months only
    GROUP BY month
)
SELECT month,
       ROUND(revenue, 2) AS revenue,
       ROUND(100.0 * (revenue - LAG(revenue) OVER (ORDER BY month))
             / LAG(revenue) OVER (ORDER BY month), 2) AS mom_growth_pct
FROM monthly
ORDER BY month;

-- 4. Average order value (AOV) overall and by customer state
WITH order_val AS (
    SELECT o.order_id, o.customer_id, SUM(oi.price) AS order_value
    FROM orders o
    JOIN order_items oi ON oi.order_id = o.order_id
    WHERE o.order_status = 'delivered'
    GROUP BY o.order_id, o.customer_id
)
SELECT c.customer_state,
       COUNT(*) AS orders,
       ROUND(AVG(ov.order_value), 2) AS aov
FROM order_val ov
JOIN customers c ON c.customer_id = ov.customer_id
GROUP BY c.customer_state
HAVING COUNT(*) >= 100
ORDER BY aov DESC;

-- 5. Repeat purchase rate (use customer_unique_id, not customer_id)
WITH per_customer AS (
    SELECT c.customer_unique_id, COUNT(DISTINCT o.order_id) AS n_orders
    FROM orders o
    JOIN customers c ON c.customer_id = o.customer_id
    WHERE o.order_status = 'delivered'
    GROUP BY c.customer_unique_id
)
SELECT COUNT(*) AS total_customers,
       SUM(CASE WHEN n_orders > 1 THEN 1 ELSE 0 END) AS repeat_customers,
       ROUND(100.0 * SUM(CASE WHEN n_orders > 1 THEN 1 ELSE 0 END) / COUNT(*), 2) AS repeat_rate_pct
FROM per_customer;

-- 6. Seller concentration: share of revenue from the top 10% of sellers
WITH seller_rev AS (
    SELECT oi.seller_id, SUM(oi.price) AS revenue
    FROM order_items oi
    JOIN orders o ON o.order_id = oi.order_id
    WHERE o.order_status = 'delivered'
    GROUP BY oi.seller_id
),
ranked AS (
    SELECT revenue,
           NTILE(10) OVER (ORDER BY revenue DESC) AS decile
    FROM seller_rev
)
SELECT COUNT(*) AS sellers,
       ROUND(100.0 * SUM(CASE WHEN decile = 1 THEN revenue END) / SUM(revenue), 2) AS top10pct_sellers_revenue_share
FROM ranked;
