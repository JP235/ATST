from __future__ import annotations

import math
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from matplotlib.axes import Axes

from ATST.blocks import (
    Assay,
    Entities,
    FileMetadata,
    Layout,
    Metadata,
    Readings,
    ReadoutIds,
    Study,
)
from ATST.blocks.layout import layout_key_column, layout_key_values
from ATST.errors import ATSTValidationError


@dataclass
class ATSTFile:
    """In-memory representation of a single-readout ATST file."""

    file_info: FileMetadata
    study: Study
    readings: Readings
    metadata: Metadata
    assay: Assay
    layout: Layout
    entities: Entities
    readout_ids: ReadoutIds | None = None
    readout_id: str | None = None

    def data_by_type(self, layout_type: str):
        """Return readings columns for entries with a matching layout `type`.

        Args:
            layout_type: Value from the layout table's `type` column.
        """

        ltypes = self.layout.data["type"].unique()

        if layout_type not in ltypes:
            raise ValueError(f"Layout type {layout_type} not in {ltypes}")

        key_column = layout_key_column(self.layout.data)
        identifiers = self.layout.data[self.layout.data["type"] == layout_type][
            key_column
        ]

        return self.readings.data[identifiers]

    def plot(
        self,
        *,
        group_by: str | Iterable[str] | None = None,
        filters: dict[str, Any] | None = None,
        facet_by: str | Iterable[str] | None = None,
        require_all_filters: bool = True,
        points_only: bool = False,
        summary: Literal["replicates", "median_minmax", "mean_sd"] = "replicates",
        time_unit: str | None = None,
        labels: dict[Any, str] | None = None,
        colors: dict[Any, Any] | None = None,
        title: str | None = None,
        ax: Axes | Iterable[Axes] | np.ndarray | None = None,
        return_fig: bool = False,
    ):
        """Plot selected curves; see ATST.plotting.plot_readouts for options."""
        from ATST.plotting import plot_readouts

        return plot_readouts(
            [self],
            group_by=group_by,
            filters=filters,
            facet_by=facet_by,
            require_all_filters=require_all_filters,
            points_only=points_only,
            summary=summary,
            time_unit=time_unit,
            labels=labels,
            colors=colors,
            title=title,
            axes=ax,
            return_fig=return_fig,
        )

    def summarize(
        self, *, group_by: str | Iterable[str], filters: dict[str, Any] | None = None
    ):
        """Return per-time curve statistics within explicit group_by conditions."""
        from ATST.plotting import summarize

        return summarize(self, group_by=group_by, filters=filters)

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
        """Plot plate readings grouped by layout annotations.

        Args:
            layout_types: Optional layout `type` value or values to include.
            group_by: Layout column or columns used to group wells into panels.
            plate_loc_ordered: Keep panels in plate row/column order when true.
            x: Readings column to use for the x axis; defaults to `Time` when present.
            drop_empty_groups: Skip groups with blank grouping values.
            label_fields: Layout columns to include in well labels.
            show_control: Layout `type` value or values to overlay as controls.
        """

        if isinstance(layout_types, bool):
            plate_loc_ordered = layout_types
            layout_types = None

        key_column = layout_key_column(self.layout.data)
        if key_column == "curve_id":
            plate_loc_ordered = False

        groups = group_layout_wells(
            self.layout.data,
            self.readings.data,
            layout_types=layout_types,
            group_by=group_by,
            drop_empty_groups=drop_empty_groups,
            label_fields=label_fields,
        )
        control_wells = control_layout_wells(
            self.layout.data,
            self.readings.data,
            show_control=show_control,
        )

        if not groups:
            raise ValueError("No plottable wells found for the requested layout filter")

        n = len(groups)
        if plate_loc_ordered:
            row_groups = {}
            for group in groups:
                row_groups.setdefault(group["sort_key"][0], []).append(group)
            group_grid = [
                sorted(row, key=lambda group: group["sort_key"])
                for _, row in sorted(row_groups.items())
            ]
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
        data = self.readings.data
        layout_columns = set(self.layout.data[key_column])
        x_values, x_label = plot_x_values(
            data,
            x=x,
            well_columns=layout_columns,
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
                if (
                    legend
                    and len(group["wells"]) + len(control_wells["lines"]) > 1
                    and len(group["wells"]) < 10
                ):
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
        """Write this ATST file to `path` using `write_atst`."""

        from .write_files import write_atst

        return write_atst(self, path)


def validate_atst(atst: ATSTFile | MultiReadoutATST) -> None:
    """Validate all current values."""
    from ATST.validation import (
        validate_long_table,
        validate_table,
        validate_ids,
        validate_entities,
        validate_readout_registry,
    )
    from ATST.blocks.readings import validate_readings_columns
    from ATST.numeric import readings_text

    if isinstance(atst, MultiReadoutATST):
        declared = validate_readout_registry(atst.readout_ids)
        if set(declared) != set(atst.readouts):
            raise ATSTValidationError(
                "MultiReadoutATST readouts must match READOUT_IDS"
            )
        validate_long_table("FILE_INFO", atst.file_info.data)
        validate_long_table("STUDY", atst.study.data)
        validate_entities(atst.entities)
        for readout_id, readout in atst.readouts.items():
            if readout.readout_id != readout_id:
                raise ATSTValidationError(
                    f"Readout identity differs from registry key {readout_id!r}"
                )
            if (
                readout.file_info.data != atst.file_info.data
                or readout.study.data != atst.study.data
            ):
                raise ATSTValidationError(
                    f"Readout {readout_id!r} must share file and study metadata with its container"
                )
            validate_atst(readout)
        return

    for name, block in (
        ("FILE_INFO", atst.file_info),
        ("STUDY", atst.study),
        ("METADATA", atst.metadata),
        ("ASSAY", atst.assay),
    ):
        validate_long_table(name, block.data)
    validate_entities(atst.entities)
    if atst.readout_ids is not None:
        ids = validate_readout_registry(atst.readout_ids)
        if atst.readout_id not in ids:
            raise ATSTValidationError("Readout identity is absent from READOUT_IDS")
    elif atst.readout_id is not None:
        raise ATSTValidationError("A readout_id requires READOUT_IDS")

    validate_table(
        atst.layout.data, context="LAYOUT", allowed={"well_loc", "curve_id", "type"}
    )
    key_column, layout_keys = layout_key_values(atst.layout.data)
    validate_ids(layout_keys, context=f"LAYOUT.{key_column}")
    if (
        key_column == "well_loc"
        and not str(atst.assay.data.get("plate_format", "")).strip()
    ):
        raise ATSTValidationError(
            "ASSAY.plate_format is required for a well_loc layout."
        )
    validate_table(atst.readings.data, context="READINGS", allowed={"Time"})
    validate_readings_columns(
        atst.readings.data, context=f"READINGS {atst.readout_id or ''}".strip()
    )
    readings_keys = set(atst.readings.data.columns) - {"Time"}
    layout_key_set = set(layout_keys)
    annotation_columns = [
        column for column in atst.layout.data.columns if column != key_column
    ]
    annotated_layout_keys = {
        str(row[key_column]).strip()
        for _, row in atst.layout.data.iterrows()
        if any(
            not pd.isna(row[column]) and str(row[column]).strip() != ""
            for column in annotation_columns
        )
    }
    unannotated_layout_keys = layout_key_set - annotated_layout_keys

    missing = annotated_layout_keys - readings_keys
    if missing:
        raise ATSTValidationError(
            f"Annotated LAYOUT {key_column} values missing from READINGS: "
            + ", ".join(sorted(missing))
        )
    missing = readings_keys - layout_key_set
    if missing:
        raise ATSTValidationError(
            f"READINGS columns missing from LAYOUT.{key_column}: "
            + ", ".join(sorted(missing))
        )

    text_readings = readings_text(atst.readings.data)
    nonempty_unannotated = [
        key
        for key in sorted(unannotated_layout_keys & readings_keys)
        if text_readings[key].map(lambda value: str(value).strip() != "").any()
    ]
    if nonempty_unannotated:
        raise ATSTValidationError(
            f"Unannotated LAYOUT {key_column} values must be absent from READINGS "
            "or have only empty readings: " + ", ".join(nonempty_unannotated)
        )


def group_layout_wells(
    layout: pd.DataFrame,
    data: pd.DataFrame,
    *,
    layout_types: str | list[str] | tuple[str, ...] | None,
    group_by: str | list[str] | tuple[str, ...] | None,
    drop_empty_groups: bool,
    label_fields: str | list[str] | tuple[str, ...] | None,
) -> list[dict[str, Any]]:
    key_column = layout_key_column(layout, context="layout")
    _require_columns(layout, {"type"}, "layout")
    layout = layout.copy()
    if key_column == "well_loc":
        layout["_layout_sort_key"] = layout[key_column].map(_well_sort_key)
    else:
        layout["_layout_sort_key"] = [
            (0, index, str(value)) for index, value in enumerate(layout[key_column])
        ]
    layout = layout.sort_values("_layout_sort_key")

    if layout_types is not None:
        layout = _filter_layout_by_types(layout, layout_types)

    data_keys = set(map(str, data.columns))
    layout = layout[layout[key_column].astype(str).isin(data_keys)]

    group_cols = _as_list(group_by) if group_by is not None else []
    _require_columns(layout, set(group_cols), "layout")
    if label_fields is None:
        label_cols = [
            col
            for col in layout.columns
            if col not in {key_column, "type", "_layout_sort_key", *group_cols}
        ]
    else:
        label_cols = _as_list(label_fields)
    _require_columns(layout, set(label_cols), "layout")

    if not group_cols:
        return [
            {
                "key": row[key_column],
                "wells": [str(row[key_column])],
                "labels": {
                    str(row[key_column]): _layout_label(
                        row,
                        key_column=key_column,
                        label_cols=label_cols,
                    )
                },
                "sort_key": row["_layout_sort_key"],
                "title": str(row[key_column]),
            }
            for _, row in layout.iterrows()
        ]

    grouped: dict[tuple[Any, ...], dict[str, Any]] = {}
    for _, row in layout.iterrows():
        key = tuple(_normalize_group_value(row[col]) for col in group_cols)
        if drop_empty_groups and any(value == "" for value in key):
            continue

        identifier = str(row[key_column])
        if key not in grouped:
            grouped[key] = {
                "key": key,
                "wells": [],
                "labels": {},
                "sort_key": row["_layout_sort_key"],
                "title": " | ".join(
                    f"{col}={display_value(row[col])}" for col in group_cols
                ),
            }
        grouped[key]["wells"].append(identifier)
        grouped[key]["labels"][identifier] = _layout_label(
            row,
            key_column=key_column,
            label_cols=label_cols,
        )

    groups = sorted(grouped.values(), key=lambda group: group["sort_key"])
    for group in groups:
        identifiers = ", ".join(group["wells"])
        group["title"] = (
            f"{group['title']}\n{identifiers[:100]}{'...' if len(identifiers) > 100 else ''}"
        )

    return groups


def control_layout_wells(
    layout: pd.DataFrame,
    data: pd.DataFrame,
    *,
    show_control: str | list[str] | tuple[str, ...] | None,
) -> dict[str, Any]:
    if show_control is None:
        return {"lines": []}

    key_column = layout_key_column(layout, context="layout")
    _require_columns(layout, {"type"}, "layout")
    layout = layout.copy()
    if key_column == "well_loc":
        layout["_layout_sort_key"] = layout[key_column].map(_well_sort_key)
    else:
        layout["_layout_sort_key"] = [
            (0, index, str(value)) for index, value in enumerate(layout[key_column])
        ]
    layout = layout.sort_values("_layout_sort_key")
    control_types = _type_list(show_control)
    layout = _filter_layout_by_types(layout, control_types)

    data_keys = set(map(str, data.columns))
    layout = layout[layout[key_column].astype(str).isin(data_keys)]
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
        identifier = str(row[key_column])
        control_type = str(_normalize_group_value(row["type"]))
        if control_type in labelled_types:
            label = "_nolegend_"
        else:
            label = f"control: {control_type}"
            labelled_types.add(control_type)
        lines.append(
            {
                "well": identifier,
                "label": label,
                "linestyle": styles[control_type],
            }
        )

    return {"lines": lines}


def _as_list(value):
    if isinstance(value, str):
        return [value]

    return [v for v in value if v is not None and v != "" and str(v) == v]


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


def _layout_label(
    row: pd.Series,
    *,
    key_column: str,
    label_cols: list[str],
) -> str:
    identifier = str(row[key_column])
    label_bits = [
        display_value(row[col])
        for col in label_cols
        if _normalize_group_value(row[col]) != ""
    ]
    if not label_bits:
        return identifier

    return " | ".join(label_bits)


def display_value(value) -> str:
    value = _normalize_group_value(value)
    return "<blank>" if value == "" else str(value)


def _normalize_group_value(value):
    if pd.isna(value):
        return ""

    if isinstance(value, str) and value.strip().upper() in {"", "NA", "N/A", "NONE"}:
        return ""

    return value


def plot_x_values(
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


def _well_sort_key(well) -> tuple[int, int, str]:
    well = str(well).strip().upper()
    match = re.fullmatch(r"([A-Z]+)(\d+)", well)
    if match is None:
        return (10**9, 10**9, well)

    row, col = match.groups()
    number = 0
    for char in row:
        number = number * 26 + ord(char) - ord("A") + 1
    return (number, int(col), well)


@dataclass
class MultiReadoutATST:
    """In-memory representation of an ATST file with multiple readout IDs."""

    file_info: FileMetadata
    study: Study
    readout_ids: ReadoutIds
    readouts: dict[str, ATSTFile]
    entities: Entities

    def __post_init__(self) -> None:
        declared_ids = set(self.readout_ids.data["readout_id"])
        actual_ids = set(self.readouts)
        if declared_ids != actual_ids:
            raise ATSTValidationError(
                "MultiReadoutATST readouts must match READOUT_IDS"
            )

        for readout_id, atst in self.readouts.items():
            atst.readout_id = readout_id

    def plot(
        self, *, readouts: str | Iterable[str] | None = None,
        ax: Axes | Iterable[Axes] | np.ndarray | None = None, **kwargs: Any,
    ):
        """Plot selected readouts in separate panels, using ATSTFile.plot options."""
        from ATST.plotting import plot_readouts

        ids = list(self.readouts) if readouts is None else _as_list(readouts)
        return plot_readouts([self.readouts[key] for key in ids], axes=ax, **kwargs)

    def summarize(
        self,
        *,
        group_by: str | Iterable[str],
        readouts: str | Iterable[str] | None = None,
        filters: dict[str, Any] | None = None,
    ):
        """Return tidy statistics with a readout_id column; never pool readouts."""
        ids = list(self.readouts) if readouts is None else _as_list(readouts)
        if not ids:
            raise ValueError("Select at least one readout")
        return pd.concat(
            [
                self.readouts[key]
                .summarize(group_by=group_by, filters=filters)
                .assign(readout_id=key)
                for key in ids
            ],
            ignore_index=True,
        )

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
