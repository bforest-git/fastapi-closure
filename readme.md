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

## Развертывание приложения

Приложение состоит из трех основных компонентов:
1. FastAPI-бэкенд для обработки данных
2. Синхронизация с Яндекс.Трекером для создания и отслеживания тикетов
3. Telegram-бот для приема сообщений от пользователей

### Запуск всех компонентов

Для полноценной работы приложения необходимо запустить:
1. FastAPI-бэкенд (из корневой директории)
2. Telegram-бота (из директории telegram-bot)

Оба компонента должны работать одновременно для корректной обработки сообщений.

```bash
python3 main.py

cd telegram-bot
python3 bot.py
```

### Использование приложения

1. Пользователи отправляют сообщения в Telegram-бота с хештегами:
   - `#перекрытие`
   - `#roads`
   - `#closure`

2. Сообщения автоматически сохраняются в базу данных и создаются тикеты в Яндекс.Трекере

3. При обновлении тикетов в Яндекс.Трекере, изменения синхронизируются с базой данных и отправляются уведомления пользователям в Telegram
