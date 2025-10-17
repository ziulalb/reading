import os
from datetime import timedelta


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))

    # Banco de dados - PostgreSQL para produção, SQLite para desenvolvimento
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if DATABASE_URL:
        # Render usa DATABASE_URL com postgres://, mas SQLAlchemy precisa postgresql://
        if DATABASE_URL.startswith('postgres://'):
            DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
        SQLALCHEMY_DATABASE_URI = DATABASE_URL
    else:
        SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(BASE_DIR, 'reading_tracker.db')
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Upload de arquivos
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static/uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

    # Google Books API
    GOOGLE_BOOKS_API_KEY = os.environ.get('GOOGLE_BOOKS_API_KEY', '')
    GOOGLE_BOOKS_API_URL = 'https://www.googleapis.com/books/v1/volumes'

    # Session
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    
    # Socket.IO - Redis para produção, threading para desenvolvimento
    REDIS_URL = os.environ.get('REDIS_URL')
    if REDIS_URL:
        SOCKETIO_ASYNC_MODE = 'redis'
        SOCKETIO_MESSAGE_QUEUE = REDIS_URL
    else:
        SOCKETIO_ASYNC_MODE = 'threading'
