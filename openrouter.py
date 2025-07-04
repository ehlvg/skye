import aiohttp
import asyncio
import logging
from typing import List, Dict, Any
from config import Config

logger = logging.getLogger(__name__)

class OpenRouterClient:
    def __init__(self):
        self.api_key = Config.OPENROUTER_API_KEY
        self.base_url = "https://openrouter.ai/api/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    async def get_completion(self, messages: List[Dict[str, Any]], model: str) -> str:
        """Get completion from OpenRouter API"""
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "model": model,
                    "messages": messages
                }
                
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=self.headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data["choices"][0]["message"]["content"]
                    else:
                        error_text = await response.text()
                        logger.error(f"OpenRouter API error: {response.status} - {error_text}")
                        return "Sorry, I couldn't get a response from the AI service."
        
        except Exception as e:
            logger.error(f"Error calling OpenRouter API: {e}")
            return "Sorry, I encountered an error while processing your request."

# Global OpenRouter client instance
openrouter_client = OpenRouterClient()