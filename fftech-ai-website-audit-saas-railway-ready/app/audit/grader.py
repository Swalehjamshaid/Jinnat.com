# fftech-ai-website-audit-saas-railway-ready/app/audit/grader.py

"""
Standalone page grader for FFTech AI Website Audit.
Analyzes a single HTML document and computes SEO / Performance / Security / Content scores.
Returns a nested breakdown suitable for dashboards or reports.
"""

import re
from typing import Dict
from bs4 import BeautifulSoup
from urllib.parse import urlparse


def grade_website(html: str, url: str) -> Dict:
    soup = BeautifulSoup(html, 'html.parser')
    breakdown = {}

    # ---------------------
    # 1) SEO Score
    # ---------------------
    title = soup.title.string.strip() if soup.title and soup.title.string else ''
    meta_desc_tag = soup.find('meta', attrs={'name': 'description'})
    meta_desc = meta_desc_tag['content'].strip() if meta_desc_tag and meta_desc_tag.get('content') else ''
    h1_tags = soup.find_all('h1')
    images = soup.find_all('img')
    images_without_alt = [img for img in images if not img.get('alt')]

    seo_score = 0
    seo_issues = []

    if title:
        seo_score += 15
    else:
        seo_issues.append('Missing <title> tag')

    if meta_desc:
        seo_score += 15
    else:
        seo_issues.append('Missing meta description')

    if len(h1_tags) == 1:
        seo_score += 10
    elif len(h1_tags) == 0:
        seo_issues.append('No H1 tag found')
    else:
        seo_issues.append('Multiple H1 tags found')

    if images:
        alt_ratio = (len(images) - len(images_without_alt)) / len(images)
        seo_score += int(10 * alt_ratio)
        if images_without_alt:
            seo_issues.append(f'{len(images_without_alt)} images missing alt attributes')
    else:
        seo_score += 5  # small score for pages without images

    breakdown['seo'] = {'score': seo_score, 'issues': seo_issues}

    # ---------------------
    # 2) Performance Score (DOM heuristics only)
    # ---------------------
    scripts = soup.find_all('script')
    stylesheets = soup.find_all('link', rel='stylesheet')
    perf_score = 100
    perf_issues = []

    if len(scripts) > 20:
        perf_score -= 15
        perf_issues.append('Too many JavaScript files (>20)')
    if len(stylesheets) > 10:
        perf_score -= 10
        perf_issues.append('Too many CSS files (>10)')
    if not soup.find('meta', attrs={'name': 'viewport'}):
        perf_score -= 15
        perf_issues.append('Missing viewport meta tag for responsive design')

    breakdown['performance'] = {'score': max(perf_score, 0), 'issues': perf_issues}

    # ---------------------
    # 3) Security Score
    # ---------------------
    parsed = urlparse(url)
    security_score = 0
    security_issues = []

    if parsed.scheme == 'https':
        security_score += 30
    else:
        security_issues.append('Website is not using HTTPS')

    if soup.find('meta', attrs={'http-equiv': 'Content-Security-Policy'}):
        security_score += 20
    else:
        security_issues.append('Missing Content Security Policy')

    if soup.find('meta', attrs={'http-equiv': 'X-Frame-Options'}):
        security_score += 10
    else:
        security_issues.append('Missing X-Frame-Options')

    breakdown['security'] = {'score': security_score, 'issues': security_issues}

    # ---------------------
    # 4) Content Score
    # ---------------------
    text = soup.get_text(separator=' ')
    words = re.findall(r'\w+', text)  # fixed word counting regex

    content_score = 0
    content_issues = []

    if len(words) > 300:
        content_score += 30
    else:
        content_issues.append('Low text content on page (<300 words)')

    internal_links = [
        a for a in soup.find_all('a', href=True)
        if urlparse(a['href']).netloc == parsed.netloc
    ]

    if len(internal_links) >= 5:
        content_score += 20
    else:
        content_issues.append(f'Low internal linking ({len(internal_links)} internal links)')

    breakdown['content'] = {'score': content_score, 'issues': content_issues}

    # ---------------------
    # Total Score and Grade
    # ---------------------
    total_score = (
        breakdown['seo']['score'] +
        breakdown['performance']['score'] +
        breakdown['security']['score'] +
        breakdown['content']['score']
    )

    total_score = min(int(total_score / 4), 100)  # normalize to 100

    if total_score >= 90:
        grade = 'A+'
    elif total_score >= 80:
        grade = 'A'
    elif total_score >= 70:
        grade = 'B'
    elif total_score >= 60:
        grade = 'C'
    else:
        grade = 'D'

    return {
        'overall_score': total_score,
        'grade': grade,
        'breakdown': breakdown,
    }
