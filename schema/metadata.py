from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class TechnicalMetadataPDF(BaseModel):
    page_count: int
    word_count: int
    char_count: int
    is_scanned: bool
    pdf_version: Optional[str] = None
    reading_time_min: float


class ColumnProfile(BaseModel):
    name: str
    dtype: str
    null_pct: float
    unique_count: int
    sample_values: List[str] = []
    pii_suspected: bool = False
    min_value: Optional[str] = None
    max_value: Optional[str] = None


class TechnicalMetadataTable(BaseModel):
    row_count: int
    column_count: int
    encoding: Optional[str] = None
    sheet_names: Optional[List[str]] = None
    columns: List[ColumnProfile]
    completeness_score: float
    uniqueness_score: float


class TechnicalMetadata(BaseModel):
    file_name: str
    asset_type: str   # "unstructured" | "structured"
    subtype: str      # "pdf" | "csv" | "excel"
    size_bytes: int
    checksum_sha256: str
    created_at: Optional[datetime] = None
    modified_at: Optional[datetime] = None
    pdf: Optional[TechnicalMetadataPDF] = None
    table: Optional[TechnicalMetadataTable] = None


class BusinessMetadata(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None
    tags: List[str] = []
    domain: Optional[str] = None
    language: Optional[str] = None
    column_descriptions: Optional[dict] = None   # table only: {col_name: business description}


class GovernanceMetadata(BaseModel):
    sensitivity: Optional[str] = None   # public | internal | confidential | restricted
    pii_detected: bool = False
    pii_fields: List[str] = []


class LineageMetadata(BaseModel):
    ingested_at: datetime
    pipeline_version: str = "1.0.0"


class UnifiedMetadata(BaseModel):
    asset: TechnicalMetadata
    business: BusinessMetadata
    governance: GovernanceMetadata
    lineage: LineageMetadata
