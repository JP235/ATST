"""Numeric readings with lossless source tokens for unchanged cells.

The numeric DataFrame remains suitable for analysis. Its attrs retain source
text keyed by (numeric Time, column), so row sorting does not detach provenance.
Replacing a value invalidates its old token automatically at serialization.
"""
from __future__ import annotations

import json
import math
import re
from decimal import Decimal
import pandas as pd
from ATST.errors import ATSTValidationError

TOKENS = "atst_readings_tokens"
NUMBER = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z")


def load_tokens(data: pd.DataFrame) -> dict:
    """Decode immutable, JSON-compatible DataFrame provenance metadata."""
    raw = data.attrs.get(TOKENS)
    if raw is None:
        return {}
    return {(time, column): (value, token)
            for time, column, value, token in json.loads(raw)}


def save_tokens(data: pd.DataFrame, tokens: dict) -> None:
    def scalar(value):
        if pd.isna(value):
            return None
        return value.item() if hasattr(value, "item") else value

    # A string is cheap for pandas to copy and survives Arrow metadata encoding.
    data.attrs[TOKENS] = json.dumps([
        [scalar(time), column, scalar(value), token]
        for (time, column), (value, token) in tokens.items()
    ], separators=(",", ":"), allow_nan=False)


def number(value, *, context: str, allow_missing: bool = False):
    if pd.isna(value):
        if allow_missing:
            return float("nan")
        raise ATSTValidationError(f"{context} must be numeric and finite.")
    text = str(value).strip()
    if allow_missing and text in {"", "NA"}:
        return float("nan")
    if not NUMBER.fullmatch(text):
        raise ATSTValidationError(f"{context} must be numeric (or empty/NA for measurements): {text!r}")
    result = int(text) if re.fullmatch(r"[+-]?[0-9]+", text) else float(text)
    try:
        finite = math.isfinite(result)
    except OverflowError:
        finite = False
    if not finite:
        raise ATSTValidationError(f"{context} must be finite: {text!r}")
    return result


def same_value(left, right) -> bool:
    if pd.isna(left) or pd.isna(right):
        return bool(pd.isna(left) and pd.isna(right))
    return bool(left == right)


def readings_text(data: pd.DataFrame) -> pd.DataFrame:
    """Return editable/serializable text, retaining NA and original precision."""
    tokens = load_tokens(data)
    times = data["Time"].to_numpy()
    rows = []
    for time, row in zip(times, data.itertuples(index=False, name=None)):
        values = []
        for column, value in zip(data.columns, row):
            previous = tokens.get((time, column))
            if previous is not None and same_value(value, previous[0]):
                text = previous[1]
            else:
                text = "" if pd.isna(value) else str(value).strip()
            values.append(text)
        rows.append(values)
    return pd.DataFrame(rows, columns=data.columns, index=data.index)


def numeric_readings(data: pd.DataFrame, *, context: str) -> pd.DataFrame:
    text = readings_text(data)
    result = pd.DataFrame({
        column: [number(value, context=f"{context}.{column} row {i + 1}",
                        allow_missing=column != "Time")
                 for i, value in enumerate(text[column])]
        for column in data.columns
    }, index=data.index)
    tokens = {}
    for i in range(len(result)):
        time = result["Time"].iloc[i]
        for j, column in enumerate(result.columns):
            tokens[(time, column)] = (result.iat[i, j], text.iat[i, j])
    save_tokens(result, tokens)
    return result


def duration_text(value: str, *, hours_to_units: int, minutes_to_units: int) -> str:
    """Convert HH:MM:SS[.fraction] exactly, without binary-float rounding."""
    match = re.fullmatch(r"([0-9]+):([0-9]{2}):([0-9]{2}(?:\.[0-9]+)?)", value)
    if match is None:
        raise ValueError(f"Unsupported duration: {value!r}")
    hours, minutes, seconds = map(Decimal, match.groups())
    if minutes >= 60 or seconds >= 60:
        raise ValueError(f"Unsupported duration: {value!r}")
    return str(hours * hours_to_units + minutes * minutes_to_units + seconds * Decimal(minutes_to_units) / 60)
