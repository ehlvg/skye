const TelegramBot = require('node-telegram-bot-api');
const config = require('./config');
const database = require('./database');
const openrouter = require('./openrouter');
const axios = require('axios');

console.log('Starting bot initialization...');

// Initialize bot with polling and callback query handling
const bot = new TelegramBot(config.telegramToken, { 
    polling: {
        interval: 300,
        autoStart: true,
        params: {
            timeout: 10
        }
    }
});

console.log('Bot instance created, setting up event handlers...');

// Log when bot is ready
bot.on('polling_error', (error) => {
    console.error('Polling error:', error);
});

bot.on('webhook_error', (error) => {
    console.error('Webhook error:', error);
});

bot.on('error', (error) => {
    console.error('Bot error:', error);
});

async function downloadFile(fileId, filePath) {
    try {
        const url = await bot.getFileLink(fileId);
        const response = await axios({
            url,
            method: 'GET',
            responseType: 'arraybuffer'
        });
        return response.data;
    } catch (error) {
        console.error('Error downloading file from Telegram:', error);
        return null;
    }
}

database.loadDatabase();

setInterval(() => {
    database.saveDatabase();
}, 5 * 60 * 1000);

process.on('SIGINT', async () => {
    console.log('Saving database before exiting...');
    await database.saveDatabase();
    process.exit(0);
});

process.on('SIGTERM', async () => {
    console.log('Saving database before exiting...');
    await database.saveDatabase();
    process.exit(0);
});

bot.on('message', async (msg) => {
    console.log('Received message:', msg.text);
    const chatId = msg.chat.id;
    const userId = msg.from.id;
    const text = msg.text;
    const caption = msg.caption || '';
    const document = msg.document;
    const photo = msg.photo;

    // if (config.allowedChats.length > 0 && !config.allowedChats.includes(chatId)) {
    //     console.log(`Message from unauthorized chat ID: ${chatId}`);

    //     if (text && text.startsWith('/ask ')) {
    //          bot.sendMessage(chatId, '🚫 This chat is not authorized to use this bot.', { reply_to_message_id: msg.message_id });
    //     }

    //     return;
    // }

    if (text === '/start') {
        const welcomeMessage = '👋 Hi! I am a Telegram bot powered by OpenRouter. I can answer your questions and process attached PDF documents and images.\n\nHere are the available commands:\n' +
                             '❓ /ask <your_query> - Ask me a question (you can also attach a file/image).\n' +
                             '⚙️ /setprompt <your_prompt> - Set a system prompt for this chat.\n' +
                             '🔄 /resetprompt - Reset the system prompt for this chat.\n' +
                             '📝 /getprompt - Display the current system prompt for this chat.\n' +
                             '🗑️ /resetcontext - Clear the chat history context for this chat.\n' +
                             '🤖 /model - Change the AI model for this chat.\n' +
                             '👤 /profile - View your profile and usage limits.\n' +
                             '⭐️ /upgrade - Upgrade to Plus tier for more features.';
        bot.sendMessage(chatId, welcomeMessage, { reply_to_message_id: msg.message_id });
        return;
    }

    if (text === '/profile') {
        const profile = database.getUserProfile(userId);
        const message = `👤 *Your Profile*\n\n` +
                       `🆔 User ID: \`${profile.userId}\`\n` +
                       `⭐️ Tier: ${profile.tier === 'plus' ? 'Plus' : 'Lite'}\n` +
                       `📊 Daily messages remaining: ${profile.dailyRemaining}\n` +
                       `📈 Monthly messages remaining: ${profile.monthlyRemaining}\n` +
                       `🤖 Current model: ${profile.model}\n`;
        
        if (profile.subscriptionEndDate) {
            const endDate = new Date(profile.subscriptionEndDate);
            message += `📅 Subscription valid until: ${endDate.toLocaleDateString()}`;
        }
        
        bot.sendMessage(chatId, message, { 
            reply_to_message_id: msg.message_id,
            parse_mode: 'Markdown'
        });
        return;
    }

    if (text === '/upgrade') {
        const profile = database.getUserProfile(userId);
        if (profile.tier === 'plus') {
            bot.sendMessage(chatId, 'You are already a Plus user! 🎉', { reply_to_message_id: msg.message_id });
            return;
        }

        const invoice = {
            chat_id: chatId,
            title: 'Upgrade to Plus Tier',
            description: 'Get access to more messages and premium models!',
            payload: JSON.stringify({ type: 'subscription', userId: userId }),
            provider_token: config.paymentProviderToken,
            currency: 'XTR',
            prices: [{ label: 'Plus Subscription', amount: config.subscriptionPrice }],
            start_parameter: 'upgrade_to_plus'
        };

        bot.sendInvoice(chatId, invoice.title, invoice.description, invoice.payload, 
            invoice.provider_token, invoice.currency, invoice.prices, {
                reply_to_message_id: msg.message_id
            });
        return;
    }

    if (text === '/model') {
        console.log('Model command received from user:', userId);
        const availableModels = database.getAvailableModels(userId);
        console.log('Available models:', availableModels);
        
        const keyboard = {
            keyboard: availableModels.map(model => [model]),
            one_time_keyboard: true,
            resize_keyboard: true
        };
        
        console.log('Sending model selection keyboard:', keyboard);
        bot.sendMessage(chatId, 'Select a model:', {
            reply_markup: keyboard,
            reply_to_message_id: msg.message_id
        });
        return;
    }

    // Handle model selection from keyboard
    if (text && (text.startsWith('openai/') || text.startsWith('google/'))) {
        console.log('Model selection received:', text);
        const availableModels = database.getAvailableModels(userId);
        
        if (availableModels.includes(text)) {
            if (database.setModel(userId, text)) {
                bot.sendMessage(chatId, `✅ Model changed to: ${text}`, {
                    reply_markup: { remove_keyboard: true }
                });
            } else {
                bot.sendMessage(chatId, '❌ Failed to change model. Please try again.', {
                    reply_markup: { remove_keyboard: true }
                });
            }
        } else {
            bot.sendMessage(chatId, '❌ This model is not available for your tier.', {
                reply_markup: { remove_keyboard: true }
            });
        }
        return;
    }

    if (text && text.startsWith('/setprompt ')) {
        const newPrompt = text.replace('/setprompt ', '').trim();
        database.setSystemPrompt(userId, newPrompt);
        database.saveDatabase();
        bot.sendMessage(chatId, '✅ System prompt updated.', { reply_to_message_id: msg.message_id });
        return;
    }

    if (text === '/resetprompt') {
        database.resetSystemPrompt(userId);
        database.saveDatabase();
        bot.sendMessage(chatId, '🔄 System prompt reset.', { reply_to_message_id: msg.message_id });
        return;
    }

    if (text === '/getprompt') {
        const currentPrompt = database.getSystemPrompt(userId);
        if (currentPrompt) {
            bot.sendMessage(chatId, `📝 Current system prompt:\n${currentPrompt}`, { reply_to_message_id: msg.message_id });
        } else {
            bot.sendMessage(chatId, 'ℹ️ No system prompt is currently set.', { reply_to_message_id: msg.message_id });
        }
        return;
    }

    if (text === '/resetcontext') {
        database.resetContext(userId);
        database.saveDatabase();
        bot.sendMessage(chatId, '🗑️ Chat context has been reset.', { reply_to_message_id: msg.message_id });
        return;
    }

    const hasDocument = document && (document.mime_type === 'application/pdf' || document.mime_type.startsWith('image/'));
    const hasPhoto = photo && photo.length > 0;

    // Check if this is a message we should process
    const hasAskCommand = (text && text.startsWith('/ask ')) || (caption && caption.startsWith('/ask '));
    const hasAttachment = hasDocument || hasPhoto;

    // Skip if:
    // 1. No text and no caption (empty message)
    // 2. Has attachment but no /ask command
    if ((!text && !caption) || (hasAttachment && !hasAskCommand)) {
        if (hasAttachment) {
            console.log(`📎 Ignoring attachment message without /ask command from user ID: ${userId}`);
        }
        return;
    }

    // Check message limits
    if (text.startsWith('/ask') && !database.canSendMessage(userId)) {
        bot.sendMessage(chatId, '❌ You have reached your message limit. Please upgrade to Plus tier for more messages or wait until your limits reset.', { reply_to_message_id: msg.message_id });
        return;
    }

    let userQuery = '';
    if (text && text.startsWith('/ask ')) {
        userQuery = text.replace('/ask ', '').trim();
    } else if (caption && caption.startsWith('/ask ')) {
        userQuery = caption.replace('/ask ', '').trim();
    }

    const messageContent = [];

    if (userQuery) {
        messageContent.push({ type: 'text', text: userQuery });
    }

    if (hasDocument) {
        const fileId = document.file_id;
        const mimeType = document.mime_type;
        const fileName = document.file_name;

        if (mimeType === 'application/pdf' || mimeType.startsWith('image/')) {
            const fileBuffer = await downloadFile(fileId, fileName);
            if (fileBuffer) {
                const base64Data = fileBuffer.toString('base64');
                if (mimeType === 'application/pdf') {
                    messageContent.push({
                        type: 'file',
                        file: {
                            filename: fileName,
                            file_data: `data:${mimeType};base64,${base64Data}`
                        }
                    });
                } else if (mimeType.startsWith('image/')) {
                     messageContent.push({
                        type: 'image_url',
                        image_url: {
                            url: `data:${mimeType};base64,${base64Data}`
                        }
                    });
                }
            } else {
                 bot.sendMessage(chatId, '❌ Could not download the attached file.', { reply_to_message_id: msg.message_id });
                 return;
            }
        } else {
             bot.sendMessage(chatId, '❌ Unsupported file type. Only PDF and images are supported.', { reply_to_message_id: msg.message_id });
             return;
        }
    }

    if (hasPhoto) {
        const photoFile = photo[photo.length - 1];
        const fileId = photoFile.file_id;
        const mimeType = 'image/jpeg';
        const fileName = `photo_${fileId}.jpg`;

        const fileBuffer = await downloadFile(fileId, fileName);
        if (fileBuffer) {
            const base64Data = fileBuffer.toString('base64');
             messageContent.push({
                type: 'image_url',
                image_url: {
                    url: `data:${mimeType};base64,${base64Data}`
                }
            });
        } else {
             bot.sendMessage(chatId, '❌ Could not download the attached image.', { reply_to_message_id: msg.message_id });
             return;
        }
    }

    if (messageContent.length === 0) {
        return;
    }

    database.addMessageToContext(userId, { role: 'user', content: messageContent });

    const context = database.getContext(userId, config.contextSize);
    const systemPrompt = database.getSystemPrompt(userId);
    const model = database.getModel(userId);

    const messages = [];
    if (systemPrompt) {
        messages.push({ role: 'system', content: systemPrompt });
    }
    messages.push(...context);

    const botResponse = await openrouter.getOpenRouterResponse(messages, model);

    database.addMessageToContext(userId, { role: 'assistant', content: [{ type: 'text', text: botResponse }] });

    database.saveDatabase();

    bot.sendMessage(chatId, `🤖 ${botResponse}`, { reply_to_message_id: msg.message_id });
});

// Handle callback queries (model selection)
bot.on('callback_query', function onCallbackQuery(callbackQuery) {
    console.log('Callback query received:', callbackQuery);
    const action = callbackQuery.data;
    const msg = callbackQuery.message;
    const userId = callbackQuery.from.id;
    const opts = {
        chat_id: msg.chat.id,
        message_id: msg.message_id
    };

    console.log('Processing callback query:', {
        action,
        userId,
        chatId: msg.chat.id,
        messageId: msg.message_id
    });

    if (action) {
        const model = action.replace('model_', '');
        console.log('Attempting to set model:', model, 'for user:', userId);
        
        // First answer the callback query to remove the loading state
        bot.answerCallbackQuery(callbackQuery.id).then(() => {
            if (database.setModel(userId, model)) {
                const availableModels = database.getAvailableModels(userId);
                const keyboard = {
                    inline_keyboard: availableModels.map(m => [{
                        text: m,
                        callback_data: `model_${m}`
                    }])
                };

                opts.reply_markup = keyboard;
                console.log('Updating message with new model:', model);
                return bot.editMessageText(`Current model: ${model}`, opts);
            } else {
                console.log('Model not available for user tier');
                return bot.answerCallbackQuery(callbackQuery.id, {
                    text: 'This model is not available for your tier',
                    show_alert: true
                });
            }
        }).catch(error => {
            console.error('Error handling callback query:', error);
            bot.answerCallbackQuery(callbackQuery.id, {
                text: 'An error occurred while changing the model',
                show_alert: true
            });
        });
    }
});

// Handle pre-checkout queries
bot.on('pre_checkout_query', async (query) => {
    console.log('Received pre-checkout query:', query);
    try {
        // Always approve the pre-checkout query
        await bot.answerPreCheckoutQuery(query.id, true);
        console.log('Pre-checkout query approved');
    } catch (error) {
        console.error('Error handling pre-checkout query:', error);
        await bot.answerPreCheckoutQuery(query.id, false, 'An error occurred while processing your payment.');
    }
});

// Handle successful payments
bot.on('successful_payment', async (msg) => {
    console.log('Received successful payment:', msg.successful_payment);
    try {
        const userId = msg.from.id;
        const payload = JSON.parse(msg.successful_payment.invoice_payload);
        
        if (payload.type === 'subscription') {
            // Set subscription end date to 30 days from now
            const subscriptionEndDate = new Date();
            subscriptionEndDate.setDate(subscriptionEndDate.getDate() + 30);
            
            database.upgradeToPlus(userId, subscriptionEndDate.toISOString());
            await database.saveDatabase();
            
            await bot.sendMessage(msg.chat.id, 
                '🎉 Thank you for upgrading to Plus tier! Your subscription is now active.\n\n' +
                'Your benefits:\n' +
                '• 50 messages per day\n' +
                '• 500 messages per month\n' +
                '• Access to premium models\n' +
                `• Subscription valid until ${subscriptionEndDate.toLocaleDateString()}`,
                {
                    reply_to_message_id: msg.message_id
                }
            );
        }
    } catch (error) {
        console.error('Error processing successful payment:', error);
        await bot.sendMessage(msg.chat.id, 
            '❌ There was an error processing your payment. Please contact support.',
            {
                reply_to_message_id: msg.message_id
            }
        );
    }
});

console.log('Bot initialization complete, starting polling...'); 