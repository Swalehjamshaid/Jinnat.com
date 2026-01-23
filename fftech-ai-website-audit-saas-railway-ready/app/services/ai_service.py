# app/services/ai_service.py

from typing import Any, Dict, List
import requests
import logging

logger = logging.getLogger(__name__)

class AIService:
    """
    AIService handles communication with external AI or data analysis services.
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.exampleai.com/v1"  # replace with actual AI service URL

    def analyze_website(self, website_url: str) -> Dict[str, Any]:
        """
        Sends a website URL to the AI service and returns analysis results.
        """
        try:
            response = requests.post(
                f"{self.base_url}/analyze",
                json={"url": website_url},
                headers={"Authorization": f"Bearer {self.api_key}"}
            )
            response.raise_for_status()
            data = response.json()
            return data
        except requests.RequestException as e:
            logger.error(f"Website analysis failed: {e}")
            return {"error": str(e)}

    def summarize_content(self, text: str) -> str:
        """
        Summarizes a large text using the AI service.
        """
        try:
            response = requests.post(
                f"{self.base_url}/summarize",
                json={"text": text},
                headers={"Authorization": f"Bearer {self.api_key}"}
            )
            response.raise_for_status()
            return response.json().get("summary", "")
        except requests.RequestException as e:
            logger.error(f"Text summarization failed: {e}")
            return ""

    def evaluate_metrics(self, metrics: Dict[str, Any]) -> Dict[str, float]:
        """
        Evaluates website metrics using the AI service.
        """
        try:
            response = requests.post(
                f"{self.base_url}/evaluate",
                json={"metrics": metrics},
                headers={"Authorization": f"Bearer {self.api_key}"}
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Metrics evaluation failed: {e}")
            return {}

    def batch_process(self, urls: List[str]) -> List[Dict[str, Any]]:
        """
        Processes a batch of website URLs.
        """
        results = []
        for url in urls:
            analysis = self.analyze_website(url)
            results.append({"url": url, "analysis": analysis})
        return results
