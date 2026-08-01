import aiosqlite
from datetime import datetime

DB_NAME = "socialize_bot.db"

async def init_db():
    """Инициализация базы данных"""
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            # Включаем поддержку внешних ключей
            await db.execute("PRAGMA foreign_keys = ON")
            
            # Таблица пользователей
            await db.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    full_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица аккаунтов пользователей
            await db.execute('''
                CREATE TABLE IF NOT EXISTS user_accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    platform TEXT,
                    account_name TEXT,
                    account_data TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
                )
            ''')
            
            # Таблица постов пользователей
            await db.execute('''
                CREATE TABLE IF NOT EXISTS user_posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    text TEXT,
                    media_path TEXT,
                    media_type TEXT,
                    status TEXT DEFAULT 'pending',
                    published_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
                )
            ''')
            
            await db.commit()
            print("✅ База данных успешно создана!")
            return True
    except Exception as e:
        print(f"❌ Ошибка при создании базы данных: {e}")
        return False
