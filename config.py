import logging
import sqlite3
import sys
from aiogram import Bot, Dispatcher


# Configuration
TOKEN = "7511166749:AAEXfRoxFc-LD2UYSb5HczJY8i-3oUCQVSY"  # Replace with your actual bot token
DATABASE_PATH = 'movie_bot.db'

# Initialize bot and dispatcher
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Setup logging
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# SQLite connection
conn = sqlite3.connect(DATABASE_PATH)
cursor = conn.cursor()

# Create necessary tables
cursor.execute('''
    CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY,
        telegram_id TEXT UNIQUE
    )
''')
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        telegram_id TEXT UNIQUE
    )
''')
cursor.execute('''
    CREATE TABLE IF NOT EXISTS channels (
        id INTEGER PRIMARY KEY,
        telegram_id TEXT UNIQUE
    )
''')
cursor.execute('''
    CREATE TABLE IF NOT EXISTS movies (
        id INTEGER PRIMARY KEY,
        code TEXT UNIQUE,
        title TEXT,
        year INTEGER,
        genre TEXT,
        language TEXT,
        video TEXT
    )
''')
conn.commit()

# User state management
user_states = {}

# Track previous states for back functionality
previous_states = {}