import logging
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, PreCheckoutQueryHandler, filters, ContextTypes
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
    
    def _setup_handlers(self):
        """Setup all bot handlers"""
        # Command handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("profile", self.profile_command))
        self.application.add_handler(CommandHandler("upgrade", self.upgrade_command))
        self.application.add_handler(CommandHandler("model", self.model_command))
        self.application.add_handler(CommandHandler("setprompt", self.set_prompt_command))
        self.application.add_handler(CommandHandler("resetprompt", self.reset_prompt_command))
        self.application.add_handler(CommandHandler("getprompt", self.get_prompt_command))
        self.application.add_handler(CommandHandler("resetcontext", self.reset_context_command))
        self.application.add_handler(CommandHandler("ask", self.ask_command))
        
        # Message handlers
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.application.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, self.handle_media))
        
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
    
    async def model_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /model command"""
        user_id = update.effective_user.id
        available_models = await db.get_available_models(user_id)
        current_model = await db.get_user_model(user_id)
        
        keyboard = []
        for model in available_models:
            emoji = "✅" if model == current_model else "◻️"
            keyboard.append([InlineKeyboardButton(
                f"{emoji} {model}",
                callback_data=f"model_{model}"
            )])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"🤖 Выберите модель:\n\nТекущая модель: {current_model}",
            reply_markup=reply_markup
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
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle text messages"""
        # Check if message contains model selection
        text = update.message.text
        user_id = update.effective_user.id
        
        available_models = await db.get_available_models(user_id)
        if text in available_models:
            success = await db.set_user_model(user_id, text)
            if success:
                await update.message.reply_text(
                    f"✅ Модель изменена на: {text}",
                    reply_markup={"remove_keyboard": True}
                )
            else:
                await update.message.reply_text("❌ Ошибка изменения модели")
            return
        
        # For other messages, ignore unless it's a command
        pass
    
    async def handle_media(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle media messages with /ask command"""
        user_id = update.effective_user.id
        
        # Check if message has /ask command in caption
        caption = update.message.caption or ""
        if not caption.startswith("/ask"):
            await update.message.reply_text("📎 Для обработки файлов используйте команду /ask в подписи к файлу")
            return
        
        if not await db.can_send_message(user_id):
            await update.message.reply_text(
                "❌ Вы достигли лимита сообщений. Обновитесь до Plus тарифа для увеличения лимитов или дождитесь их сброса."
            )
            return
        
        query = caption.replace("/ask", "").strip()
        await self._process_media_request(update, user_id, query)
    
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
            model = await db.get_user_model(user_id)
            
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
            model = await db.get_user_model(user_id)
            
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
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    bot = TelegramBot()
    bot.run()