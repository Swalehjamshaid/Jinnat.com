# app/audit/seo.py

from bs4 import BeautifulSoup
from collections import Counter

def analyze_onpage(html_docs: dict[str, str]):
    """
    Detailed SEO analysis of all HTML pages collected by the crawler.
    Analyzes titles, meta descriptions, headers, and images.
    """
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
        
        # 1. Title Tag Analysis
        title_tag = soup.title.string.strip() if soup.title and soup.title.string else None
        if not title_tag:
            metrics['missing_title_tags'] += 1
        else:
            titles.append(title_tag)
            # Standard SEO length recommendations: 10-60 characters
            if len(title_tag) > 60:
                metrics['title_too_long'] += 1
            elif len(title_tag) < 10:
                metrics['title_too_short'] += 1

        # 2. Meta Description Analysis
        md = soup.find('meta', attrs={'name': 'description'})
        if md and md.get('content') and md.get('content').strip():
            metas.append(md['content'].strip())
        else:
            metrics['missing_meta_descriptions'] += 1

        # 3. Heading (H1) Analysis
        h1s = soup.find_all('h1')
        if not h1s:
            metrics['missing_h1'] += 1
        elif len(h1s) > 1:
            metrics['multiple_h1'] += 1

        # 4. Image Alt Attribute Analysis
        for img in soup.find_all('img'):
            # Checks if 'alt' attribute is missing OR explicitly empty
            if not img.get('alt') or not img.get('alt').strip():
                metrics['image_missing_alt'] += 1

    # 5. Duplication Analysis (Using Counter for Efficiency)
    # Counts how many titles/metas appear on more than one page
    title_counts = Counter(titles)
    metrics['duplicate_title_tags'] = sum(1 for text, count in title_counts.items() if count > 1)
    
    meta_counts = Counter(metas)
    metrics['duplicate_meta_descriptions'] = sum(1 for text, count in meta_counts.items() if count > 1)

    return metrics
