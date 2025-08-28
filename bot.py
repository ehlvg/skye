import logging
import asyncio
import uuid
import base64
import io
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice, InlineQueryResultArticle, InputTextMessageContent, InputMediaPhoto
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, PreCheckoutQueryHandler, InlineQueryHandler, filters, ContextTypes
from telegram.constants import ParseMode

from config import Config
from database import db
from openrouter import openrouter_client
from utils import FileProcessor, MessageFormatter

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self):
        self.application = Application.builder().token(Config.TELEGRAM_BOT_TOKEN).build()
        self.file_processor = FileProcessor()
        self.message_formatter = MessageFormatter()
        self._setup_handlers()

    def _should_process_message(self, update: Update) -> bool:
        """Check if a message should be processed based on chat type, mention/reply status, and commands"""
        if not update.message:
            return False
            
        # Always process messages in private chats
        if update.message.chat.type == 'private':
            return True
            
        message = update.message
        
        # Check if message is a reply to bot's message
        if message.reply_to_message and message.reply_to_message.from_user:
            if message.reply_to_message.from_user.id == self.application.bot.id:
                return True
        
        # Check for mention of the bot
        if message.text:
            bot_username = self.application.bot.username
            if f"@{bot_username}" in message.text:
                return True
                
        # Check for commands
        text = message.text or message.caption or ""
        commands = ["/ask", "/search", "/img", "/start", "/profile", "/upgrade", 
                   "/setprompt", "/resetprompt", "/getprompt", "/resetcontext"]
        if any(text.startswith(cmd) for cmd in commands):
            return True
                
        return False
    
    def _setup_handlers(self):
        """Setup all bot handlers"""
        # Command handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("profile", self.profile_command))
        self.application.add_handler(CommandHandler("upgrade", self.upgrade_command))
        self.application.add_handler(CommandHandler("setprompt", self.set_prompt_command))
        self.application.add_handler(CommandHandler("resetprompt", self.reset_prompt_command))
        self.application.add_handler(CommandHandler("getprompt", self.get_prompt_command))
        self.application.add_handler(CommandHandler("resetcontext", self.reset_context_command))
        self.application.add_handler(CommandHandler("ask", self.ask_command))
        self.application.add_handler(CommandHandler("search", self.search_command))
        self.application.add_handler(CommandHandler("img", self.img_command))
        
        # Inline query handler
        self.application.add_handler(InlineQueryHandler(self.handle_inline_query))
        
        # Message handlers
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.application.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, self.handle_media))
        self.application.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, self.handle_audio))
        
        # Callback handlers
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))
        
        # Payment handlers
        self.application.add_handler(PreCheckoutQueryHandler(self.handle_pre_checkout))
        
        # Error handler
        self.application.add_error_handler(self.error_handler)
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command"""
        await update.message.reply_text(
            self.message_formatter.format_welcome_message(),
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def profile_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /profile command"""
        user_id = update.effective_user.id
        profile = await db.get_user_profile(user_id)
        
        if profile:
            await update.message.reply_text(
                self.message_formatter.format_profile_message(profile),
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text("❌ Ошибка получения профиля")
    
    async def upgrade_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /upgrade command"""
        user_id = update.effective_user.id
        user_data = await db.get_user_data(user_id)
        
        if user_data and user_data['tier'] == 'plus':
            await update.message.reply_text("Вы уже Premium пользователь! 🎉")
            return
        
        # Create invoice for Telegram Stars
        await update.message.reply_invoice(
            title="Обновление до Plus тарифа",
            description="Получите доступ к большему количеству сообщений и премиум моделям!",
            payload=f"upgrade_plus_{user_id}",
            provider_token="",  # Empty for Telegram Stars
            currency="XTR",
            prices=[LabeledPrice("Plus подписка", Config.SUBSCRIPTION_PRICE_STARS)],
            start_parameter="upgrade_to_plus"
        )
    

    
    async def set_prompt_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /setprompt command"""
        user_id = update.effective_user.id
        
        if not context.args:
            await update.message.reply_text("❌ Укажите текст промпта после команды")
            return
        
        prompt = " ".join(context.args)
        await db.set_system_prompt(user_id, prompt)
        await update.message.reply_text("✅ Системный промпт обновлён")
    
    async def reset_prompt_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /resetprompt command"""
        user_id = update.effective_user.id
        await db.reset_system_prompt(user_id)
        await update.message.reply_text("🔄 Системный промпт сброшен")
    
    async def get_prompt_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /getprompt command"""
        user_id = update.effective_user.id
        prompt = await db.get_system_prompt(user_id)
        
        if prompt:
            await update.message.reply_text(f"📝 Текущий системный промпт:\n{prompt}")
        else:
            await update.message.reply_text("ℹ️ Системный промпт не установлен")
    
    async def reset_context_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /resetcontext command"""
        user_id = update.effective_user.id
        await db.reset_context(user_id)
        await update.message.reply_text("🗑️ Контекст чата сброшен")
    
    async def ask_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /ask command"""
        user_id = update.effective_user.id
        
        if not await db.can_send_message(user_id):
            await update.message.reply_text(
                "❌ Вы достигли лимита сообщений. Обновитесь до Plus тарифа для увеличения лимитов или дождитесь их сброса."
            )
            return
        
        if not context.args:
            await update.message.reply_text("❌ Укажите вопрос после команды /ask")
            return
        
        query = " ".join(context.args)
        await self._process_ai_request(update, user_id, query)
    
    async def search_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /search command - web search using Gemini online model"""
        user_id = update.effective_user.id
        
        # Check if user has Plus tier
        user_data = await db.get_user_data(user_id)
        if not user_data or user_data['tier'] != 'plus':
            await update.message.reply_text(
                "🔒 Команда /search доступна только для Plus пользователей.\nИспользуйте /upgrade для обновления до Plus тарифа."
            )
            return
        
        if not await db.can_send_message(user_id):
            await update.message.reply_text(
                "❌ Вы достигли лимита сообщений. Дождитесь их сброса."
            )
            return
        
        if not context.args:
            await update.message.reply_text("❌ Укажите поисковый запрос после команды /search")
            return
        
        query = " ".join(context.args)
        await self._process_search_request(update, user_id, query)

    async def img_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /img command for image generation."""
        user_id = update.effective_user.id

        if not await db.can_send_message(user_id):
            await update.message.reply_text("Вы достигли лимита сообщений. Попробуйте позже или обновитесь до Plus.")
            return

        if not context.args:
            await update.message.reply_text("Пожалуйста, введите текстовый промпт для генерации изображения после команды /img.")
            return

        query = " ".join(context.args)
        await self._process_image_generation_request(update, user_id, query)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle text messages"""
        # Check if we should process this message
        if not self._should_process_message(update):
            return
            
        # Process the message if bot was mentioned or replied to
        if update.message and update.message.text:
            user_id = update.effective_user.id
            text = update.message.text.replace(f"@{self.application.bot.username}", "").strip()
            if text:  # Only process if there's actual text after removing the mention
                await self._process_ai_request(update, user_id, text)
    
    async def handle_media(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle media messages with /ask or /search command"""
        # Check if we should process this message
        if not self._should_process_message(update):
            return
            
        user_id = update.effective_user.id
        
        caption = update.message.caption or ""
        
        if not await db.can_send_message(user_id):
            await update.message.reply_text("Вы достигли лимита сообщений. Попробуйте позже или обновитесь до Plus.")
            return
        
        # Handle search command with media
        if caption.startswith("/search"):
            user_data = await db.get_user_data(user_id)
            if not user_data or user_data['tier'] != 'plus':
                await update.message.reply_text("🔍 Поиск по файлам доступен только для подписчиков Plus.")
                return
            
            query = caption.replace("/search", "").strip()
            await self._process_media_search_request(update, user_id, query)
        elif caption.startswith("/img"):
            query = caption.replace("/img", "").strip()
            await self._process_image_generation_request(update, user_id, query)
        else:
            query = caption.replace("/ask", "").strip()
            await self._process_media_request(update, user_id, query)

    async def handle_audio(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle voice or audio messages"""
        # Check if we should process this message
        if not self._should_process_message(update):
            return
            
        user_id = update.effective_user.id

        if not await db.can_send_message(user_id):
            await update.message.reply_text(
                "❌ Вы достигли лимита сообщений. Обновитесь до Plus тарифа для увеличения лимитов или дождитесь их сброса."
            )
            return

        file = None
        if update.message.voice:
            file = await update.message.voice.get_file()
        elif update.message.audio:
            file = await update.message.audio.get_file()

        if not file:
            return

        file_data = await self.file_processor.download_file(file.file_path)
        if not file_data:
            await update.message.reply_text("❌ Ошибка скачивания аудио")
            return

        processed_data = await asyncio.to_thread(self.file_processor.process_audio, file_data)
        if not processed_data:
            await update.message.reply_text("❌ Ошибка обработки аудио")
            return

        await self._process_audio_request(update, user_id, processed_data, "mp3")
    
    async def _process_ai_request(self, update: Update, user_id: int, query: str) -> None:
        """Process AI request"""
        try:
            # Send typing indicator
            await update.message.reply_chat_action("typing")
            
            # Prepare message content
            message_content = [{"type": "text", "text": query}]
            
            # Get context and system prompt
            context = await db.get_context(user_id)
            system_prompt = await db.get_system_prompt(user_id)
            model = "google/gemini-2.5-flash"
            
            # Build messages for API
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            
            messages.extend(context)
            messages.append({"role": "user", "content": message_content})
            
            # Get AI response
            response = await openrouter_client.get_completion(messages, model)
            
            # Save to context
            await db.add_message_to_context(user_id, "user", message_content)
            await db.add_message_to_context(user_id, "assistant", [{"type": "text", "text": response}])
            
            # Send response
            await update.message.reply_text(f"🤖 {response}")
            
        except Exception as e:
            logger.error(f"Error processing AI request: {e}")
            await update.message.reply_text("❌ Произошла ошибка при обработке запроса")
    
    async def _process_image_generation_request(self, update: Update, user_id: int, query: str) -> None:
        """Process image generation request using Gemini 2.5 Flash Image Preview."""
        try:
            await update.message.reply_text("🎨 Генерирую изображение...", reply_to_message_id=update.message.message_id)
            
            content_parts = [{"type": "text", "text": query}]
            
            # Handle attached image
            if update.message.photo:
                photo_size = update.message.photo[-1] # Get the highest resolution
                file = await photo_size.get_file()
                file_data = await self.file_processor.download_file(file.file_path)
                if file_data:
                    base64_image_url = self.file_processor.process_image(file_data, 'image/jpeg') 
                    if base64_image_url:
                        content_parts.append({"type": "image_url", "image_url": {"url": base64_image_url}})

            messages = [{"role": "user", "content": content_parts}]
            
            # Call OpenRouter API
            model = "google/gemini-2.5-flash-image-preview"
            response = await openrouter_client.get_completion(
                messages=messages,
                model=model,
                modalities=["image", "text"]
            )

            await db.add_message_to_context(user_id, "user", query)
            
            # For image generation, response will be a dict if images were generated, or string if not
            if isinstance(response, dict) and "images" in response:
                generated_images = []
                for image_info in response["images"]:
                    image_url = image_info["image_url"]["url"]
                    header, encoded = image_url.split(",", 1)
                    image_data = base64.b64decode(encoded)
                    generated_images.append(InputMediaPhoto(media=image_data))

                # Send all generated images
                if len(generated_images) > 1:
                    await update.message.reply_media_group(media=generated_images)
                else:
                    await update.message.reply_photo(photo=generated_images[0].media)

                # If there's an explanation text, send it after the images
                if response.get("content"):
                    await update.message.reply_text(response["content"])
                    await db.add_message_to_context(user_id, "assistant", response["content"])
            else:
                # If we got a string response or no images, just send the text
                text_response = response if isinstance(response, str) else "Не удалось сгенерировать изображение. Попробуйте еще раз."
                await update.message.reply_text(text_response)
                await db.add_message_to_context(user_id, "assistant", text_response)

        except Exception as e:
            logger.error(f"Error processing image generation request: {e}")
            await update.message.reply_text("Произошла ошибка при генерации изображения.")

    async def _process_media_request(self, update: Update, user_id: int, query: str) -> None:
        """Process media request"""
        try:
            await update.message.reply_chat_action("typing")
            
            message_content = []
            if query:
                message_content.append({"type": "text", "text": query})
            
            # Process document
            if update.message.document:
                doc = update.message.document
                if doc.mime_type == "application/pdf":
                    file = await doc.get_file()
                    file_data = await self.file_processor.download_file(file.file_path)
                    
                    if file_data:
                        processed_data = self.file_processor.process_pdf(file_data)
                        if processed_data:
                            message_content.append({
                                "type": "file",
                                "file": {
                                    "filename": doc.file_name,
                                    "file_data": processed_data
                                }
                            })
                        else:
                            await update.message.reply_text("❌ Ошибка обработки PDF файла")
                            return
                    else:
                        await update.message.reply_text("❌ Ошибка скачивания файла")
                        return
                
                elif doc.mime_type.startswith("image/"):
                    file = await doc.get_file()
                    file_data = await self.file_processor.download_file(file.file_path)
                    
                    if file_data:
                        processed_data = self.file_processor.process_image(file_data, doc.mime_type)
                        if processed_data:
                            message_content.append({
                                "type": "image_url",
                                "image_url": {"url": processed_data}
                            })
                        else:
                            await update.message.reply_text("❌ Ошибка обработки изображения")
                            return
                    else:
                        await update.message.reply_text("❌ Ошибка скачивания файла")
                        return
                else:
                    await update.message.reply_text("❌ Неподдерживаемый тип файла. Поддерживаются только PDF и изображения.")
                    return
            
            # Process photo
            if update.message.photo:
                photo = update.message.photo[-1]  # Get highest resolution
                file = await photo.get_file()
                file_data = await self.file_processor.download_file(file.file_path)
                
                if file_data:
                    processed_data = self.file_processor.process_image(file_data, "image/jpeg")
                    if processed_data:
                        message_content.append({
                            "type": "image_url",
                            "image_url": {"url": processed_data}
                        })
                    else:
                        await update.message.reply_text("❌ Ошибка обработки изображения")
                        return
                else:
                    await update.message.reply_text("❌ Ошибка скачивания изображения")
                    return
            
            if not message_content:
                await update.message.reply_text("❌ Нет содержимого для обработки")
                return
            
            # Get context and system prompt
            context = await db.get_context(user_id)
            system_prompt = await db.get_system_prompt(user_id)
            model = "google/gemini-2.5-flash"
            
            # Build messages for API
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            
            messages.extend(context)
            messages.append({"role": "user", "content": message_content})
            
            # Get AI response
            response = await openrouter_client.get_completion(messages, model)
            
            # Save to context
            await db.add_message_to_context(user_id, "user", message_content)
            await db.add_message_to_context(user_id, "assistant", [{"type": "text", "text": response}])
            
            # Send response
            await update.message.reply_text(f"🤖 {response}")
            
        except Exception as e:
            logger.error(f"Error processing media request: {e}")
            await update.message.reply_text("❌ Произошла ошибка при обработке запроса")

    async def _process_audio_request(
        self,
        update: Update,
        user_id: int,
        audio_data: str,
        audio_format: str,
        prompt_text: Optional[str] = None,
        prefix: str = "🤖",
    ) -> None:
        """Process audio request"""
        try:
            await update.message.reply_chat_action("typing")

            message_content: List[Dict[str, Any]] = []
            if prompt_text:
                message_content.append({"type": "text", "text": prompt_text})
            message_content.append({
                "type": "input_audio",
                "input_audio": {"data": audio_data, "format": audio_format},
            })

            context_data = await db.get_context(user_id)
            system_prompt = await db.get_system_prompt(user_id)
            # Always use Gemini 2.5 Flash for audio inputs as it's the only model that supports audio
            model = "google/gemini-2.5-flash"

            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.extend(context_data)
            messages.append({"role": "user", "content": message_content})

            response = await openrouter_client.get_completion(messages, model)

            await db.add_message_to_context(user_id, "user", message_content)
            await db.add_message_to_context(user_id, "assistant", [{"type": "text", "text": response}])

            await update.message.reply_text(f"{prefix} {response}")
        except Exception as e:
            logger.error(f"Error processing audio request: {e}")
            await update.message.reply_text("❌ Произошла ошибка при обработке аудио")
    
    async def _process_search_request(self, update: Update, user_id: int, query: str) -> None:
        """Process search request using Gemini online model"""
        try:
            # Send typing indicator
            await update.message.reply_chat_action("typing")
            
            # Prepare message content for search
            message_content = [{"type": "text", "text": query}]
            
            # Get context and system prompt
            context = await db.get_context(user_id)
            system_prompt = await db.get_system_prompt(user_id)
            
            # Use the special Gemini online model for search
            search_model = "google/gemini-2.5-flash"
            
            # Define search plugins with custom prompt to avoid markdown
            search_plugins = [{
                "id": "web",
                "max_results": 3,
                "search_prompt": "Here are relevant web search results (provide information without any markdown formatting, use plain text only with bare URLs when needed):"
            }]
            
            # Build messages for API
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            
            messages.extend(context)
            messages.append({"role": "user", "content": message_content})
            
            # Get AI response with web search
            response = await openrouter_client.get_completion(messages, search_model, plugins=search_plugins)
            
            # Save to context
            await db.add_message_to_context(user_id, "user", message_content)
            await db.add_message_to_context(user_id, "assistant", [{"type": "text", "text": response}])
            
            # Send response with search indicator
            await update.message.reply_text(f"🔍 Результат поиска:\n\n{response}")
            
        except Exception as e:
            logger.error(f"Error processing search request: {e}")
            await update.message.reply_text("❌ Произошла ошибка при выполнении поиска")
    
    async def _process_media_search_request(self, update: Update, user_id: int, query: str) -> None:
        """Process media search request using Gemini online model"""
        try:
            await update.message.reply_chat_action("typing")
            
            message_content = []
            if query:
                message_content.append({"type": "text", "text": query})
            
            # Process document
            if update.message.document:
                doc = update.message.document
                if doc.mime_type == "application/pdf":
                    file = await doc.get_file()
                    file_data = await self.file_processor.download_file(file.file_path)
                    
                    if file_data:
                        processed_data = self.file_processor.process_pdf(file_data)
                        if processed_data:
                            message_content.append({
                                "type": "file",
                                "file": {
                                    "filename": doc.file_name,
                                    "file_data": processed_data
                                }
                            })
                        else:
                            await update.message.reply_text("❌ Ошибка обработки PDF файла")
                            return
                    else:
                        await update.message.reply_text("❌ Ошибка скачивания файла")
                        return
                
                elif doc.mime_type.startswith("image/"):
                    file = await doc.get_file()
                    file_data = await self.file_processor.download_file(file.file_path)
                    
                    if file_data:
                        processed_data = self.file_processor.process_image(file_data, doc.mime_type)
                        if processed_data:
                            message_content.append({
                                "type": "image_url",
                                "image_url": {"url": processed_data}
                            })
                        else:
                            await update.message.reply_text("❌ Ошибка обработки изображения")
                            return
                    else:
                        await update.message.reply_text("❌ Ошибка скачивания файла")
                        return
                else:
                    await update.message.reply_text("❌ Неподдерживаемый тип файла. Поддерживаются только PDF и изображения.")
                    return
            
            # Process photo
            if update.message.photo:
                photo = update.message.photo[-1]  # Get highest resolution
                file = await photo.get_file()
                file_data = await self.file_processor.download_file(file.file_path)
                
                if file_data:
                    processed_data = self.file_processor.process_image(file_data, "image/jpeg")
                    if processed_data:
                        message_content.append({
                            "type": "image_url",
                            "image_url": {"url": processed_data}
                        })
                    else:
                        await update.message.reply_text("❌ Ошибка обработки изображения")
                        return
                else:
                    await update.message.reply_text("❌ Ошибка скачивания изображения")
                    return
            
            if not message_content:
                await update.message.reply_text("❌ Нет содержимого для поиска")
                return
            
            # Get context and system prompt
            context = await db.get_context(user_id)
            system_prompt = await db.get_system_prompt(user_id)
            
            # Use the special Gemini online model for search
            search_model = "google/gemini-2.5-flash"
            
            # Define search plugins with custom prompt to avoid markdown
            search_plugins = [{
                "id": "web",
                "max_results": 3,
                "search_prompt": "Here are relevant web search results (provide information without any markdown formatting, use plain text only with bare URLs when needed):"
            }]
            
            # Build messages for API
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            
            messages.extend(context)
            messages.append({"role": "user", "content": message_content})
            
            # Get AI response with web search
            response = await openrouter_client.get_completion(messages, search_model, plugins=search_plugins)
            
            # Save to context
            await db.add_message_to_context(user_id, "user", message_content)
            await db.add_message_to_context(user_id, "assistant", [{"type": "text", "text": response}])
            
            # Send response with search indicator
            await update.message.reply_text(f"🔍 Результат поиска:\n\n{response}")
            
        except Exception as e:
            logger.error(f"Error processing media search request: {e}")
            await update.message.reply_text("❌ Произошла ошибка при выполнении поиска")

    async def handle_inline_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle inline queries"""
        query = update.inline_query.query
        user_id = update.effective_user.id
        
        if not query.strip():
            # Show help text when query is empty
            results = [
                InlineQueryResultArticle(
                    id="help",
                    title="🤖 Как использовать бота",
                    description="Введите ваш вопрос после @botname",
                    input_message_content=InputTextMessageContent(
                        message_text="Для использования бота в inline-режиме введите ваш вопрос после упоминания бота.\n\nПример: @botname Что такое искусственный интеллект?"
                    )
                )
            ]
            await update.inline_query.answer(results, cache_time=300)
            return
        
        # Check if user can send messages
        if not await db.can_send_message(user_id):
            results = [
                InlineQueryResultArticle(
                    id="limit_exceeded",
                    title="❌ Лимит сообщений исчерпан",
                    description="Обновитесь до Plus тарифа или дождитесь сброса лимитов",
                    input_message_content=InputTextMessageContent(
                        message_text="❌ Вы достигли лимита сообщений. Используйте /upgrade для обновления до Plus тарифа или дождитесь их сброса."
                    )
                )
            ]
            await update.inline_query.answer(results, cache_time=0)
            return
        
        # Check if query starts with "search " for web search
        is_search_query = query.lower().startswith("search ")
        if is_search_query:
            # Check if user has Plus tier for search
            user_data = await db.get_user_data(user_id)
            if not user_data or user_data['tier'] != 'plus':
                results = [
                    InlineQueryResultArticle(
                        id="search_plus_only",
                        title="🔒 Поиск доступен только для Plus",
                        description="Обновитесь до Plus тарифа для использования поиска",
                        input_message_content=InputTextMessageContent(
                            message_text="🔒 Поиск в интернете доступен только для Plus пользователей.\nИспользуйте /upgrade для обновления до Plus тарифа."
                        )
                    )
                ]
                await update.inline_query.answer(results, cache_time=300)
                return
            
            # Remove "search " prefix for processing
            query = query[7:].strip()
            if not query:
                results = [
                    InlineQueryResultArticle(
                        id="search_empty",
                        title="🔍 Введите поисковый запрос",
                        description="Пример: search Последние новости ИИ",
                        input_message_content=InputTextMessageContent(
                            message_text="❌ Укажите поисковый запрос после 'search '.\nПример: @botname search Последние новости ИИ"
                        )
                    )
                ]
                await update.inline_query.answer(results, cache_time=300)
                return
        
        try:
            # Get AI response
            if is_search_query:
                response = await self._get_search_response(user_id, query)
                response_prefix = "🔍 Результат поиска:\n\n"
                title_prefix = "🔍 "
            else:
                response = await self._get_ai_response(user_id, query)
                response_prefix = "🤖 "
                title_prefix = "🤖 "
            
            # Truncate response for preview if too long
            preview_text = response[:100] + "..." if len(response) > 100 else response
            full_response = f"{response_prefix}{response}"
            
            results = [
                InlineQueryResultArticle(
                    id=f"response_{str(uuid.uuid4())}",
                    title=f"{title_prefix}{query[:50]}{'...' if len(query) > 50 else ''}",
                    description=preview_text,
                    input_message_content=InputTextMessageContent(
                        message_text=full_response
                    )
                )
            ]
            
            await update.inline_query.answer(results, cache_time=0)
            
        except Exception as e:
            logger.error(f"Error processing inline query: {e}")
            results = [
                InlineQueryResultArticle(
                    id="error",
                    title="❌ Произошла ошибка",
                    description="Попробуйте еще раз или используйте команды в личных сообщениях",
                    input_message_content=InputTextMessageContent(
                        message_text="❌ Произошла ошибка при обработке запроса. Попробуйте еще раз."
                    )
                )
            ]
            await update.inline_query.answer(results, cache_time=0)

    async def _get_ai_response(self, user_id: int, query: str) -> str:
        """Get AI response for inline query"""
        try:
            # Prepare message content
            message_content = [{"type": "text", "text": query}]
            
            # Get context and system prompt
            context = await db.get_context(user_id)
            system_prompt = await db.get_system_prompt(user_id)
            model = "google/gemini-2.5-flash"
            
            # Build messages for API
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            
            messages.extend(context)
            messages.append({"role": "user", "content": message_content})
            
            # Get AI response
            response = await openrouter_client.get_completion(messages, model)
            
            # Save to context
            await db.add_message_to_context(user_id, "user", message_content)
            await db.add_message_to_context(user_id, "assistant", [{"type": "text", "text": response}])
            
            return response
            
        except Exception as e:
            logger.error(f"Error getting AI response for inline: {e}")
            raise

    async def _get_search_response(self, user_id: int, query: str) -> str:
        """Get search response for inline query"""
        try:
            # Prepare message content for search
            message_content = [{"type": "text", "text": query}]
            
            # Get context and system prompt
            context = await db.get_context(user_id)
            system_prompt = await db.get_system_prompt(user_id)
            
            # Use the special Gemini online model for search
            search_model = "google/gemini-2.5-flash"
            
            # Define search plugins with custom prompt to avoid markdown
            search_plugins = [{
                "id": "web",
                "max_results": 3,
                "search_prompt": "Here are relevant web search results (provide information without any markdown formatting, use plain text only with bare URLs when needed):"
            }]
            
            # Build messages for API
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            
            messages.extend(context)
            messages.append({"role": "user", "content": message_content})
            
            # Get AI response with web search
            response = await openrouter_client.get_completion(messages, search_model, plugins=search_plugins)
            
            # Save to context
            await db.add_message_to_context(user_id, "user", message_content)
            await db.add_message_to_context(user_id, "assistant", [{"type": "text", "text": response}])
            
            return response
            
        except Exception as e:
            logger.error(f"Error getting search response for inline: {e}")
            raise

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle callback queries"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        data = query.data
        
        if data.startswith("model_"):
            model = data.replace("model_", "")
            success = await db.set_user_model(user_id, model)
            
            if success:
                # Update the message with new model selection
                available_models = await db.get_available_models(user_id)
                keyboard = []
                for m in available_models:
                    emoji = "✅" if m == model else "◻️"
                    keyboard.append([InlineKeyboardButton(
                        f"{emoji} {m}",
                        callback_data=f"model_{m}"
                    )])
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(
                    f"🤖 Выберите модель:\n\nТекущая модель: {model}",
                    reply_markup=reply_markup
                )
            else:
                await query.edit_message_text("❌ Эта модель недоступна для вашего тарифа")
    
    async def handle_pre_checkout(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle pre-checkout queries"""
        query = update.pre_checkout_query
        
        # Always approve pre-checkout for Telegram Stars
        await query.answer(ok=True)
        
        # Process successful payment
        user_id = update.effective_user.id
        
        # Upgrade user to Plus
        subscription_end_date = datetime.now() + timedelta(days=30)
        success = await db.upgrade_to_plus(user_id, subscription_end_date)
        
        if success:
            # Record payment
            await db.record_payment(
                user_id,
                query.telegram_payment_charge_id,
                Config.SUBSCRIPTION_PRICE_STARS,
                "XTR"
            )
            
            await context.bot.send_message(
                chat_id=user_id,
                text=f"""🎉 Спасибо за обновление до Plus тарифа! Ваша подписка активна.

Ваши преимущества:
• 50 сообщений в день
• 500 сообщений в месяц  
• Доступ к премиум моделям
• Подписка действует до {subscription_end_date.strftime('%d.%m.%Y')}"""
            )
        else:
            await context.bot.send_message(
                chat_id=user_id,
                text="❌ Произошла ошибка при обработке платежа. Обратитесь в поддержку."
            )
    
    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle errors"""
        logger.error(f"Exception while handling an update: {context.error}")
    
    def run(self):
        """Run the bot"""
        logger.info("Starting bot...")
        self.application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == "__main__":
    bot = TelegramBot()
    bot.run()
