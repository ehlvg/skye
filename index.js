const TelegramBot = require('node-telegram-bot-api');
const config = require('./config');
const database = require('./database');
const openrouter = require('./openrouter');
const axios = require('axios');
const fs = require('fs').promises;
const path = require('path');

const bot = new TelegramBot(config.telegramToken, { polling: true });

// Function to download a file from Telegram
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

// Load the database when the bot starts
database.loadDatabase();

// Save the database periodically (e.g., every 5 minutes)
setInterval(() => {
    database.saveDatabase();
}, 5 * 60 * 1000);

// Save the database when the process is exiting
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
    const userId = msg.from.id;
    const text = msg.text;
    const document = msg.document;
    const photo = msg.photo;

    if (config.allowedChats.length > 0 && !config.allowedChats.includes(chatId)) {
        console.log(`Message from unauthorized chat ID: ${chatId}`);
        bot.sendMessage(chatId, 'This chat is not authorized to use this bot.');
        return;
    }

    if (text && text.startsWith('/setprompt ')) {
        const newPrompt = text.replace('/setprompt ', '').trim();
        database.setSystemPrompt(chatId, newPrompt);
        database.saveDatabase();
        bot.sendMessage(chatId, 'System prompt updated.');
        return;
    }

    if (text === '/resetprompt') {
        database.resetSystemPrompt(chatId);
        database.saveDatabase();
        bot.sendMessage(chatId, 'System prompt reset.');
        return;
    }

    if (text === '/getprompt') {
        const currentPrompt = database.getSystemPrompt(chatId);
        if (currentPrompt) {
            bot.sendMessage(chatId, `Current system prompt:\n${currentPrompt}`);
        } else {
            bot.sendMessage(chatId, 'No system prompt is currently set.');
        }
        return;
    }

    const isAskCommand = text && text.startsWith('/ask ');
    const hasDocument = document && (document.mime_type === 'application/pdf' || document.mime_type.startsWith('image/'));
    const hasPhoto = photo && photo.length > 0;

    if (!isAskCommand && !hasDocument && !hasPhoto) {
        return;
    }

    let userQuery = '';
    if (isAskCommand) {
        userQuery = text.replace('/ask ', '').trim();
        if (!userQuery && !hasDocument && !hasPhoto) {
             bot.sendMessage(chatId, 'Please provide a query after /ask or attach a supported file/image.');
             return;
        }
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
                 bot.sendMessage(chatId, 'Could not download the attached file.');
                 return;
            }
        } else {
             bot.sendMessage(chatId, 'Unsupported file type. Only PDF and images are supported.');
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
             bot.sendMessage(chatId, 'Could not download the attached image.');
             return;
        }
    }

    if (messageContent.length === 0) {
        bot.sendMessage(chatId, 'Please provide a query or attach a supported file/image.');
        return;
    }

    database.addMessageToContext(chatId, { role: 'user', content: messageContent });

    const context = database.getContext(chatId, config.contextSize);
    const systemPrompt = database.getSystemPrompt(chatId);

    const messages = [];
    if (systemPrompt) {
        messages.push({ role: 'system', content: systemPrompt });
    }
    messages.push(...context);

    const botResponse = await openrouter.getOpenRouterResponse(messages);

    database.addMessageToContext(chatId, { role: 'assistant', content: [{ type: 'text', text: botResponse }] });

    database.saveDatabase();

    bot.sendMessage(chatId, botResponse);
});

console.log('Telegram bot started...'); 