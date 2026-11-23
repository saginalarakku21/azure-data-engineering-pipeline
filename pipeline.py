"""Summarize order CSVs locally or between private Azure Blob containers."""
import argparse
import csv
import io
import json
import os
from collections import defaultdict
from decimal import Decimal
from pathlib import Path


def summarize(source):
    totals = defaultdict(Decimal)
    seen = set()
    for row in csv.DictReader(io.StringIO(source)):
        order_id = row["order_id"].strip()
        region = row["region"].strip().lower()
        amount = Decimal(row["amount"])
        if not order_id or order_id in seen or not region or not amount.is_finite() or amount < 0:
            raise ValueError(f"Invalid order {order_id!r}")
        seen.add(order_id)
        totals[region] += amount
    if not seen:
        raise ValueError("Input contains no orders")
    return json.dumps({"orders": len(seen), "totals": {
        region: str(total) for region, total in sorted(totals.items())
    }}, indent=2) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--azure", action="store_true")
    args = parser.parse_args()
    if args.azure:
        from azure.identity import AzureCliCredential
        from azure.storage.blob import BlobServiceClient, ContentSettings

        service = BlobServiceClient(
            account_url=os.environ["AZURE_STORAGE_ACCOUNT_URL"],
            credential=AzureCliCredential(),
        )
        source = service.get_blob_client("raw", "orders.csv").download_blob().readall()
        result = summarize(source.decode("utf-8-sig"))
        service.get_blob_client("curated", "regional-sales.json").upload_blob(
            result.encode("utf-8"), overwrite=True,
            content_settings=ContentSettings(content_type="application/json"),
        )
        print("curated/regional-sales.json")
        return

    result = summarize(Path("data/orders.csv").read_text(encoding="utf-8-sig"))
    target = Path("output/regional-sales.json")
    target.parent.mkdir(exist_ok=True)
    target.write_text(result, encoding="utf-8")
    print(target)


if __name__ == "__main__":
    main()
