from bs4 import BeautifulSoup
from typing import Dict
import requests

def analyze_onpage(html_docs: Dict[str, str]) -> Dict[str, int]:
    metrics = {
        "missing_title": 0,
        "missing_meta_description": 0,
        "missing_h1": 0,
        "images_missing_alt": 0,
        "broken_links": 0
    }

    for url, html in html_docs.items():
        soup = BeautifulSoup(html, "lxml")

        if not soup.title or not soup.title.string.strip():
            metrics["missing_title"] += 1

        if not soup.find("meta", attrs={"name":"description"}):
            metrics["missing_meta_description"] += 1

        if not soup.find("h1"):
            metrics["missing_h1"] += 1

        for img in soup.find_all("img"):
            if not img.get("alt"):
                metrics["images_missing_alt"] += 1

        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("http"):
                try:
                    r = requests.head(href, timeout=5, verify=False)
                    if r.status_code >= 400:
                        metrics["broken_links"] += 1
                except:
                    metrics["broken_links"] += 1

    return metrics
