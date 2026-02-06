"""Resolve hierarchical target asset allocations to flat per-ticker percentages."""


class _Node:
    """A node in the allocation tree."""

    __slots__ = ("tickers", "absolute_pct", "children")

    def __init__(self, tickers, absolute_pct):
        self.tickers = list(tickers)
        self.absolute_pct = absolute_pct
        self.children = None  # None means leaf; dict means branch

    def find(self, path):
        """Navigate the tree using *path* (a list of child keys)."""
        node = self
        for key in path:
            if node.children is None:
                raise ValueError(
                    f"Cannot navigate to '{key}': node is a leaf "
                    f"(path so far: {path})."
                )
            if key not in node.children:
                raise ValueError(
                    f"Child '{key}' not found. "
                    f"Available children: {list(node.children)}."
                )
            node = node.children[key]
        return node

    def leaves(self):
        """Yield all leaf nodes."""
        if self.children is None:
            yield self
        else:
            for child in self.children.values():
                yield from child.leaves()


def _group_tickers(tickers, metadata, column):
    """Group *tickers* by their value in *column*."""
    groups = {}
    for ticker in tickers:
        value = metadata[ticker].get(column, "")
        groups.setdefault(value, []).append(ticker)
    return groups


def resolve_targets(config, metadata):
    """Convert hierarchical ``target_asset_alloc`` to a flat ``{ticker: pct}`` dict.

    Parameters
    ----------
    config : dict
        Loaded YAML configuration (must contain ``target_asset_alloc``).
    metadata : dict[str, dict[str, str]]
        Per-ticker metadata from the CSV (column-name -> value).

    Returns
    -------
    flat_alloc : dict[str, float]
        ``{ticker: absolute_percentage}`` summing to 100.
    targets_info : list[tuple[str, list, dict]]
        Ordered list of ``(target_name, constraint, allocations)`` for
        downstream consumers (e.g. plotting).
    groups : list[list[str]]
        Leaf groups — each element is a list of tickers that share the same
        leaf node.  Used by the optimizer to work at group level.
    """
    raw = config.get("target_asset_alloc")
    if not isinstance(raw, dict) or not raw:
        raise ValueError("target_asset_alloc must be a non-empty mapping.")

    # Parse and sort targets by constraint length (ascending).
    targets_info = []
    for name, spec in raw.items():
        constraint = spec.get("Constraint")
        if not isinstance(constraint, list) or not constraint:
            raise ValueError(
                f"Target '{name}' must have a non-empty 'Constraint' list."
            )
        allocations = {k: v for k, v in spec.items() if k != "Constraint"}
        if not allocations:
            raise ValueError(f"Target '{name}' has no allocation entries.")
        targets_info.append((name, constraint, allocations))

    targets_info.sort(key=lambda t: len(t[1]))

    # Build the allocation tree.
    all_tickers = list(metadata.keys())
    root = _Node(all_tickers, 100.0)

    for name, constraint, allocations in targets_info:
        filter_path = constraint[:-1]
        group_column = constraint[-1]

        # Validate allocations sum to 100.
        alloc_sum = sum(allocations.values())
        if abs(alloc_sum - 100.0) > 0.01:
            raise ValueError(
                f"Target '{name}': allocations sum to {alloc_sum}, not 100."
            )

        # Navigate to parent node.
        parent = root.find(filter_path)
        if parent.children is not None:
            raise ValueError(
                f"Target '{name}': node at {filter_path} is already subdivided."
            )

        # Group parent tickers by the target column.
        groups = _group_tickers(parent.tickers, metadata, group_column)

        # Validate every allocation key has matching tickers.
        for value in allocations:
            if value not in groups:
                raise ValueError(
                    f"Target '{name}': allocation key '{value}' has no matching "
                    f"tickers in column '{group_column}'."
                )

        # Validate every ticker group is covered by an allocation key.
        for group_val in groups:
            if group_val not in allocations:
                raise ValueError(
                    f"Target '{name}': tickers with {group_column}='{group_val}' "
                    f"exist but have no allocation entry."
                )

        # Subdivide.
        parent.children = {}
        for value, pct in allocations.items():
            child_tickers = groups.get(value, [])
            parent.children[value] = _Node(
                child_tickers, parent.absolute_pct * pct / 100.0
            )

    # Flatten leaves to per-ticker allocations and collect groups.
    flat_alloc = {}
    groups = []
    for leaf in root.leaves():
        if not leaf.tickers:
            continue
        groups.append(leaf.tickers)
        per_ticker = leaf.absolute_pct / len(leaf.tickers)
        for ticker in leaf.tickers:
            flat_alloc[ticker] = flat_alloc.get(ticker, 0.0) + per_ticker

    # Sanity check.
    total = sum(flat_alloc.values())
    if abs(total - 100.0) > 0.01:
        raise ValueError(
            f"Resolved allocations sum to {total:.4f}%, expected 100%."
        )

    return flat_alloc, targets_info, groups
