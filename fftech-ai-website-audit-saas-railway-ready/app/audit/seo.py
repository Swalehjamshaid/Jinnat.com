from bs4 import BeautifulSoup
from collections import Counter

def run_seo_audit(crawl_obj):
    """
    CATEGORY C & D: CRAWLABILITY & ON-PAGE SEO (21-75)
    Standardizes SEO data for the international dashboard.
    """
    html_docs = {page.url: page.html for page in crawl_obj.pages if hasattr(page, 'html')}
    raw = analyze_onpage(html_docs)
    
    # Official International Numbering
    metrics = {
        "21_HTTP_2xx": len([p for p in crawl_obj.pages if 200 <= p.get('status_code', 0) < 300]),
        "23_HTTP_4xx": len([p for p in crawl_obj.pages if p.get('status_code') == 404]),
        "41_Missing_Titles": raw['missing_title_tags'],
        "42_Duplicate_Titles": raw['duplicate_title_tags'],
        "49_Missing_H1": raw['missing_h1'],
        "50_Multiple_H1": raw['multiple_h1'],
        "65_Missing_Alt": raw['image_missing_alt']
    }

    # Internal Scoring Logic
    penalty = (raw['missing_title_tags'] * 5) + (raw['missing_h1'] * 2)
    score = max(0, 100 - penalty)

    return {
        "score": round(score, 2),
        "metrics": metrics,
        "color": "#4F46E5"
    }

def analyze_onpage(html_docs: dict[str, str]):
    metrics = {
        'missing_title_tags': 0, 'duplicate_title_tags': 0, 'title_too_long': 0,
        'title_too_short': 0, 'missing_meta_descriptions': 0, 'duplicate_meta_descriptions': 0,
        'missing_h1': 0, 'multiple_h1': 0, 'image_missing_alt': 0,
    }
    titles, metas = [], []
    for url, html in html_docs.items():
        soup = BeautifulSoup(html, 'html.parser')
        title_tag = soup.title.string.strip() if soup.title and soup.title.string else None
        if not title_tag:
            metrics['missing_title_tags'] += 1
        else:
            titles.append(title_tag)
            if len(title_tag) > 60: metrics['title_too_long'] += 1
        
        md = soup.find('meta', attrs={'name':'description'})
        if md and md.get('content'):
            metas.append(md['content'].strip())
        else:
            metrics['missing_meta_descriptions'] += 1
            
        h1s = soup.find_all('h1')
        if not h1s: metrics['missing_h1'] += 1
        if len(h1s) > 1: metrics['multiple_h1'] += 1
        
        for img in soup.find_all('img'):
            if not img.get('alt'): metrics['image_missing_alt'] += 1
            
    metrics['duplicate_title_tags'] = sum(1 for cnt in Counter(titles).values() if cnt > 1)
    metrics['duplicate_meta_descriptions'] = sum(1 for cnt in Counter(metas).values() if cnt > 1)
    return metrics
