# Telegram OpenRouter Bot

A Telegram bot that uses OpenRouter to answer user questions, maintains chat context, and allows setting a system prompt per chat. Features a freemium model with Lite and Plus tiers.

## Features

-   Connects to Telegram using `node-telegram-bot-api`.
-   Uses OpenRouter for AI responses, including processing attached PDF documents and images.
-   Maintains context of the last 10 messages per chat.
-   Allows setting and resetting a system prompt for individual chats.
-   Freemium model with Lite and Plus tiers:
    -   Lite tier: 10 messages daily, 50 messages monthly
    -   Plus tier: 50 messages daily, 500 messages monthly
-   Premium models available for Plus tier users
-   Monthly subscription using Telegram Stars
-   Persists chat context and system prompts using a simple file-based database (`database.json`).

## Prerequisites

-   Node.js installed (v14 or higher recommended).
-   A Telegram BotFather token.
-   An OpenRouter API key.
-   A Telegram Payment Provider token for handling subscriptions.

## Setup

1.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd telegram-openrouter-bot
    ```

2.  **Install dependencies:**
    ```bash
    npm install
    ```

3.  **Create a `.env` file:**
    Create a file named `.env` in the root directory of the project with the following content:

    ```env
    TELEGRAM_TOKEN=YOUR_TELEGRAM_BOT_TOKEN
    OPENROUTER_API_KEY=YOUR_OPENROUTER_API_KEY
    PAYMENT_PROVIDER_TOKEN=YOUR_PAYMENT_PROVIDER_TOKEN
    ```

    -   Replace `YOUR_TELEGRAM_BOT_TOKEN` with the token you got from BotFather.
    -   Replace `YOUR_OPENROUTER_API_KEY` with your OpenRouter API key.
    -   Replace `YOUR_PAYMENT_PROVIDER_TOKEN` with your Telegram Payment Provider token.

4.  **Running the bot:**

    ```bash
    npm start
    ```

    The bot should now be running and ready to accept messages from any user.

## Commands

-   `/ask <your_query>`: Ask the bot a question. The bot will only respond to messages starting with this command.
-   `/setprompt <your_prompt>`: Sets the system prompt for the current chat.
-   `/resetprompt`: Resets the system prompt for the current chat.
-   `/getprompt`: Displays the current system prompt for the current chat.
-   `/start`: Introduces the bot and lists available commands.
-   `/resetcontext`: Clears the chat history context for the current chat.
-   `/model`: Shows available models for your tier and allows selection.
-   `/profile`: Shows your current tier, usage limits, and subscription status.
-   `/upgrade`: Initiates the upgrade process to Plus tier.

## Subscription Tiers

### Lite Tier (Free)
- 10 messages per day
- 50 messages per month
- Access to basic models:
  - GPT-4.1
  - Gemini 2.5 Flash

### Plus Tier (300 Stars/month)
- 50 messages per day
- 500 messages per month
- Access to all models:
  - GPT-4.1
  - Gemini 2.5 Flash
  - Gemini 2.5 Pro
  - GPT-4 Mini

## Persistence

The bot uses a file named `database.json` in the project directory to store chat context, system prompts, and user data. This file will be automatically created and updated by the bot. Do not manually edit this file while the bot is running.

## Running on a Server

To run this bot on a server, you'll typically follow the same setup steps (cloning, installing dependencies, creating `.env`). You'll need a server environment with Node.js installed. Process managers like `pm2` or `forever` are recommended to keep the bot running reliably in the background and automatically restart it if it crashes.

1.  **Install a process manager (e.g., pm2):**
    ```bash
    npm install -g pm2
    ```

2.  **Start the bot using pm2:**
    Navigate to your project directory on the server and run:
    ```bash
    pm2 start index.js --name "telegram-openrouter-bot"
    ```

3.  **Save the pm2 process list:**
    To ensure the bot restarts after a server reboot:
    ```bash
    pm2 save
    ```

4.  **Startup script generation:**
    Generate a startup script to configure pm2 to start on boot:
    ```bash
    pm2 startup
    ```
    Follow the instructions provided by the `pm2 startup` command.

## Notes

-   Ensure your server's firewall allows outgoing connections to the Telegram and OpenRouter APIs.
-   Keep your `.env` file secure and do not commit it to version control.
-   Monitor the bot's logs for any errors.
-   Attached PDF documents and images are sent to OpenRouter as part of the prompt (requires a multimodal model).
-   Message limits reset daily at 00:00 UTC and monthly on the first day of each month.
-   Subscriptions are valid for 30 days from the purchase date. 