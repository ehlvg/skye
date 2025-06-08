const TelegramBot = require('node-telegram-bot-api');
const config = require('./config');
const database = require('./database');
const openrouter = require('./openrouter');
const axios = require('axios');

const bot = new TelegramBot(config.telegramToken, { polling: true });

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
    const chatId = msg.chat.id;
    const text = msg.text;
    const caption = msg.caption || '';
    const document = msg.document;
    const photo = msg.photo;

    if (config.allowedChats.length > 0 && !config.allowedChats.includes(chatId)) {
        console.log(`Message from unauthorized chat ID: ${chatId}`);

        if (text && text.startsWith('/ask ')) {
             bot.sendMessage(chatId, '🚫 This chat is not authorized to use this bot.', { reply_to_message_id: msg.message_id });
        }

        return;
    }

    if (text === '/start') {
        const welcomeMessage = '👋 Hi! I am a Telegram bot powered by OpenRouter. I can answer your questions and process attached PDF documents and images.\n\nHere are the available commands:\n' +
                             '❓ /ask <your_query> - Ask me a question (you can also attach a file/image).\n' +
                             '⚙️ /setprompt <your_prompt> - Set a system prompt for this chat.\n' +
                             '🔄 /resetprompt - Reset the system prompt for this chat.\n' +
                             '📝 /getprompt - Display the current system prompt for this chat.\n' +
                             '🗑️ /resetcontext - Clear the chat history context for this chat.\n' +
                             '🤖 /model <model_name> - Set the AI model for this chat (e.g., /model openai/gpt-4.1).\n' +
                             'ℹ️ /getmodel - Display the current model for this chat.\n' +
                             '🔄 /resetmodel - Reset the model to default (Gemini).';
        bot.sendMessage(chatId, welcomeMessage, { reply_to_message_id: msg.message_id });
        return;
    }

    if (text && text.startsWith('/setprompt ')) {
        const newPrompt = text.replace('/setprompt ', '').trim();
        database.setSystemPrompt(chatId, newPrompt);
        database.saveDatabase();
        bot.sendMessage(chatId, '✅ System prompt updated.', { reply_to_message_id: msg.message_id });
        return;
    }

    if (text === '/resetprompt') {
        database.resetSystemPrompt(chatId);
        database.saveDatabase();
        bot.sendMessage(chatId, '🔄 System prompt reset.', { reply_to_message_id: msg.message_id });
        return;
    }

    if (text === '/getprompt') {
        const currentPrompt = database.getSystemPrompt(chatId);
        if (currentPrompt) {
            bot.sendMessage(chatId, `📝 Current system prompt:\n${currentPrompt}`, { reply_to_message_id: msg.message_id });
        } else {
            bot.sendMessage(chatId, 'ℹ️ No system prompt is currently set.', { reply_to_message_id: msg.message_id });
        }
        return;
    }

    if (text === '/resetcontext') {
        database.resetContext(chatId);
        database.saveDatabase();
        bot.sendMessage(chatId, '🗑️ Chat context has been reset.', { reply_to_message_id: msg.message_id });
        return;
    }

    if (text && text.startsWith('/model ')) {
        const newModel = text.replace('/model ', '').trim();
        database.setModel(chatId, newModel);
        database.saveDatabase();
        bot.sendMessage(chatId, `🤖 Model updated to: ${newModel}`, { reply_to_message_id: msg.message_id });
        return;
    }

    if (text === '/getmodel') {
        const currentModel = database.getModel(chatId);
        bot.sendMessage(chatId, `ℹ️ Current model: ${currentModel}`, { reply_to_message_id: msg.message_id });
        return;
    }

    if (text === '/resetmodel') {
        database.resetModel(chatId);
        database.saveDatabase();
        bot.sendMessage(chatId, '🔄 Model reset to default (Gemini).', { reply_to_message_id: msg.message_id });
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
            console.log(`📎 Ignoring attachment message without /ask command from chat ID: ${chatId}`);
        }
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

    database.addMessageToContext(chatId, { role: 'user', content: messageContent });

    const context = database.getContext(chatId, config.contextSize);
    const systemPrompt = database.getSystemPrompt(chatId);
    const model = database.getModel(chatId);

    const messages = [];
    if (systemPrompt) {
        messages.push({ role: 'system', content: systemPrompt });
    }
    messages.push(...context);

    const botResponse = await openrouter.getOpenRouterResponse(messages, model);

    database.addMessageToContext(chatId, { role: 'assistant', content: [{ type: 'text', text: botResponse }] });

    database.saveDatabase();

    bot.sendMessage(chatId, `🤖 ${botResponse}`, { reply_to_message_id: msg.message_id });
});

console.log('🚀 Telegram bot started...'); 