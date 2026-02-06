from pathlib import Path

from rebalance import Portfolio
from rebalance.plotting import plot_rebalance
from rebalance.reader import get_cash_config
from rebalance.reader import load_config
from rebalance.reader import parse_args
from rebalance.reader import read_positions
from rebalance.reader import resolve_csv_path
from rebalance.targets import resolve_targets


def _tickers_in_scope(constraint, metadata):
    """Return the tickers that match a target's filter values."""
    filter_values = constraint[:-1]

    # Build reverse lookup: value -> column.
    value_to_col = {}
    for meta in metadata.values():
        for col, val in meta.items():
            if val and val not in value_to_col:
                value_to_col[val] = col

    conditions = [(value_to_col[v], v) for v in filter_values if v in value_to_col]

    return [
        t for t, meta in metadata.items()
        if all(meta.get(c) == v for c, v in conditions)
    ]


def _print_report(targets_info, metadata, flat_alloc, old_alloc, new_alloc,
                  new_units, prices, exchange_history, max_diff, portfolio):
    """Print per-target summary tables followed by the per-ticker table."""

    # --- Per-target summary tables ---
    for name, constraint, allocations in targets_info:
        group_column = constraint[-1]
        scope_tickers = _tickers_in_scope(constraint, metadata)

        # Total scope allocation (for normalising to relative %).
        scope_old_total = sum(old_alloc.get(t, 0.0) for t in scope_tickers)
        scope_new_total = sum(new_alloc.get(t, 0.0) for t in scope_tickers)

        print("")
        print(f"  {name}  --  Constraint: {constraint}")
        print(
            " Category        Amount    Currency    Old allocation   New allocation     Target allocation"
        )
        print(
            "                    ($)                      (%)              (%)                 (%)"
        )
        print(
            "--------------------------------------------------------------------------------------------"
        )

        for category, target_pct in allocations.items():
            # Tickers in this category.
            cat_tickers = [
                t for t in scope_tickers
                if metadata[t].get(group_column) == category
            ]

            cat_amount = sum(
                new_units.get(t, 0.0) * prices[t][0] for t in cat_tickers
            )
            currency = prices[cat_tickers[0]][1] if cat_tickers else ""

            cat_old = sum(old_alloc.get(t, 0.0) for t in cat_tickers)
            cat_new = sum(new_alloc.get(t, 0.0) for t in cat_tickers)

            # Convert to relative % within scope.
            rel_old = cat_old / scope_old_total * 100 if scope_old_total else 0.0
            rel_new = cat_new / scope_new_total * 100 if scope_new_total else 0.0

            print(
                "%9s    %10.2f     %4s          %5.2f            %5.2f               %5.2f"
                % (category, cat_amount, currency, rel_old, rel_new, target_pct)
            )

        print("")

    # --- Per-ticker table ---
    print("")
    print(
        " Ticker      Ask     Quantity      Amount    Currency     Old allocation   New allocation     Target allocation"
    )
    print(
        "                      to buy         ($)                      (%)              (%)                 (%)"
    )
    print(
        "---------------------------------------------------------------------------------------------------------------"
    )
    for ticker in portfolio.assets:
        cost_t = new_units[ticker] * prices[ticker][0]
        print(
            "%8s  %7.2f   %7.3f        %8.2f     %4s          %5.2f            %5.2f               %5.2f"
            % (
                ticker, prices[ticker][0], new_units[ticker], cost_t,
                prices[ticker][1], old_alloc[ticker], new_alloc[ticker],
                flat_alloc[ticker],
            )
        )

    print("")
    print(
        "Largest discrepancy between the new and the target asset allocation is %.2f %%."
        % max_diff
    )

    # Print conversion exchange.
    if exchange_history:
        print("")
        if len(exchange_history) > 1:
            print(
                "Before making the above purchases, the following currency conversions are required:"
            )
        else:
            print(
                "Before making the above purchases, the following currency conversion is required:"
            )
        for from_amount, from_currency, to_amount, to_currency, rate in exchange_history:
            print(
                "    %.2f %s to %.2f %s at a rate of %.4f."
                % (from_amount, from_currency, to_amount, to_currency, rate)
            )

    # Print remaining cash.
    print("")
    print("Remaining cash:")
    for cash in portfolio.cash.values():
        print("    %.2f %s." % (cash.amount, cash.currency))


def main():
    args = parse_args()
    config_path = Path(args.config)
    config = load_config(config_path)
    csv_path = resolve_csv_path(config_path, config)

    tickers, quantities, metadata = read_positions(csv_path)

    portfolio = Portfolio()
    portfolio.easy_add_assets(tickers=tickers, quantities=quantities)

    cash_amounts, cash_currency = get_cash_config(config)
    if cash_amounts is not None:
        portfolio.easy_add_cash(amounts=cash_amounts, currencies=cash_currency)

    # Resolve hierarchical targets to flat {ticker: pct}.
    flat_alloc, targets_info, groups = resolve_targets(config, metadata)

    # Capture current allocation before rebalancing.
    old_alloc = portfolio.asset_allocation()

    portfolio.selling_allowed = False
    new_units, prices, exchange_history, max_diff = portfolio.rebalance(
        flat_alloc, groups=groups, verbose=False
    )

    # Capture new allocation after rebalancing.
    new_alloc = portfolio.asset_allocation()

    _print_report(
        targets_info, metadata, flat_alloc, old_alloc, new_alloc,
        new_units, prices, exchange_history, max_diff, portfolio,
    )

    plot_rebalance(targets_info, metadata, flat_alloc, old_alloc, new_alloc,
                   new_units, prices, max_diff, portfolio)


if __name__ == "__main__":
    main()
