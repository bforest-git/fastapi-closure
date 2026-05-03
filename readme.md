# FastAPI Project

FastAPI project structure.

## Project Structure

```
.
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── api/
│   │   ├── __init__.py
│   │   └── closures.py
│   ├── models/
│   │   └── __init__.py
│   ├── schemas/
│   │   └── __init__.py
│   ├── database/
│   │   └── __init__.py
│   ├── sync.py
│   └── tracker.py
├── main.py
├── requirements.txt
├── readme.md
└── telegram-bot/
    ├── bot.py
    ├── requirements.txt
    └── .env.example
```

## API Documentation

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Application Deployment

The application consists of three main components:
1. FastAPI backend for data processing
2. Synchronization with Yandex.Tracker for creating and tracking tickets
3. Telegram bot for receiving messages from users

### Running all components

For the application to work properly, you need to run:
1. FastAPI backend (from the root directory)
2. Telegram bot (from the telegram-bot directory)

Both components must run simultaneously for correct message processing.

```bash
python3 main.py

cd telegram-bot
python3 bot.py
```

### Using the application

1. Users send messages to the Telegram bot with hashtags:
   - `#перекрытие`
   - `#roads`
   - `#closure`

2. Messages are automatically saved to the database and tickets are created in Yandex.Tracker

3. When tickets are updated in Yandex.Tracker, changes are synchronized with the database and notifications are sent to users in Telegram
