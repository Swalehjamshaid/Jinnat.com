import os
import logging
from typing import Optional
from google import genai

logger = logging.getLogger("AIService")

class AIService:
    def __init__(self):
        """
        Initializes the modern Google GenAI Client.
        Uses GEMINI_API_KEY from Railway Environment Variables.
        """
        self.api_key = os.getenv("GEMINI_API_KEY")
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
            self.model_id = "gemini-2.0-flash"
            logger.info("World-Class GenAI Client initialized successfully.")
        else:
            logger.error("CRITICAL: GEMINI_API_KEY missing from environment.")
            self.client = None

    async def generate_audit_summary(self, audit_data: dict) -> str:
        """
        Generates professional executive insights using the modern GenAI SDK.
        """
        if not self.client:
            return "AI Analysis currently unavailable."

        prompt = f"""
        Analyze this website audit data as a Senior SEO & Performance Consultant:
        URL: {audit_data.get('url')}
        Global Score: {audit_data.get('score')}%
        Technical Metrics: {audit_data.get('performance')}
        
        Provide a 3-sentence executive summary:
        1. Current status of the site.
        2. The single most important technical fix needed.
        3. The expected business impact of that fix.
        """

        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=prompt
            )
            return response.text
        except Exception as e:
            logger.error(f"Gemini modern SDK error: {str(e)}")
            return "Audit data processed. AI summary is currently being regenerated."
