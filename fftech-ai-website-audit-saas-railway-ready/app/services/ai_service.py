import os
import logging
from google import genai

logger = logging.getLogger("AIService")

class AIService:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
            self.model_id = "gemini-2.0-flash"
            logger.info("GenAI Client initialized successfully.")
        else:
            logger.error("CRITICAL: GEMINI_API_KEY missing.")
            self.client = None

    async def generate_audit_summary(self, audit_data: dict) -> str:
        if not self.client:
            return "AI Analysis currently unavailable."

        prompt = f"Analyze site: {audit_data.get('url')}. Score: {audit_data.get('score')}%."

        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=prompt
            )
            return response.text
        except Exception as e:
            logger.error(f"Gemini modern SDK error: {e}")
            return "AI Summary currently processing."
