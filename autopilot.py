import asyncio
import aiosqlite
from datetime import datetime

DB_NAME = "socialize_bot.db"

async def get_all_accounts():
    """Получить все аккаунты из базы"""
    async with aiosqlite.connect(DB_NAME) as conn:
        cursor = await conn.execute(
            "SELECT id, user_id, platform, account_name, account_data FROM accounts WHERE is_active = 1"
        )
        return await cursor.fetchall()

async def auto_like(account):
    """Автоматический лайкинг"""
    print(f"👍 Лайк от {account[3]} ({account[2]})")
    return True

async def auto_post(account):
    """Автоматический постинг"""
    print(f"📝 Пост опубликован в {account[3]} ({account[2]})")
    return True

async def auto_message(account):
    """Автоматическая рассылка"""
    print(f"💬 Сообщение отправлено из {account[3]} ({account[2]})")
    return True

async def run_autopilot():
    """Главная функция автопилота"""
    print(f"🔄 Автопилот запущен в {datetime.now()}")
    
    accounts = await get_all_accounts()
    
    if not accounts:
        print("❌ Нет активных аккаунтов для автопилота")
        return
    
    for account in accounts:
        platform = account[2]
        
        if platform == "vk":
            await auto_like(account)
            await auto_post(account)
        elif platform == "telegram":
            await auto_message(account)
        elif platform == "instagram":
            await auto_like(account)
            await auto_post(account)
    
    print(f"✅ Автопилот завершен! {datetime.now()}")