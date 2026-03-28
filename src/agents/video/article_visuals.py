"""Article visuals helper — fetches images from source article page for video backgrounds."""

import os
import re
from urllib.parse import urljoin, urlparse
import httpx
from src.config import OUTPUT_DIR
from src.audit import log_agent_step, AuditTimer


_META_PATTERNS = [
    r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
    r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',
    r'<meta[^>]+property=["\']og:image:url["\'][^>]+content=["\']([^"\']+)["\']',
]
_IMG_PATTERN = r'<img[^>]+src=["\']([^"\']+)["\']'


def _looks_like_image(url: str) -> bool:
    lower = url.lower()
    return any(ext in lower for ext in [".jpg", ".jpeg", ".png", ".webp", "format=jpg", "format=png"])


async def fetch_article_visuals(
    source_url: str,
    session_id: str = "default",
    max_images: int = 4,
) -> list[str]:
    """Fetch candidate article images and download them locally."""
    if not source_url:
        return []

    visuals_dir = os.path.join(OUTPUT_DIR, "visuals", session_id)
    os.makedirs(visuals_dir, exist_ok=True)

    with AuditTimer() as timer:
        status = "success"
        error = ""
        downloaded: list[str] = []

        try:
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
                html_resp = await client.get(source_url)
                html_resp.raise_for_status()
                html = html_resp.text

                candidates: list[str] = []
                for pattern in _META_PATTERNS:
                    candidates.extend(re.findall(pattern, html, flags=re.IGNORECASE))
                candidates.extend(re.findall(_IMG_PATTERN, html, flags=re.IGNORECASE))

                # Normalize and dedupe while preserving order.
                seen = set()
                normalized = []
                for item in candidates:
                    u = urljoin(source_url, item.strip())
                    if u in seen:
                        continue
                    if not _looks_like_image(u):
                        continue
                    seen.add(u)
                    normalized.append(u)

                for idx, image_url in enumerate(normalized[:max_images]):
                    try:
                        img_resp = await client.get(image_url)
                        img_resp.raise_for_status()
                        suffix = os.path.splitext(urlparse(image_url).path)[1].lower()
                        if suffix not in [".jpg", ".jpeg", ".png", ".webp"]:
                            suffix = ".jpg"
                        out_path = os.path.join(visuals_dir, f"article_{idx+1}{suffix}")
                        with open(out_path, "wb") as f:
                            f.write(img_resp.content)
                        downloaded.append(out_path)
                    except Exception:
                        continue

                if not downloaded:
                    status = "fallback"

        except Exception as e:
            status = "fallback"
            error = str(e)

    log_agent_step(
        agent_name="ArticleVisualFetcher",
        action="fetch_article_visuals",
        model_used="httpx + html meta parse",
        input_summary=f"URL: {source_url[:120]}",
        output_summary=f"Downloaded visuals: {len(downloaded)}",
        latency_ms=timer.elapsed_ms,
        status=status,
        error_detail=error,
        session_id=session_id,
    )

    return downloaded
