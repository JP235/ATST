from dataclasses import dataclass

import pandas as pd
from ATST.blocks import READINGS
from ATST.blocks.base_classes import WideTableBlock
from ATST.errors import ATSTValidationError
from ATST.numeric import load_tokens, save_tokens, number, numeric_readings, readings_text


@dataclass
class Readings(WideTableBlock):
    """Numeric readings; source tokens preserve NA/empty and unchanged precision."""
    name: str = READINGS

    def __post_init__(self):
        super().__post_init__()
        if self.per_readout_data:
            for readout_id, readout in self.readouts.items():
                context = f"READINGS readout {readout_id!r}"
                validate_readings_columns(readout.data, context=context)
                readout.data = numeric_readings(readout.data, context=context)
            return
        validate_readings_columns(self.data, context=READINGS)
        self.data = numeric_readings(self.data, context=READINGS)

    def to_text(self) -> pd.DataFrame:
        """Return a leaf readings table as text for editing or export."""
        if self.per_readout_data:
            raise ValueError("Select one readout before converting readings to text")
        return readings_text(self.data)

    def set_missing(self, time, column: str, *, kind: str = "NA") -> None:
        """Set one measurement to explicit NA or empty, addressed by Time."""
        if kind not in {"NA", ""} or column == "Time" or column not in self.data:
            raise ValueError("Use a measurement column and kind='NA' or kind=''")
        rows = self.data["Time"] == time
        if rows.sum() != 1:
            raise ValueError("Time must identify exactly one row")
        self.data.loc[rows, column] = float("nan")
        tokens = load_tokens(self.data)
        tokens[(time, column)] = (float("nan"), kind)
        save_tokens(self.data, tokens)


def validate_readings_columns(df, *, context: str) -> None:
    columns = list(df.columns)
    if not columns or columns[0] != "Time":
        raise ATSTValidationError(f"{context} first column must be Time.")
    if len(columns) != len(set(columns)):
        raise ATSTValidationError(f"{context} has duplicate columns.")
    if df.empty:
        raise ATSTValidationError(f"{context} must contain at least one time point.")
    times = [number(value, context=f"{context}.Time row {i + 1}")
             for i, value in enumerate(df["Time"])]
    if len(times) != len(set(times)):
        raise ATSTValidationError(f"{context} Time values must be unique.")
    if any(right <= left for left, right in zip(times, times[1:])):
        raise ATSTValidationError(f"{context} Time values must be strictly increasing.")
    for column in columns[1:]:
        for i, value in enumerate(df[column]):
            number(value, context=f"{context}.{column} row {i + 1}", allow_missing=True)
