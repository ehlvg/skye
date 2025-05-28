# Telegram OpenRouter Bot

A Telegram bot that uses OpenRouter to answer user questions, maintains chat context, and allows setting a system prompt per chat.

## Features

-   Connects to Telegram using `node-telegram-bot-api`.
-   Uses OpenRouter for AI responses, including processing attached PDF documents and images.
-   Maintains context of the last 10 messages per chat.
-   Allows setting and resetting a system prompt for individual chats.
-   Restricts bot usage to a predefined list of allowed chat IDs.
-   Persists chat context and system prompts using a simple file-based database (`database.json`).

## Prerequisites

-   Node.js installed (v14 or higher recommended).
-   A Telegram BotFather token.
-   An OpenRouter API key.
-   The IDs of the Telegram chats/groups where the bot is allowed.

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
    ALLOWED_CHATS=CHAT_ID_1,CHAT_ID_2,GROUP_ID_1
    ```

    -   Replace `YOUR_TELEGRAM_BOT_TOKEN` with the token you got from BotFather.
    -   Replace `YOUR_OPENROUTER_API_KEY` with your OpenRouter API key.
    -   Replace `CHAT_ID_1,CHAT_ID_2,GROUP_ID_1` with a comma-separated list of the allowed chat and group IDs. Make sure these are the numerical IDs.

4.  **Running the bot:**

    ```bash
    npm start
    ```

    The bot should now be running and listening for messages in the allowed chats.

## Commands

-   `/ask <your_query>`: Ask the bot a question. The bot will only respond to messages starting with this command.
-   `/setprompt <your_prompt>`: Sets the system prompt for the current chat.
-   `/resetprompt`: Resets the system prompt for the current chat.
-   `/getprompt`: Displays the current system prompt for the current chat.
-   `/start`: Introduces the bot and lists available commands.
-   `/resetcontext`: Clears the chat history context for the current chat.

## Persistence

The bot uses a file named `database.json` in the project directory to store chat context and system prompts. This file will be automatically created and updated by the bot. Do not manually edit this file while the bot is running.

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

-   The IDs of the Telegram chats/groups where the bot is allowed. 