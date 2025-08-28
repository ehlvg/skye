import aiohttp
import asyncio
import logging
from typing import List, Dict, Any, Optional, Union
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
    
    async def get_completion(self, messages: List[Dict[str, Any]], model: str, plugins: Optional[List[Dict[str, Any]]] = None, modalities: Optional[List[str]] = None) -> Union[str, Dict[str, Any]]:
        """Get completion from OpenRouter API.
        Returns:
            - For text responses: a string containing the response text
            - For image generation: a dict containing the full message with images
        """
        try:
            async with aiohttp.ClientSession() as session:
                payload: Dict[str, Any] = {
                    "model": model,
                    "messages": messages
                }
                
                # Add plugins if provided (for online models)
                if plugins:
                    payload["plugins"] = plugins
                
                # Add modalities if provided (for image generation)
                if modalities:
                    payload["modalities"] = modalities
                
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=self.headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        message = data["choices"][0]["message"]
                        
                        # If this is an image generation response (has images field), return full message
                        if "images" in message:
                            return message
                        # Otherwise return just the content text
                        return message.get("content", "Sorry, I couldn't understand the AI's response.")
                    else:
                        error_text = await response.text()
                        logger.error(f"OpenRouter API error: {response.status} - {error_text}")
                        return "Sorry, I couldn't get a response from the AI service."
        
        except Exception as e:
            logger.error(f"Error calling OpenRouter API: {e}")
            return "Sorry, I encountered an error while processing your request."

# Global OpenRouter client instance
openrouter_client = OpenRouterClient()