from bs4 import BeautifulSoup
from collections import Counter
from typing import Union, Dict

def analyze_onpage(html_docs: Union[Dict[str, str], str]) -> dict:
    """
    Detailed SEO analysis of all HTML pages collected by the crawler.
    Evaluates:
      - Title tags (missing, duplicate, length issues)
      - Meta descriptions (missing, duplicate)
      - H1 tags (missing, multiple)
      - Image alt attributes (missing)
    Returns a metrics dictionary summarizing the SEO health.
    """
    # If a single HTML string is passed, wrap it in a dict
    if isinstance(html_docs, str):
        html_docs = {"single_url": html_docs}

    metrics = {
        'missing_title_tags': 0,
        'duplicate_title_tags': 0,
        'title_too_long': 0,
        'title_too_short': 0,
        'missing_meta_descriptions': 0,
        'duplicate_meta_descriptions': 0,
        'missing_h1': 0,
        'multiple_h1': 0,
        'image_missing_alt': 0,
    }

    titles = []
    metas = []

    for url, html in html_docs.items():
        soup = BeautifulSoup(html, 'html.parser')

        # 1️⃣ Title Tag Analysis
        title_tag = soup.title.string.strip() if soup.title and soup.title.string else None
        if not title_tag:
            metrics['missing_title_tags'] += 1
        else:
            titles.append(title_tag)
            if len(title_tag) > 60:
                metrics['title_too_long'] += 1
            elif len(title_tag) < 10:
                metrics['title_too_short'] += 1

        # 2️⃣ Meta Description Analysis
        md = soup.find('meta', attrs={'name': 'description'})
        if md and md.get('content') and md.get('content').strip():
            metas.append(md['content'].strip())
        else:
            metrics['missing_meta_descriptions'] += 1

        # 3️⃣ H1 Tag Analysis
        h1s = soup.find_all('h1')
        if not h1s:
            metrics['missing_h1'] += 1
        elif len(h1s) > 1:
            metrics['multiple_h1'] += 1

        # 4️⃣ Image Alt Attribute Analysis
        for img in soup.find_all('img'):
            if not img.get('alt') or not img.get('alt').strip():
                metrics['image_missing_alt'] += 1

    # 5️⃣ Duplicate Analysis using Counter
    title_counts = Counter(titles)
    metrics['duplicate_title_tags'] = sum(1 for text, count in title_counts.items() if count > 1)

    meta_counts = Counter(metas)
    metrics['duplicate_meta_descriptions'] = sum(1 for text, count in meta_counts.items() if count > 1)

    return metrics
