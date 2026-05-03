from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import logging

SQLALCHEMY_DATABASE_URL = "sqlite:///./closures.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def migrate_database():
    """Добавляет новые колонки в таблицу closures если они отсутствуют"""
    logger = logging.getLogger(__name__)
    try:
        with engine.connect() as conn:
            # Проверяем существование колонки result
            result = conn.execute(text("PRAGMA table_info(closures)")).fetchall()
            columns = [row[1] for row in result]
            
            if 'result' not in columns:
                logger.info("Adding 'result' column to closures table")
                conn.execute(text("ALTER TABLE closures ADD COLUMN result TEXT"))
                conn.commit()
            
            if 'tracker_text' not in columns:
                logger.info("Adding 'tracker_text' column to closures table")
                conn.execute(text("ALTER TABLE closures ADD COLUMN tracker_text TEXT"))
                conn.commit()
                
    except Exception as e:
        logger.error(f"Database migration error: {e}")