"""Run the SQL analysis, save results to results/ and charts to charts/.

Usage: python analysis.py olist.db
"""
import json
import sqlite3
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

db = sys.argv[1] if len(sys.argv) > 1 else "olist.db"
con = sqlite3.connect(db)
Path("results").mkdir(exist_ok=True)
Path("charts").mkdir(exist_ok=True)

# Split the SQL file into statements, skipping comment-only chunks
raw = Path("sql/analysis_queries.sql").read_text()
stmts = [s for s in raw.split(";")
         if any(l.strip() and not l.strip().startswith("--") for l in s.splitlines())]
names = ["total_orders", "delivered_orders", "category_revenue", "top_sellers_by_category",
         "monthly_revenue", "aov_by_state", "repeat_rate", "seller_concentration"]
res = {n: pd.read_sql(s, con) for n, s in zip(names, stmts)}
for n, df in res.items():
    df.to_csv(f"results/{n}.csv", index=False)

# Extra numbers used in the README
cat_all = pd.read_sql("""
    SELECT COALESCE(t.product_category_name_english, p.product_category_name, 'unknown') AS category,
           SUM(oi.price) AS revenue
    FROM order_items oi
    JOIN orders o ON o.order_id = oi.order_id
    JOIN products p ON p.product_id = oi.product_id
    LEFT JOIN category_translation t ON t.product_category_name = p.product_category_name
    WHERE o.order_status = 'delivered'
    GROUP BY category ORDER BY revenue DESC""", con)
total_rev = float(cat_all.revenue.sum())
n_orders = int(res["delivered_orders"].iloc[0, 0])
cust = pd.read_sql("""
    SELECT o.order_id, SUM(oi.price) AS v FROM orders o
    JOIN order_items oi ON oi.order_id = o.order_id
    WHERE o.order_status='delivered' GROUP BY o.order_id""", con)
monthly = res["monthly_revenue"]
peak = monthly.loc[monthly.revenue.idxmax()]
summary = {
    "total_orders": int(res["total_orders"].iloc[0, 0]),
    "delivered_orders": n_orders,
    "total_revenue_brl": round(total_rev, 2),
    "n_categories": int(len(cat_all)),
    "top_category": cat_all.iloc[0].category,
    "top_category_share_pct": round(100 * cat_all.iloc[0].revenue / total_rev, 2),
    "top5_share_pct": round(100 * cat_all.revenue.head(5).sum() / total_rev, 2),
    "top10_share_pct": round(100 * cat_all.revenue.head(10).sum() / total_rev, 2),
    "overall_aov_brl": round(float(cust.v.mean()), 2),
    "peak_month": peak.month, "peak_month_revenue": round(float(peak.revenue), 2),
    "peak_month_mom_pct": float(peak.mom_growth_pct),
    "repeat": res["repeat_rate"].iloc[0].to_dict(),
    "seller": res["seller_concentration"].iloc[0].to_dict(),
}
Path("results/summary.json").write_text(json.dumps(summary, indent=2, default=str))

# Charts
plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False, "font.size": 10})
top10 = res["category_revenue"].iloc[::-1]
fig, ax = plt.subplots(figsize=(8, 4.5))
ax.barh(top10.category, top10.revenue / 1e6, color="#2b6cb0")
for y, v in enumerate(top10.revenue / 1e6):
    ax.text(v + 0.01, y, f"{v:.2f}M", va="center", fontsize=9)
ax.set_xlabel("Revenue (million BRL)")
ax.set_title("Top 10 categories by revenue (delivered orders)")
fig.tight_layout(); fig.savefig("charts/revenue_by_category.png", dpi=160); plt.close(fig)

fig, ax = plt.subplots(figsize=(9, 4.2))
ax.plot(monthly.month, monthly.revenue / 1e3, marker="o", color="#2b6cb0")
ax.annotate("Nov 2017 peak", (monthly.month.tolist().index("2017-11"), monthly.revenue.max() / 1e3),
            xytext=(-60, 6), textcoords="offset points", fontsize=9)
ax.set_xticks(range(0, len(monthly), 2)); ax.set_xticklabels(monthly.month[::2], rotation=45, ha="right")
ax.set_ylim(0, 1100); ax.set_ylabel("Revenue (thousand BRL)")
ax.set_title("Monthly revenue, Jan 2017 to Aug 2018")
fig.tight_layout(); fig.savefig("charts/monthly_revenue.png", dpi=160); plt.close(fig)

aov = res["aov_by_state"].sort_values("aov")
fig, ax = plt.subplots(figsize=(8, 5.5))
ax.barh(aov.customer_state, aov.aov, color="#2b6cb0")
ax.axvline(summary["overall_aov_brl"], color="#c53030", ls="--", lw=1)
ax.text(summary["overall_aov_brl"] + 2, 0, f"overall {summary['overall_aov_brl']:.0f}", color="#c53030", fontsize=9)
ax.set_xlabel("Average order value (BRL)")
ax.set_title("AOV by customer state (states with 100+ orders)")
fig.tight_layout(); fig.savefig("charts/aov_by_state.png", dpi=160); plt.close(fig)
print(json.dumps(summary, indent=2, default=str))
