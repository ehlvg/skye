import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    SUBSCRIPTION_PRICE_STARS = int(os.getenv("SUBSCRIPTION_PRICE_STARS", "300"))
    CONTEXT_SIZE = int(os.getenv("CONTEXT_SIZE", "10"))
    
    # Model configuration
    AVAILABLE_MODELS = {
        "lite": [
            "openai/gpt-4.1", 
            "google/gemini-2.5-flash"
        ],
        "plus": [
            "openai/gpt-4.1", 
            "google/gemini-2.5-flash",
            "anthropic/claude-sonnet-4",
            "google/gemini-2.5-pro"
        ]
    }
    
    # Usage limits
    USAGE_LIMITS = {
        "lite": {
            "daily": 20,
            "monthly": 100
        },
        "plus": {
            "daily": 100,
            "monthly": 1000
        }
    }