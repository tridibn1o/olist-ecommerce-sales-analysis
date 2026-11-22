"""Load the Olist CSV files into a local SQLite database.

Usage: python sql/load_data.py path/to/csv_folder olist.db
"""
import sqlite3
import sys
from pathlib import Path

import pandas as pd

FILES = {
    "olist_orders_dataset.csv": "orders",
    "olist_order_items_dataset.csv": "order_items",
    "olist_products_dataset.csv": "products",
    "olist_customers_dataset.csv": "customers",
    "product_category_name_translation.csv": "category_translation",
}

def main(csv_dir: str, db_path: str) -> None:
    con = sqlite3.connect(db_path)
    for fname, table in FILES.items():
        df = pd.read_csv(Path(csv_dir) / fname)
        df.to_sql(table, con, if_exists="replace", index=False)
        print(f"{table}: {len(df):,} rows")
    con.close()

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
