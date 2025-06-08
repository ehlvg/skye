const fs = require('fs').promises;
const path = require('path');

const DB_FILE = path.join(__dirname, 'database.json');

let db = {};

const DEFAULT_LIMITS = {
    lite: {
        daily: 10,
        monthly: 50
    },
    plus: {
        daily: 50,
        monthly: 500
    }
};

const AVAILABLE_MODELS = {
    lite: ["openai/gpt-4.1", "google/gemini-2.5-flash-preview-05-20"],
    plus: ["openai/gpt-4.1", "google/gemini-2.5-flash-preview-05-20", "google/gemini-2.5-pro-preview-05-20", "openai/gpt-4-mini"]
};

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

function getUserData(userId) {
    if (!db[userId]) {
        db[userId] = {
            context: [],
            systemPrompt: null,
            model: "openai/gpt-4.1",
            tier: "lite",
            subscriptionEndDate: null,
            messageCounts: {
                daily: 0,
                monthly: 0,
                lastDailyReset: new Date().toISOString(),
                lastMonthlyReset: new Date().toISOString()
            }
        };
    }
    return db[userId];
}

function getContext(userId, contextSize) {
    return getUserData(userId).context.slice(-contextSize);
}

function addMessageToContext(userId, message) {
    const userData = getUserData(userId);
    userData.context.push(message);
    incrementMessageCount(userId);
}

function getSystemPrompt(userId) {
    return getUserData(userId).systemPrompt;
}

function setSystemPrompt(userId, prompt) {
    getUserData(userId).systemPrompt = prompt;
}

function resetSystemPrompt(userId) {
    getUserData(userId).systemPrompt = null;
}

function resetContext(userId) {
    getUserData(userId).context = [];
}

function getModel(userId) {
    return getUserData(userId).model;
}

function setModel(userId, model) {
    const userData = getUserData(userId);
    const availableModels = AVAILABLE_MODELS[userData.tier];
    if (availableModels.includes(model)) {
        userData.model = model;
        resetContext(userId);
        return true;
    }
    return false;
}

function resetModel(userId) {
    getUserData(userId).model = "openai/gpt-4.1";
}

function getUserProfile(userId) {
    const userData = getUserData(userId);
    const now = new Date();
    const lastDailyReset = new Date(userData.messageCounts.lastDailyReset);
    const lastMonthlyReset = new Date(userData.messageCounts.lastMonthlyReset);
    
    // Check if we need to reset daily count
    if (now.getUTCDate() !== lastDailyReset.getUTCDate() || 
        now.getUTCMonth() !== lastDailyReset.getUTCMonth() || 
        now.getUTCFullYear() !== lastDailyReset.getUTCFullYear()) {
        userData.messageCounts.daily = 0;
        userData.messageCounts.lastDailyReset = now.toISOString();
    }
    
    // Check if we need to reset monthly count
    if (now.getUTCMonth() !== lastMonthlyReset.getUTCMonth() || 
        now.getUTCFullYear() !== lastMonthlyReset.getUTCFullYear()) {
        userData.messageCounts.monthly = 0;
        userData.messageCounts.lastMonthlyReset = now.toISOString();
    }

    const limits = DEFAULT_LIMITS[userData.tier];
    return {
        userId,
        tier: userData.tier,
        subscriptionEndDate: userData.subscriptionEndDate,
        dailyRemaining: limits.daily - userData.messageCounts.daily,
        monthlyRemaining: limits.monthly - userData.messageCounts.monthly,
        model: userData.model
    };
}

function incrementMessageCount(userId) {
    const userData = getUserData(userId);
    userData.messageCounts.daily++;
    userData.messageCounts.monthly++;
}

function canSendMessage(userId) {
    const userData = getUserData(userId);
    const limits = DEFAULT_LIMITS[userData.tier];
    return userData.messageCounts.daily < limits.daily && 
           userData.messageCounts.monthly < limits.monthly;
}

function upgradeToPlus(userId, subscriptionEndDate) {
    const userData = getUserData(userId);
    userData.tier = "plus";
    userData.subscriptionEndDate = subscriptionEndDate;
    userData.messageCounts.daily = 0;
    userData.messageCounts.monthly = 0;
    userData.messageCounts.lastDailyReset = new Date().toISOString();
    userData.messageCounts.lastMonthlyReset = new Date().toISOString();
}

function getAvailableModels(userId) {
    const userData = getUserData(userId);
    return AVAILABLE_MODELS[userData.tier];
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
    resetModel,
    getUserProfile,
    canSendMessage,
    upgradeToPlus,
    getAvailableModels
}; 