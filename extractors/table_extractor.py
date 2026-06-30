from __future__ import annotations

import re
from io import BytesIO

import pandas as pd

from schema.metadata import (
    ColumnProfile,
    TechnicalMetadata,
    TechnicalMetadataTable,
)
from utils.cache import compute_checksum

_PII_COLUMN_KEYWORDS = {
    "email", "phone", "mobile", "contact",
    "ssn", "nric", "ic", "passport",
    "dob", "birth", "birthdate",
    "address", "postcode", "zipcode",
    "salary", "income", "wage",
    "fullname", "full_name", "firstname", "lastname",
    "gender", "race", "religion", "nationality",
}

_PII_PATTERNS = [
    re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"),  # email
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),                             # SSN
    re.compile(r"\b\+?[\d\s\-\(\)]{9,15}\b"),                         # phone
]


def _is_pii(col_name: str, sample: list[str]) -> bool:
    normalized = col_name.lower().replace(" ", "_").replace("-", "_")
    if any(kw in normalized for kw in _PII_COLUMN_KEYWORDS):
        return True
    sample_text = " ".join(sample[:20])
    return any(p.search(sample_text) for p in _PII_PATTERNS)


def _read_df(file_bytes: bytes, subtype: str) -> tuple[pd.DataFrame, list[str] | None, str | None]:
    if subtype == "excel":
        xf = pd.ExcelFile(BytesIO(file_bytes))
        df = pd.read_excel(BytesIO(file_bytes), sheet_name=0)
        return df, xf.sheet_names, None

    for enc in ("utf-8", "latin-1", "cp1252"):
        try:
            df = pd.read_csv(BytesIO(file_bytes), encoding=enc)
            return df, None, enc
        except (UnicodeDecodeError, pd.errors.ParserError):
            continue

    df = pd.read_csv(BytesIO(file_bytes), encoding="utf-8", errors="replace")
    return df, None, "utf-8"


def extract_table_metadata(
    file_bytes: bytes, filename: str, subtype: str
) -> tuple[TechnicalMetadata, str]:
    """Return (TechnicalMetadata, llm_context_string)."""
    checksum = compute_checksum(file_bytes)
    df, sheet_names, encoding = _read_df(file_bytes, subtype)

    total_cells = df.shape[0] * df.shape[1]
    total_nulls = int(df.isnull().sum().sum())
    completeness = 1.0 - (total_nulls / total_cells) if total_cells > 0 else 1.0
    uniqueness = 1.0 - (df.duplicated().sum() / len(df)) if len(df) > 0 else 1.0

    columns: list[ColumnProfile] = []
    for col in df.columns:
        sample = df[col].dropna().head(5).astype(str).tolist()
        col_meta = ColumnProfile(
            name=str(col),
            dtype=str(df[col].dtype),
            null_pct=round(float(df[col].isnull().mean()), 4),
            unique_count=int(df[col].nunique()),
            sample_values=sample,
            pii_suspected=_is_pii(str(col), sample),
        )
        if pd.api.types.is_numeric_dtype(df[col]):
            col_meta.min_value = str(df[col].min())
            col_meta.max_value = str(df[col].max())
        columns.append(col_meta)

    table_meta = TechnicalMetadataTable(
        row_count=len(df),
        column_count=len(df.columns),
        encoding=encoding,
        sheet_names=sheet_names,
        columns=columns,
        completeness_score=round(completeness, 4),
        uniqueness_score=round(uniqueness, 4),
    )

    technical = TechnicalMetadata(
        file_name=filename,
        asset_type="structured",
        subtype=subtype,
        size_bytes=len(file_bytes),
        checksum_sha256=checksum,
        table=table_meta,
    )

    col_lines = "\n".join(
        f"  - {c.name} ({c.dtype}): {c.unique_count} unique, "
        f"{c.null_pct * 100:.1f}% null. "
        f"Sample: {', '.join(c.sample_values[:3])}"
        + (f". Range: {c.min_value} – {c.max_value}" if c.min_value is not None else "")
        for c in columns
    )
    llm_context = (
        f"Filename: {filename}\n"
        f"Rows: {len(df)} | Columns: {len(df.columns)}\n"
        f"Completeness: {completeness * 100:.1f}%\n\n"
        f"Columns:\n{col_lines}"
    )

    return technical, llm_context
