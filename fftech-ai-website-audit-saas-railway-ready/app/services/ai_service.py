import os
import logging
from typing import Optional
import google.generativeai as genai

logger = logging.getLogger("AIService")

class AIService:
    def __init__(self):
        # SYNCED with your Railway Variable
        self.api_key = os.getenv("GEMINI_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-1.5-pro')
        else:
            logger.error("CRITICAL: GEMINI_API_KEY missing from environment.")
            self.model = None

    async def generate_audit_summary(self, audit_data: dict) -> str:
        """
        Generates an international-standard executive summary using AI.
        """
        if not self.model:
            return "AI Analysis unavailable: Missing API Key."

        prompt = f"""
        As a World-Class SEO and Performance Expert, analyze this website audit data:
        URL: {audit_data.get('url')}
        Performance Score: {audit_data.get('score')}%
        LCP: {audit_data.get('performance', {}).get('lcp')}
        CLS: {audit_data.get('performance', {}).get('cls')}
        Connectivity: {audit_data.get('connectivity', {}).get('status')}

        Provide a 3-sentence executive summary:
        1. Current state of the website.
        2. The most critical issue to fix.
        3. The predicted impact of fixing that issue.
        Keep the tone professional and authoritative.
        """

        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            logger.error(f"Gemini AI Error: {e}")
            return "AI was unable to generate a summary for this audit."
