const fs = require('fs').promises;
const path = require('path');

const DB_FILE = path.join(__dirname, 'database.json');

let db = {};

async function loadDatabase() {
    try {
        const data = await fs.readFile(DB_FILE, 'utf8');
        db = JSON.parse(data);
        console.log('Database loaded successfully.');
    } catch (error) {
            console.log('Database file not found, starting with an empty database.');
            db = {};
    }
}

async function saveDatabase() {
    try {
        await fs.writeFile(DB_FILE, JSON.stringify(db, null, 2), 'utf8');
        console.log('Database saved successfully.');
    } catch (error) {
        console.error('Error saving database:', error);
    }
}

function getChatData(chatId) {
    if (!db[chatId]) {
        db[chatId] = { context: [], systemPrompt: null, model: "google/gemini-2.5-flash-preview-05-20" };
    }
    return db[chatId];
}

function getContext(chatId, contextSize) {
    return getChatData(chatId).context.slice(-contextSize);
}

function addMessageToContext(chatId, message) {
    const chatData = getChatData(chatId);
    chatData.context.push(message);
}

function getSystemPrompt(chatId) {
    return getChatData(chatId).systemPrompt;
}

function setSystemPrompt(chatId, prompt) {
    getChatData(chatId).systemPrompt = prompt;
}

function resetSystemPrompt(chatId) {
    getChatData(chatId).systemPrompt = null;
}

function resetContext(chatId) {
    getChatData(chatId).context = [];
}

function getModel(chatId) {
    return getChatData(chatId).model;
}

function setModel(chatId, model) {
    getChatData(chatId).model = model;
    resetContext(chatId);
}

function resetModel(chatId) {
    getChatData(chatId).model = "google/gemini-2.5-flash-preview-05-20";
}

module.exports = {
    loadDatabase,
    saveDatabase,
    getContext,
    addMessageToContext,
    getSystemPrompt,
    setSystemPrompt,
    resetSystemPrompt,
    resetContext,
    getModel,
    setModel,
    resetModel
}; 