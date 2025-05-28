require('dotenv').config();

module.exports = {
    telegramToken: process.env.TELEGRAM_TOKEN,
    openrouterApiKey: process.env.OPENROUTER_API_KEY,
    allowedChats: process.env.ALLOWED_CHATS ? process.env.ALLOWED_CHATS.split(',').map(id => parseInt(id.trim(), 10)) : [],
    contextSize: 10 // Store last 10 messages per chat
}; 