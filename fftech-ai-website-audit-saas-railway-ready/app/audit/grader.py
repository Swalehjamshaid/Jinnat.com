import os
import requests
import logging
from typing import Dict, Optional
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import urllib3
import certifi

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

HEADERS = {"User-Agent": "FFTech-AuditBot/2.0 (+https://fftech.ai)"}
TIMEOUT = (10, 25)
PSI_API_KEY: Optional[str] = os.getenv("PSI_API_KEY")


class WebsiteGrader:
    """Class-based website grader with SSL fallback and PSI support"""

    def __init__(self):
        self.headers = HEADERS
        self.timeout = TIMEOUT
        self.psi_key = PSI_API_KEY

    def fetch_page(self, url: str) -> requests.Response:
        """Fetch page with SSL verification, fallback to verify=False"""
        try:
            resp = requests.get(url, headers=self.headers, timeout=self.timeout, allow_redirects=True, verify=certifi.where())
            resp.raise_for_status()
            return resp
        except requests.exceptions.SSLError as ssl_err:
            logger.warning(f"SSL failed for {url}: {ssl_err}, using fallback verify=False")
            resp = requests.get(url, headers=self.headers, timeout=self.timeout, allow_redirects=True, verify=False)
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            logger.error(f"Request failed for {url}: {e}")
            raise

    def analyze_seo(self, html: str) -> Dict:
        soup = BeautifulSoup(html, "html.parser")
        score = 100
        metrics = {}

        title = soup.title.string.strip() if soup.title and soup.title.string else None
        metrics["title_present"] = bool(title)
        if not title: score -= 15
        elif len(title) < 10 or len(title) > 70: score -= 5

        meta_tag = soup.find("meta", attrs={"name": "description"})
        meta_desc = meta_tag["content"].strip() if meta_tag and meta_tag.get("content") else None
        metrics["meta_description_present"] = bool(meta_desc)
        if not meta_desc: score -= 15
        elif len(meta_desc) < 50 or len(meta_desc) > 160: score -= 3

        h1_tags = soup.find_all("h1")
        metrics["h1_count"] = len(h1_tags)
        if len(h1_tags) != 1: score -= 10

        canonical = soup.find("link", rel="canonical")
        metrics["canonical_present"] = bool(canonical)
        if not canonical: score -= 5

        images = soup.find_all("img")
        if images:
            missing_alt = sum(1 for img in images if not img.get("alt") or not img["alt"].strip())
            metrics["images_missing_alt_count"] = missing_alt
            metrics["images_total"] = len(images)
            if missing_alt / len(images) > 0.25: score -= 10
        else:
            metrics["images_missing_alt_count"] = 0

        return {"score": max(score, 0), "metrics": metrics, "color": "#22C55E" if score >= 80 else "#F59E0B" if score >= 50 else "#EF4444"}

    def analyze_security(self, url: str, response: requests.Response) -> Dict:
        score = 100
        metrics = {}
        parsed = urlparse(response.url)
        metrics["https"] = parsed.scheme == "https"
        if not metrics["https"]: score -= 40

        headers_lower = {k.lower() for k in response.headers}
        check_headers = ["content-security-policy","x-frame-options","strict-transport-security","x-content-type-options","referrer-policy","permissions-policy"]
        missing = [h for h in check_headers if h not in headers_lower]
        metrics["missing_security_headers"] = missing
        score -= len(missing) * 7

        metrics["redirect_chain_length"] = len(response.history)
        if len(response.history) > 2: score -= 10

        return {"score": max(score, 0), "metrics": metrics, "color": "#0EA5E9" if score >= 80 else "#EF4444"}

    def analyze_content(self, html: str) -> Dict:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script","style","nav","footer","header","noscript"]): tag.decompose()
        text = soup.get_text(separator=" ", strip=True)
        words = len(text.split())
        score = 100
        metrics = {"word_count": words}
        if words < 300: score -= 50
        elif words < 600: score -= 30
        elif words < 1000: score -= 15
        return {"score": max(score,0), "metrics": metrics, "color": "#10B981" if score >= 70 else "#F59E0B"}

    def analyze_i18n(self, html: str) -> Dict:
        soup = BeautifulSoup(html, "html.parser")
        hreflangs = soup.find_all("link", rel="alternate", hreflang=True)
        x_default = any(link.get("hreflang")=="x-default" for link in hreflangs)
        count = len(hreflangs)
        score = 95 if count>=2 and x_default else (80 if count>=1 else 50)
        return {"score": score, "metrics":{"hreflang_count":count,"has_x_default":x_default}, "color": "#6366F1" if score>=80 else "#F97316"}

    def analyze_performance(self, url: str) -> Dict:
        try:
            psi_url = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
            params = {"url":url, "strategy":"mobile"}
            if self.psi_key: params["key"]=self.psi_key
            res = requests.get(psi_url, params=params, timeout=self.timeout)
            res.raise_for_status()
            data = res.json()
            perf = data["lighthouseResult"]["categories"]["performance"]
            audits = data["lighthouseResult"]["audits"]
            score = round(perf["score"]*100)
            metrics = {
                "lcp_ms": audits.get("largest-contentful-paint", {}).get("numericValue"),
                "cls": audits.get("cumulative-layout-shift", {}).get("numericValue"),
                "inp_ms": audits.get("interaction-to-next-paint", {}).get("numericValue") or audits.get("max-potential-fid", {}).get("numericValue")
            }
            return {"score":score, "metrics":metrics, "color": "#3B82F6" if score>=90 else "#10B981" if score>=50 else "#EF4444"}
        except requests.HTTPError as e:
            note = "PageSpeed rate-limited (API key required)" if e.response and e.response.status_code==429 else "PageSpeed unavailable"
            logger.warning(f"PSI failed for {url}: {note}")
            return {"score":60, "metrics":{"note":note}, "color":"#94A3B8"}

    def calculate_overall_score(self, cats: Dict) -> float:
        return round(
            cats["Performance"]["score"]*0.35 +
            cats["SEO"]["score"]*0.25 +
            cats["Security"]["score"]*0.2 +
            cats["Content Quality"]["score"]*0.1 +
            cats["Internationalization"]["score"]*0.1, 2
        )

    def assign_grade(self, score: float) -> str:
        if score>=90: return "A+"
        if score>=85: return "A"
        if score>=75: return "B+"
        if score>=65: return "B"
        if score>=50: return "C"
        return "F"

    async def run_full_audit(self, url: str) -> Dict:
        """Async wrapper for FastAPI"""
        try:
            response = self.fetch_page(url)
            html = response.text
            categories = {
                "Performance": self.analyze_performance(url),
                "SEO": self.analyze_seo(html),
                "Security": self.analyze_security(url,response),
                "Content Quality": self.analyze_content(html),
                "Internationalization": self.analyze_i18n(html)
            }
            overall = self.calculate_overall_score(categories)
            return {
                "url": response.url,
                "overall_score": overall,
                "grade": self.assign_grade(overall),
                "categories": categories,
                "competitors": []
            }
        except Exception as e:
            logger.exception(f"AUDIT FAILED for {url}: {e}")
            return {"url": url, "overall_score":0,"grade":"N/A","categories":{},"competitors":[],"error":str(e)}
