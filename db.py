import sqlite3
from bot import DATABASE_PATH

conn = sqlite3.connect(DATABASE_PATH)
cursor = conn.cursor()

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

# Create necessary tables
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
    video TEXT  -- Storing the video file_id as TEXT
);

    ''')

conn.commit()