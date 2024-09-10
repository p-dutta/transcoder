"""
Database Connections
"""

from urllib.parse import quote

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from .config import settings

# URL-encode the password
encoded_password = quote(settings.DB_PASSWORD)
SQLALCHEMY_DATABASE_URL = (f"postgresql://{settings.DB_USER}:{encoded_password}@{settings.DB_HOSTNAME}:"
                           f"{settings.DB_PORT}/{settings.DB_NAME}")

engine = create_engine(SQLALCHEMY_DATABASE_URL)

# used for actually talking to the database
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Define the base class which is used for extending our models
Base = declarative_base()


def get_db():
    """Dependency for using ORM"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
