from __future__ import annotations

import json
import re

from openai import AzureOpenAI

from schema.metadata import BusinessMetadata, GovernanceMetadata

_PDF_SYSTEM = """\
You are a metadata extraction expert. Given document text, return a JSON object with exactly these keys:
- title (string): inferred document title
- summary (string): 2-3 sentence summary
- tags (array of strings): 5-8 relevant keywords
- domain (string): one of finance, hr, legal, operations, marketing, technology, other
- language (string): ISO 639-1 code e.g. "en"
- sensitivity (string): one of public, internal, confidential, restricted
- pii_detected (boolean): whether personally identifiable information is present
- pii_fields (array of strings): descriptions of PII found, empty array if none
Return only valid JSON. No markdown fences."""

_TABLE_SYSTEM = """\
You are a metadata extraction expert. Given a structured dataset summary, return a JSON object with exactly these keys:
- title (string): inferred table or dataset name
- summary (string): 2-3 sentences describing what this dataset represents
- tags (array of strings): 5-8 relevant keywords
- domain (string): one of finance, hr, sales, operations, marketing, technology, other
- sensitivity (string): one of public, internal, confidential, restricted
- pii_detected (boolean): whether PII columns are likely present
- pii_fields (array of strings): column names that likely contain PII
- column_descriptions (object): mapping of every column name to a one-line description
Return only valid JSON. No markdown fences."""


def _parse(raw: str) -> dict:
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return json.loads(cleaned)


def _client(cfg: dict) -> AzureOpenAI:
    return AzureOpenAI(
        azure_endpoint=cfg["endpoint"],
        api_key=cfg["api_key"],
        api_version=cfg.get("api_version", "2024-10-21"),
    )


def enrich_pdf(
    text: str, filename: str, azure_cfg: dict
) -> tuple[BusinessMetadata, GovernanceMetadata]:
    client = _client(azure_cfg)
    resp = client.chat.completions.create(
        model=azure_cfg["deployment"],
        messages=[
            {"role": "system", "content": _PDF_SYSTEM},
            {"role": "user", "content": f"Filename: {filename}\n\nText:\n{text[:3500]}"},
        ],
        temperature=0.1,
        max_tokens=900,
    )
    data = _parse(resp.choices[0].message.content)
    business = BusinessMetadata(
        title=data.get("title"),
        summary=data.get("summary"),
        tags=data.get("tags", []),
        domain=data.get("domain"),
        language=data.get("language"),
    )
    governance = GovernanceMetadata(
        sensitivity=data.get("sensitivity"),
        pii_detected=data.get("pii_detected", False),
        pii_fields=data.get("pii_fields", []),
    )
    return business, governance


def enrich_table(
    context: str, filename: str, azure_cfg: dict
) -> tuple[BusinessMetadata, GovernanceMetadata]:
    client = _client(azure_cfg)
    resp = client.chat.completions.create(
        model=azure_cfg["deployment"],
        messages=[
            {"role": "system", "content": _TABLE_SYSTEM},
            {"role": "user", "content": context},
        ],
        temperature=0.1,
        max_tokens=1200,
    )
    data = _parse(resp.choices[0].message.content)
    business = BusinessMetadata(
        title=data.get("title"),
        summary=data.get("summary"),
        tags=data.get("tags", []),
        domain=data.get("domain"),
        column_descriptions=data.get("column_descriptions"),
    )
    governance = GovernanceMetadata(
        sensitivity=data.get("sensitivity"),
        pii_detected=data.get("pii_detected", False),
        pii_fields=data.get("pii_fields", []),
    )
    return business, governance
