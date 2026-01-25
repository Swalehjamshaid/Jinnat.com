# app/audit/links.py
from typing import Dict
from bs4 import BeautifulSoup

def analyze_links(html_docs: Dict[str, str]) -> Dict[str, int]:
    """
    Analyzes internal and external links.
    """
    internal_links = set()
    external_links = set()
    for html in html_docs.values():
        soup = BeautifulSoup(html, "lxml")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("http"):
                external_links.add(href)
            else:
                internal_links.add(href)

    return {
        "internal_links_count": len(internal_links),
        "external_links_count": len(external_links)
    }
