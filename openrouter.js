const axios = require('axios');
const config = require('./config');

async function getOpenRouterResponse(messages, enableWeb) {
    let chosenModel = enableWeb ? "google/gemini-2.5-flash-preview-05-20:online" : "google/gemini-2.5-flash-preview-05-20";
    try {
        const response = await axios.post('https://openrouter.ai/api/v1/chat/completions', {
            model: chosenModel,
            messages: messages
        }, {
            headers: {
                'Authorization': `Bearer ${config.openrouterApiKey}`
            }
        });

        return response.data.choices[0].message.content;
    } catch (error) {
        console.error('Error calling OpenRouter API:', error.response ? error.response.data : error.message);
        return "Sorry, I couldn't get a response from the AI.";
    }
}

module.exports = {
    getOpenRouterResponse
}; 