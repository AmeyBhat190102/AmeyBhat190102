"""Deterministic layout engine: HTML/CSS in, print-grade pixels out.

Why this exists: diffusion models still garble small type, and a business
card is *all* small type. So agents design layouts as code (HTML/CSS is the
best-understood layout language any LLM speaks), and Chromium renders them
exactly. Generated imagery enters only as background/motif layers under the
type. PDF output is sized in physical mm for the print house.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from playwright.async_api import async_playwright

# Print target: 300dpi. CSS px are 96/inch, so scale factor ≈ 3.125.
_PRINT_SCALE = 300 / 96
_MM_TO_CSS_PX = 96 / 25.4


def _chromium_executable() -> str | None:
    """Honor AURA_CHROMIUM, else fall back to a preinstalled Playwright
    browser tree (e.g. /opt/pw-browsers) when the pip-installed Playwright
    pins a build revision that isn't downloaded."""
    if explicit := os.getenv("AURA_CHROMIUM"):
        return explicit
    root = os.getenv("PLAYWRIGHT_BROWSERS_PATH")
    if root:
        for pattern in ("chromium-*/chrome-linux/chrome",
                        "chromium_headless_shell-*/chrome-linux/headless_shell"):
            for hit in sorted(Path(root).glob(pattern), reverse=True):
                return str(hit)
    return None  # let Playwright resolve its own managed browser


class PlaywrightRenderer:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._executable = _chromium_executable()

    async def render_png(self, *, html: str, width_px: int, height_px: int) -> bytes:
        async with self._lock, async_playwright() as p:
            browser = await p.chromium.launch(executable_path=self._executable)
            try:
                # Viewport at CSS scale, device_scale_factor recovers print
                # density; dimensions must keep the artifact's exact aspect.
                page = await browser.new_page(
                    viewport={"width": round(width_px / 3), "height": round(height_px / 3)},
                    device_scale_factor=3,
                )
                await page.set_content(html, wait_until="networkidle")
                return await page.screenshot(type="png", full_page=False)
            finally:
                await browser.close()

    async def render_pdf(self, *, html: str, width_mm: float, height_mm: float) -> bytes:
        async with self._lock, async_playwright() as p:
            browser = await p.chromium.launch(executable_path=self._executable)
            try:
                page = await browser.new_page(viewport={
                    "width": int(width_mm * _MM_TO_CSS_PX),
                    "height": int(height_mm * _MM_TO_CSS_PX),
                })
                await page.set_content(html, wait_until="networkidle")
                await page.emulate_media(media="print")
                return await page.pdf(
                    width=f"{width_mm}mm", height=f"{height_mm}mm",
                    print_background=True, page_ranges="1",
                )
            finally:
                await browser.close()


def png_dimensions_for(width_mm: float, height_mm: float) -> tuple[int, int]:
    """Preview PNG dimensions at print density for a physical artifact."""
    return (int(width_mm * _MM_TO_CSS_PX * _PRINT_SCALE),
            int(height_mm * _MM_TO_CSS_PX * _PRINT_SCALE))
