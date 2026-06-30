import hashlib
import json
from pathlib import Path
from typing import Optional

_CACHE_DIR = Path(".metadata_cache")


def compute_checksum(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()


def cache_get(checksum: str) -> Optional[dict]:
    path = _CACHE_DIR / f"{checksum}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def cache_set(checksum: str, data: dict) -> None:
    _CACHE_DIR.mkdir(exist_ok=True)
    path = _CACHE_DIR / f"{checksum}.json"
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
