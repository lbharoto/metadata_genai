from pathlib import Path

_STRUCTURED = {
    ".csv": "csv",
    ".xlsx": "excel",
    ".xls": "excel",
}

_UNSTRUCTURED = {
    ".pdf": "pdf",
}


def detect_asset_type(filename: str) -> tuple[str, str]:
    """Return (asset_type, subtype) for the given filename."""
    ext = Path(filename).suffix.lower()
    if ext in _STRUCTURED:
        return "structured", _STRUCTURED[ext]
    if ext in _UNSTRUCTURED:
        return "unstructured", _UNSTRUCTURED[ext]
    return "unknown", "unknown"
