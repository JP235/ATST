from dataclasses import dataclass

import math
from pathlib import Path
import re
from typing import Any

from matplotlib import pyplot as plt
import pandas as pd

from ATST.blocks import (
    Assay,
    Data,
    Entities,
    FileMetadata,
    Layout,
    LayoutSchema,
    Metadata,
    ReadoutManifest,
    Study,
)


@dataclass
class ATSTFile:
    file_info: FileMetadata
    study: Study
    data: Data
    metadata: Metadata
    assay: Assay
    layout: Layout
    entities: Entities | None = None
    layout_schema: LayoutSchema | None = None
    readout_manifest: ReadoutManifest | None = None
    readout_id: str | None = None

    def data_by_type(self, layout_type: str):
        ltypes = self.layout.data["type"].unique()

        if layout_type not in ltypes:
            raise ValueError(f"Layout type {layout_type} not in {ltypes}")

        wells = self.layout.data[self.layout.data["type"] == layout_type]["well_loc"]

        return self.data.data[wells]

    def plt(self, *args, **kwargs):
        return self.plot_full_plate(*args, **kwargs)

    def plot_full_plate(
        self,
        layout_types: str | list[str] | tuple[str, ...] | bool | None = None,
        group_by: str | list[str] | tuple[str, ...] | None = None,
        plate_loc_ordered: bool = True,
        *,
        x: str | None = None,
        drop_empty_groups: bool = True,
        label_fields: str | list[str] | tuple[str, ...] | None = None,
        show_control: str | list[str] | tuple[str, ...] | None = None,
        **kwargs,
    ):
        if isinstance(layout_types, bool):
            plate_loc_ordered = layout_types
            layout_types = None

        groups, _plate_cols = _group_layout_wells(
            self.layout.data,
            self.data.data,
            layout_types=layout_types,
            group_by=group_by,
            drop_empty_groups=drop_empty_groups,
            label_fields=label_fields,
        )
        control_wells = _control_layout_wells(
            self.layout.data,
            self.data.data,
            show_control=show_control,
            label_fields=label_fields,
        )

        if not groups:
            raise ValueError("No plottable wells found for the requested layout filter")

        n = len(groups)
        if plate_loc_ordered:
            group_grid = _ordered_group_grid(groups)
            n_rows = len(group_grid)
            min_cols = max(len(row_groups) for row_groups in group_grid)
            n_cols = kwargs.get(
                "n_cols",
                min_cols,
            )
            n_cols = max(int(n_cols), min_cols)
        else:
            n_cols = kwargs.get("n_cols", 2 if n > 1 else 1)
            n_cols = max(1, min(int(n_cols), n))

            n_rows = math.ceil(n / n_cols)
            group_grid = [
                groups[index : index + n_cols] for index in range(0, n, n_cols)
            ]

        width = kwargs.get("width", 10)
        height = kwargs.get("height", 7)
        fig, axes_arr = plt.subplots(
            n_rows,
            n_cols,
            figsize=(width * n_cols, height * n_rows),
            sharex=kwargs.get("sharex", True),
            sharey=kwargs.get("sharey", True),
        )

        axes = pd.Series(
            axes_arr.reshape(-1) if hasattr(axes_arr, "reshape") else [axes_arr]
        )
        data = self.data.data
        x_values, x_label = _plot_x_values(
            data,
            x=x,
            well_columns=_all_well_columns(self.layout.data),
        )
        ylabel = kwargs.get("ylabel", getattr(self.assay, "readout_unit", "readout"))
        logscale = kwargs.get("logscale", False)
        legend = kwargs.get("legend", True)

        plotted_indexes = set()
        for row_index, row_groups in enumerate(group_grid):
            for col_index, group in enumerate(row_groups[:n_cols]):
                axis_index = row_index * n_cols + col_index
                plotted_indexes.add(axis_index)
                ax = axes.iloc[axis_index]
                for well in group["wells"]:
                    ax.plot(
                        x_values,
                        data[well],
                        label=group["labels"][well],
                        linewidth=kwargs.get("linewidth", 1),
                        alpha=kwargs.get("alpha", 0.9),
                    )
                for control_line in control_wells["lines"]:
                    ax.plot(
                        x_values,
                        data[control_line["well"]],
                        label=control_line["label"],
                        linewidth=kwargs.get("control_linewidth", 1),
                        alpha=kwargs.get("control_alpha", 0.8),
                        linestyle=control_line["linestyle"],
                        color=kwargs.get("control_color", "gray"),
                    )

                ax.set_title(group["title"], fontsize=kwargs.get("title_fontsize", 9))
                ax.tick_params(labelsize=kwargs.get("tick_labelsize", 8))
                if logscale:
                    ax.set_yscale("log")
                if legend and len(group["wells"]) + len(control_wells["lines"]) > 1:
                    ax.legend(fontsize=kwargs.get("legend_fontsize", "small"))

        for index, ax in enumerate(axes):
            if index not in plotted_indexes:
                fig.delaxes(ax)

        for index in plotted_indexes:
            ax = axes.iloc[index]
            if ax.get_subplotspec().is_last_row():
                ax.set_xlabel(kwargs.get("xlabel", x_label))
            if ax.get_subplotspec().is_first_col():
                ax.set_ylabel(ylabel)

        title = kwargs.get(
            "title",
            self.readout_id or getattr(self.study, "study_id", None),
        )
        if title:
            fig.suptitle(title)
            plt.tight_layout(rect=(0, 0, 1, 0.97))
        else:
            plt.tight_layout()

        if kwargs.get("show", True):
            plt.show()

        return [fig]

    def save_atst(self, path: str | Path):
        from .write_files import write_atst

        return write_atst(self, path)


def wellsort(col):
    return col.map(_well_sort_key)


def _group_layout_wells(
    layout: pd.DataFrame,
    data: pd.DataFrame,
    *,
    layout_types: str | list[str] | tuple[str, ...] | None,
    group_by: str | list[str] | tuple[str, ...] | None,
    drop_empty_groups: bool,
    label_fields: str | list[str] | tuple[str, ...] | None,
) -> tuple[list[dict[str, Any]], int]:
    _require_columns(layout, {"well_loc", "type"}, "layout")
    layout = layout.copy()
    layout["_well_sort_key"] = layout["well_loc"].map(_well_sort_key)
    layout = layout.sort_values("_well_sort_key")

    if layout_types is not None:
        layout = _filter_layout_by_types(layout, layout_types)

    data_wells = set(map(str, data.columns))
    layout = layout[layout["well_loc"].astype(str).isin(data_wells)]

    group_cols = _as_list(group_by) if group_by is not None else []
    _require_columns(layout, set(group_cols), "layout")
    if label_fields is None:
        label_cols = [
            col
            for col in layout.columns
            if col not in {"well_loc", "type", "_well_sort_key", *group_cols}
        ]
    else:
        label_cols = _as_list(label_fields)
    _require_columns(layout, set(label_cols), "layout")

    if not group_cols:
        return (
            [
                {
                    "key": row["well_loc"],
                    "wells": [str(row["well_loc"])],
                    "labels": {
                        str(row["well_loc"]): _well_label(row, label_cols=label_cols)
                    },
                    "sort_key": row["_well_sort_key"],
                    "title": str(row["well_loc"]),
                }
                for _, row in layout.iterrows()
            ],
            _plate_column_count(layout),
        )

    grouped: dict[tuple[Any, ...], dict[str, Any]] = {}
    for _, row in layout.iterrows():
        key = tuple(_normalize_group_value(row[col]) for col in group_cols)
        if drop_empty_groups and any(value == "" for value in key):
            continue

        well = str(row["well_loc"])
        if key not in grouped:
            grouped[key] = {
                "key": key,
                "wells": [],
                "labels": {},
                "sort_key": row["_well_sort_key"],
                "title": _group_title(row, group_cols=group_cols),
            }
        grouped[key]["wells"].append(well)
        grouped[key]["labels"][well] = _well_label(row, label_cols=label_cols)

    groups = sorted(grouped.values(), key=lambda group: group["sort_key"])
    for group in groups:
        wells = ", ".join(group["wells"])
        group["title"] = f"{group['title']}\n{wells}"

    return groups, _plate_column_count(layout)


def _control_layout_wells(
    layout: pd.DataFrame,
    data: pd.DataFrame,
    *,
    show_control: str | list[str] | tuple[str, ...] | None,
    label_fields: str | list[str] | tuple[str, ...] | None,
) -> dict[str, Any]:
    if show_control is None:
        return {"lines": []}

    _require_columns(layout, {"well_loc", "type"}, "layout")
    layout = layout.copy()
    layout["_well_sort_key"] = layout["well_loc"].map(_well_sort_key)
    layout = layout.sort_values("_well_sort_key")
    control_types = _type_list(show_control)
    layout = _filter_layout_by_types(layout, control_types)

    data_wells = set(map(str, data.columns))
    layout = layout[layout["well_loc"].astype(str).isin(data_wells)]
    if layout.empty:
        raise ValueError(
            f"No plottable control wells found for layout type(s): {_type_list(show_control)}"
        )

    linestyles = (":", "--", "-.")
    styles = {
        control_type: linestyles[index % len(linestyles)]
        for index, control_type in enumerate(control_types)
    }
    labelled_types = set()
    lines = []
    for _, row in layout.iterrows():
        well = str(row["well_loc"])
        control_type = str(_normalize_group_value(row["type"]))
        if control_type in labelled_types:
            label = "_nolegend_"
        else:
            label = f"control: {control_type}"
            labelled_types.add(control_type)
        lines.append(
            {
                "well": well,
                "label": label,
                "linestyle": styles[control_type],
            }
        )

    return {"lines": lines}


def _ordered_group_grid(groups: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    row_groups: dict[int, list[dict[str, Any]]] = {}
    for group in groups:
        row_number = group["sort_key"][0]
        row_groups.setdefault(row_number, []).append(group)

    return [
        sorted(row, key=lambda group: group["sort_key"])
        for _, row in sorted(row_groups.items())
    ]


def _as_list(value):
    if isinstance(value, str):
        return [value]

    return list([v for v in value if v is not None and v != "" and str(v) == v])


def _type_list(value) -> list[str]:
    return [str(_normalize_group_value(item)) for item in _as_list(value)]


def _filter_layout_by_types(
    layout: pd.DataFrame,
    layout_types: str | list[str] | tuple[str, ...],
) -> pd.DataFrame:
    types = _type_list(layout_types)
    layout_type_values = layout["type"].map(_normalize_group_value).map(str)
    available_types = sorted(value for value in set(layout_type_values) if value != "")
    unknown_types = sorted(set(types) - set(available_types))
    if unknown_types:
        raise ValueError(f"Layout type {unknown_types} not in {available_types}")

    return layout[layout_type_values.isin(types)]


def _require_columns(df: pd.DataFrame, columns: set[str], name: str) -> None:
    missing = sorted(columns - set(df.columns))
    if missing:
        raise ValueError(f"Missing {name} column(s): {missing}")


def _group_title(row: pd.Series, *, group_cols: list[str]) -> str:
    return " | ".join(f"{col}={_display_value(row[col])}" for col in group_cols)


def _well_label(row: pd.Series, *, label_cols: list[str]) -> str:
    well = str(row["well_loc"])
    label_bits = [
        _display_value(row[col])
        for col in label_cols
        if _normalize_group_value(row[col]) != ""
    ]
    if not label_bits:
        return well

    return " | ".join(label_bits)


def _display_value(value) -> str:
    value = _normalize_group_value(value)
    return "<blank>" if value == "" else str(value)


def _normalize_group_value(value):
    if pd.isna(value):
        return ""

    if isinstance(value, str) and value.strip().upper() in {"", "NA", "N/A", "NONE"}:
        return ""

    return value


def _plot_x_values(
    data: pd.DataFrame,
    *,
    x: str | None,
    well_columns: set[str],
) -> tuple[pd.Series | pd.Index, str]:
    if x is not None:
        if x not in data.columns:
            raise ValueError(f"Missing data column for x axis: {x}")
        return data[x], x

    time_columns = [
        col
        for col in data.columns
        if str(col).strip().lower() in {"time", "time_s", "time_sec", "time_seconds"}
    ]
    if time_columns:
        return data[time_columns[0]], str(time_columns[0])

    non_well_columns = [col for col in data.columns if str(col) not in well_columns]
    if non_well_columns:
        return data[non_well_columns[0]], str(non_well_columns[0])

    return data.index, str(data.index.name or "index")


def _all_well_columns(layout: pd.DataFrame) -> set[str]:
    if "well_loc" not in layout.columns:
        return set()

    return set(layout["well_loc"].astype(str))


def _plate_column_count(layout: pd.DataFrame) -> int:
    columns = [
        _well_sort_key(well)[1]
        for well in layout["well_loc"]
        if _well_sort_key(well)[1] > 0
    ]
    return max(columns, default=1)


def _well_sort_key(well) -> tuple[int, int, str]:
    well = str(well).strip().upper()
    match = re.fullmatch(r"([A-Z]+)(\d+)", well)
    if match is None:
        return (10**9, 10**9, well)

    row, col = match.groups()
    return (_row_number(row), int(col), well)


def _row_number(row: str) -> int:
    number = 0
    for char in row:
        number = number * 26 + ord(char) - ord("A") + 1
    return number


@dataclass
class MultiReadoutATST:
    file_info: FileMetadata
    study: Study
    readout_manifest: ReadoutManifest
    readouts: dict[str, ATSTFile] 
    entities: Entities | None
    layout_schema: LayoutSchema | None

    def __post_init__(self) -> None:
        for readout_id, atst in self.readouts.items():
            atst.readout_id = readout_id

    def __getattr__(self, name: str) -> ATSTFile:
        if name.startswith("_"):
            raise AttributeError(
                f"'{type(self).__name__}' object has no attribute '{name}'"
            )

        if name in self.readouts:
            return self.readouts[name]

        raise AttributeError(
            f"'{type(self).__name__}' object has no attribute '{name}'"
        )

    def __dir__(self) -> list[str]:
        return sorted(set(super().__dir__()) | set(self.readouts.keys()))
