import copy

import numpy as np
from scipy.optimize import minimize

def rebalance(portfolio, target_allocation, groups=None):
    """
    Rebalances the portfolio using the specified target allocation, the portfolio's current allocation,
    and the available cash.

    Args:
        portfolio (:class:`.Portfolio`): Object of portfolio to rebalance.
        target_allocation (np.ndarray): Target asset allocation of the portfolio (in %).
        groups (list[list[str]], optional): Leaf groups from the target tree.
            Each element is a list of tickers that share the same leaf node.
            When provided, the optimizer works at the group level and splits
            purchases equally within each group.

    Returns:
        (tuple): tuple containing:
            * new_units (Dict[str, float]): Units of each asset to buy.
            * prices (Dict[str, [float, str]]): Price and currency per ticker.
            * cost (Dict[str, float]): Market value of each asset to buy.
            * exchange_history (list): Currency conversions performed.
    """

    balanced_portfolio = copy.deepcopy(portfolio)

    if portfolio.selling_allowed:
        balanced_portfolio._sell_everything()

    balanced_portfolio._combine_cash()

    # Solve optimization problem
    to_buy_vals = rebalance_optimizer(
        balanced_portfolio, target_allocation, groups
    )

    # See how many units of each asset you need to buy based on optimization solution
    # and total cost/currency
    cmn_curr = portfolio._common_currency
    new_units = {}
    currency_cost = {}
    for sol_mv, ticker in zip(to_buy_vals,
                              balanced_portfolio.assets.keys()):
        if portfolio.selling_allowed:
            new_units[ticker] = (
                sol_mv - portfolio.assets[ticker].market_value_in(cmn_curr)
            ) / portfolio.assets[ticker].price_in(cmn_curr)
        else:
            new_units[ticker] = sol_mv / portfolio.assets[ticker].price_in(
                cmn_curr
            )

        asset_i = portfolio.assets[ticker]
        if asset_i.currency not in currency_cost:
            currency_cost[asset_i.currency] = asset_i.cost_of(
                new_units[ticker])
        else:
            currency_cost[asset_i.currency] += asset_i.cost_of(
                new_units[ticker])

    # Since we converted the cash to one common currency for the rebalancing calculation, revert back
    balanced_portfolio.cash = copy.deepcopy(portfolio.cash)

    # Since we might have sold all assets for the rebalancing calculation, revert back
    balanced_portfolio._assets = copy.deepcopy(portfolio.assets)

    # Make necessary currency conversions
    exchange_history = balanced_portfolio._smart_exchange(currency_cost)

    # Buy new units
    prices = {}
    cost = {}
    for ticker, asset in balanced_portfolio.assets.items():
        prices[ticker] = [asset.price,
                          asset.currency]  # price and currency of price
        cost[ticker] = balanced_portfolio.buy_asset(
            ticker, new_units[ticker])


    return balanced_portfolio, new_units, prices, cost, exchange_history


def _build_group_indices(portfolio, groups):
    """Map ticker-name groups to index-based groups aligned with the portfolio.

    Returns
    -------
    group_indices : list[list[int]]
        Each element is a list of portfolio-order indices for that group.
    """
    tickers = list(portfolio.assets.keys())
    ticker_to_idx = {t: i for i, t in enumerate(tickers)}
    group_indices = []
    for grp in groups:
        group_indices.append([ticker_to_idx[t] for t in grp])
    return group_indices


def rebalance_optimizer(portfolio, target_alloc, groups=None):
    """
    Handles the optimization algorithm for the rebalancing procedure.

    When *groups* is provided the optimizer operates on group-level variables
    (one per leaf group) and splits purchases equally within each group.

    Args:
        portfolio (:class:`.Portfolio`): Object of portfolio to rebalance.
        target_alloc (np.ndarray): Target allocation of Portfolio's assets (in %).
        groups (list[list[str]], optional): Leaf groups of ticker names.

    Returns:
        (np.ndarray): Per-ticker market value of new purchases.
    """

    cmn_curr = portfolio._common_currency
    nb_assets = len(portfolio.assets)
    total_cash = portfolio.cash[cmn_curr].amount

    current_asset_values = np.array([
        asset.market_value_in(cmn_curr)
        for asset in portfolio.assets.values()
    ])

    # --- Grouped optimisation path ---
    if groups is not None:
        group_indices = _build_group_indices(portfolio, groups)
        nb_groups = len(group_indices)

        # Group-level targets (sum per-ticker targets within each group).
        group_targets = np.array([
            sum(target_alloc[i] for i in idx) for idx in group_indices
        ])

        # Group-level current values.
        current_group_values = np.array([
            sum(current_asset_values[i] for i in idx) for idx in group_indices
        ])

        bound = (0.00, total_cash)
        bounds = tuple(bound for _ in range(nb_groups))
        constraints = [{
            'type': 'ineq',
            'fun': lambda x: total_cash - np.sum(x),
        }]

        total_value = portfolio.value(cmn_curr)
        x0 = np.clip(
            group_targets / 100.0 * total_value - current_group_values,
            0.0, total_cash,
        )

        solution = minimize(
            rebalance_objective,
            x0,
            args=(current_group_values, group_targets / 100.0, total_cash),
            method='SLSQP',
            bounds=bounds,
            constraints=constraints,
        )

        # Expand group solution to per-ticker purchase values.
        per_ticker_buy = np.zeros(nb_assets)
        for g, idx in enumerate(group_indices):
            per_ticker = solution.x[g] / len(idx)
            for i in idx:
                per_ticker_buy[i] = per_ticker

        return per_ticker_buy

    # --- Original per-ticker path (backward compatibility) ---
    bound = (0.00, total_cash)
    bounds = ((bound, ) * nb_assets)
    constraints = [{
        'type':
        'ineq',
        'fun':
        lambda new_asset_values: total_cash - np.sum(new_asset_values)
    }]

    new_asset_values0 = target_alloc / 100. * portfolio.value(
        cmn_curr) - current_asset_values

    solution = minimize(rebalance_objective,
                        new_asset_values0,
                        args=(current_asset_values,
                              target_alloc / 100.,
                              total_cash),
                        method='SLSQP',
                        bounds=bounds,
                        constraints=constraints)

    return solution.x

def rebalance_objective(new_values, current_values,
                         target_allocation, total_cash):
    """
    Objective function used in optimization problem of portfolio rebalancing.

    Works for both per-ticker and per-group optimisation — the arrays just
    have different lengths.

    Args:
        new_values (np.ndarray): Market value of new purchases (per ticker or per group).
        current_values (np.ndarray): Current market values (per ticker or per group).
        target_allocation (np.ndarray): Target allocation (in decimal).
        total_cash (float): Total cash available for investing.

    Returns:
        float: Value of objective function.
    """

    vals = current_values + new_values
    tot_val = np.sum(vals)
    current_allocation = vals / tot_val

    # Penalize allocation difference from target (L2 norm).
    alloc_diff = target_allocation - current_allocation
    j1 = np.inner(alloc_diff, alloc_diff)

    # Penalize unused cash (L2 norm).
    spent = np.sum(new_values)
    cash_diff = (total_cash - spent) / (total_cash + spent)
    j2 = cash_diff * cash_diff

    return j1 + j2
