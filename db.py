from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config import Config

def get_engine():
    return create_engine(Config.DATABASE_URL)

def get_sessionmaker():
    engine = get_engine()
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)

def get_session():
    Session = get_sessionmaker()
    return Session()
