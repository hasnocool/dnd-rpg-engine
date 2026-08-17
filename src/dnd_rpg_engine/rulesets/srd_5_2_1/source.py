# src/dnd_rpg_engine/rulesets/srd_5_2_1/source.py
from __future__ import annotations

import asyncio
from pathlib import Path
from urllib.parse import urlparse

import httpx

from dnd_rpg_engine.rulesets.srd_5_2_1.models import SRDSourceMetadata


OFFICIAL_SRD_SOURCE = SRDSourceMetadata(
    notes={
        "release_page_last_verified": "2026-08-16",
        "license_scope": "SRD content only; D&D Beyond Basic Rules are not an import source",
    }
)


class SRDSourceError(RuntimeError):
    pass


def validate_official_source_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in OFFICIAL_SRD_SOURCE.official_host_allowlist:
        raise SRDSourceError("SRD source must use an allowlisted official HTTPS host")
    lowered = parsed.path.lower()
    if "basic-rules" in lowered or "basic_rules" in lowered:
        raise SRDSourceError("D&D Beyond Basic Rules are not licensed as this project's reusable SRD source")


async def fetch_official_srd_pdf(
    output: str | Path,
    *,
    url: str = OFFICIAL_SRD_SOURCE.pdf_url,
    max_bytes: int = 40_000_000,
) -> Path:
    """Fetch the official SRD PDF without blocking the event loop."""
    validate_official_source_url(url)
    timeout = httpx.Timeout(45.0, connect=15.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        response = await client.get(url, headers={"User-Agent": "dnd-rpg-engine-srd-source/1.1"})
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").lower()
        if "pdf" not in content_type and not response.content.startswith(b"%PDF-"):
            raise SRDSourceError("official SRD source did not return a PDF")
        if len(response.content) > max_bytes:
            raise SRDSourceError("official SRD PDF exceeds configured size limit")
        destination = Path(output)
        await asyncio.to_thread(destination.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(destination.write_bytes, response.content)
        return destination
