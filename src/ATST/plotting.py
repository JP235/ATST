"""Condition plots and tidy replicate statistics for ATST objects."""

from __future__ import annotations

import math
from collections.abc import Iterable
from typing import Any, Literal

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from matplotlib.axes import Axes

from ATST.ATSTFile.ATST import ATSTFile, _as_list, group_layout_wells
from ATST.blocks.layout import layout_key_column


def _layout(atst: ATSTFile, filters: dict[str, Any] | None):
    layout = atst.layout.data
    for column, values in (filters or {}).items():
        if column not in layout:
            raise ValueError(f"Missing layout column: {column}")
        if not isinstance(values, (list, tuple, set)):
            values = [values]
        layout = layout[layout[column].isin(values)]
    if layout.empty:
        raise ValueError("No curves match the requested filters")
    return layout


def _groups(atst: ATSTFile, layout: pd.DataFrame, columns: list[str]):
    return group_layout_wells(
        layout,
        atst.readings.data,
        layout_types=None,
        group_by=columns,
        drop_empty_groups=False,
        label_fields=[],
    )


def _statistics(atst: ATSTFile, layout: pd.DataFrame, columns: list[str]):
    if not columns:
        raise ValueError("Specify group_by to identify replicate conditions")
    if "replicate" in columns or layout_key_column(layout) in columns:
        raise ValueError(
            "group_by must describe conditions, not curve or replicate IDs"
        )
    frames = []
    for group in _groups(atst, layout, columns):
        values = atst.readings.data[group["wells"]]
        frame = pd.DataFrame(
            {
                "Time": atst.readings.data["Time"],
                "n": values.count(axis=1),
                "mean": values.mean(axis=1),
                "sd": values.std(axis=1, ddof=1),
                "median": values.median(axis=1),
                "min": values.min(axis=1),
                "max": values.max(axis=1),
            }
        )
        for column, value in zip(columns, group["key"]):
            frame[column] = value
        frames.append(
            frame[columns + ["Time", "n", "mean", "sd", "median", "min", "max"]]
        )
    if not frames:
        raise ValueError("No plottable curves match the selection")
    return pd.concat(frames, ignore_index=True)


def summarize(
    atst: ATSTFile,
    *,
    group_by: str | Iterable[str],
    filters: dict[str, Any] | None = None,
):
    """Summarize curves within explicit group_by conditions, ignoring replicate labels.

    At each original Time, n counts nonmissing values and SD uses ddof=1.
    """
    return _statistics(atst, _layout(atst, filters), _as_list(group_by))


def plot_readouts(
    readouts: Iterable[ATSTFile],
    *,
    group_by: str | Iterable[str] | None = None,
    filters: dict[str, Any] | None = None,
    facet_by: str | Iterable[str] | None = None,
    summary: Literal["replicates", "median_minmax", "mean_sd"] = "replicates",
    time_unit: str | None = None,
    labels: dict[Any, str] | None = None,
    colors: dict[Any, Any] | None = None,
    title: str | None = None,
    axes: Axes | Iterable[Axes] | None = None,
):
    """Return one matplotlib Figure without requiring pyplot calls.

    group_by defines condition colours and replicate aggregation; facet_by defines
    panels within each readout. filters maps layout columns to values or lists.
    summary is 'replicates', 'median_minmax' (whiskers), or 'mean_sd' (shading).
    Summaries require explicit group_by; replicate labels are not required or checked.
    labels/colors map condition keys (scalar for one column, tuple for multiple)
    to legend labels/colours. Blank condition values are retained as ''.
    Time defaults to ASSAY.time_unit; conversion supports s, min, h.
    Readouts always occupy separate panels and retain their own time grids.
    ax accepts one Axes per panel (a single Axes or an array/list of Axes).
    Supplied axes must belong to one figure; their layout is left to the caller.
    With supplied axes, title sets the panel title instead of the figure title.
    """
    if summary not in {"replicates", "median_minmax", "mean_sd"}:
        raise ValueError("summary must be replicates, median_minmax, or mean_sd")
    columns = _as_list(group_by) if group_by is not None else []
    facets = _as_list(facet_by) if facet_by is not None else []
    panels = []
    for atst in readouts:
        layout = _layout(atst, filters)
        mode = summary
        if facets:
            key = layout_key_column(layout)
            for group in _groups(atst, layout, facets):
                panels.append(
                    (
                        atst,
                        layout[layout[key].isin(group["wells"])],
                        group["title"].split("\n")[0],
                        mode,
                    )
                )
        else:
            panels.append((atst, layout, "", mode))
    if not panels:
        raise ValueError("Select at least one readout")

    # Prepare and validate before creating a figure.
    prepared = []
    units = {"s": 1, "min": 60, "h": 3600}
    for atst, layout, facet_title, mode in panels:
        source_unit = atst.assay.time_unit
        target_unit = time_unit or source_unit
        if target_unit == source_unit:
            scale = 1
        else:
            if source_unit not in units or target_unit not in units:
                raise ValueError("Time conversion supports s, min, h")
            scale = units[source_unit] / units[target_unit]
        stats = _statistics(atst, layout, columns) if mode != "replicates" else None
        groups = _groups(atst, layout, columns)
        if not groups:
            raise ValueError("No plottable curves match the selection")
        prepared.append((atst, facet_title, mode, scale, target_unit, stats, groups))

    supplied_axes = axes is not None
    if supplied_axes:
        axes = np.asarray(axes, dtype=object).reshape(-1)
        if len(axes) != len(prepared):
            raise ValueError("Supply exactly one axis per panel")
        if not all(isinstance(axis, Axes) for axis in axes):
            raise ValueError("ax must contain matplotlib Axes")
        fig = axes[0].figure
        if any(axis.figure is not fig for axis in axes):
            raise ValueError("Supplied axes must belong to one figure")
    else:
        ncols = min(2, len(prepared))
        fig, ax = plt.subplots(
            math.ceil(len(prepared) / ncols),
            ncols,
            figsize=(6 * ncols, 4.5 * math.ceil(len(prepared) / ncols)),
            squeeze=False,
        )
    assert axes

    palette = plt.rcParams["axes.prop_cycle"].by_key()["color"]
    condition_colors = {}
    for ax, (atst, facet_title, mode, scale, unit, stats, groups) in zip(
        axes.flat, prepared
    ):
        for group in groups:
            condition = group["key"]
            if columns and len(columns) == 1:
                condition = condition[0]
            label = (labels or {}).get(
                condition,
                " | ".join(map(str, group["key"])) if columns else str(condition),
            )
            color = (colors or {}).get(condition)
            if color is None:
                color = condition_colors.setdefault(
                    condition, palette[len(condition_colors) % len(palette)]
                )
            if mode == "replicates":
                for index, curve in enumerate(group["wells"]):
                    ax.plot(
                        atst.readings.data["Time"] * scale,
                        atst.readings.data[curve],
                        color=color,
                        alpha=0.6,
                        label=label if index == 0 else None,
                    )
            else:
                selected = stats
                for column, value in zip(columns, group["key"]):
                    selected = selected[selected[column] == value]
                x = selected["Time"].to_numpy(dtype=float) * scale
                if mode == "mean_sd":
                    mean = selected["mean"].to_numpy(dtype=float)
                    sd = selected["sd"].to_numpy(dtype=float)
                    ax.plot(x, mean, color=color, label=label)
                    ax.fill_between(x, mean - sd, mean + sd, color=color, alpha=0.2)
                else:
                    median = selected["median"].to_numpy(dtype=float)
                    ax.errorbar(
                        x,
                        median,
                        yerr=[
                            median - selected["min"].to_numpy(dtype=float),
                            selected["max"].to_numpy(dtype=float) - median,
                        ],
                        fmt="o-",
                        capsize=3,
                        color=color,
                        label=label,
                    )
        ax.set(
            xlabel=f"Time ({unit})",
            ylabel=atst.assay.readout_unit,
            title=title
            if supplied_axes and title is not None
            else " | ".join(value for value in [atst.readout_id, facet_title] if value),
        )
        ax.legend(frameon=False)
        
    if not supplied_axes:
        for ax in list(axes.flat)[len(prepared) :]:
            fig.delaxes(ax)
        if title:
            fig.suptitle(title)
        fig.tight_layout()
        
    return fig
