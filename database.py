import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from supabase import create_client, Client
from config import Config

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        self.supabase: Client = create_client(
            Config.SUPABASE_URL,
            Config.SUPABASE_SERVICE_ROLE_KEY
        )
        self._init_tables()
    
    def _init_tables(self):
        """Initialize database tables if they don't exist"""
        try:
            # Check if tables exist by trying to query them
            # If they don't exist, the user needs to create them manually in Supabase
            self.supabase.table('users').select('*').limit(1).execute()
            self.supabase.table('user_context').select('*').limit(1).execute()
            self.supabase.table('payments').select('*').limit(1).execute()
            logger.info("Database tables verified successfully")
            
        except Exception as e:
            logger.error(f"Database tables not found. Please run the setup_database.sql script in your Supabase dashboard: {e}")
            logger.error("Go to Supabase Dashboard → SQL Editor → Run setup_database.sql")
    
    async def get_user_data(self, user_id: int) -> Dict[str, Any]:
        """Get user data, create if doesn't exist"""
        try:
            response = self.supabase.table('users').select('*').eq('user_id', user_id).execute()
            
            if response.data:
                user_data = response.data[0]
                # Check if we need to reset counters
                await self._check_and_reset_counters(user_data)
                return user_data
            else:
                # Create new user
                new_user = {
                    'user_id': user_id,
                    'tier': 'lite',
                    'system_prompt': None,
                    'current_model': 'openai/gpt-4.1',
                    'daily_count': 0,
                    'monthly_count': 0,
                    'last_daily_reset': datetime.now().date().isoformat(),
                    'last_monthly_reset': datetime.now().date().isoformat()
                }
                
                response = self.supabase.table('users').insert(new_user).execute()
                return response.data[0]
        except Exception as e:
            logger.error(f"Error getting user data: {e}")
            return None
    
    async def _check_and_reset_counters(self, user_data: Dict[str, Any]) -> None:
        """Check and reset daily/monthly counters if needed"""
        try:
            user_id = user_data['user_id']
            today = datetime.now().date()
            
            updates = {}
            
            # Check daily reset
            if user_data['last_daily_reset'] != today:
                updates['daily_count'] = 0
                updates['last_daily_reset'] = today.isoformat()
            
            # Check monthly reset
            last_monthly_reset = datetime.fromisoformat(user_data['last_monthly_reset']).date()
            if last_monthly_reset.month != today.month:
                updates['monthly_count'] = 0
                updates['last_monthly_reset'] = today.isoformat()
            
            if updates:
                self.supabase.table('users').update(updates).eq('user_id', user_id).execute()
        except Exception as e:
            logger.error(f"Error resetting counters: {e}")
    
    async def can_send_message(self, user_id: int) -> bool:
        """Check if user can send a message"""
        try:
            user_data = await self.get_user_data(user_id)
            if not user_data:
                return False
            
            limits = Config.USAGE_LIMITS[user_data['tier']]
            return (user_data['daily_count'] < limits['daily'] and 
                   user_data['monthly_count'] < limits['monthly'])
        except Exception as e:
            logger.error(f"Error checking message limits: {e}")
            return False
    
    async def increment_message_count(self, user_id: int) -> None:
        """Increment user's message count"""
        try:
            user_data = await self.get_user_data(user_id)
            if user_data:
                self.supabase.table('users').update({
                    'daily_count': user_data['daily_count'] + 1,
                    'monthly_count': user_data['monthly_count'] + 1
                }).eq('user_id', user_id).execute()
        except Exception as e:
            logger.error(f"Error incrementing message count: {e}")
    
    async def get_context(self, user_id: int, limit: int = None) -> List[Dict[str, Any]]:
        """Get user's conversation context"""
        try:
            if limit is None:
                limit = Config.CONTEXT_SIZE
            
            response = self.supabase.table('user_context').select('*').eq('user_id', user_id).order('created_at', desc=False).limit(limit).execute()
            
            return [{'role': item['role'], 'content': item['content']} for item in response.data]
        except Exception as e:
            logger.error(f"Error getting context: {e}")
            return []
    
    async def add_message_to_context(self, user_id: int, role: str, content: Any) -> None:
        """Add message to user's context"""
        try:
            # First increment message count
            await self.increment_message_count(user_id)
            
            # Add to context
            self.supabase.table('user_context').insert({
                'user_id': user_id,
                'role': role,
                'content': content
            }).execute()
            
            # Keep only last N messages
            messages = self.supabase.table('user_context').select('id').eq('user_id', user_id).order('created_at', desc=True).execute()
            
            if len(messages.data) > Config.CONTEXT_SIZE:
                ids_to_delete = [msg['id'] for msg in messages.data[Config.CONTEXT_SIZE:]]
                self.supabase.table('user_context').delete().in_('id', ids_to_delete).execute()
                
        except Exception as e:
            logger.error(f"Error adding message to context: {e}")
    
    async def reset_context(self, user_id: int) -> None:
        """Reset user's conversation context"""
        try:
            self.supabase.table('user_context').delete().eq('user_id', user_id).execute()
        except Exception as e:
            logger.error(f"Error resetting context: {e}")
    
    async def get_system_prompt(self, user_id: int) -> Optional[str]:
        """Get user's system prompt"""
        try:
            user_data = await self.get_user_data(user_id)
            return user_data.get('system_prompt') if user_data else None
        except Exception as e:
            logger.error(f"Error getting system prompt: {e}")
            return None
    
    async def set_system_prompt(self, user_id: int, prompt: str) -> None:
        """Set user's system prompt"""
        try:
            self.supabase.table('users').update({
                'system_prompt': prompt
            }).eq('user_id', user_id).execute()
        except Exception as e:
            logger.error(f"Error setting system prompt: {e}")
    
    async def reset_system_prompt(self, user_id: int) -> None:
        """Reset user's system prompt"""
        try:
            self.supabase.table('users').update({
                'system_prompt': None
            }).eq('user_id', user_id).execute()
        except Exception as e:
            logger.error(f"Error resetting system prompt: {e}")
    
    async def get_user_model(self, user_id: int) -> str:
        """Get user's current model"""
        try:
            user_data = await self.get_user_data(user_id)
            return user_data.get('current_model', 'openai/gpt-4.1') if user_data else 'openai/gpt-4.1'
        except Exception as e:
            logger.error(f"Error getting user model: {e}")
            return 'openai/gpt-4.1'
    
    async def set_user_model(self, user_id: int, model: str) -> bool:
        """Set user's model if available for their tier"""
        try:
            user_data = await self.get_user_data(user_id)
            if not user_data:
                return False
            
            available_models = Config.AVAILABLE_MODELS[user_data['tier']]
            if model in available_models:
                self.supabase.table('users').update({
                    'current_model': model
                }).eq('user_id', user_id).execute()
                # Reset context when changing models
                await self.reset_context(user_id)
                return True
            return False
        except Exception as e:
            logger.error(f"Error setting user model: {e}")
            return False
    
    async def get_available_models(self, user_id: int) -> List[str]:
        """Get available models for user's tier"""
        try:
            user_data = await self.get_user_data(user_id)
            if not user_data:
                return Config.AVAILABLE_MODELS['lite']
            
            return Config.AVAILABLE_MODELS[user_data['tier']]
        except Exception as e:
            logger.error(f"Error getting available models: {e}")
            return Config.AVAILABLE_MODELS['lite']
    
    async def get_user_profile(self, user_id: int) -> Dict[str, Any]:
        """Get user's profile information"""
        try:
            user_data = await self.get_user_data(user_id)
            if not user_data:
                return {}
            
            limits = Config.USAGE_LIMITS[user_data['tier']]
            
            return {
                'user_id': user_id,
                'tier': user_data['tier'],
                'subscription_end_date': user_data.get('subscription_end_date'),
                'daily_remaining': limits['daily'] - user_data['daily_count'],
                'monthly_remaining': limits['monthly'] - user_data['monthly_count'],
                'current_model': user_data['current_model']
            }
        except Exception as e:
            logger.error(f"Error getting user profile: {e}")
            return {}
    
    async def upgrade_to_plus(self, user_id: int, subscription_end_date: datetime) -> bool:
        """Upgrade user to Plus tier"""
        try:
            updates = {
                'tier': 'plus',
                'subscription_end_date': subscription_end_date.isoformat(),
                'daily_count': 0,
                'monthly_count': 0,
                'last_daily_reset': datetime.now().date().isoformat(),
                'last_monthly_reset': datetime.now().date().isoformat()
            }
            
            self.supabase.table('users').update(updates).eq('user_id', user_id).execute()
            return True
        except Exception as e:
            logger.error(f"Error upgrading to plus: {e}")
            return False
    
    async def record_payment(self, user_id: int, charge_id: str, amount: int, currency: str) -> None:
        """Record a successful payment"""
        try:
            self.supabase.table('payments').insert({
                'user_id': user_id,
                'telegram_payment_charge_id': charge_id,
                'amount': amount,
                'currency': currency,
                'status': 'completed'
            }).execute()
        except Exception as e:
            logger.error(f"Error recording payment: {e}")

# Global database instance
db = DatabaseManager()