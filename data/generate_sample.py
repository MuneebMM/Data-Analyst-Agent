"""Create a small reproducible fake sales CSV using only the standard library."""
from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from pathlib import Path


def main() -> None:
    random.seed(42)
    products = {"Notebook": 12.0, "Headphones": 55.0, "Lamp": 28.0, "Backpack": 40.0}
    regions = ["North", "South", "East", "West"]
    path = Path(__file__).with_name("sample_sales.csv")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["date", "product", "region", "quantity", "revenue"])
        writer.writeheader()
        for index in range(100):
            product = list(products)[index % 4]
            quantity = random.randint(1, 8)
            day = date(2025, 1, 1) + timedelta(days=index * 3)
            writer.writerow({
                "date": day.isoformat(), "product": product, "region": regions[(index * 3) % 4],
                "quantity": "" if index in (13, 67) else quantity,
                "revenue": "" if index in (22, 81) else round(quantity * products[product] * (1 + (index % 3) * 0.05), 2),
            })
    print(f"Created {path} with 100 rows")


if __name__ == "__main__":
    main()
