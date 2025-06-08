require('dotenv').config();

module.exports = {
    telegramToken: process.env.TELEGRAM_TOKEN,
    openrouterApiKey: process.env.OPENROUTER_API_KEY,
    contextSize: 10,
    paymentProviderToken: process.env.PAYMENT_PROVIDER_TOKEN,
    subscriptionPrice: 300 // in Telegram Stars
}; 