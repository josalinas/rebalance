from pathlib import Path

from rebalance import Portfolio
from rebalance.reader import get_cash_config
from rebalance.reader import load_config
from rebalance.reader import parse_args
from rebalance.reader import read_positions
from rebalance.reader import resolve_csv_path


def main():
    args = parse_args()
    config_path = Path(args.config)
    config = load_config(config_path)
    csv_path = resolve_csv_path(config_path, config)

    tickers, quantities = read_positions(csv_path)

    portfolio = Portfolio()
    portfolio.easy_add_assets(tickers=tickers, quantities=quantities)

    cash_amounts, cash_currency = get_cash_config(config)
    if cash_amounts is not None:
        portfolio.easy_add_cash(amounts=cash_amounts, currencies=cash_currency)

    target_asset_alloc = config.get("target_asset_alloc")
    if not isinstance(target_asset_alloc, dict) or not target_asset_alloc:
        raise ValueError("target_asset_alloc must be a non-empty mapping.")

    portfolio.selling_allowed = False
    portfolio.rebalance(target_asset_alloc, verbose=True)


if __name__ == "__main__":
    main()
