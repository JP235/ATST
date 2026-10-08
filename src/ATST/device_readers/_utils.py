from __future__ import annotations

from datetime import datetime
import re

from ATST.errors import ATSTValidationError
from ATST.validation import DATE_FIELDS, validate_date


FILENAME_RE = re.compile(
    r"(?P<date_start>\d{4}[-_]\d{2}[-_]\d{2})[-_]"
    r"(?P<body>.+)_"
    r"(?P<plate_num>\d+)_"
    r"(?P<export_date>\d{1,2}-[A-Za-z]{3}-\d{4})[ _]"
    r"(?P<export_time>\d{2}-\d{2}-\d{2})$"
)
RUN_DATE_RE = re.compile(r"\d{4}[-_]\d{2}[-_]\d{2}")
EXPORT_DATETIME_RE = re.compile(
    r"(?P<export_date>\d{1,2}-[A-Za-z]{3}-\d{4})[ _]"
    r"(?P<export_time>\d{2}-\d{2}-\d{2})"
)
PLATE_TOKEN_RE = re.compile(
    r"(?:^|[_\s-])(?:plate(?:[_\s-]*(?:num(?:ber)?|no))?[_\s-]*)"
    r"(?P<plate_num>\d+)(?=$|[_\s-])",
    flags=re.IGNORECASE,
)
ISOLATE_STRING_RE = re.compile(r"(?:[A-Z]+\d+)+$")
FILENAME_SHAKING_FREQUENCY_RE = re.compile(
    r"(?<![A-Za-z0-9])(?P<rpm>\d+)rpm(?![A-Za-z0-9])",
    flags=re.IGNORECASE,
)
WELL_LOCATION_RE = re.compile(r"^[A-Za-z]+\d+$")
WELL_LOCATION_PARTS_RE = re.compile(r"^([A-Za-z]+)0*(\d+)$")
PLATE_ROW_RE = re.compile(r"^[A-Z]{1,2}$")
ISOLATE_ID_RE = re.compile(r"[A-Z]+\d+")


def is_real_layout_value(value: str) -> bool:
    text = str(value).strip()
    return bool(text) and text.casefold() not in {"none", "nan", "n/a", "na"}


def normalize_metadata_dates(metadata: dict[str, str]) -> dict[str, str]:
    """Normalize known date fields; retain unparseable source text explicitly."""

    result = dict(metadata)
    for field in DATE_FIELDS & result.keys():
        raw = result[field].strip()
        if not raw:
            continue
        candidate = raw.replace("_", "-")
        if len(candidate) > 10 and candidate[10] == " ":
            candidate = candidate[:10] + "T" + candidate[11:]
        try:
            validate_date(candidate, context=field)
        except ATSTValidationError:
            parsed = None
            for pattern in (
                "%d/%m/%Y %H:%M:%S",
                "%d/%m/%Y",
                "%d-%b-%Y %H:%M:%S",
                "%d-%b-%Y",
            ):
                try:
                    parsed = datetime.strptime(raw, pattern)  # noqa: DTZ007
                    candidate = (
                        parsed.isoformat() if "%H" in pattern else parsed.date().isoformat()
                    )
                    break
                except ValueError:
                    continue
            if parsed is None:
                result[field + "_source"] = raw
                result[field] = ""
                continue
        result[field] = candidate
    return result
