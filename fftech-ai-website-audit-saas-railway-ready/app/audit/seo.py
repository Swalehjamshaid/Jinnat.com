
from bs4 import BeautifulSoup
from collections import Counter

def analyze_onpage(html_docs: dict[str, str]):
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
        title_tag = soup.title.string.strip() if soup.title and soup.title.string else None
        if not title_tag:
            metrics['missing_title_tags'] += 1
        else:
            titles.append(title_tag)
            if len(title_tag) > 60:
                metrics['title_too_long'] += 1
            if len(title_tag) < 10:
                metrics['title_too_short'] += 1
        md = soup.find('meta', attrs={'name':'description'})
        if md and md.get('content'):
            metas.append(md['content'].strip())
        else:
            metrics['missing_meta_descriptions'] += 1
        h1s = soup.find_all('h1')
        if not h1s:
            metrics['missing_h1'] += 1
        if len(h1s) > 1:
            metrics['multiple_h1'] += 1
        for img in soup.find_all('img'):
            if not img.get('alt'):
                metrics['image_missing_alt'] += 1
    c = Counter(titles)
    metrics['duplicate_title_tags'] = sum(1 for _t, cnt in c.items() if cnt > 1)
    c2 = Counter(metas)
    metrics['duplicate_meta_descriptions'] = sum(1 for _t, cnt in c2.items() if cnt > 1)
    return metrics
