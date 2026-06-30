from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

import config
from enrichment.azure_llm import enrich_pdf, enrich_table
from extractors.pdf_extractor import extract_pdf_metadata
from extractors.table_extractor import extract_table_metadata
from schema.metadata import (
    BusinessMetadata,
    GovernanceMetadata,
    LineageMetadata,
    UnifiedMetadata,
)
from utils.cache import cache_get, cache_set, compute_checksum
from utils.type_detector import detect_asset_type

st.set_page_config(
    page_title="Metadata Generator",
    page_icon="🗂️",
    layout="wide",
)

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ Configuration")
    use_cache = st.toggle("Cache results by file checksum", value=True)
    skip_llm = st.toggle("Technical metadata only (skip LLM)", value=False)

    if not config.AZURE_OPENAI_API_KEY:
        st.warning("AZURE_OPENAI_API_KEY is not set in .env — LLM enrichment will be skipped.")

# ── Header ─────────────────────────────────────────────────────────────────────
st.title("🗂️ Metadata Generator")
st.caption(
    "Upload a **PDF** (unstructured) or **CSV / Excel** (structured) file "
    "to generate unified technical, business, and governance metadata."
)

# ── File upload ────────────────────────────────────────────────────────────────
uploaded = st.file_uploader(
    "Drop a file here",
    type=["pdf", "csv", "xlsx", "xls"],
    label_visibility="collapsed",
)

if not uploaded:
    st.info("Supported: PDF · CSV · Excel (.xlsx / .xls)")
    st.stop()

col_fn, col_sz, col_btn = st.columns([3, 1, 1])
col_fn.write(f"📄 **{uploaded.name}**")
col_sz.write(f"`{uploaded.size:,}` bytes")
run = col_btn.button("Generate", type="primary", use_container_width=True)

if not run:
    st.stop()

# ── Processing ─────────────────────────────────────────────────────────────────
file_bytes = uploaded.read()
checksum = compute_checksum(file_bytes)
asset_type, subtype = detect_asset_type(uploaded.name)

if asset_type == "unknown":
    st.error(f"Unsupported file type: `{Path(uploaded.name).suffix}`")
    st.stop()

from_cache = False
result: dict = {}

if use_cache:
    cached = cache_get(checksum)
    if cached:
        st.success("Loaded from cache — file unchanged since last run.")
        result = cached
        from_cache = True

if not from_cache:
    llm_context = ""
    with st.status("Extracting technical metadata…", expanded=True) as status:
        try:
            if subtype == "pdf":
                technical, llm_context = extract_pdf_metadata(file_bytes, uploaded.name)
            else:
                technical, llm_context = extract_table_metadata(file_bytes, uploaded.name, subtype)
            status.update(label="Technical metadata extracted ✅", state="complete")
        except Exception as exc:
            status.update(label=f"Extraction failed: {exc}", state="error")
            st.stop()

    business = BusinessMetadata()
    governance = GovernanceMetadata()

    if not skip_llm and config.AZURE_OPENAI_API_KEY:
        with st.status("Enriching with Azure OpenAI GPT-4o…", expanded=True) as status:
            try:
                azure_cfg = {
                    "endpoint": config.AZURE_OPENAI_ENDPOINT,
                    "api_key": config.AZURE_OPENAI_API_KEY,
                    "deployment": config.AZURE_OPENAI_DEPLOYMENT,
                    "api_version": config.AZURE_OPENAI_API_VERSION,
                }
                if subtype == "pdf":
                    business, governance = enrich_pdf(llm_context, uploaded.name, azure_cfg)
                else:
                    business, governance = enrich_table(llm_context, uploaded.name, azure_cfg)
                status.update(label="LLM enrichment complete ✅", state="complete")
            except Exception as exc:
                status.update(label=f"LLM enrichment failed: {exc}", state="error")
                st.warning("Displaying technical metadata only.")

    lineage = LineageMetadata(ingested_at=datetime.now(timezone.utc))
    unified = UnifiedMetadata(
        asset=technical,
        business=business,
        governance=governance,
        lineage=lineage,
    )
    result = json.loads(unified.model_dump_json())
    if use_cache:
        cache_set(checksum, result)

# ── Results ────────────────────────────────────────────────────────────────────
st.divider()
tab_tech, tab_biz, tab_gov, tab_raw = st.tabs(
    ["🔧 Technical", "📊 Business", "🛡️ Governance", "{ } Raw JSON"]
)

asset = result["asset"]
biz = result.get("business", {})
gov = result.get("governance", {})
lineage_data = result.get("lineage", {})

# ── Technical tab ──────────────────────────────────────────────────────────────
with tab_tech:
    c1, c2, c3 = st.columns(3)
    c1.metric("Type", f"{asset['asset_type']} / {asset['subtype']}")
    c2.metric("Size", f"{asset['size_bytes']:,} B")
    c3.metric("SHA-256", asset["checksum_sha256"][:16] + "…")

    if asset["subtype"] == "pdf" and asset.get("pdf"):
        p = asset["pdf"]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Pages", p["page_count"])
        c2.metric("Words", f"{p['word_count']:,}")
        c3.metric("Reading time", f"{p['reading_time_min']} min")
        c4.metric("Scanned / OCR", "Yes" if p["is_scanned"] else "No")
        if p.get("pdf_version"):
            st.caption(f"PDF version: {p['pdf_version']}")

    elif asset.get("table"):
        t = asset["table"]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Rows", f"{t['row_count']:,}")
        c2.metric("Columns", t["column_count"])
        c3.metric("Completeness", f"{t['completeness_score'] * 100:.1f}%")
        c4.metric("Uniqueness", f"{t['uniqueness_score'] * 100:.1f}%")

        if t.get("sheet_names"):
            st.write(f"**Sheets:** {', '.join(t['sheet_names'])}")
        if t.get("encoding"):
            st.caption(f"Detected encoding: {t['encoding']}")

        if t.get("columns"):
            rows = []
            for c in t["columns"]:
                row = {
                    "Column": c["name"],
                    "Type": c["dtype"],
                    "Null %": f"{c['null_pct'] * 100:.1f}%",
                    "Unique": c["unique_count"],
                    "PII": "⚠️" if c["pii_suspected"] else "—",
                    "Sample values": ", ".join(c.get("sample_values", [])[:3]),
                }
                if c.get("min_value") is not None:
                    row["Min"] = c["min_value"]
                    row["Max"] = c["max_value"]
                rows.append(row)
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

# ── Business tab ───────────────────────────────────────────────────────────────
with tab_biz:
    if not any([biz.get("title"), biz.get("summary"), biz.get("tags")]):
        st.info("No business metadata — enable LLM enrichment and provide Azure credentials.")
    else:
        if biz.get("title"):
            st.subheader(biz["title"])
        if biz.get("summary"):
            st.write(biz["summary"])
        col_left, col_right = st.columns(2)
        with col_left:
            if biz.get("domain"):
                st.write(f"**Domain:** `{biz['domain']}`")
            if biz.get("language"):
                st.write(f"**Language:** `{biz['language']}`")
        with col_right:
            if biz.get("tags"):
                st.write("**Tags:**")
                st.markdown("  ".join(f"`{t}`" for t in biz["tags"]))

        if biz.get("column_descriptions"):
            st.divider()
            st.write("**Column Descriptions**")
            col_desc_rows = [
                {"Column": col, "Description": desc}
                for col, desc in biz["column_descriptions"].items()
            ]
            st.dataframe(pd.DataFrame(col_desc_rows), use_container_width=True, hide_index=True)

# ── Governance tab ─────────────────────────────────────────────────────────────
with tab_gov:
    sensitivity = (gov.get("sensitivity") or "unknown").lower()
    _emoji = {"public": "🟢", "internal": "🔵", "confidential": "🟠", "restricted": "🔴"}
    st.markdown(
        f"### {_emoji.get(sensitivity, '⚪')} Sensitivity: **{sensitivity.upper()}**"
    )

    pii = gov.get("pii_detected", False)
    st.write(f"**PII Detected:** {'⚠️ Yes' if pii else '✅ No'}")

    if gov.get("pii_fields"):
        st.write("**PII Fields:** " + ", ".join(f"`{f}`" for f in gov["pii_fields"]))

    st.divider()
    if lineage_data.get("ingested_at"):
        st.write(f"**Ingested at:** {lineage_data['ingested_at']}")
    st.write(f"**Pipeline version:** {lineage_data.get('pipeline_version', '1.0.0')}")

# ── Raw JSON tab ───────────────────────────────────────────────────────────────
with tab_raw:
    st.json(result)
    st.download_button(
        label="⬇️ Download JSON",
        data=json.dumps(result, indent=2, default=str),
        file_name=f"{Path(uploaded.name).stem}_metadata.json",
        mime="application/json",
    )
