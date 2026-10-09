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
    require_all_filters: bool = True,
    points_only: bool = False,
    summary: Literal["replicates", "median_minmax", "mean_sd"] = "replicates",
    time_unit: str | None = None,
    labels: dict[Any, str] | None = None,
    colors: dict[Any, Any] | None = None,
    title: str | None = None,
    axes: Axes | Iterable[Axes] | None = None,
    return_fig: bool = False,
):
    """Plot readouts; return None unless return_fig=True is requested.

    group_by defines condition colours and replicate aggregation; facet_by defines
    panels within each readout. filters maps layout columns to values or lists.
    With facet_by, require_all_filters=True keeps only panels containing every
    requested value for every filter column after filtering. For example,
    filters={"phage_id": ["Pa2", ""]} requires both Pa2 and controls in each
    facet. False keeps every nonempty filtered panel, including partial matches.
    Row filtering always uses AND across columns and OR within each value list.
    summary is 'replicates', 'median_minmax' (whiskers), or 'mean_sd' (shading).
    Summaries require explicit group_by; replicate labels are not required or checked.
    labels/colors map condition keys (scalar for one column, tuple for multiple)
    to legend labels/colours. Missing/blank phage_id displays as 'control';
    underlying condition keys remain unchanged, including for custom labels.
    points_only=True draws unconnected points; median_minmax adds whiskers,
    while mean_sd is rejected. Legends are shared above the figure's panels,
    titled with group_by columns in the same order as the legend values.
    Time defaults to ASSAY.time_unit; conversion supports s, min, h.
    Readouts always occupy separate panels and retain their own time grids.
    axes accepts one Axes per panel (a single Axes or an array/list of Axes).
    Supplied axes must belong to one figure. Layout reserves space for the legend.
    With supplied axes, title sets the panel title instead of the figure title.
    The default return avoids duplicate notebook display; use return_fig=True
    when assigning the figure for further customization or saving.
    """
    if summary not in {"replicates", "median_minmax", "mean_sd"}:
        raise ValueError("summary must be replicates, median_minmax, or mean_sd")
    if points_only and summary == "mean_sd":
        raise ValueError("points_only does not support mean_sd; use replicates or median_minmax")
    columns = _as_list(group_by) if group_by is not None else []
    facets = _as_list(facet_by) if facet_by is not None else []
    panels = []
    for atst in readouts:
        layout = _layout(atst, filters)
        mode = summary
        if facets:
            key = layout_key_column(layout)
            for group in _groups(atst, layout, facets):
                panel_layout = layout[layout[key].isin(group["wells"])]
                if require_all_filters and any(
                    not panel_layout[column].isin([value]).any()
                    for column, values in (filters or {}).items()
                    for value in (values if isinstance(values, (list, tuple, set)) else [values])
                ):
                    continue
                panels.append(
                    (
                        atst,
                        panel_layout,
                        group["title"].split("\n")[0],
                        mode,
                    )
                )
        else:
            panels.append((atst, layout, "", mode))
    if not panels:
        raise ValueError("No panels match the requested filters and facet requirements")

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
        fig, axes = plt.subplots(
            math.ceil(len(prepared) / ncols),
            ncols,
            figsize=(6 * ncols, 4.5 * math.ceil(len(prepared) / ncols)),
            squeeze=False,
        )

    assert axes is not None

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
                " | ".join(
                    "control" if column == "phage_id" and (pd.isna(value) or value == "") else str(value)
                    for column, value in zip(columns, group["key"])
                ) if columns else str(condition),
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
                        linestyle="None" if points_only else "-",
                        marker="o" if points_only else None,
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
                        fmt="o" if points_only else "o-",
                        capsize=3,
                        color=color,
                        label=label,
                    )
        ax.set(
            xlabel=f"Time ({unit})",
            ylabel=str(atst.assay.readout_unit).upper(),
            title=title
            if supplied_axes and title is not None
            else " | ".join(value for value in [atst.readout_id, facet_title] if value),
        )
        if ax.get_legend() is not None:
            ax.get_legend().remove()

    if not supplied_axes:
        for ax in list(axes.flat)[len(prepared) :]:
            fig.delaxes(ax)
        if title:
            fig.suptitle(title)
    legend_entries = {}
    for axis in fig.axes:
        handles, legend_labels = axis.get_legend_handles_labels()
        for handle, label in zip(handles, legend_labels):
            legend_entries.setdefault(label, handle)
    for legend in list(fig.legends):
        if legend.get_gid() == "atst_legend":
            legend.remove()
    legend_height = 0
    title_height = 0.3 / fig.get_figheight() if fig._suptitle is not None else 0
    if legend_entries:
        ncols = 1 if max(map(len, legend_entries)) > 40 else min(4, len(legend_entries))
        legend_title = " | ".join(columns) if columns else layout_key_column(prepared[0][0].layout.data)
        legend = fig.legend(
            list(legend_entries.values()), list(legend_entries),
            title=legend_title, loc="upper center",
            bbox_to_anchor=(0.5, 1 - title_height), ncol=ncols, frameon=False,
        )
        legend.set_gid("atst_legend")
        legend_height = (0.25 * math.ceil(len(legend_entries) / ncols) + 0.4) / fig.get_figheight()
    fig.tight_layout(rect=(0, 0, 1, 1 - legend_height - title_height))

    if return_fig:
        return fig
