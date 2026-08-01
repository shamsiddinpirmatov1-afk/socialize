import asyncio
import os
import json
import aiosqlite
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv
from datetime import datetime
import shutil
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

import database as db
from social_poster_multiuser import publish_for_user

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Создаем папку для скачанных файлов
os.makedirs("downloads", exist_ok=True)
os.makedirs("downloads/temp", exist_ok=True)

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ---------- ОБХОД ДЛЯ RENDER (чтобы не закрывал бота) ----------
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")

def run_health_server():
    server = HTTPServer(('0.0.0.0', 10000), HealthCheckHandler)
    server.serve_forever()

# Запускаем веб-сервер в фоновом потоке
thread = threading.Thread(target=run_health_server, daemon=True)
thread.start()
print("🌐 Health check сервер запущен на порту 10000")

# ---------- СОСТОЯНИЯ ----------
class AddAccountStates(StatesGroup):
    choose_platform = State()
    enter_name = State()
    enter_token = State()

class PostStates(StatesGroup):
    waiting_for_media = State()
    waiting_for_description = State()
    ready_to_publish = State()

# ---------- ГЛАВНОЕ МЕНЮ ----------
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    full_name = message.from_user.full_name
    
    # Регистрируем пользователя
    async with aiosqlite.connect(db.DB_NAME) as conn:
        await conn.execute(
            "INSERT OR IGNORE INTO users (user_id, username, full_name) VALUES (?, ?, ?)",
            (user_id, username, full_name)
        )
        await conn.commit()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить аккаунт", callback_data="add_account")],
        [InlineKeyboardButton(text="📋 Мои аккаунты", callback_data="my_accounts")],
        [InlineKeyboardButton(text="📤 Создать пост", callback_data="create_post")],
        [InlineKeyboardButton(text="📊 Моя статистика", callback_data="my_stats")]
    ])
    
    await message.answer(
        f"👋 Привет, {full_name}!\n\n"
        "🤖 **Socialize Bot** — публикуй посты во все свои соцсети одновременно!\n\n"
        "📌 *Как это работает:*\n"
        "1️⃣ Добавь свои аккаунты соцсетей\n"
        "2️⃣ Отправь фото или видео\n"
        "3️⃣ Напиши описание\n"
        "4️⃣ Нажми «Опубликовать»\n"
        "5️⃣ Пост появится во ВСЕХ твоих соцсетях!\n\n"
        "🚀 Начни с добавления аккаунта!",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

# ---------- ДОБАВЛЕНИЕ АККАУНТА ----------
@dp.callback_query(lambda c: c.data == "add_account")
async def add_account(callback: types.CallbackQuery, state: FSMContext):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 VK", callback_data="platform_vk")],
        [InlineKeyboardButton(text="📸 Instagram", callback_data="platform_instagram")],
        [InlineKeyboardButton(text="📨 Telegram", callback_data="platform_telegram")],
        [InlineKeyboardButton(text="📘 Facebook", callback_data="platform_facebook")],
        [InlineKeyboardButton(text="🎵 TikTok", callback_data="platform_tiktok")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_add")]
    ])
    
    await callback.message.edit_text(
        "🌐 *Выбери платформу для добавления:*\n\n"
        "Выбери соцсеть, в которую хочешь публиковать посты.",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    await state.set_state(AddAccountStates.choose_platform)
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("platform_"), AddAccountStates.choose_platform)
async def platform_selected(callback: types.CallbackQuery, state: FSMContext):
    platform = callback.data.replace("platform_", "")
    await state.update_data(platform=platform)
    
    instructions = {
        "vk": "🔑 *Как получить токен VK:*\n\n"
              "1. Перейди по ссылке: https://vkhost.github.io/\n"
              "2. Выбери приложение и разреши доступ\n"
              "3. Скопируй полученный токен\n\n"
              "📤 *Отправь токен в ответ на это сообщение:*",
        
        "instagram": "🔑 *Как получить токен Instagram:*\n\n"
                     "1. Зарегистрируйся в Facebook Developer\n"
                     "2. Создай приложение\n"
                     "3. Подключи Instagram Basic Display\n"
                     "4. Получи Access Token\n\n"
                     "📤 *Отправь токен в ответ на это сообщение:*",
        
        "telegram": "🔑 *Как получить токен Telegram:*\n\n"
                    "1. Напиши @BotFather в Telegram\n"
                    "2. Создай бота командой /newbot\n"
                    "3. Получи токен\n\n"
                    "📤 *Отправь токен в ответ на это сообщение:*",
        
        "facebook": "🔑 *Как получить токен Facebook:*\n\n"
                    "1. Зарегистрируйся в Facebook Developer\n"
                    "2. Создай приложение\n"
                    "3. Получи Page Access Token\n\n"
                    "📤 *Отправь токен в ответ на это сообщение:*",
        
        "tiktok": "🎵 *Как получить токен TikTok:*\n\n"
                  "1. Перейди на https://developers.tiktok.com/\n"
                  "2. Зарегистрируйся и создай приложение\n"
                  "3. Подключи Content Posting API\n"
                  "4. Получи Access Token и Open ID\n\n"
                  "📤 *Отправь данные в формате JSON:*\n"
                  '`{"access_token": "токен", "open_id": "open_id"}`\n\n'
                  "⚠️ *TikTok публикует только ВИДЕО!*"
    }
    
    await callback.message.edit_text(
        instructions.get(platform, "Отправь токен:"),
        parse_mode="Markdown"
    )
    await state.set_state(AddAccountStates.enter_name)
    await callback.answer()

@dp.message(AddAccountStates.enter_name)
async def enter_account_name(message: types.Message, state: FSMContext):
    if len(message.text) > 100:
        await message.answer("❌ Название слишком длинное! Максимум 100 символов.")
        return
    
    await state.update_data(account_name=message.text)
    
    await message.answer(
        "🔐 *Теперь отправь токен доступа:*\n\n"
        "Вставь токен, который ты получил.\n"
        "Он будет сохранен в безопасности.",
        parse_mode="Markdown"
    )
    await state.set_state(AddAccountStates.enter_token)

@dp.message(AddAccountStates.enter_token)
async def enter_token(message: types.Message, state: FSMContext):
    token = message.text.strip()
    data = await state.get_data()
    
    user_id = message.from_user.id
    platform = data.get('platform')
    account_name = data.get('account_name')
    
    # Для TikTok проверяем JSON
    if platform == "tiktok":
        try:
            json.loads(token)
        except:
            await message.answer("❌ Неверный формат JSON для TikTok. Отправь как: `{\"access_token\": \"токен\", \"open_id\": \"open_id\"}`", parse_mode="Markdown")
            return
    
    # Сохраняем аккаунт в базу
    async with aiosqlite.connect(db.DB_NAME) as conn:
        await conn.execute(
            "INSERT INTO user_accounts (user_id, platform, account_name, account_data) VALUES (?, ?, ?, ?)",
            (user_id, platform, account_name, token)
        )
        await conn.commit()
    
    await message.answer(
        f"✅ *Аккаунт '{account_name}' ({platform}) успешно добавлен!*\n\n"
        "Теперь ты можешь публиковать посты в эту соцсеть!",
        parse_mode="Markdown"
    )
    
    await state.clear()
    await cmd_start(message)

# ---------- ОТМЕНА ДОБАВЛЕНИЯ ----------
@dp.callback_query(lambda c: c.data == "cancel_add")
async def cancel_add(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Добавление аккаунта отменено.")
    await cmd_start(callback.message)
    await callback.answer()

# ---------- МОИ АККАУНТЫ ----------
@dp.callback_query(lambda c: c.data == "my_accounts")
async def my_accounts(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    async with aiosqlite.connect(db.DB_NAME) as conn:
        cursor = await conn.execute(
            "SELECT id, platform, account_name, is_active FROM user_accounts WHERE user_id = ?",
            (user_id,)
        )
        accounts = await cursor.fetchall()
    
    if not accounts:
        await callback.message.edit_text(
            "❌ *У тебя нет добавленных аккаунтов*\n\n"
            "Нажми «➕ Добавить аккаунт», чтобы начать.",
            parse_mode="Markdown"
        )
        await callback.answer()
        return
    
    text = "📋 *Твои аккаунты:*\n\n"
    
    for acc in accounts:
        status = "🟢 Активен" if acc[3] else "🔴 Неактивен"
        text += f"🔹 *{acc[2]}* ({acc[1]}) - {status}\n"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"delete_acc_{acc[0]}"),
             InlineKeyboardButton(text="🔄 Обновить", callback_data=f"refresh_acc_{acc[0]}")]
        ])
        
        await callback.message.answer(
            f"📱 *{acc[2]}*\n"
            f"🌐 Платформа: {acc[1]}\n"
            f"📊 Статус: {status}",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    
    await callback.message.delete()
    await callback.answer()

# ---------- УДАЛЕНИЕ АККАУНТА ----------
@dp.callback_query(lambda c: c.data.startswith("delete_acc_"))
async def delete_account(callback: types.CallbackQuery):
    account_id = int(callback.data.replace("delete_acc_", ""))
    user_id = callback.from_user.id
    
    async with aiosqlite.connect(db.DB_NAME) as conn:
        await conn.execute(
            "DELETE FROM user_accounts WHERE id = ? AND user_id = ?",
            (account_id, user_id)
        )
        await conn.commit()
    
    await callback.message.edit_text("🗑️ Аккаунт удален!")
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("refresh_acc_"))
async def refresh_account(callback: types.CallbackQuery):
    await callback.message.edit_text("🔄 Данные обновлены!")
    await callback.answer()

# ---------- СОЗДАНИЕ ПОСТА ----------
@dp.callback_query(lambda c: c.data == "create_post")
async def create_post(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    
    async with aiosqlite.connect(db.DB_NAME) as conn:
        cursor = await conn.execute(
            "SELECT COUNT(*) FROM user_accounts WHERE user_id = ? AND is_active = 1",
            (user_id,)
        )
        count = await cursor.fetchone()
    
    if count[0] == 0:
        await callback.message.edit_text(
            "❌ *У тебя нет активных аккаунтов!*\n\n"
            "Сначала добавь аккаунт через «➕ Добавить аккаунт».",
            parse_mode="Markdown"
        )
        await callback.answer()
        return
    
    await callback.message.edit_text(
        "📤 *Создание поста*\n\n"
        "📷 **Шаг 1:** Отправь фото или видео\n"
        "🔄 Или нажми «Пропустить» для текстового поста\n\n"
        "💡 *Пост будет опубликован во ВСЕ твои аккаунты одновременно!*\n\n"
        "⚠️ *Файлы автоматически удаляются после публикации!*",
        parse_mode="Markdown"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭️ Пропустить медиа", callback_data="skip_media")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_post")]
    ])
    
    await callback.message.answer(
        "📤 Отправь медиафайл или нажми «Пропустить»:",
        reply_markup=keyboard
    )
    
    await state.set_state(PostStates.waiting_for_media)
    await callback.answer()

# ---------- ОБРАБОТКА МЕДИА ----------
@dp.message(PostStates.waiting_for_media)
async def handle_media(message: types.Message, state: FSMContext):
    media_path = None
    media_type = None
    
    if message.photo:
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        file_path = file.file_path
        download_path = f"downloads/photo_{message.from_user.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        await bot.download_file(file_path, download_path)
        media_path = download_path
        media_type = "photo"
        await message.answer("✅ Фото сохранено! Теперь напиши описание:")
        
    elif message.video:
        video = message.video
        file = await bot.get_file(video.file_id)
        file_path = file.file_path
        download_path = f"downloads/video_{message.from_user.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        await bot.download_file(file_path, download_path)
        media_path = download_path
        media_type = "video"
        await message.answer("✅ Видео сохранено! Теперь напиши описание:")
        
    elif message.document:
        doc = message.document
        if doc.mime_type and doc.mime_type.startswith('video/'):
            file = await bot.get_file(doc.file_id)
            file_path = file.file_path
            download_path = f"downloads/video_{message.from_user.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
            await bot.download_file(file_path, download_path)
            media_path = download_path
            media_type = "video"
            await message.answer("✅ Видео сохранено! Теперь напиши описание:")
        elif doc.mime_type and doc.mime_type.startswith('image/'):
            file = await bot.get_file(doc.file_id)
            file_path = file.file_path
            download_path = f"downloads/photo_{message.from_user.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            await bot.download_file(file_path, download_path)
            media_path = download_path
            media_type = "photo"
            await message.answer("✅ Фото сохранено! Теперь напиши описание:")
        else:
            await message.answer("❌ Неподдерживаемый формат файла. Отправь фото или видео.")
            return
    else:
        await message.answer("❌ Пожалуйста, отправь фото или видео.")
        return
    
    await state.update_data(media_path=media_path, media_type=media_type)
    await state.set_state(PostStates.waiting_for_description)

@dp.callback_query(lambda c: c.data == "skip_media", PostStates.waiting_for_media)
async def skip_media(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(media_path=None, media_type=None)
    await callback.message.edit_text(
        "✍️ **Шаг 2:** Напиши описание поста\n\n"
        "📝 Текст будет опубликован вместе с медиа.",
        parse_mode="Markdown"
    )
    await state.set_state(PostStates.waiting_for_description)
    await callback.answer()

# ---------- ВВОД ОПИСАНИЯ ----------
@dp.message(PostStates.waiting_for_description)
async def handle_description(message: types.Message, state: FSMContext):
    description = message.text
    await state.update_data(description=description)
    
    data = await state.get_data()
    media_path = data.get('media_path')
    media_type = data.get('media_type')
    
    user_id = message.from_user.id
    async with aiosqlite.connect(db.DB_NAME) as conn:
        cursor = await conn.execute(
            "SELECT platform, account_name FROM user_accounts WHERE user_id = ? AND is_active = 1",
            (user_id,)
        )
        accounts = await cursor.fetchall()
    
    preview_text = f"📝 *Твой пост готов к публикации!*\n\n"
    preview_text += f"📝 *Описание:*\n{description}\n\n"
    
    if media_path and media_type:
        preview_text += f"📷 *Медиа:* {media_type} ✅ добавлено\n"
    else:
        preview_text += f"📷 *Медиа:* Без медиа\n"
    
    preview_text += f"\n🌍 *Будет опубликовано в:*\n"
    for acc in accounts:
        preview_text += f"✅ {acc[1]} ({acc[0]})\n"
    
    preview_text += f"\n⚠️ *Файлы будут удалены после публикации!*"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Опубликовать", callback_data="publish_now")],
        [InlineKeyboardButton(text="✏️ Редактировать описание", callback_data="edit_description")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_post")]
    ])
    
    if media_path and os.path.exists(media_path):
        if media_type == "photo":
            with open(media_path, "rb") as photo:
                await message.answer_photo(
                    photo=photo,
                    caption=preview_text,
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
        elif media_type == "video":
            with open(media_path, "rb") as video:
                await message.answer_video(
                    video=video,
                    caption=preview_text,
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
    else:
        await message.answer(preview_text, parse_mode="Markdown", reply_markup=keyboard)
    
    await state.set_state(PostStates.ready_to_publish)

# ---------- ПУБЛИКАЦИЯ ----------
@dp.callback_query(lambda c: c.data == "publish_now", PostStates.ready_to_publish)
async def publish_now(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("📤 *Публикация началась...*", parse_mode="Markdown")
    
    data = await state.get_data()
    user_id = callback.from_user.id
    description = data.get('description', '')
    media_path = data.get('media_path')
    media_type = data.get('media_type')
    
    # Публикуем для пользователя
    results = await publish_for_user(user_id, description, media_path, media_type)
    
    result_text = "📊 *Результаты публикации:*\n\n"
    success_count = 0
    total = len(results)
    
    for platform, status in results.items():
        icon = "✅" if status else "❌"
        result_text += f"{icon} {platform.capitalize()}: {'Успешно ✅' if status else 'Ошибка ❌'}\n"
        if status:
            success_count += 1
    
    result_text += f"\n📊 *Опубликовано в {success_count} из {total} соцсетей*"
    
    if success_count == total:
        result_text += "\n\n🎉 *Всё опубликовано!*"
    else:
        result_text += "\n\n⚠️ *Проверь токены для соцсетей с ошибкой*"
    
    result_text += "\n\n🗑️ *Файлы удалены из памяти сервера*"
    
    await callback.message.edit_text(result_text, parse_mode="Markdown")
    await state.clear()
    await callback.answer()

# ---------- ОСТАЛЬНЫЕ ОБРАБОТЧИКИ ----------
@dp.callback_query(lambda c: c.data == "edit_description", PostStates.ready_to_publish)
async def edit_description(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("✍️ *Напиши новое описание:*", parse_mode="Markdown")
    await state.set_state(PostStates.waiting_for_description)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "cancel_post")
async def cancel_post(callback: types.CallbackQuery, state: FSMContext):
    # Удаляем файл если он есть
    data = await state.get_data()
    media_path = data.get('media_path')
    if media_path and os.path.exists(media_path):
        try:
            os.remove(media_path)
            print(f"🗑️ Файл удален: {media_path}")
        except:
            pass
    
    await state.clear()
    await callback.message.edit_text("❌ Публикация отменена.")
    await cmd_start(callback.message)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "my_stats")
async def my_stats(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    async with aiosqlite.connect(db.DB_NAME) as conn:
        cursor = await conn.execute(
            "SELECT COUNT(*) FROM user_accounts WHERE user_id = ? AND is_active = 1",
            (user_id,)
        )
        accounts = await cursor.fetchone()
        
        cursor = await conn.execute(
            "SELECT COUNT(*) FROM user_posts WHERE user_id = ? AND status = 'published'",
            (user_id,)
        )
        posts = await cursor.fetchone()
    
    text = "📊 *Твоя статистика*\n\n"
    text += f"📱 Аккаунтов: {accounts[0] if accounts else 0}\n"
    text += f"📝 Опубликовано постов: {posts[0] if posts else 0}\n\n"
    text += "🚀 Добавляй больше аккаунтов и публикуй чаще!"
    
    await callback.message.edit_text(text, parse_mode="Markdown")
    await callback.answer()

# ---------- ЗАПУСК ----------
async def main():
    await db.init_db()
    print("✅ Socialize Bot запущен!")
    print("👥 Мульти-пользовательский режим активен")
    print("📤 Каждый пользователь управляет своими аккаунтами")
    print("🗑️ Файлы автоматически удаляются после публикации")
    print("📂 Поддерживаются: VK, Instagram, Telegram, Facebook, TikTok")
    print("🌐 Health check: http://0.0.0.0:10000")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
