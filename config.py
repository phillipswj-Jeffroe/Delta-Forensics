import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or os.urandom(24).hex()
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 52428800))
    DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///app.db')

    @classmethod
    def from_env(cls):
        return cls()
