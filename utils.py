import io
import base64
import logging
import tempfile
import subprocess
import os
import asyncio
from typing import Optional, List, Dict, Any
from PIL import Image
import PyPDF2
import aiohttp

logger = logging.getLogger(__name__)

class FileProcessor:
    @staticmethod
    async def download_file(file_url: str) -> Optional[bytes]:
        """Download file from Telegram servers"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(file_url) as response:
                    if response.status == 200:
                        return await response.read()
                    else:
                        logger.error(f"Failed to download file: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Error downloading file: {e}")
            return None
    
    @staticmethod
    def process_image(image_data: bytes, mime_type: str) -> Optional[str]:
        """Process image and return base64 encoded data URL"""
        try:
            # Validate and optimize image
            image = Image.open(io.BytesIO(image_data))
            
            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Resize if too large (max 1024x1024 for API efficiency)
            if image.width > 1024 or image.height > 1024:
                image.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
            
            # Convert back to bytes
            output = io.BytesIO()
            image.save(output, format='JPEG', quality=85)
            processed_data = output.getvalue()
            
            # Encode as base64
            base64_data = base64.b64encode(processed_data).decode('utf-8')
            return f"data:image/jpeg;base64,{base64_data}"
        
        except Exception as e:
            logger.error(f"Error processing image: {e}")
            return None
    
    @staticmethod
    def process_pdf(pdf_data: bytes) -> Optional[str]:
        """Process PDF and return base64 encoded data URL"""
        try:
            # Validate PDF
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_data))
            
            # Check if PDF has content
            if len(pdf_reader.pages) == 0:
                logger.error("PDF has no pages")
                return None
            
            # Encode as base64
            base64_data = base64.b64encode(pdf_data).decode('utf-8')
            return f"data:application/pdf;base64,{base64_data}"
        
        except Exception as e:
            logger.error(f"Error processing PDF: {e}")
            return None

    @staticmethod
    def process_audio(audio_data: bytes) -> Optional[str]:
        """Convert audio to MP3 and return base64 string"""
        try:
            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as src:
                src.write(audio_data)
                src_path = src.name
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as dst:
                dst_path = dst.name
            subprocess.run([
                "ffmpeg",
                "-y",
                "-i",
                src_path,
                dst_path,
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            with open(dst_path, "rb") as f:
                mp3_data = f.read()
            base64_data = base64.b64encode(mp3_data).decode("utf-8")
            return base64_data
        except Exception as e:
            logger.error(f"Error processing audio: {e}")
            return None
        finally:
            for path in [locals().get('src_path'), locals().get('dst_path')]:
                if path and os.path.exists(path):
                    try:
                        os.remove(path)
                    except Exception:
                        pass

class MessageFormatter:
    @staticmethod
    def format_welcome_message() -> str:
        """Format welcome message"""
        return """👋 Привет! Я Telegram бот на базе OpenRouter. Я могу отвечать на вопросы и обрабатывать вложенные PDF документы и изображения.

Доступные команды:
❓ /ask <ваш_вопрос> - Задать вопрос (можно прикрепить файл/изображение)
🔍 /search <поисковый_запрос> - Поиск в интернете (только Plus) 
⚙️ /setprompt <ваш_промпт> - Установить системный промпт для этого чата
🔄 /resetprompt - Сбросить системный промпт
📝 /getprompt - Показать текущий системный промпт
🗑️ /resetcontext - Очистить контекст чата
🤖 /model - Выбрать модель ИИ
👤 /profile - Посмотреть профиль и лимиты
⭐️ /upgrade - Обновиться до Plus тарифа

💡 **Inline-режим:** Используйте бота в любом чате!
• @botname ваш_вопрос - Обычный запрос к ИИ
• @botname search ваш_запрос - Поиск в интернете (только Plus)

Просто начните печатать @botname в любом чате и задайте свой вопрос!"""
    
    @staticmethod
    def format_profile_message(profile: Dict[str, Any]) -> str:
        """Format user profile message"""
        tier_emoji = "⭐️" if profile['tier'] == 'plus' else "🆓"
        message = f"""👤 **Ваш профиль**

🆔 ID пользователя: `{profile['user_id']}`
{tier_emoji} Тариф: {profile['tier'].title()}
📊 Осталось сообщений сегодня: {profile['daily_remaining']}
📈 Осталось сообщений в месяце: {profile['monthly_remaining']}
🤖 Текущая модель: {profile['current_model']}"""
        
        if profile.get('subscription_end_date'):
            from datetime import datetime
            end_date = datetime.fromisoformat(profile['subscription_end_date'].replace('Z', '+00:00'))
            message += f"\n📅 Подписка действует до: {end_date.strftime('%d.%m.%Y')}"
        
        return message
    
    @staticmethod
    def format_upgrade_message() -> str:
        """Format upgrade message"""
        return """⭐️ **Обновление до Plus тарифа**

Преимущества Plus тарифа:
• 50 сообщений в день (вместо 10)
• 500 сообщений в месяц (вместо 50)
• Доступ к премиум моделям
• 🔍 Поиск в интернете (/search)
• Приоритетная поддержка

Стоимость: 300 Telegram Stars
Срок действия: 30 дней"""