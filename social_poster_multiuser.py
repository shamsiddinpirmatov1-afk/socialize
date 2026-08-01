import os
import requests
import vk_api
from vk_api.upload import VkUpload
from aiogram import Bot
from dotenv import load_dotenv
import aiosqlite
import json
import shutil

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
telegram_bot = Bot(token=BOT_TOKEN)

DB_NAME = "socialize_bot.db"

async def get_user_accounts(user_id):
    """Получить все аккаунты пользователя"""
    async with aiosqlite.connect(DB_NAME) as conn:
        cursor = await conn.execute(
            "SELECT id, platform, account_name, account_data FROM user_accounts WHERE user_id = ? AND is_active = 1",
            (user_id,)
        )
        return await cursor.fetchall()

# ---------- ПУБЛИКАЦИЯ В VK ----------
def post_to_vk(account_data, text, media_path=None, media_type=None):
    try:
        vk_session = vk_api.VkApi(token=account_data)
        vk = vk_session.get_api()
        
        if media_path and os.path.exists(media_path):
            upload = VkUpload(vk_session)
            if media_type == 'photo':
                photo = upload.photo_wall(photos=[media_path])[0]
                attachment = f"photo{photo['owner_id']}_{photo['id']}"
                vk.wall.post(message=text, attachments=attachment)
            elif media_type == 'video':
                # Для видео используем прямой метод
                video_data = upload.video(media_path, name=text[:100] if text else "Video")
                attachment = f"video{video_data['owner_id']}_{video_data['video_id']}"
                vk.wall.post(message=text, attachments=attachment)
            else:
                vk.wall.post(message=text)
        else:
            vk.wall.post(message=text)
        return True
    except Exception as e:
        print(f"VK ошибка: {e}")
        return False

# ---------- ПУБЛИКАЦИЯ В TELEGRAM ----------
async def post_to_telegram(account_data, text, media_path=None, media_type=None):
    try:
        bot = Bot(token=account_data)
        if media_path and os.path.exists(media_path):
            with open(media_path, 'rb') as file:
                if media_type == 'photo':
                    await bot.send_photo(chat_id="@ваш_канал", photo=file, caption=text[:1024])
                elif media_type == 'video':
                    await bot.send_video(chat_id="@ваш_канал", video=file, caption=text[:1024])
                else:
                    await bot.send_message(chat_id="@ваш_канал", text=text)
        else:
            await bot.send_message(chat_id="@ваш_канал", text=text)
        await bot.session.close()
        return True
    except Exception as e:
        print(f"Telegram ошибка: {e}")
        return False

# ---------- ПУБЛИКАЦИЯ В INSTAGRAM ----------
def post_to_instagram(account_data, text, media_path=None, media_type=None):
    try:
        url = f"https://graph.facebook.com/v18.0/me/media"
        data = {
            "caption": text,
            "access_token": account_data
        }
        if media_path and os.path.exists(media_path):
            with open(media_path, 'rb') as img:
                files = {"image": img}
                response = requests.post(url, data=data, files=files)
        else:
            response = requests.post(url, data=data)
        return response.status_code == 200
    except Exception as e:
        print(f"Instagram ошибка: {e}")
        return False

# ---------- ПУБЛИКАЦИЯ В FACEBOOK ----------
def post_to_facebook(account_data, text, media_path=None, media_type=None):
    try:
        url = f"https://graph.facebook.com/v18.0/me/feed"
        data = {
            "message": text,
            "access_token": account_data
        }
        if media_path and os.path.exists(media_path):
            with open(media_path, 'rb') as img:
                files = {"source": img}
                response = requests.post(
                    f"https://graph.facebook.com/v18.0/me/photos",
                    data={"message": text, "access_token": account_data},
                    files=files
                )
        else:
            response = requests.post(url, data=data)
        return response.status_code == 200
    except Exception as e:
        print(f"Facebook ошибка: {e}")
        return False

# ---------- ПУБЛИКАЦИЯ В TIKTOK ----------
def post_to_tiktok(account_data, text, media_path=None, media_type=None):
    try:
        if not media_path or not os.path.exists(media_path):
            print("❌ TikTok: Видео обязательно")
            return False
        
        # Парсим данные аккаунта
        account_info = json.loads(account_data) if isinstance(account_data, str) else account_data
        access_token = account_info.get('access_token')
        open_id = account_info.get('open_id')
        
        if not access_token or not open_id:
            print("❌ TikTok: Нет токена")
            return False
        
        headers = {"Authorization": f"Bearer {access_token}"}
        
        # Загружаем видео
        upload_url = "https://open-api.tiktok.com/share/video/upload/"
        with open(media_path, 'rb') as video_file:
            files = {'video': video_file}
            data = {'open_id': open_id, 'access_token': access_token}
            response = requests.post(upload_url, headers=headers, files=files, data=data)
            
            if response.status_code != 200:
                return False
            
            video_id = response.json().get('data', {}).get('video_id')
            if not video_id:
                return False
        
        # Публикуем
        publish_url = "https://open-api.tiktok.com/share/video/publish/"
        publish_data = {
            'open_id': open_id,
            'access_token': access_token,
            'video_id': video_id,
            'text': text[:2000],
            'privacy_level': 'PUBLIC'
        }
        response = requests.post(publish_url, headers=headers, data=publish_data)
        
        if response.status_code == 200:
            print("✅ TikTok: Видео опубликовано!")
            return True
        return False
    except Exception as e:
        print(f"TikTok ошибка: {e}")
        return False

# ---------- ФУНКЦИЯ ДЛЯ УДАЛЕНИЯ ФАЙЛА ----------
def delete_file_safely(file_path):
    """Безопасное удаление файла"""
    try:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            print(f"🗑️ Файл удален: {file_path}")
            return True
    except Exception as e:
        print(f"⚠️ Не удалось удалить файл: {e}")
        return False
    return False

# ---------- ГЛАВНАЯ ФУНКЦИЯ ----------
async def publish_for_user(user_id, text, media_path=None, media_type=None):
    """Публикует пост для конкретного пользователя во все его аккаунты"""
    
    accounts = await get_user_accounts(user_id)
    results = {}
    
    if not accounts:
        results["error"] = "Нет активных аккаунтов"
        return results
    
    # Делаем копию файла перед публикацией
    temp_file_path = None
    if media_path and os.path.exists(media_path):
        # Создаем временную копию
        temp_dir = "downloads/temp"
        os.makedirs(temp_dir, exist_ok=True)
        temp_file_path = os.path.join(temp_dir, os.path.basename(media_path))
        shutil.copy2(media_path, temp_file_path)
        print(f"📋 Создана копия: {temp_file_path}")
    
    for acc in accounts:
        account_id, platform, account_name, account_data = acc
        print(f"📤 Публикую в {platform} ({account_name})...")
        
        try:
            if platform == "vk":
                status = post_to_vk(account_data, text, temp_file_path or media_path, media_type)
            elif platform == "telegram":
                status = await post_to_telegram(account_data, text, temp_file_path or media_path, media_type)
            elif platform == "instagram":
                status = post_to_instagram(account_data, text, temp_file_path or media_path, media_type)
            elif platform == "facebook":
                status = post_to_facebook(account_data, text, temp_file_path or media_path, media_type)
            elif platform == "tiktok":
                if media_type == "video":
                    status = post_to_tiktok(account_data, text, temp_file_path or media_path, media_type)
                else:
                    print(f"⚠️ TikTok: нужно видео")
                    status = False
            else:
                status = False
        except Exception as e:
            print(f"❌ Ошибка {platform}: {e}")
            status = False
        
        results[platform] = status
        print(f"  {'✅' if status else '❌'} {platform}")
    
    # Сохраняем пост в БД
    async with aiosqlite.connect(DB_NAME) as conn:
        await conn.execute(
            "INSERT INTO user_posts (user_id, text, media_path, media_type, status) VALUES (?, ?, ?, ?, ?)",
            (user_id, text, media_path, media_type, 'published')
        )
        await conn.commit()
    
    # УДАЛЯЕМ ВРЕМЕННУЮ КОПИЮ
    if temp_file_path:
        delete_file_safely(temp_file_path)
    
    # УДАЛЯЕМ ОРИГИНАЛЬНЫЙ ФАЙЛ ПОСЛЕ ПУБЛИКАЦИИ
    if media_path and os.path.exists(media_path):
        delete_file_safely(media_path)
    
    # Очищаем папку temp если она пустая
    try:
        temp_dir = "downloads/temp"
        if os.path.exists(temp_dir) and not os.listdir(temp_dir):
            os.rmdir(temp_dir)
            print("🧹 Папка temp очищена")
    except:
        pass
    
    return results