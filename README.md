# Modular Role-Playing Chatbot Framework

A highly modular and extensible chatbot framework built with **LlamaIndex** and **Melobot**. This project demonstrates how to build a complex, maintainable, and feature-rich application using a layered architecture and modern design patterns. Its initial use case is to role-play as characters from a visual novel, but its architecture is designed to support multiple chat modes, scheduled tasks, and admin functionalities out of the box.

## ✨ Key Features

  - **🤖 Multi-Mode Chat Engine**:

      - **Role-Playing Mode (`pwvn`)**: Deeply integrated with **RAG (Retrieval-Augmented Generation)** to enable rich, in-character conversations based on a predefined knowledge base (character backstories, dialogue snippets).
      - **General QA Mode (`plain`)**: A standard, stateful question-and-answer mode suitable for general assistant scenarios.
      - **Factory Pattern Driven**: Easily extend the bot with new chat modes by adding new Factory and Service classes with minimal configuration changes.

  - **⚙️ Powerful Session Management**:

      - Full support for multi-user and multi-session isolation.
      - Users can create, switch, list, and delete sessions with simple commands.
      - Supports dynamic switching of character roles and Large Language Models (LLMs) within an active session.

  - **🚀 Proactive & Scheduled Tasks**:

      - Includes a built-in task scheduling service powered by `APScheduler`.
      - Comes with a pre-built **Daily RSS News Feed** feature that automatically fetches, aggregates, and pushes news to configured group chats at a specific time.

  - **🔑 Admin Functionality**:

      - A configuration-based permission system for admin users.
      - Admins can trigger background jobs, reload configurations (extensible), and perform other administrative tasks.

  - **🔌 Dual Adapter Support**:

      - **OneBot V11 Adapter**: Connects to any OneBot v11 compatible chat platform (e.g., QQ) via `melobot`.
      - **Command-Line Adapter**: A full-featured local development tool that can test all core functionalities, including **simulated message pushing**, without needing a live bot connection.

  - **🔧 Clean, Modern Architecture**:

      - **Strictly Layered**: The application is cleanly divided into an Adapter Layer, a Core Layer, and a Services Layer.
      - **Dependency Injection**: Services are assembled centrally at the application's entry point (`adapter/`), promoting high cohesion and low coupling.
      - **Programming to Interfaces**: Core components communicate through abstract interfaces (`interfaces.py`), not concrete implementations.

## 🏛️ Architecture Overview

This project uses a strict three-layer architecture to ensure a clean separation of concerns, enhancing maintainability and testability.

```
+-------------------------------------------------------------------+
|                           Application Entry Point (run.py)        |
|     (Initializes all services and starts background tasks)        |
+-------------------------------------------------------------------+
      |                      |                      |
      v                      v                      v
+-----------------+    +----------------------+   +-----------------------+
| Bot Framework   |    | SchedulerService     |   | Dependencies          |
| (Melobot)       |    | (apscheduler)        |   | (pusher, services...) |
+-----------------+    +----------------------+   +-----------------------+
      | (Events In)               | (Triggers Job)
      v                           v
+-------------------------------------------------------------------+
| Adapter Layer (onebot_adapter.py implementing IMessagePusher)     |<-+
+-------------------------------------------------------------------+  | (Push Msg)
      | (Calls handle_message)                                         |
      v                                                                |
+-------------------------------------------------------------------+  |
| Application Service Layer (core/)                                 |  |
| +--------------+   +-------------+                                |  |
| | UserService  |-->| AdminService|                                |  |
| +--------------+   +-------------+                                |  |
|       | (Uses Factory)                                            |  |
|       v                                                           |  |
+-------------------------------------------------------------------+  |
      | (Creates)                                                      |
      v                                                                |
+-------------------------------------------------------------------+  |
| Domain Service Layer (services/)                                  |  |
| +-------------------+   +----------------+   +-------------------+|  |
| | IChatService Impl |   | NewsService    |   | Scheduler Job Logic|--+
| | (RolePlay/General)|   | (fetch_news)   |   | (_daily_news_job)  |
| +-------------------+   +----------------+   +-------------------+|
+-------------------------------------------------------------------+
```

## 🚀 Getting Started

### 1\. Prerequisites

  - **Python**: Ensure you have Python `3.13` or newer installed.
  - **uv**: This project uses `uv` as its package manager. If you don't have it, please follow the official guide to install it.

### 2\. Installation

```bash
# Clone the repository
git clone https://github.com/fltb/bot-the-defect
cd bot-the-defect

# Install all dependencies using uv
uv sync
```

### 3\. Configuration

All project configurations are managed via environment variables.

```bash
# First, copy the example file
cp .env.example .env
```

Next, edit the `.env` file with your specific settings:

  - **`ONEBOT_WS_URL`**: The WebSocket URL of your OneBot v11 implementation (e.g., go-cqhttp).
  - **`BOT_QQ_ID`**: Your bot's QQ ID number.
  - **`USE_OLLAMA`**: Set to `true` to use a local Ollama model; otherwise, it will use DeepSeek.
  - **`DEEPSEEK_API_KEY`**: Your API key if you are using DeepSeek.
  - **`ADMIN_USER_IDS`**: A comma-separated list of admin QQ IDs (e.g., `10001,10002`).
  - **`NEWS_...`**: Configure the schedule and target group chats for the daily news feed.
  - **`RSS_...`**: Configure the RSS feed URLs for the news service.

### 4\. Prepare the Knowledge Base

Place your character definitions, dialogue data, and other knowledge files into the `knowledge/` directory. Modify `config/settings.py` if nessesary. The application will automatically build the RAG index from these files on its first run.

## 🕹️ Usage

The project provides two modes for running the application:

### Production Mode (with OneBot)

This starts the full application, including the connection to the OneBot V11 backend and the background task scheduler.

```bash
uv run run.py
```

### Development & Testing Mode (CLI)

This is a powerful local development tool that runs without connecting to QQ. It allows you to test all commands and chat logic, and it will **simulate background task message pushes directly in your console**.

```bash
uv run run.py --adapter cli
```

## 📚 Command Reference

Send commands via a private message or by @-mentioning the bot in a group chat.

| Command | Alias(es) | Description |
| :--- | :--- | :--- |
| `/new` | - | 创建新会话。最常用：`/new plain`（普通对话），`/new pwvn <你的角色> <Bot角色>`（角色扮演）。可用模式详见 `/modes`。|
| `/ls` | - | Lists all of your available sessions. |
| `/ss` | - | `/ss <session_id>` - Switches to the specified session using the first few chars of its ID. |
| `/dels`| - | `/dels <session_id>` - Deletes a session. |
| `/ds` | - | Displays detailed information about the current active session. |
| `/sbr` | - | `/sbr <role_name>` - (pwvn mode only) Switches the bot's character role. |
| `/sur` | - | `/sur <role_name>` - (pwvn mode only) Switches your user role. |
| `/sl` | - | `/sl <model_name>` - Switches the LLM for the current session (e.g., `deepseek-chat` or `ollama/qwen2.5`). |
| `/modes` | - | 查看所有对话模式和参数用法，含示例和角色列表。|
| `/help`| - | 显示所有指令帮助。 |

### Admin Commands

| Command | Description |
| :--- | :--- |
| `/admin trigger_news` | Manually triggers the daily news feed job. |
| `/admin reload` | (Placeholder) Reloads application configurations. |

## 🛠️ How to Extend

This architecture is built for extension.

### Adding a New Chat Mode

1.  **Create the Service**: Create a new chat service class in the `services/` directory that implements the `IChatService` interface.
2.  **Create the Factory**: Create a new factory class in `services/factories.py` that implements the `IChatServiceFactory` interface. Its `create_service` method should be responsible for instantiating your new service.
3.  **Register the Factory**: In `cli_adapter.py` and `onebot_adapter.py`, instantiate your new factory and add it to the `factories` dictionary with a unique mode name as the key (e.g., `'my_new_mode'`).
4.  **Done\!** Users can now access your new chat mode via the `/new my_new_mode` command.

## Project Structure

```
roleplay-chatbot/
├── adapters/
│   ├── __init__.py
│   ├── cli_adapter.py          # CLI interaction adapter
│   └── onebot_adapter.py       # OneBot v11 adapter
├── config/
│   ├── __init__.py
│   └── settings.py             # Centralized configuration file
├── core/
│   ├── __init__.py
│   ├── admin.py                # Admin logic
│   ├── interfaces.py           # Core abstraction interfaces
│   ├── models.py               # Data models (UserProfile, SessionInfo)
│   └── user_service.py         # Core user service (coordinator)
├── knowledge/
│   ├── roles.json              # Character definitions
│   ├── dialogs.json            # Dialogue data
│   └── background.txt          # Background knowledge
├── services/
│   ├── __init__.py
│   ├── factories.py            # ChatService factory function
│   ├── general_chat_service.py # General chat logic
│   ├── llm_factory.py          # LLM factory function
│   ├── news_service.py         # News fetching functionality
│   ├── roleplay_pwvn/
│   │   ├── __init__.py
│   │   ├── chatter.py          # Chat functionality
│   │   ├── loader.py           # Data loader
│   │   └── query_engine.py     # RAG (Retrieval-Augmented Generation)
│   └── scheduler_service.py    # Scheduled tasks
├── storage/
│   ├── chat-session/           # Chat session storage (auto-generated)
│   └── user-session/           # User session storage (auto-generated)
├── .env.example                # Example environment variables
├── README.md                   # Project documentation
├── pyproject.toml              # UV Project info
└── run.py                      # Main entry point
```

## 📄 License

This project is licensed under the [AGPL-3.0 license](./LICENSE).
