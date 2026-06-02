from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import pandas as pd

from ATST.blocks import BlockName


class Block:
    def __init__(self, name: str, lines: list[str]):
        self.name = name
        self.lines = lines


@dataclass
class LongTable:
    name: str
    data: dict[str, str]
    linked_file: str | None = None

    def __post_init__(self, required_fields: set[str] | None = None):
        if not isinstance(self.data, dict) or not all(
            isinstance(value, str) for value in self.data.values()
        ):
            raise TypeError("LongTable data must be dict[str, str]")

        if required_fields:
            assert set(self.data.keys()).issuperset(required_fields)

    def __getattr__(self, name: str) -> str:
        if name.startswith("_"):
            raise AttributeError(
                f"'{type(self).__name__}' object has no attribute '{name}'"
            )

        if name in self.data:
            return self.data[name]

        raise AttributeError(
            f"'{type(self).__name__}' object has no attribute '{name}'"
        )

    def __dir__(self) -> list[str]:
        return sorted(set(super().__dir__()) | set(self.data.keys()))

    def __eq__(self, value: object) -> bool:
        return isinstance(value, LongTable) and self.data == value.data


@dataclass
class WideTable:
    name: str
    data: pd.DataFrame
    linked_file: str | None = None

    def __post_init__(self, required_fields: set[str] | None = None):
        if not isinstance(self.data, pd.DataFrame):
            raise TypeError("WideTable data must be a DataFrame")

        if required_fields:
            assert set(self.data.columns).issuperset(required_fields)

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(
                f"'{type(self).__name__}' object has no attribute '{name}'"
            )

        if name in self.data.columns:
            return self.data[name]

        raise AttributeError(
            f"'{type(self).__name__}' object has no attribute '{name}'"
        )

    def __dir__(self) -> list[str]:
        columns = set(map(str, self.data.columns))
        return sorted(set(super().__dir__()) | columns)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.data!r})"

    def __eq__(self, value: object) -> bool:
        return isinstance(value, WideTable) and self.data.equals(value.data)

    def __len__(self) -> int:
        return len(self.data)


@dataclass(eq=False)
class LongTableBlock(LongTable):
    data: dict[str, str] = field(default_factory=dict)
    per_readout_data: dict[str, LongTable] = field(default_factory=dict)

    @classmethod
    def per_readout(
        cls,
        name: BlockName,
        data: dict[str, dict[str, str]],
    ) -> LongTableBlock:
        return cls(
            name=name,
            per_readout_data={
                readout_id: LongTable(name=name, data=values)
                for readout_id, values in data.items()
            },
        )

    @property
    def readouts(self) -> dict[str, LongTable]:
        if self.per_readout_data:
            return self.per_readout_data

        raise AttributeError(f"'{type(self).__name__}' object has no per-readout data")

    def __post_init__(self, required_fields: set[str] | None = None):
        if self.data and self.per_readout_data:
            raise TypeError("LongTableBlock cannot mix leaf and per-readout data")

        if not self.per_readout_data:
            return LongTable.__post_init__(self, required_fields)

        if required_fields is None:
            return

        for readout in self.per_readout_data.values():
            readout.__post_init__(required_fields)

    def __getattr__(self, name: str) -> str | LongTable | dict[str, Any]:  # pyright: ignore[reportIncompatibleMethodOverride]
        if name.startswith("_"):
            raise AttributeError(
                f"'{type(self).__name__}' object has no attribute '{name}'"
            )

        if self.per_readout_data:
            readouts = self.readouts
            if name in readouts:
                return readouts[name]

            if all(hasattr(readout, name) for readout in readouts.values()):
                return {
                    readout_id: getattr(readout, name)
                    for readout_id, readout in readouts.items()
                }

        return LongTable.__getattr__(self, name)

    def __dir__(self) -> list[str]:
        if self.per_readout_data:
            readouts = self.readouts
            field_names = set.intersection(
                *(set(readout.data.keys()) for readout in readouts.values())
            )
            return sorted(
                set(object.__dir__(self)) | set(readouts.keys()) | field_names
            )

        return LongTable.__dir__(self)


def _empty_df() -> pd.DataFrame:
    return pd.DataFrame()


@dataclass(eq=False)
class WideTableBlock(WideTable, Block):
    data: pd.DataFrame = field(default_factory=_empty_df)
    per_readout_data: dict[str, WideTable] = field(default_factory=dict)

    @classmethod
    def per_readout(
        cls,
        name: BlockName,
        data: dict[str, pd.DataFrame],
    ) -> WideTableBlock:
        return cls(
            name=name,
            per_readout_data={
                readout_id: WideTable(name=name, data=values)
                for readout_id, values in data.items()
            },
        )

    @property
    def readouts(self) -> dict[str, WideTable]:
        if not self.per_readout_data:
            raise AttributeError(
                f"'{type(self).__name__}' object has no per-readout data"
            )

        return self.per_readout_data

    def __post_init__(self, required_fields: set[str] | None = None):
        if not self.data.empty and self.per_readout_data:
            raise TypeError("WideTablePerReadout cannot mix leaf and per-readout data")

        if not self.per_readout_data:
            return WideTable.__post_init__(self, required_fields)

        if required_fields:
            for readout in self.readouts.values():
                assert set(readout.data.columns).issuperset(required_fields)

    def __getattr__(self, name: str):  # pyright: ignore[reportIncompatibleMethodOverride]
        if name.startswith("_"):
            raise AttributeError(
                f"'{type(self).__name__}' object has no attribute '{name}'"
            )

        if self.per_readout_data:
            readouts = self.readouts
            if name in readouts:
                return readouts[name]

            if all(hasattr(readout, name) for readout in readouts.values()):
                return {
                    readout_id: getattr(readout, name)
                    for readout_id, readout in readouts.items()
                }

        return WideTable.__getattr__(self, name)

    def __dir__(self) -> list[str]:
        base_names = set(object.__dir__(self))

        if self.per_readout_data:
            readouts = self.readouts
            readout_ids = set(readouts.keys())
            readout_columns: list[set[str]] = []

            for readout in readouts.values():
                readout_columns.append(set(map(str, readout.data.columns)))

            shared_columns = set.intersection(*readout_columns)
            return sorted(base_names | readout_ids | shared_columns)

        return WideTable.__dir__(self)

    def __repr__(self) -> str:
        return WideTable.__repr__(self)

    def values_equal(self, value: object) -> bool:
        if not isinstance(value, WideTableBlock):
            return False

        data = self.data
        other_data = value.data

        if self.per_readout_data and value.per_readout_data:
            return _wide_readout_values_equal(
                list(self.readouts.values()),
                list(value.readouts.values()),
            )

        if self.per_readout_data or value.per_readout_data:
            return False

        assert isinstance(data, pd.DataFrame)
        assert isinstance(other_data, pd.DataFrame)
        return data.equals(other_data)

    def __len__(self) -> int:
        return WideTable.__len__(self)


def _wide_readout_values_equal(
    left: list[WideTable],
    right: list[WideTable],
) -> bool:
    if len(left) != len(right):
        return False

    unmatched = list(right)

    for left_readout in left:
        match_index = next(
            (
                index
                for index, right_readout in enumerate(unmatched)
                if left_readout == right_readout
            ),
            None,
        )

        if match_index is None:
            return False

        unmatched.pop(match_index)

    return True
