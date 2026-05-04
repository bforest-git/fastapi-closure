# Road Closure Monitoring System

A system for collecting and processing road closure reports via Telegram bot with Yandex.Tracker integration.

## Tech Stack

- **FastAPI** — REST API backend
- **SQLAlchemy** (async) + **aiosqlite** — async database ORM
- **Alembic** — database migrations
- **Pydantic Settings** — configuration management
- **aiogram** — Telegram bot framework
- **startrek-client** — Yandex.Tracker API client
- **slowapi** — rate limiting

## Project Structure

```
.
├── app/
│   ├── main.py              # Application entry point, startup events
│   ├── config.py            # Settings via pydantic-settings
│   ├── dependencies.py      # FastAPI dependencies
│   ├── sync.py              # Background sync with Yandex.Tracker (every 30s)
│   ├── tracker.py           # Tracker client factory
│   ├── api/
│   │   ├── closures.py      # Closure endpoints
│   │   ├── authors.py       # Author management endpoints
│   │   └── issues.py        # Tracker issue endpoints
│   ├── models/              # SQLAlchemy ORM models
│   ├── schemas/             # Pydantic schemas
│   ├── database/            # Database session setup
│   └── services/            # Business logic layer
├── telegram-bot/
│   ├── bot.py               # Telegram bot (aiogram + webhook server)
│   ├── requirements.txt
│   └── .env.example
├── alembic/                 # Database migrations
├── tests/                   # Test suite
├── requirements.txt
├── requirements-dev.txt
└── main.py                  # Convenience runner
```

## Quick Start

### Prerequisites

- Python 3.11+
- Telegram Bot Token (from [@BotFather](https://t.me/BotFather))
- Yandex.Tracker OAuth token and queue key

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/bforest-git/fastapi-closure.git
   cd fastapi-closure
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Create a `.env` file in the project root (see [Environment Variables](#environment-variables)).

5. Apply database migrations:
   ```bash
   alembic upgrade head
   ```

6. Start the FastAPI backend:
   ```bash
   python main.py
   # or
   uvicorn app.main:app --reload
   ```

7. In a separate terminal, start the Telegram bot:
   ```bash
   cd telegram-bot
   pip install -r requirements.txt
   cp .env.example .env  # fill in BOT_TOKEN and API_URL
   python bot.py
   ```

## Environment Variables

Create a `.env` file in the project root:

| Variable | Description | Example |
|----------|-------------|---------|
| `ADMIN_API_KEY` | Secret key for admin endpoints | `supersecretkey` |
| `HOST` | Server host | `0.0.0.0` |
| `PORT` | Server port | `8000` |
| `DATABASE_URL` | SQLAlchemy async database URL | `sqlite+aiosqlite:///./closures.db` |
| `TRACKER_TOKEN` | Yandex.Tracker OAuth token | `y0_AgAAAA...` |
| `TRACKER_QUEUE` | Yandex.Tracker queue key | `ROADS` |
| `BOT_TOKEN` | Telegram bot token | `123456:ABC-DEF...` |

For the Telegram bot, create `telegram-bot/.env`:

| Variable | Description |
|----------|-------------|
| `BOT_TOKEN` | Telegram bot token |
| `API_URL` | FastAPI backend URL (e.g. `http://localhost:8000`) |
| `ADMIN_API_KEY` | Admin API key (same as backend) |

## API Documentation

Interactive docs available at:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Endpoints

#### Closures
| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `POST` | `/closures/` | Submit a new closure report | — |
| `GET` | `/closures/` | List all closures | — |
| `GET` | `/closures/{id}` | Get closure by ID | — |
| `PATCH` | `/closures/{id}` | Update closure | Admin |
| `DELETE` | `/closures/{id}` | Delete closure | Admin |

#### Authors
| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `POST` | `/authors/` | Create author | — |
| `GET` | `/authors/` | List authors | — |
| `GET` | `/authors/search` | Search by messenger + external_id | — |
| `GET` | `/authors/banned` | List banned authors | — |
| `POST` | `/authors/ban` | Ban author | Admin |
| `POST` | `/authors/unban` | Unban author | Admin |

#### Issues
| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `GET` | `/issues/` | List tracker issues | — |
| `GET` | `/issues/{key}` | Get issue by key | — |
| `PATCH` | `/issues/{key}` | Update issue | Admin |

> **Admin endpoints** require `X-API-Key: <ADMIN_API_KEY>` header.

## Running Tests

```bash
pip install -r requirements-dev.txt
pytest
```

## Database Migrations

Create a new migration:
```bash
alembic revision --autogenerate -m "description"
```

Apply migrations:
```bash
alembic upgrade head
```

## How It Works

1. Users send messages to the Telegram bot with hashtags: `#перекрытие`, `#roads`, or `#closure`
2. The bot supports media groups (photo/video albums) with 1-second buffering
3. Messages are saved to the database and a ticket is created in Yandex.Tracker
4. A background task syncs ticket statuses every 30 seconds
5. When a ticket status changes, the bot notifies the original user via reply

## Author

**Yaroslav Kozak**
- GitHub: [@bforest-git](https://github.com/bforest-git)
- Email: kozak.iav@phystech.edu
