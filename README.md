# Metadata Generator

A Streamlit application that automatically extracts and enriches metadata from uploaded files using Azure OpenAI GPT-4o.

Supports both **unstructured** (PDF) and **structured** (CSV / Excel) data, producing a unified metadata output covering technical, business, and governance dimensions.

---

## Features

| | PDF | CSV / Excel |
|---|---|---|
| Technical | pages, word count, reading time, scanned flag | row/column count, null %, uniqueness, per-column type |
| Business | title, summary, tags, domain, language, column descriptions | same |
| Governance | sensitivity classification, PII detection | sensitivity, PII fields |
| Cache | SHA-256 checksum-based (skip LLM on re-upload) | same |

---

## Project Structure

```
metadatagen/
├── app.py                  # Streamlit frontend
├── config.py               # Loads Azure config from .env
├── requirements.txt
├── .env.example            # Environment variable template
├── schema/
│   └── metadata.py         # Pydantic models for unified output
├── utils/
│   ├── type_detector.py    # Routes file to correct pipeline
│   └── cache.py            # SHA-256 file-based result cache
├── extractors/
│   ├── pdf_extractor.py    # PyMuPDF + optional OCR
│   └── table_extractor.py  # pandas + PII column heuristics
└── enrichment/
    └── azure_llm.py        # Azure OpenAI GPT-4o enrichment
```

---

## Prerequisites

- Python 3.10+
- An Azure OpenAI resource with a `gpt-4o` deployment

---

## Setup

**1. Clone the repo**

```bash
git clone https://github.com/lbharoto/metadata_genai.git
cd metadata_genai
```

**2. Install dependencies**

```bash
pip install -r requirements.txt
```

**3. Configure environment**

```bash
cp .env.example .env
```

Edit `.env` with your Azure OpenAI credentials:

```env
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key-here
AZURE_OPENAI_DEPLOYMENT=gpt-4o
AZURE_OPENAI_API_VERSION=2025-01-01-preview
```

**4. Run**

```bash
streamlit run app.py
```

---

## Azure OpenAI Setup (first time)

```bash
# Create the resource
az cognitiveservices account create \
  --name metadatagen-openai \
  --resource-group metadatagen \
  --kind OpenAI \
  --sku S0 \
  --location eastus

# Deploy GPT-4o
az cognitiveservices account deployment create \
  --name metadatagen-openai \
  --resource-group metadatagen \
  --deployment-name gpt-4o \
  --model-name gpt-4o \
  --model-version "2024-11-20" \
  --model-format OpenAI \
  --sku-capacity 10 \
  --sku-name Standard

# Get endpoint and key
az cognitiveservices account show \
  --name metadatagen-openai \
  --resource-group metadatagen \
  --query properties.endpoint

az cognitiveservices account keys list \
  --name metadatagen-openai \
  --resource-group metadatagen
```

---

## Output Schema

```json
{
  "asset": {
    "file_name": "report.pdf",
    "asset_type": "unstructured",
    "subtype": "pdf",
    "size_bytes": 204800,
    "checksum_sha256": "a3f...",
    "pdf": {
      "page_count": 12,
      "word_count": 4200,
      "is_scanned": false,
      "reading_time_min": 21.0
    }
  },
  "business": {
    "title": "Q1 Financial Report",
    "summary": "...",
    "tags": ["finance", "q1", "report"],
    "domain": "finance",
    "language": "en",
    "column_descriptions": { "col_name": "description" }
  },
  "governance": {
    "sensitivity": "confidential",
    "pii_detected": false,
    "pii_fields": []
  },
  "lineage": {
    "ingested_at": "2026-06-30T10:00:00Z",
    "pipeline_version": "1.0.0"
  }
}
```

---

## Optional: OCR for Scanned PDFs

To enable OCR on scanned PDFs, install Tesseract and Poppler, then uncomment in `requirements.txt`:

```
pytesseract>=0.3.13
pdf2image>=1.17.0
```

- **Tesseract**: https://github.com/UB-Mannheim/tesseract/wiki (Windows installer)
- **Poppler**: https://github.com/oschwartz10612/poppler-windows/releases
