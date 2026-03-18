"""Utilities for converting between record formats."""

from typing import Any


def cols_to_named(
    records: dict[str, list] | None,
    key: str = "name",
) -> dict[str, dict[str, Any]] | None:
    """Convert column-oriented records to a dict keyed by element name.

    Input:  {"name": ["line1", "line2"], "bus1": ["a", "b"]}
    Output: {"line1": {"bus1": "a"}, "line2": {"bus1": "b"}}

    Args:
        records: Column-oriented dict from py-dss-toolkit, or None.
        key: Column to use as the dict key (default ``"name"``).

    Returns:
        Name-keyed dict, or None if *records* is empty/missing the key column.
    """
    if not records:
        return None
    names = records.get(key)
    if not names:
        return None
    cols = {k: v for k, v in records.items() if k != key}
    return {
        name: {col: vals[i] for col, vals in cols.items()}
        for i, name in enumerate(names)
    }
