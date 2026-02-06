"""Nested donut charts and summary tables for portfolio rebalancing."""

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.gridspec import GridSpec


# ---------------------------------------------------------------------------
# Tree / ring helpers (for the nested donuts)
# ---------------------------------------------------------------------------

def _build_tree(metadata, targets_info):
    """Build the category tree from the target hierarchy."""
    sorted_targets = sorted(targets_info, key=lambda t: len(t[1]))
    subdivisions = {}
    for _name, constraint, allocations in sorted_targets:
        path = tuple(constraint[:-1])
        subdivisions[path] = (constraint[-1], list(allocations.keys()))

    root = {"label": "", "tickers": list(metadata), "children": []}

    def _sub(node, path):
        if path not in subdivisions:
            return
        col, keys = subdivisions[path]
        groups = {}
        for t in node["tickers"]:
            groups.setdefault(metadata[t].get(col, ""), []).append(t)
        for k in keys:
            if k in groups:
                child = {"label": k, "tickers": groups[k], "children": []}
                node["children"].append(child)
                _sub(child, path + (k,))

    _sub(root, ())
    return root, len(sorted_targets)


def _flatten_rings(root, n_cat, alloc):
    """Flatten tree into per-ring wedge lists via DFS."""
    n_rings = n_cat + 1
    rings = [[] for _ in range(n_rings)]

    def _dfs(node, depth, gidx):
        val = sum(alloc.get(t, 0.0) for t in node["tickers"])
        rings[depth].append(
            {"label": node["label"], "value": val, "group": gidx, "span": False})
        if node["children"]:
            for ch in node["children"]:
                _dfs(ch, depth + 1, gidx)
        else:
            for d in range(depth + 1, n_cat):
                rings[d].append(
                    {"label": node["label"], "value": val,
                     "group": gidx, "span": True})
            for t in node["tickers"]:
                rings[n_rings - 1].append(
                    {"label": t, "value": alloc.get(t, 0.0),
                     "group": gidx, "span": False})

    for i, ch in enumerate(root["children"]):
        _dfs(ch, 0, i)
    return rings


def _make_colors(rings, n_groups):
    """Per-group hue, progressively lighter toward the centre."""
    cmap = plt.colormaps["tab10"]
    bases = [np.array(cmap(i)[:3]) for i in range(n_groups)]
    n = len(rings)
    out = []
    for ri, ring in enumerate(rings):
        f = ri / max(n - 1, 1)
        out.append([bases[e["group"]] + (1.0 - bases[e["group"]]) * f * 0.55
                     for e in ring])
    return out


def _draw_donut(ax, rings, colors, title):
    """Draw a single nested donut on *ax*."""
    nr = len(rings)
    R = 1.0
    hole = 0.15
    w = (R - hole) / nr

    for ri in range(nr):
        r = R - ri * w
        sizes = [e["value"] for e in rings[ri]]
        if not sizes or all(s == 0 for s in sizes):
            continue
        wedges, _ = ax.pie(
            sizes, radius=r, colors=colors[ri],
            wedgeprops=dict(width=w, edgecolor="white", linewidth=0.5),
            startangle=90, counterclock=False)

        total = sum(sizes)
        for wedge, entry in zip(wedges, rings[ri]):
            pct = entry["value"] / total * 100 if total else 0
            if pct < 3:
                continue
            mid = (wedge.theta1 + wedge.theta2) / 2
            mr = r - w / 2
            x = mr * np.cos(np.radians(mid))
            y = mr * np.sin(np.radians(mid))
            fs = max(5.5, 8 - ri)
            ax.text(x, y, f"{entry['label']}\n{pct:.1f}%",
                    ha="center", va="center", fontsize=fs,
                    weight="bold" if ri == 0 else "normal")

    ax.set_title(title, fontsize=12, pad=12)
    ax.set_aspect("equal")


# ---------------------------------------------------------------------------
# Table helpers
# ---------------------------------------------------------------------------

def _tickers_in_scope(constraint, metadata):
    """Return tickers matching a target's filter values."""
    filter_values = constraint[:-1]
    value_to_col = {}
    for meta in metadata.values():
        for col, val in meta.items():
            if val and val not in value_to_col:
                value_to_col[val] = col
    conditions = [(value_to_col[v], v) for v in filter_values if v in value_to_col]
    return [t for t, meta in metadata.items()
            if all(meta.get(c) == v for c, v in conditions)]


def _add_table(ax, title, col_labels, rows):
    """Render a styled table on *ax*."""
    ax.set_axis_off()
    if title:
        ax.set_title(title, fontsize=9, fontweight="bold", loc="left", pad=8)

    table = ax.table(
        cellText=rows,
        colLabels=col_labels,
        cellLoc="center",
        loc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(7.5)
    table.auto_set_column_width(range(len(col_labels)))

    for j in range(len(col_labels)):
        table[0, j].set_facecolor("#4472C4")
        table[0, j].set_text_props(color="white", fontweight="bold", fontsize=7)

    for i in range(len(rows)):
        for j in range(len(col_labels)):
            table[i + 1, j].set_facecolor("#D9E2F3" if i % 2 == 0 else "white")

    table.scale(1, 1.4)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def plot_rebalance(targets_info, metadata, flat_alloc, old_alloc, new_alloc,
                   new_units, prices, max_diff, portfolio):
    """Save nested donut charts + summary tables to rebalance_report.png."""

    # --- Donut data ---
    root, n_cat = _build_tree(metadata, targets_info)
    n_top = len(root["children"])
    sorted_t = sorted(targets_info, key=lambda t: len(t[1]))
    ring_labels = [c[-1] for _, c, _ in sorted_t] + ["Ticker"]

    # --- Summary table data ---
    summary_tables = []
    summary_col_labels = [
        "Category", "Amount ($)", "Currency",
        "Old (%)", "New (%)", "Target (%)"]

    for name, constraint, allocations in targets_info:
        group_col = constraint[-1]
        scope = _tickers_in_scope(constraint, metadata)
        scope_old = sum(old_alloc.get(t, 0.0) for t in scope)
        scope_new = sum(new_alloc.get(t, 0.0) for t in scope)

        rows = []
        for cat, tgt_pct in allocations.items():
            cat_t = [t for t in scope if metadata[t].get(group_col) == cat]
            amt = sum(new_units.get(t, 0.0) * prices[t][0] for t in cat_t)
            cur = prices[cat_t[0]][1] if cat_t else ""
            ro = sum(old_alloc.get(t, 0.0) for t in cat_t) / scope_old * 100 if scope_old else 0
            rn = sum(new_alloc.get(t, 0.0) for t in cat_t) / scope_new * 100 if scope_new else 0
            rows.append([cat, f"{amt:.2f}", cur,
                         f"{ro:.2f}", f"{rn:.2f}", f"{tgt_pct:.2f}"])

        title = f"{name}  --  Constraint: {constraint}"
        summary_tables.append((title, rows))

    # --- Ticker table data ---
    ticker_col_labels = [
        "Ticker", "Ask", "Qty to buy", "Amount ($)", "Currency",
        "Old (%)", "New (%)", "Target (%)"]
    ticker_rows = []
    for ticker in portfolio.assets:
        cost = new_units[ticker] * prices[ticker][0]
        ticker_rows.append([
            ticker, f"{prices[ticker][0]:.2f}", f"{new_units[ticker]:.3f}",
            f"{cost:.2f}", prices[ticker][1],
            f"{old_alloc[ticker]:.2f}", f"{new_alloc[ticker]:.2f}",
            f"{flat_alloc[ticker]:.2f}"])

    # --- Layout ---
    def _th(n_data_rows):
        return 0.4 * (n_data_rows + 1) + 0.7

    donut_h = 6.5
    ring_h = 0.4
    s_heights = [_th(len(r)) for _, r in summary_tables]
    t_height = _th(len(ticker_rows))
    disc_h = 0.4
    all_h = [donut_h, ring_h] + s_heights + [t_height, disc_h]

    fig = plt.figure(figsize=(10, sum(all_h)))
    gs = GridSpec(len(all_h), 2, figure=fig, height_ratios=all_h)

    # --- Donuts ---
    for col, alloc, label in [(0, old_alloc, "Old Allocation"),
                               (1, new_alloc, "New Allocation")]:
        ax = fig.add_subplot(gs[0, col])
        rings = _flatten_rings(root, n_cat, alloc)
        cols = _make_colors(rings, n_top)
        _draw_donut(ax, rings, cols, label)

    # --- Ring legend ---
    ax_leg = fig.add_subplot(gs[1, :])
    ax_leg.set_axis_off()
    ax_leg.text(0.5, 0.5,
                "Rings (outer to inner): " + " > ".join(ring_labels),
                ha="center", va="center", fontsize=9, style="italic",
                transform=ax_leg.transAxes)

    # --- Summary tables ---
    for i, (title, rows) in enumerate(summary_tables):
        ax = fig.add_subplot(gs[2 + i, :])
        _add_table(ax, title, summary_col_labels, rows)

    # --- Ticker table ---
    ax_t = fig.add_subplot(gs[2 + len(summary_tables), :])
    _add_table(ax_t, "", ticker_col_labels, ticker_rows)

    # --- Discrepancy ---
    ax_d = fig.add_subplot(gs[-1, :])
    ax_d.set_axis_off()
    ax_d.text(
        0.0, 0.5,
        f"Largest discrepancy between new and target allocation: {max_diff:.2f} %",
        ha="left", va="center", fontsize=9, transform=ax_d.transAxes)

    fig.suptitle("Portfolio Allocation", fontsize=14)
    fig.tight_layout()
    plt.savefig("rebalance_report.pdf", bbox_inches="tight")
    plt.close(fig)
