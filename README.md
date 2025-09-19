# Telegram Monitor Bot

A powerful and modular Telegram bot, built with `aiogram 3` and `Telethon`, designed to monitor multiple Telegram accounts, track messages in specified chats, detect deletions, and manage media downloads. The bot features a clean, well-structured architecture for easy maintenance and extension.

## ✨ Key Features

-   👤 **Multi-Account Management**: Securely connect multiple Telegram user accounts via an interactive, FSM-based setup process.
-   📡 **Flexible Chat Monitoring**: Monitor public/private channels, groups, and direct messages for new activity.
-   🗑️ **Deletion Detection**: Get instant notifications when a message is deleted from a monitored chat, preserving the original content.
-   💾 **Media Management**: Automatically download media from new messages and store them locally. This can be toggled on a per-chat basis.
-   ⚙️ **Granular Per-Chat Settings**: Customize monitoring for each chat individually:
    -   Check frequency
    -   Number of initial messages to fetch
    -   Database auto-cleaning rules
    -   Media download toggle
    -   Deletion detection toggle
-   📊 **Detailed Statistics**: View in-depth statistics for each monitored chat, including total messages, deletion rates, and total media volume.
-   🛡️ **Robust and Resilient**: Features a supervisor process that ensures monitoring tasks stay online and automatically reconnect if a session drops.
-   🏗️ **Modular Architecture**: The codebase is logically separated into modules (handlers, services, database, etc.), making it easy to understand, maintain, and extend.

---

## 🚀 Getting Started

Follow these instructions to get a local copy up and running.

### Prerequisites

-   Python 3.10+
-   A Telegram account to run the bot (`BOT_TOKEN`). Get one from [@BotFather](https://t.me/BotFather).
-   Telegram API credentials (`api_id` and `api_hash`) for the user accounts you want to monitor. You can obtain these from [my.telegram.org](https://my.telegram.org).

### Installation

1.  **Clone the repository:**
    ```sh
    git clone https://github.com/Muran-prog/telegram-monitor-bot.git
    cd telegram-monitor-bot
    ```

2.  **Create and activate a virtual environment:**
    *   **On macOS / Linux:**
        ```sh
        python3 -m venv venv
        source venv/bin/activate
        ```
    *   **On Windows:**
        ```sh
        python -m venv venv
        .\venv\Scripts\activate
        ```

3.  **Install the required dependencies:**
    ```sh
    pip install -r requirements.txt
    ```

4.  **Configure your environment:**
    Create a file named `.env` in the root directory of the project. You can copy the example:
    ```sh
    cp .env.example .env
    ```
    Now, edit the `.env` file and add your Telegram bot token:
    ```env
    # .env
    BOT_TOKEN="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
    ```

5.  **Run the bot:**
    ```sh
    python bot.py
    ```

---

## 🤖 How to Use

Once the bot is running, interact with it on Telegram.

1.  **Start the Bot**: Open a chat with your bot and send the `/start` or `/menu` command.
2.  **Connect an Account**:
    -   Since you have no accounts connected, you'll be prompted to add one.
    -   Click "➕ Add New Account".
    -   The bot will guide you through an interactive process to enter your `api_id`, `api_hash`, and phone number.
    -   You will be asked for a login code and, if enabled, your 2FA password.
3.  **Manage a Session**:
    -   Once an account is connected, it will appear in the session management menu.
    -   Click on a session (phone number) to view its details.
4.  **Start Monitoring**:
    -   From the session details menu, click "▶️ Start Monitoring". This launches the background supervisor for that account.
5.  **Add a Chat to Monitor**:
    -   Click "📡 Add Entity to Monitor".
    -   Send the bot the username (`@username`), public join link (`t.me/joinchat/...`), or ID of the channel, group, or user you wish to monitor. The connected account will attempt to join (if it's a channel/group) and add it to the monitoring list.
6.  **Manage Monitored Chats**:
    -   Click on the "XX monitored chats" button to see a list of all entities being monitored by that session.
    -   Select a chat to view its management options, including "⚙️ Settings" and "🗑️ Remove from Monitoring".
7.  **View Statistics**:
    -   From the session details menu, click "📊 Statistics" to view and sort high-level stats for all monitored chats.

---

## 📁 Project Structure

The project follows a clean, modular architecture to ensure separation of concerns.

```
telegram-monitor-bot/
├── .env                  # User-created file for secrets
├── requirements.txt      # Project dependencies
├── bot.py                # Main application entry point
└── src/
    ├── config.py           # Configuration loading and constants
    ├── globals.py          # Shared global state (active_sessions, etc.)
    ├── database/
    │   ├── models.py       # DB schema and initialization
    │   └── queries.py      # All SQLite database functions
    ├── handlers/
    │   ├── add_chat_fsm.py
    │   ├── chat_management.py
    │   ├── connect_account_fsm.py
    │   ├── session_management.py
    │   └── statistics.py     # aiogram handlers for user interactions
    ├── keyboards/
    │   └── inline.py       # Functions for creating all inline keyboards
    ├── services/
    │   └── monitoring.py   # Core logic for the Telethon supervisor & workers
    ├── states/
    │   └── user_states.py  # FSM state definitions
    └── utils/
        ├── helpers.py        # Small utility functions
        └── lexicon.py        # All user-facing text strings
```

---

## 🤝 Contributing

Contributions are what make the open-source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

1.  Fork the Project
2.  Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3.  Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4.  Push to the Branch (`git push origin feature/AmazingFeature`)
5.  Open a Pull Request

Please open an issue first to discuss any major changes you would like to make.

---

## 📝 License

Distributed under the MIT License. See `LICENSE` for more information.
