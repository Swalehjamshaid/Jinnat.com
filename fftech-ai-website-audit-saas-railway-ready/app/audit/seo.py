# app/audit/seo.py
from typing import Dict, Any
from bs4 import BeautifulSoup


def summarize_basic_seo(html: str) -> Dict[str, Any]:
    """
    Extracts basic SEO signals: title, h1 count, meta description presence.
    """
    soup = BeautifulSoup(html or "", "html.parser")
    title = (soup.title.string.strip() if soup.title and soup.title.string else "")
    h1_tags = soup.find_all("h1")
    meta_desc = soup.find("meta", attrs={"name": "description"})
    meta_desc_ok = bool(meta_desc and meta_desc.get("content"))

    has_title = 1 if title else 0
    has_h1 = 1 if h1_tags else 0

    seo_score = (has_title * 50) + (has_h1 * 50)

    return {
        "title": title,
        "h1_count": len(h1_tags),
        "has_meta_description": meta_desc_ok,
        "seo_score": seo_score,
    }
