import argparse
import csv
from pathlib import Path

import yaml

CSV_PATH_KEYS = ("positions_csv", "csv_path", "positions_path")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Rebalance a portfolio from a YAML config and CSV positions."
    )
    parser.add_argument(
        "config",
        nargs="?",
        default="portfolio.yaml",
        help="Path to the YAML config file.",
    )
    return parser.parse_args()


def load_config(path):
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Config file {path} must contain a mapping at the top level.")
    return data


def resolve_csv_path(config_path, config):
    csv_value = None
    for key in CSV_PATH_KEYS:
        csv_value = config.get(key)
        if csv_value:
            break
    if not csv_value:
        raise KeyError(
            "Config must define a CSV path under one of: "
            + ", ".join(CSV_PATH_KEYS)
        )
    csv_path = Path(csv_value)
    if not csv_path.is_absolute():
        csv_path = (config_path.parent / csv_path).resolve()
    return csv_path


def parse_quantity(raw_value):
    cleaned = str(raw_value or "").strip().replace(",", "")
    if not cleaned:
        raise ValueError("Quantity is missing for a non-empty Symbol.")
    try:
        return float(cleaned)
    except ValueError as exc:
        raise ValueError(f"Invalid Quantity value: {raw_value!r}") from exc


def read_positions(csv_path):
    tickers = []
    quantities = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError(f"No headers found in {csv_path}.")
        reader.fieldnames = [name.strip() if name else "" for name in reader.fieldnames]
        for row in reader:
            symbol = (row.get("Symbol") or "").strip()
            if not symbol:
                break
            if symbol.upper() == "SPAXX**":
                continue
            quantity = parse_quantity(row.get("Quantity"))
            tickers.append(symbol)
            quantities.append(quantity)
    if not tickers:
        raise ValueError(f"No tickers found in {csv_path}.")
    return tickers, quantities


def get_cash_config(config):
    cash_amounts = config.get("cash_amounts")
    if cash_amounts is None:
        cash_amounts = config.get("chash_amounts")
    cash_currency = config.get("cash_currency")
    if cash_amounts is None and cash_currency is None:
        return None, None
    if cash_amounts is None or cash_currency is None:
        raise ValueError(
            "Both cash_amounts (or chash_amounts) and cash_currency must be provided."
        )
    if not isinstance(cash_amounts, list) or not isinstance(cash_currency, list):
        raise ValueError("cash_amounts and cash_currency must be lists.")
    return cash_amounts, cash_currency
