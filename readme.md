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
│   │   └── items.py
│   ├── models/
│   │   └── __init__.py
│   ├── schemas/
│   │   └── __init__.py
│   └── database/
│       └── __init__.py
├── main.py
├── requirements.txt
└── README.md
```

## Installation

1. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Running the Application

```bash
uvicorn main:app --reload
```

Or:

```bash
python main.py
```

The application will be available at `http://localhost:8001`.

## API Documentation

- Swagger UI: `http://localhost:8001/docs`
- ReDoc: `http://localhost:8001/redoc`
