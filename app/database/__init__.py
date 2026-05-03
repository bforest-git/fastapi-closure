from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
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
    """Adds new columns to the closures table if they are missing"""
    try:
        with engine.connect() as conn:
            # Check for the existence of the result column
            result = conn.execute(text("PRAGMA table_info(closures)")).fetchall()
            columns = [row[1] for row in result]
            
            if 'result' not in columns:
                conn.execute(text("ALTER TABLE closures ADD COLUMN result TEXT"))
                conn.commit()
            
            if 'tracker_text' not in columns:
                conn.execute(text("ALTER TABLE closures ADD COLUMN tracker_text TEXT"))
                conn.commit()
                
            if 'is_answered' not in columns:
                conn.execute(text("ALTER TABLE closures ADD COLUMN is_answered BOOLEAN DEFAULT 0 NOT NULL"))
                conn.commit()
                
    except Exception as e:
        pass