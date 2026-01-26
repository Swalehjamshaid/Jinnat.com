
from typing import Dict
from bs4 import BeautifulSoup

def analyze_links(html_docs: Dict[str, str]) -> Dict[str, int]:
    """Very simple internal/external link counter from a set of HTML docs."""
    internal, external = set(), set()
    for html in html_docs.values():
        soup = BeautifulSoup(html, 'lxml')
        for a in soup.find_all('a', href=True):
            href = a['href']
            if href.startswith('http'):
                external.add(href)
            else:
                internal.add(href)
    return {'internal_links_count': len(internal), 'external_links_count': len(external)}
