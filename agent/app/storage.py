"""Where PDFs live: Supabase Storage (real) or a local folder (dev/tests)."""

from __future__ import annotations

from pathlib import Path

import httpx

from app.config import get_settings


class StorageError(RuntimeError):
    pass


def _safe_local_path(path: str) -> Path:
    root = get_settings().local_storage_path.resolve()
    full = (root / path).resolve()
    if root not in full.parents:
        raise StorageError("Invalid storage path")
    return full


def _supabase(method: str, url_path: str, **kwargs) -> httpx.Response:
    s = get_settings()
    if not s.supabase_url or not s.supabase_service_role_key:
        raise StorageError("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY for Supabase Storage")
    headers = {
        "Authorization": f"Bearer {s.supabase_service_role_key}",
        "apikey": s.supabase_service_role_key,
        **kwargs.pop("headers", {}),
    }
    url = f"{s.supabase_url.rstrip('/')}/storage/v1/{url_path}"
    r = httpx.request(method, url, headers=headers, timeout=120, **kwargs)
    if r.status_code >= 400:
        raise StorageError(f"Supabase Storage {method} failed ({r.status_code}): {r.text[:300]}")
    return r


def upload(path: str, data: bytes, content_type: str = "application/pdf") -> None:
    s = get_settings()
    if s.storage_backend == "local":
        full = _safe_local_path(path)
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_bytes(data)
        return
    _supabase(
        "POST",
        f"object/{s.storage_bucket}/{path}",
        content=data,
        headers={"Content-Type": content_type, "x-upsert": "true"},
    )


def download(path: str) -> bytes:
    s = get_settings()
    if s.storage_backend == "local":
        full = _safe_local_path(path)
        if not full.exists():
            raise StorageError(f"File not found: {path}")
        return full.read_bytes()
    return _supabase("GET", f"object/{s.storage_bucket}/{path}").content


def delete(path: str) -> None:
    s = get_settings()
    if s.storage_backend == "local":
        full = _safe_local_path(path)
        full.unlink(missing_ok=True)
        return
    _supabase("DELETE", f"object/{s.storage_bucket}", json={"prefixes": [path]})
