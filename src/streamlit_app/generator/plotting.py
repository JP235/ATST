from __future__ import annotations

import math
from typing import Any

import plotly.graph_objects as go
from plotly.colors import qualitative
from plotly.subplots import make_subplots

from ATST.ATSTFile.ATST import (
    ATSTFile,
    control_layout_wells,
    display_value,
    group_layout_wells,
    plot_x_values,
)


def plot_readings_by_layout(
    atst: ATSTFile,
    *,
    group_by: list[str] | None = None,
    plate_loc_ordered: bool = True,
    x: str | None = None,
    color_by: str | None = None,
    show_reference: list[str] | None = None,
    ignore_types: list[str] | None = None,
    include_in_legend: list[str] | None = None,
    ylabel: str | None = None,
    title: str | None = None,
) -> go.Figure:
    """Build an interactive equivalent of ``ATSTFile.plot_full_plate``."""

    layout = atst.layout.data
    readings = atst.readings.data
    ylabel = ylabel or getattr(atst.assay, "readout_unit", None) or "readout"
    title = title or atst.readout_id or getattr(atst.study, "study_id", None)
    ignored_types = {
        str(value).strip()
        for value in (ignore_types or [])
        if str(value).strip()
    }
    plotted_layout = layout[
        ~layout["type"].fillna("").astype(str).str.strip().isin(ignored_types)
    ]
    groups = group_layout_wells(
        plotted_layout,
        readings,
        layout_types=None,
        group_by=group_by,
        drop_empty_groups=True,
        label_fields=include_in_legend,
    )
    if not groups:
        raise ValueError("No plottable wells found for the selected layout columns")

    if color_by is not None and color_by not in plotted_layout.columns:
        raise ValueError(f"Missing layout column for color: {color_by}")
    layout_by_well = plotted_layout.assign(
        _well_key=plotted_layout["well_loc"].astype(str)
    ).set_index("_well_key", drop=False)
    color_values = (
        sorted(
            {
                display_value(value)
                for value in plotted_layout[color_by]
            }
        )
        if color_by is not None
        else []
    )
    colors_by_value = {
        value: qualitative.Plotly[index % len(qualitative.Plotly)]
        for index, value in enumerate(color_values)
    }
    reference_lines = control_layout_wells(
        plotted_layout,
        readings,
        show_control=[
            value
            for value in (show_reference or [])
            if str(value).strip() not in ignored_types
        ]
        or None,
    )["lines"]

    group_grid = _group_grid(groups, plate_loc_ordered=plate_loc_ordered)
    n_rows = len(group_grid)
    n_cols = max(len(row) for row in group_grid)
    horizontal_spacing = 0.04
    vertical_spacing = min(0.08, 0.25 / n_rows)
    plot_height_ratio = (
        (3 / 5)
        * (1 - horizontal_spacing * (n_cols - 1))
        / n_cols
        * n_rows
        / (1 - vertical_spacing * (n_rows - 1))
    )
    subplot_titles = [
        row[col]["title"].replace("\n", "<br>") if col < len(row) else " "
        for row in group_grid
        for col in range(n_cols)
    ]
    fig = make_subplots(
        rows=n_rows,
        cols=n_cols,
        shared_xaxes=True,
        shared_yaxes=True,
        subplot_titles=subplot_titles,
        horizontal_spacing=horizontal_spacing,
        vertical_spacing=vertical_spacing,
    )

    well_columns = (
        set(layout["well_loc"].astype(str)) if "well_loc" in layout.columns else set()
    )
    x_values, x_label = plot_x_values(
        readings,
        x=x,
        well_columns=well_columns,
    )
    label_colors: dict[str, str] = {}
    for row_index, row_groups in enumerate(group_grid, start=1):
        for col_index, group in enumerate(row_groups, start=1):
            for well in group["wells"]:
                label = group["labels"][well]
                if color_by is None:
                    color = label_colors.setdefault(
                        label,
                        qualitative.Plotly[
                            len(label_colors) % len(qualitative.Plotly)
                        ],
                    )
                else:
                    color_value = display_value(layout_by_well.loc[well, color_by])
                    color = colors_by_value[color_value]
                fig.add_trace(
                    go.Scatter(
                        x=x_values,
                        y=readings[well],
                        mode="lines",
                        name=label,
                        showlegend=False,
                        line={"color": color},
                        hovertemplate=(
                            f"{label}<br>{x_label}=%{{x}}<br>"
                            f"{ylabel}=%{{y}}<extra></extra>"
                        ),
                    ),
                    row=row_index,
                    col=col_index,
                )
            for reference in reference_lines:
                reference_well = reference["well"]
                reference_type = display_value(
                    layout_by_well.loc[reference_well, "type"]
                )
                fig.add_trace(
                    go.Scatter(
                        x=x_values,
                        y=readings[reference_well],
                        mode="lines",
                        name=f"reference: {reference_type} | {reference_well}",
                        showlegend=False,
                        line={
                            "color": "#777777",
                            "dash": _plotly_dash(reference["linestyle"]),
                            "width": 1,
                        },
                        opacity=0.8,
                        hovertemplate=(
                            f"reference: {reference_type} | {reference_well}"
                            f"<br>{x_label}=%{{x}}<br>"
                            f"{ylabel}=%{{y}}<extra></extra>"
                        ),
                    ),
                    row=row_index,
                    col=col_index,
                )

    for row_index, row_groups in enumerate(group_grid, start=1):
        for col_index in range(len(row_groups) + 1, n_cols + 1):
            fig.update_xaxes(visible=False, row=row_index, col=col_index)
            fig.update_yaxes(visible=False, row=row_index, col=col_index)

    fig.update_xaxes(title_text=x_label, row=n_rows)
    fig.update_yaxes(title_text=ylabel, col=1)
    fig.update_layout(
        title=title,
        template="plotly_white",
        hovermode="x unified",
        showlegend=False,
        autosize=True,
        margin={"l": 55, "r": 25, "t": 80, "b": 45},
        meta={"readings_plot_height_ratio": plot_height_ratio},
    )
    return fig


def _plotly_dash(matplotlib_style: str) -> str:
    return {":": "dot", "--": "dash", "-.": "dashdot"}[matplotlib_style]


def _group_grid(
    groups: list[dict[str, Any]], *, plate_loc_ordered: bool
) -> list[list[dict[str, Any]]]:
    if plate_loc_ordered:
        rows: dict[int, list[dict[str, Any]]] = {}
        for group in groups:
            rows.setdefault(group["sort_key"][0], []).append(group)
        return [
            sorted(row, key=lambda group: group["sort_key"])
            for _, row in sorted(rows.items())
        ]

    n_cols = min(2, len(groups))
    n_rows = math.ceil(len(groups) / n_cols)
    return [groups[index * n_cols : (index + 1) * n_cols] for index in range(n_rows)]
