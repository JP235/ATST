from __future__ import annotations

from streamlit_app.tables.utils import PLATE_FORMAT_OPTIONS


ASSAY_SELECT_OPTIONS = {
    "readout_type": ["Absorbance", "Fluorescence"],
    "readout_unit": ["OD", "RFU", "GFP"],
    "time_unit": ["seconds", "minutes", "hours"],
    "plate_format": PLATE_FORMAT_OPTIONS,
}

ASSAY_SELECT_DEFAULTS = {
    "readout_type": "Absorbance",
    "readout_unit": "OD",
    "time_unit": "seconds",
    "plate_format": "96_well",
}
