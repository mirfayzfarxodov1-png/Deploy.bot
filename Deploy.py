# ================================================================
# ANICITY RASMIY BOT - MANABU USLUBIDAGI MAJBURIY OBUNA BILAN
# ================================================================
# Muallif: @s_2akk
# Kanal: @AniCity_Rasmiy
# ================================================================

import asyncio
import logging
import sqlite3
import os
import re
import io
import hashlib
import random
from datetime import datetime, date
from typing import Tuple, List, Dict, Any, Callable, Awaitable

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, FSInputFile, BufferedInputFile
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ================================================================
# 1-KONFIGURATSIYA
# ================================================================
BOT_TOKEN = "8545654766:AAHc9XBWMsgQWxibBXcPN44vu1rZ6AILlMg"
ADMINS = [5675087151, 6498527560]
MAIN_CHANNEL = "@AniCity_Rasmiy"
AUTHOR_USERNAME = "@s_2akk"
AUTHOR_LINK = "https://t.me/S_2ak"
SUPPORT_USERNAME = "@s_2akk"
SUPPORT_LINK = "https://t.me/S_2ak"
BASE_CHANNEL_ID = -1003888128587

# LOCAL RASMLAR
START_IMAGE_PATH = "Anime.jpg"
ADMIN_IMAGE_PATH = "admin.png"

# ================================================================
# 2-DATABASE
# ================================================================
DB_NAME = 'anime_bot.db'

conn = sqlite3.connect(DB_NAME, check_same_thread=False)
cursor = conn.cursor()

# Media jadvali
cursor.execute('''
CREATE TABLE IF NOT EXISTS media (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code INTEGER UNIQUE,
    type TEXT,
    name TEXT UNIQUE,
    description TEXT,
    image_url TEXT,
    genre TEXT,
    status TEXT DEFAULT "ongoing",
    season INTEGER DEFAULT 1,
    total_parts INTEGER DEFAULT 0,
    views INTEGER DEFAULT 0,
    voice TEXT DEFAULT "",
    sponsor TEXT DEFAULT "",
    quality TEXT DEFAULT "720p",
    created_at TEXT
)
''')

# Qismlar jadvali
cursor.execute('''
CREATE TABLE IF NOT EXISTS parts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    media_id INTEGER,
    part_number INTEGER,
    file_id TEXT,
    caption TEXT,
    created_at TEXT,
    FOREIGN KEY (media_id) REFERENCES media (id) ON DELETE CASCADE
)
''')

# Foydalanuvchilar jadvali
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bot_token TEXT DEFAULT 'main',
    user_id INTEGER,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    is_blocked INTEGER DEFAULT 0,
    registered_at TEXT,
    last_active TEXT,
    coins INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1,
    experience INTEGER DEFAULT 0,
    referral_code TEXT,
    referred_by INTEGER,
    referral_count INTEGER DEFAULT 0,
    last_daily TEXT,
    daily_streak INTEGER DEFAULT 0
)
''')

# Adminlar jadvali
cursor.execute('''
CREATE TABLE IF NOT EXISTS admins (
    user_id INTEGER PRIMARY KEY,
    added_by INTEGER,
    added_at TEXT,
    is_owner INTEGER DEFAULT 0,
    is_co_owner INTEGER DEFAULT 0
)
''')

# Majburiy kanallar jadvali (Manabu uslubida)
cursor.execute('''
CREATE TABLE IF NOT EXISTS channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id TEXT NOT NULL,
    channel_title TEXT,
    channel_url TEXT,
    is_mandatory INTEGER DEFAULT 1,
    added_at TEXT
)
''')

# Sozlamalar jadvali
cursor.execute('''
CREATE TABLE IF NOT EXISTS settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE,
    value TEXT,
    updated_at TEXT
)
''')

# Dastlabki adminlarni qo'shish
now = datetime.now().isoformat()
for admin_id in ADMINS:
    cursor.execute("INSERT OR IGNORE INTO admins (user_id, added_by, added_at, is_owner) VALUES (?, ?, ?, ?)",
                   (admin_id, admin_id, now, 1))
conn.commit()

# Dastlabki sozlamalar
cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", ('force_subscribe', '1'))
cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", ('welcome_message', '✨ Anime botga xush kelibsiz! ✨'))
conn.commit()

print("✅ Database muvaffaqiyatli yuklandi!")

# ================================================================
# 3-BOT
# ================================================================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

# ================================================================
# 4-LOCAL RASM FUNKSIYALARI
# ================================================================
def get_start_image():
    return FSInputFile(START_IMAGE_PATH) if os.path.exists(START_IMAGE_PATH) else None

def get_admin_image():
    return FSInputFile(ADMIN_IMAGE_PATH) if os.path.exists(ADMIN_IMAGE_PATH) else None

# ================================================================
# 5-MAJBURIY OBUNA FUNKSIYALARI (MANABU USLUBIDA)
# ================================================================
def get_force_subscribe_status() -> int:
    """Majburiy obuna faolligini tekshirish"""
    result = cursor.execute("SELECT value FROM settings WHERE key='force_subscribe'").fetchone()
    return int(result[0]) if result else 1

def set_force_subscribe_status(status: int):
    """Majburiy obuna holatini o'zgartirish"""
    cursor.execute("UPDATE settings SET value=?, updated_at=? WHERE key='force_subscribe'", (str(status), datetime.now().isoformat()))
    conn.commit()

def get_channels(is_mandatory: int = 1) -> List[tuple]:
    """Majburiy kanallar ro'yxatini olish"""
    return cursor.execute("SELECT channel_id, channel_title, channel_url FROM channels WHERE is_mandatory=?", (is_mandatory,)).fetchall()

def add_channel(channel_id: str, channel_title: str, channel_url: str, is_mandatory: int = 1):
    """Yangi kanal qo'shish"""
    cursor.execute("INSERT OR IGNORE INTO channels (channel_id, channel_title, channel_url, is_mandatory, added_at) VALUES (?, ?, ?, ?, ?)",
                   (channel_id, channel_title, channel_url, is_mandatory, datetime.now().isoformat()))
    conn.commit()

def remove_channel(channel_id: str):
    """Kanalni o'chirish"""
    cursor.execute("DELETE FROM channels WHERE channel_id=?", (channel_id,))
    conn.commit()

async def check_force_subscription(user_id: int) -> bool:
    """Foydalanuvchi majburiy kanallarga a'zoligini tekshirish (Manabu uslubida)"""
    if get_force_subscribe_status() == 0:
        return True
    
    channels = get_channels(is_mandatory=1)
    if not channels:
        return True
    
    for channel in channels:
        channel_id = channel[0]
        try:
            member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
            if member.status in ['left', 'kicked']:
                return False
        except Exception as e:
            print(f"Kanal tekshirish xatosi {channel_id}: {e}")
            return False
    
    return True

async def send_force_channels(message: Message):
    """Majburiy kanallarni ko'rsatish"""
    channels = get_channels(is_mandatory=1)
    if not channels:
        return
    
    text = "⚠️ Botdan foydalanish uchun quyidagi kanallarga a'zo bo'ling:\n\n"
    for ch in channels:
        text += f"📢 {ch[1]}\n{ch[2]}\n\n"
    text += "✅ A'zo bo'lgach **Tekshirish** tugmasini bosing."
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_subscription")]
    ])
    
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")

def get_welcome_message() -> str:
    """Xush kelibsiz xabarini olish"""
    result = cursor.execute("SELECT value FROM settings WHERE key='welcome_message'").fetchone()
    return result[0] if result else "✨ Anime botga xush kelibsiz! ✨"

# ================================================================
# 6-FOYDALANUVCHI FUNKSIYALARI (MANABU USLUBIDA)
# ================================================================
def generate_referral_code(user_id: int) -> str:
    """Referal kod yaratish"""
    return hashlib.md5(f"{user_id}_{datetime.now().isoformat()}".encode()).hexdigest()[:8]

def save_user(user) -> None:
    """Foydalanuvchini bazaga saqlash"""
    existing = cursor.execute("SELECT id FROM users WHERE user_id=? AND bot_token='main'", (user.id,)).fetchone()
    now_str = datetime.now().isoformat()
    
    if not existing:
        referral_code = generate_referral_code(user.id)
        cursor.execute("INSERT INTO users (bot_token, user_id, username, first_name, last_name, registered_at, last_active, referral_code, coins) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                       ('main', user.id, user.username, user.first_name, user.last_name, now_str, now_str, referral_code, 100))
        conn.commit()
    else:
        cursor.execute("UPDATE users SET last_active=?, username=?, first_name=? WHERE user_id=? AND bot_token='main'",
                       (now_str, user.username, user.first_name, user.id))
        conn.commit()

def update_user_coins(user_id: int, amount: int):
    """Foydalanuvchi tangalarini yangilash"""
    cursor.execute("UPDATE users SET coins = coins + ? WHERE user_id=? AND bot_token='main'", (amount, user_id))
    conn.commit()

def get_user_data(user_id: int) -> dict:
    """Foydalanuvchi ma'lumotlarini olish"""
    result = cursor.execute("SELECT coins, level, experience, referral_code, referral_count FROM users WHERE user_id=? AND bot_token='main'", (user_id,)).fetchone()
    if result:
        return {'coins': result[0], 'level': result[1], 'experience': result[2], 'referral_code': result[3], 'referral_count': result[4]}
    return {'coins': 0, 'level': 1, 'experience': 0, 'referral_code': None, 'referral_count': 0}

async def daily_reward(user_id: int) -> tuple:
    """Kunlik bonus berish"""
    today = date.today().isoformat()
    user = cursor.execute("SELECT last_daily, daily_streak FROM users WHERE user_id=? AND bot_token='main'", (user_id,)).fetchone()
    
    if user and user[0] == today:
        return False, 0, 0
    
    streak = 1
    if user and user[0]:
        last_date = datetime.fromisoformat(user[0]).date()
        if (date.today() - last_date).days == 1:
            streak = (user[1] or 0) + 1
    
    reward = random.randint(50, 200) + streak * 10
    cursor.execute("UPDATE users SET coins = coins + ?, last_daily = ?, daily_streak = ? WHERE user_id=? AND bot_token='main'",
                   (reward, today, streak, user_id))
    conn.commit()
    
    return True, reward, streak

# ================================================================
# 7-STATE'LAR
# ================================================================
class AddMediaState(StatesGroup):
    type = State()
    name = State()
    code = State()
    description = State()
    image = State()
    genre = State()
    status = State()
    season = State()
    voice = State()
    sponsor = State()
    quality = State()

class AddPartState(StatesGroup):
    select_media = State()
    part_number = State()
    video = State()
    caption = State()

class AddMultiplePartsState(StatesGroup):
    select_media = State()
    videos = State()

class EditMediaState(StatesGroup):
    select = State()
    field = State()
    value = State()

class EditPartState(StatesGroup):
    select_media = State()
    select_part = State()
    field = State()
    value = State()

class BroadcastState(StatesGroup):
    message = State()

class AdminManageState(StatesGroup):
    action = State()
    user_id = State()

class SearchState(StatesGroup):
    query = State()
    search_type = State()

class PostState(StatesGroup):
    media_id = State()
    channel = State()
    confirm = State()

class PartPostState(StatesGroup):
    media_id = State()
    part_id = State()
    channel = State()
    confirm = State()

class CodeSearchState(StatesGroup):
    waiting_for_code = State()

class ImageSearchState(StatesGroup):
    waiting_for_image = State()

class ChannelState(StatesGroup):
    waiting_for_channel_id = State()
    waiting_for_channel_title = State()
    waiting_for_channel_url = State()

# ================================================================
# 8-TUGMALAR (MANABU USLUBIDA)
# ================================================================
def create_main_menu():
    """Asosiy menyu (Manabu uslubida)"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = [
        ["🎬 Animelar", "🔍 Qidirish"],
        ["🎲 Random", "📊 Top"],
        ["🆕 Yangi qismlar", "⭐ Sevimlilar"],
        ["👤 Profil", "💰 Kunlik bonus"],
        ["🏆 Reyting", "❓ Yordam"]
    ]
    for row in buttons:
        keyboard.row(*[KeyboardButton(btn) for btn in row])
    return keyboard

def create_admin_menu(user_id: int):
    """Admin menyusi (Manabu uslubida)"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
    buttons = [
        ["📝 Media Qo'shish", "➕ Qism Qo'shish", "📊 Statistika"],
        ["👥 Majburiy Kanal", "👤 Admin Qo'shish", "👤 Admin Chiqarish"],
        ["📋 Bot statistikasi", "💾 Backup", "📢 Xabar Yuborish"],
        ["❌ Chiqish"]
    ]
    for row in buttons:
        keyboard.row(*[KeyboardButton(btn) for btn in row])
    return keyboard

def start_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Kod orqali qidiruv", callback_data="search_by_code")],
        [InlineKeyboardButton(text="🎬 Anime Qidiruv", callback_data="search_anime"),
         InlineKeyboardButton(text="🎭 Drama Qidiruv", callback_data="search_drama")],
        [InlineKeyboardButton(text="🖼 Rasm Orqali Anime Qidiruv", callback_data="search_image"),
         InlineKeyboardButton(text="📖 Qo'llanma", callback_data="guide")],
        [InlineKeyboardButton(text="📢 Reklama", callback_data="advertisement"),
         InlineKeyboardButton(text="📋 Ro'yxat", callback_data="list_all")],
        [InlineKeyboardButton(text="🔐 Admin Panel", callback_data="admin_panel")]
    ])

def admin_panel_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="➕ Media Qo'shish"), KeyboardButton(text="➕ Qism Qo'shish")],
        [KeyboardButton(text="➕ Ko'p Qism Qo'shish"), KeyboardButton(text="✏️ Media Tahrirlash")],
        [KeyboardButton(text="✏️ Qismni Tahrirlash"), KeyboardButton(text="📊 Statistika")],
        [KeyboardButton(text="📢 Xabar Yuborish"), KeyboardButton(text="👥 Majburiy Kanal")],
        [KeyboardButton(text="👑 Admin Qo'shish"), KeyboardButton(text="📨 Post Qilish")],
        [KeyboardButton(text="🎬 Qismni Post Qilish"), KeyboardButton(text="🔙 Asosiy menyu")]
    ], resize_keyboard=True)

def media_list_keyboard(media_type=None, page=0):
    builder = InlineKeyboardBuilder()
    if media_type:
        cursor.execute("SELECT id, name, code FROM media WHERE type = ? ORDER BY name", (media_type,))
    else:
        cursor.execute("SELECT id, name, code FROM media ORDER BY name")
    media_list = cursor.fetchall()
    per_page = 10
    start = page * per_page
    for media_id, name, code in media_list[start:start+per_page]:
        builder.button(text=f"{name} [{code}]", callback_data=f"select_media_{media_id}")
    builder.adjust(1)
    if page > 0:
        builder.row(InlineKeyboardButton(text="⬅️", callback_data=f"media_page_{page-1}_{media_type or ''}"))
    if start+per_page < len(media_list):
        builder.row(InlineKeyboardButton(text="➡️", callback_data=f"media_page_{page+1}_{media_type or ''}"))
    builder.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_admin_reply"))
    return builder.as_markup()

def parts_list_keyboard(media_id, page=0):
    builder = InlineKeyboardBuilder()
    cursor.execute("SELECT part_number, id FROM parts WHERE media_id = ? ORDER BY part_number", (media_id,))
    parts = cursor.fetchall()
    per_page = 20
    start = page * per_page
    for part_num, part_id in parts[start:start+per_page]:
        builder.button(text=f"📹 {part_num}-qism", callback_data=f"select_part_{part_id}")
    builder.adjust(2)
    if page > 0:
        builder.row(InlineKeyboardButton(text="⬅️", callback_data=f"parts_page_{media_id}_{page-1}"))
    if start+per_page < len(parts):
        builder.row(InlineKeyboardButton(text="➡️", callback_data=f"parts_page_{media_id}_{page+1}"))
    builder.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"back_to_media_{media_id}"))
    return builder.as_markup()

def watch_parts_keyboard(media_id, page=0):
    builder = InlineKeyboardBuilder()
    cursor.execute("SELECT part_number FROM parts WHERE media_id = ? ORDER BY part_number", (media_id,))
    parts = cursor.fetchall()
    per_page = 10
    start = page * per_page
    for part_num in parts[start:start+per_page]:
        builder.button(text=f"{part_num[0]}", callback_data=f"watch_part_{media_id}_{part_num[0]}")
    builder.adjust(5)
    if page > 0:
        builder.row(InlineKeyboardButton(text="⬅️", callback_data=f"watch_parts_page_{media_id}_{page-1}"))
    if start+per_page < len(parts):
        builder.row(InlineKeyboardButton(text="➡️", callback_data=f"watch_parts_page_{media_id}_{page+1}"))
    builder.row(InlineKeyboardButton(text="🔙 Ortga", callback_data=f"view_media_{media_id}"))
    return builder.as_markup()

def edit_media_fields_keyboard(media_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Nomi", callback_data=f"edit_media_{media_id}_name")],
        [InlineKeyboardButton(text="🔢 Kod", callback_data=f"edit_media_{media_id}_code")],
        [InlineKeyboardButton(text="📄 Tavsif", callback_data=f"edit_media_{media_id}_description")],
        [InlineKeyboardButton(text="🖼 Rasm", callback_data=f"edit_media_{media_id}_image")],
        [InlineKeyboardButton(text="🎭 Janr", callback_data=f"edit_media_{media_id}_genre")],
        [InlineKeyboardButton(text="📊 Holat", callback_data=f"edit_media_{media_id}_status")],
        [InlineKeyboardButton(text="🎬 Sezon", callback_data=f"edit_media_{media_id}_season")],
        [InlineKeyboardButton(text="🎙 Ovoz", callback_data=f"edit_media_{media_id}_voice")],
        [InlineKeyboardButton(text="🤝 Himoy", callback_data=f"edit_media_{media_id}_sponsor")],
        [InlineKeyboardButton(text="📀 Sifat", callback_data=f"edit_media_{media_id}_quality")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"back_to_media_{media_id}")]
    ])

def edit_part_fields_keyboard(part_id, media_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📹 Video", callback_data=f"edit_part_{part_id}_video")],
        [InlineKeyboardButton(text="📝 Caption", callback_data=f"edit_part_{part_id}_caption")],
        [InlineKeyboardButton(text="🔢 Qism raqami", callback_data=f"edit_part_{part_id}_number")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"back_to_parts_{media_id}")]
    ])

def status_keyboard(media_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟢 Davom etmoqda", callback_data=f"set_status_{media_id}_ongoing")],
        [InlineKeyboardButton(text="✅ Tugallangan", callback_data=f"set_status_{media_id}_completed")],
        [InlineKeyboardButton(text="⏸ To'xtatilgan", callback_data=f"set_status_{media_id}_hiatus")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"back_to_media_{media_id}")]
    ])

# ================================================================
# 9-YORDAMCHI FUNKSIYALAR
# ================================================================
def is_admin(user_id: int) -> bool:
    cursor.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
    return cursor.fetchone() is not None

def is_owner(user_id: int) -> bool:
    cursor.execute("SELECT is_owner FROM admins WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    return result is not None and result[0] == 1

def is_co_owner(user_id: int) -> bool:
    cursor.execute("SELECT is_co_owner FROM admins WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    return result is not None and result[0] == 1

def get_total_anime() -> int:
    return cursor.execute("SELECT COUNT(*) FROM media WHERE type='anime'").fetchone()[0]

def get_total_episodes() -> int:
    return cursor.execute("SELECT COUNT(*) FROM parts").fetchone()[0]

def get_total_users() -> int:
    return cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]

def get_total_views() -> int:
    result = cursor.execute("SELECT SUM(views) FROM media").fetchone()[0]
    return result if result else 0

async def safe_send_message(chat_id: int, text: str, **kwargs):
    try:
        return await bot.send_message(chat_id, text, **kwargs)
    except Exception as e:
        logging.error(f"Xabar yuborish xatosi: {e}")
        return None

async def safe_send_photo(chat_id: int, photo, caption=None, **kwargs):
    try:
        return await bot.send_photo(chat_id, photo, caption=caption, **kwargs)
    except Exception as e:
        logging.error(f"Rasm yuborish xatosi: {e}")
        return await safe_send_message(chat_id, caption if caption else "Rasm yuborib bo'lmadi!", **kwargs)

async def safe_send_video(chat_id: int, video, caption=None, **kwargs):
    try:
        return await bot.send_video(chat_id, video, caption=caption, **kwargs)
    except Exception as e:
        logging.error(f"Video yuborish xatosi: {e}")
        return None

async def send_text_file(chat_id: int, text: str, filename: str):
    try:
        file = io.BytesIO(text.encode('utf-8'))
        document = BufferedInputFile(file.getvalue(), filename=filename)
        await bot.send_document(chat_id, document)
    except Exception as e:
        logging.error(f"Fayl yuborish xatosi: {e}")

async def view_media_by_id(message: Message, media_id: int):
    try:
        cursor.execute("SELECT name, type, description, image_url, genre, status, season, total_parts, views, code, voice, sponsor, quality FROM media WHERE id = ?", (media_id,))
        media = cursor.fetchone()
        if not media:
            await safe_send_message(message.chat.id, "❌ Media topilmadi!")
            return
        name, media_type, desc, image, genre, status, season, total_parts, views, code, voice, sponsor, quality = media
        cursor.execute("UPDATE media SET views = views + 1 WHERE id = ?", (media_id,))
        conn.commit()
        
        status_text = {"ongoing": "🟢 Davom etmoqda", "completed": "✅ Tugallangan", "hiatus": "⏸ To'xtatilgan"}.get(status, "❓")
        voice_text = voice if voice else f"{AUTHOR_USERNAME}"
        sponsor_text = sponsor if sponsor else "AniCity Rasmiy"
        
        text = f"""
┌─────────────────────────────────
🎬 <b>{name}</b>
└─────────────────────────────────

┌─────────────────────────────────
• Janr: {genre}
• Sezon: {season}
• Qism: {total_parts} ta
• Holati: {status_text}
• Ovoz: {voice_text}
• Himoy: {sponsor_text}
• Sifat: {quality}
└─────────────────────────────────

🔢 Kod: <code>{code}</code>
📢 Kanal: {MAIN_CHANNEL}
"""
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📺 Tomosha qilish", callback_data=f"watch_parts_{media_id}")],
            [InlineKeyboardButton(text="🔙 Ortga", callback_data="back_to_start")]
        ])
        
        if image and (image.startswith("http") or image.startswith("AgA")):
            await safe_send_photo(message.chat.id, photo=image, caption=text, reply_markup=keyboard, parse_mode="HTML")
        else:
            await safe_send_message(message.chat.id, text, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        logging.error(f"view_media_by_id xatosi: {e}")
        await safe_send_message(message.chat.id, "❌ Xatolik yuz berdi!")

# ================================================================
# 10-START HANDLER (MANABU USLUBIDA MAJBURIY OBUNA BILAN)
# ================================================================
@dp.message(Command("start"))
async def start(message: Message):
    save_user(message.from_user)
    user_id = message.from_user.id
    
    # Referal kodni tekshirish
    args = message.text.split()
    if len(args) > 1 and args[1].startswith('ref_'):
        ref_code = args[1].replace('ref_', '')
        referrer = cursor.execute("SELECT user_id FROM users WHERE referral_code=? AND bot_token='main'", (ref_code,)).fetchone()
        if referrer and referrer[0] != user_id:
            cursor.execute("UPDATE users SET referred_by=? WHERE user_id=? AND bot_token='main'", (referrer[0], user_id))
            cursor.execute("UPDATE users SET coins = coins + 100, referral_count = referral_count + 1 WHERE user_id=? AND bot_token='main'", (referrer[0],))
            cursor.execute("UPDATE users SET coins = coins + 50 WHERE user_id=? AND bot_token='main'", (user_id,))
            conn.commit()
            await message.answer("✅ Referal kod ishlatildi! +50 tanga!")
    
    # Kod orqali qidiruv parametrini tekshirish
    if len(args) > 1 and args[1].startswith("code_"):
        code = args[1].replace("code_", "")
        if "&part=" in code:
            code, part_num = code.split("&part=")
            try:
                code_int = int(code)
                part_num_int = int(part_num)
                cursor.execute("SELECT id FROM media WHERE code = ?", (code_int,))
                media = cursor.fetchone()
                if media:
                    cursor.execute("SELECT file_id, caption FROM parts WHERE media_id = ? AND part_number = ?", (media[0], part_num_int))
                    part = cursor.fetchone()
                    if part:
                        cursor.execute("SELECT name FROM media WHERE id = ?", (media[0],))
                        media_name = cursor.fetchone()[0]
                        full_caption = f"🎬 {media_name}\n📹 {part_num_int}-qism\n\n{part[1] if part[1] else ''}"
                        await safe_send_video(message.chat.id, video=part[0], caption=full_caption, parse_mode="HTML")
                        return
            except:
                pass
        else:
            try:
                code_int = int(code)
                cursor.execute("SELECT id FROM media WHERE code = ?", (code_int,))
                media = cursor.fetchone()
                if media:
                    await view_media_by_id(message, media[0])
                    return
            except:
                pass
    
    # MAJBURIY OBUNA TEKSHIRUVI (Manabu uslubida)
    if get_force_subscribe_status() == 1:
        if not await check_force_subscription(user_id):
            await send_force_channels(message)
            return
    
    # Xush kelibsiz xabari
    start_image = get_start_image()
    user_data = get_user_data(user_id)
    
    welcome_text = f"""
✨ Assalomu alaykum, {message.from_user.first_name}!

📊 Statistika:
🎬 Animelar: {get_total_anime()}
📺 Qismlar: {get_total_episodes()}
👥 Foydalanuvchilar: {get_total_users()}

👤 Profilingiz:
💰 Tangalar: {user_data['coins']}
⭐ Daraja: {user_data['level']}
📈 Tajriba: {user_data['experience']}

{get_welcome_message()}

⬇️ Quyidagi tugmalardan birini tanlang:
"""
    
    if start_image:
        await safe_send_photo(message.chat.id, photo=start_image, caption=welcome_text, reply_markup=create_main_menu(), parse_mode="HTML")
    else:
        await safe_send_message(message.chat.id, welcome_text, reply_markup=create_main_menu(), parse_mode="HTML")

@dp.callback_query(F.data == "check_subscription")
async def check_subscription_callback(callback: CallbackQuery):
    if await check_force_subscription(callback.from_user.id):
        await callback.answer("✅ A'zolik tasdiqlandi!", show_alert=True)
        await callback.message.delete()
        await start(callback.message)
    else:
        await callback.answer("❌ Siz hali kanallarga a'zo bo'lmagansiz!", show_alert=True)

@dp.callback_query(F.data == "back_to_start")
async def back_to_start(callback: CallbackQuery):
    start_image = get_start_image()
    user_data = get_user_data(callback.from_user.id)
    
    welcome_text = f"""
✨ Assalomu alaykum, {callback.from_user.first_name}!

📊 Statistika:
🎬 Animelar: {get_total_anime()}
📺 Qismlar: {get_total_episodes()}
👥 Foydalanuvchilar: {get_total_users()}

👤 Profilingiz:
💰 Tangalar: {user_data['coins']}
⭐ Daraja: {user_data['level']}
📈 Tajriba: {user_data['experience']}

{get_welcome_message()}

⬇️ Quyidagi tugmalardan birini tanlang:
"""
    try:
        await callback.message.delete()
    except:
        pass
    if start_image:
        await safe_send_photo(callback.from_user.id, photo=start_image, caption=welcome_text, reply_markup=create_main_menu(), parse_mode="HTML")
    else:
        await safe_send_message(callback.from_user.id, welcome_text, reply_markup=create_main_menu(), parse_mode="HTML")
    await callback.answer()

# ================================================================
# 11-FOYDALANUVCHI FUNKSIYALARI (MANABU USLUBIDA)
# ================================================================
@dp.message(F.text == "🎬 Animelar")
async def list_anime(message: Message):
    animes = cursor.execute("SELECT id, name, code, views FROM media WHERE type='anime' ORDER BY created_at DESC LIMIT 20").fetchall()
    if not animes:
        await message.answer("📭 Hozircha anime mavjud emas!")
        return
    
    text = "🎬 ANIMELAR:\n\n"
    builder = InlineKeyboardBuilder()
    for anime_id, name, code, views in animes:
        text += f"• {name} (Kod: {code}) 👁 {views}\n"
        builder.button(text=f"{name[:20]}", callback_data=f"view_media_{anime_id}")
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="🔙 Ortga", callback_data="back_to_start"))
    await message.answer(text, reply_markup=builder.as_markup())

@dp.message(F.text == "🔍 Qidirish")
async def search_start(message: Message, state: FSMContext):
    await state.set_state(SearchState.query)
    await state.update_data(search_type="all")
    await message.answer("🔍 Qidirmoqchi bo'lgan anime nomini yuboring:")

@dp.message(F.text == "🎲 Random")
async def random_anime(message: Message):
    anime = cursor.execute("SELECT id FROM media ORDER BY RANDOM() LIMIT 1").fetchone()
    if anime:
        await view_media_by_id(message, anime[0])
    else:
        await message.answer("📭 Hozircha anime mavjud emas!")

@dp.message(F.text == "📊 Top")
async def top_anime(message: Message):
    animes = cursor.execute("SELECT id, name, code, views FROM media ORDER BY views DESC LIMIT 10").fetchall()
    if not animes:
        await message.answer("📭 Hozircha anime mavjud emas!")
        return
    
    text = "📊 TOP 10 ANIMELAR:\n\n"
    builder = InlineKeyboardBuilder()
    for i, (anime_id, name, code, views) in enumerate(animes, 1):
        text += f"{i}. {name} (Kod: {code}) - 👁 {views}\n"
        builder.button(text=f"{i}. {name[:15]}", callback_data=f"view_media_{anime_id}")
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="🔙 Ortga", callback_data="back_to_start"))
    await message.answer(text, reply_markup=builder.as_markup())

@dp.message(F.text == "🆕 Yangi qismlar")
async def new_episodes(message: Message):
    episodes = cursor.execute("""
        SELECT p.media_id, m.name, p.part_number, p.created_at 
        FROM parts p JOIN media m ON p.media_id = m.id 
        ORDER BY p.created_at DESC LIMIT 10
    """).fetchall()
    
    if not episodes:
        await message.answer("📭 Yangi qismlar mavjud emas!")
        return
    
    text = "🆕 YANGI QISMLAR:\n\n"
    builder = InlineKeyboardBuilder()
    for media_id, name, part_num, created_at in episodes:
        date_str = created_at[:10] if created_at else "Noma'lum"
        text += f"• {name} - {part_num}-qism ({date_str})\n"
        builder.button(text=f"{name[:15]} {part_num}-q", callback_data=f"watch_part_{media_id}_{part_num}")
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="🔙 Ortga", callback_data="back_to_start"))
    await message.answer(text, reply_markup=builder.as_markup())

@dp.message(F.text == "⭐ Sevimlilar")
async def show_favorites(message: Message):
    await message.answer("⭐ Sevimlilar funksiyasi keyingi versiyada qo'shiladi!")

@dp.message(F.text == "👤 Profil")
async def show_profile(message: Message):
    user_data = get_user_data(message.from_user.id)
    text = f"""
👤 PROFIL

📝 Ism: {message.from_user.first_name}
🆔 ID: {message.from_user.id}
💰 Tangalar: {user_data['coins']}
⭐ Daraja: {user_data['level']}
📈 Tajriba: {user_data['experience']}
👥 Referallar: {user_data['referral_count']}
🔗 Referal kodingiz: `ref_{user_data['referral_code']}`

📊 Umumiy statistika:
🎬 Ko'rilgan animelar: 0
📺 Ko'rilgan qismlar: 0
"""
    await message.answer(text, parse_mode="HTML")

@dp.message(F.text == "💰 Kunlik bonus")
async def daily_bonus(message: Message):
    success, reward, streak = await daily_reward(message.from_user.id)
    if success:
        await message.answer(f"✅ Kunlik bonus: +{reward} tanga! (Streak: {streak} kun)")
    else:
        await message.answer("❌ Bugungi bonusni allaqachon olgansiz! Ertaga qaytib keling.")

@dp.message(F.text == "🏆 Reyting")
async def show_leaderboard(message: Message):
    users = cursor.execute("""
        SELECT user_id, username, first_name, coins, level 
        FROM users WHERE bot_token='main' 
        ORDER BY coins DESC LIMIT 10
    """).fetchall()
    
    if not users:
        await message.answer("📭 Reyting bo'sh!")
        return
    
    text = "🏆 TOP 10 (Tangalar bo'yicha):\n\n"
    for i, (user_id, username, first_name, coins, level) in enumerate(users, 1):
        name = f"@{username}" if username else (first_name or f"ID{user_id}")
        text += f"{i}. {name} - 💰{coins} (⭐{level})\n"
    
    await message.answer(text)

@dp.message(F.text == "❓ Yordam")
async def help_command(message: Message):
    text = """
❓ YORDAM

/start - Botni ishga tushirish
/help - Yordam
/admin - Admin panel
/daily - Kunlik bonus
/profile - Profil

📺 Qolgan funksiyalar tugmalarda

👨‍💻 Muallif: @s_2akk
📢 Kanal: @AniCity_Rasmiy
"""
    await message.answer(text)

@dp.message(F.text == "❌ Chiqish")
async def exit_admin(message: Message):
    start_image = get_start_image()
    user_data = get_user_data(message.from_user.id)
    
    welcome_text = f"""
✨ Assalomu alaykum, {message.from_user.first_name}!

📊 Statistika:
🎬 Animelar: {get_total_anime()}
📺 Qismlar: {get_total_episodes()}
👥 Foydalanuvchilar: {get_total_users()}

👤 Profilingiz:
💰 Tangalar: {user_data['coins']}
⭐ Daraja: {user_data['level']}
📈 Tajriba: {user_data['experience']}

{get_welcome_message()}

⬇️ Quyidagi tugmalardan birini tanlang:
"""
    if start_image:
        await safe_send_photo(message.chat.id, photo=start_image, caption=welcome_text, reply_markup=create_main_menu(), parse_mode="HTML")
    else:
        await safe_send_message(message.chat.id, welcome_text, reply_markup=create_main_menu(), parse_mode="HTML")

# ================================================================
# 12-KOD ORQALI QIDIRUV
# ================================================================
@dp.callback_query(F.data == "search_by_code")
async def search_by_code_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(CodeSearchState.waiting_for_code)
    text = "🔍 Qidirilishi kerak bo'lgan anime yoki drama kodini yuboring"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_start")]])
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except:
        await safe_send_message(callback.from_user.id, text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@dp.message(CodeSearchState.waiting_for_code)
async def search_by_code(message: Message, state: FSMContext):
    text = message.text.strip()
    
    if not text.isdigit():
        await message.answer("❌ Iltimos, faqat raqam (kod) yuboring!")
        return
    
    code = int(text)
    cursor.execute("SELECT id FROM media WHERE code = ?", (code,))
    media = cursor.fetchone()
    
    if media:
        await view_media_by_id(message, media[0])
    else:
        await message.answer(f"❌ '{code}' kodli media topilmadi!")
    
    await state.clear()

# ================================================================
# 13-NOM BO'YICHA QIDIRUV
# ================================================================
@dp.callback_query(F.data == "search_anime")
async def search_anime_start(callback: CallbackQuery, state: FSMContext):
    await state.update_data(search_type="anime")
    await state.set_state(SearchState.query)
    text = "🔍 Qidirilishi kerak bo'lgan anime nomini yuboring"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_start")]])
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except:
        await safe_send_message(callback.from_user.id, text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "search_drama")
async def search_drama_start(callback: CallbackQuery, state: FSMContext):
    await state.update_data(search_type="drama")
    await state.set_state(SearchState.query)
    text = "🔍 Qidirilishi kerak bo'lgan drama nomini yuboring"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_start")]])
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except:
        await safe_send_message(callback.from_user.id, text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@dp.message(SearchState.query)
async def search_media_query(message: Message, state: FSMContext):
    query = message.text.strip()
    data = await state.get_data()
    search_type = data.get('search_type', 'all')
    
    if search_type == 'anime':
        cursor.execute("SELECT id, name, code, total_parts, status, views FROM media WHERE type='anime' AND name LIKE ? ORDER BY name", (f"%{query}%",))
    elif search_type == 'drama':
        cursor.execute("SELECT id, name, code, total_parts, status, views FROM media WHERE type='drama' AND name LIKE ? ORDER BY name", (f"%{query}%",))
    else:
        cursor.execute("SELECT id, name, type, code, total_parts, status, views FROM media WHERE name LIKE ? ORDER BY name", (f"%{query}%",))
    
    results = cursor.fetchall()
    
    if not results:
        await safe_send_message(message.chat.id, f"❌ '{query}' bo'yicha hech narsa topilmadi!")
        await state.clear()
        return
    
    builder = InlineKeyboardBuilder()
    for row in results:
        if search_type == 'all':
            media_id, name, m_type, code, parts, status, views = row
            status_emoji = "🟢" if status == "ongoing" else "✅" if status == "completed" else "⏸"
            emoji = "🎬" if m_type == 'anime' else "🎭"
            builder.button(text=f"{emoji} {name} [{code}] {status_emoji} ({parts} qism)", callback_data=f"view_media_{media_id}")
        else:
            media_id, name, code, parts, status, views = row
            status_emoji = "🟢" if status == "ongoing" else "✅" if status == "completed" else "⏸"
            builder.button(text=f"{name} [{code}] {status_emoji} ({parts} qism)", callback_data=f"view_media_{media_id}")
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_start"))
    
    await safe_send_message(message.chat.id, f"🔍 '{query}' bo'yicha topilganlar ({len(results)}):", reply_markup=builder.as_markup())
    await state.clear()

# ================================================================
# 14-RASM ORQALI QIDIRUV
# ================================================================
@dp.callback_query(F.data == "search_image")
async def search_image_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ImageSearchState.waiting_for_image)
    text = (
        "🖼 RASM ORQALI ANIME QIDIRUV\n\n"
        "Qidirmoqchi bo'lgan animening rasmni yuboring.\n\n"
        "📌 QO'LLANMA:\n"
        "• Animening skrinshotini yuboring\n"
        "• Anime posteri yoki banneri EMAS\n\n"
        "Bot rasmni tahlil qilib, eng mos animeni topadi."
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_start")]])
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except:
        await safe_send_message(callback.from_user.id, text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@dp.message(ImageSearchState.waiting_for_image, F.photo)
async def search_by_image(message: Message, state: FSMContext):
    await message.answer("🖼 Rasm qabul qilindi! 🔍 Qidiruv boshlanmoqda...")
    
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    file_bytes = await bot.download_file(file.file_path)
    
    import aiohttp
    import base64
    
    image_base64 = base64.b64encode(file_bytes.read()).decode('utf-8')
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post('https://api.trace.moe/search', data={'image': image_base64}) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    if result.get('result') and len(result['result']) > 0:
                        top_result = result['result'][0]
                        anime_name = top_result.get('filename', 'Noma\'lum')
                        similarity = top_result.get('similarity', 0) * 100
                        episode = top_result.get('episode', '?')
                        
                        cursor.execute("SELECT id, name, code FROM media WHERE name LIKE ? LIMIT 5", (f"%{anime_name}%",))
                        media_results = cursor.fetchall()
                        
                        if media_results:
                            text = f"🔍 Topilgan anime: <b>{anime_name}</b>\n📊 Aniqlik: {similarity:.1f}%\n📺 Epizod: {episode}\n\n"
                            builder = InlineKeyboardBuilder()
                            for media_id, name, code in media_results:
                                builder.button(text=f"🎬 {name} [{code}]", callback_data=f"view_media_{media_id}")
                            builder.adjust(1)
                            builder.row(InlineKeyboardButton(text="🔙 Ortga", callback_data="back_to_start"))
                            await safe_send_message(message.chat.id, text, reply_markup=builder.as_markup(), parse_mode="HTML")
                        else:
                            await message.answer(f"🔍 Topilgan anime: <b>{anime_name}</b>\n📊 Aniqlik: {similarity:.1f}%\n\n❌ Bu anime botda topilmadi!", parse_mode="HTML")
                    else:
                        await message.answer("❌ Hech qanday anime topilmadi! Boshqa rasm yuborib ko'ring.")
                else:
                    await message.answer("❌ API xatolik! Keyinroq urinib ko'ring.")
        except Exception as e:
            logging.error(f"Rasm qidiruv xatosi: {e}")
            cursor.execute("SELECT id, name, code FROM media LIMIT 10")
            media_list = cursor.fetchall()
            if media_list:
                text = "🔍 API vaqtincha ishlamayapti. Quyidagi animelarni ko'ring:\n\n"
                builder = InlineKeyboardBuilder()
                for media_id, name, code in media_list:
                    builder.button(text=f"🎬 {name} [{code}]", callback_data=f"view_media_{media_id}")
                builder.adjust(1)
                builder.row(InlineKeyboardButton(text="🔙 Ortga", callback_data="back_to_start"))
                await safe_send_message(message.chat.id, text, reply_markup=builder.as_markup())
            else:
                await message.answer("❌ Hech qanday anime topilmadi! Keyinroq urinib ko'ring.")
    
    await state.clear()

@dp.message(ImageSearchState.waiting_for_image)
async def search_by_image_invalid(message: Message, state: FSMContext):
    await message.answer("❌ Iltimos, rasm yuboring!")

# ================================================================
# 15-GUIDE, ADVERTISEMENT, LIST ALL
# ================================================================
@dp.callback_query(F.data == "guide")
async def guide_start(callback: CallbackQuery):
    text = (
        "📚 Botni ishlatish bo'yicha qo'llanma:\n\n"
        "🔍 Kod orqali qidiruv - Anime kodini yuborib topish\n"
        "🎬 Anime Qidirish - Botda mavjud bo'lgan animelarni qidirish\n"
        "🎭 Drama Qidirish - Botda mavjud bo'lgan dramalarni qidirish\n"
        "🖼 Rasm Orqali Anime Qidiruv - Nomini topa olmayotgan animeingizni rasm orqali topish\n"
        "💸 Reklama - bot adminlari bilan reklama yoki homiylik yuzasidan aloqaga chiqish\n"
        "📓 Ro'yxat - Botga joylangan Anime va Dramalar ro'yxati\n\n"
        f"👨‍💻 Muallif: <a href='{AUTHOR_LINK}'>{AUTHOR_USERNAME}</a>\n"
        f"🆘 Yordam: <a href='{SUPPORT_LINK}'>{SUPPORT_USERNAME}</a>\n\n"
        f"🆔 Botdagi ID ingiz: {callback.from_user.id}"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_start")]])
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except:
        await safe_send_message(callback.from_user.id, text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "advertisement")
async def advertisement_start(callback: CallbackQuery):
    text = (
        "📌 Reklama va homiylik masalasida admin bilan bog'laning\n\n"
        f"👨‍💻 Muallif: <a href='{AUTHOR_LINK}'>{AUTHOR_USERNAME}</a>"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_start")]])
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except:
        await safe_send_message(callback.from_user.id, text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "list_all")
async def list_all_start(callback: CallbackQuery):
    anime_list = cursor.execute("SELECT name, code, total_parts, status FROM media WHERE type='anime' ORDER BY name").fetchall()
    drama_list = cursor.execute("SELECT name, code, total_parts, status FROM media WHERE type='drama' ORDER BY name").fetchall()
    
    if anime_list:
        anime_text = "🎬 ANIMELAR RO'YXATI\n\n"
        for i, (name, code, parts, status) in enumerate(anime_list, 1):
            status_emoji = "🟢" if status == "ongoing" else "✅" if status == "completed" else "⏸"
            anime_text += f"{i}. {name}\n   Kod: {code} | Qism: {parts} | {status_emoji}\n\n"
        await send_text_file(callback.from_user.id, anime_text, "Animelar_Royxati.txt")
    
    if drama_list:
        drama_text = "🎭 DRAMALAR RO'YXATI\n\n"
        for i, (name, code, parts, status) in enumerate(drama_list, 1):
            status_emoji = "🟢" if status == "ongoing" else "✅" if status == "completed" else "⏸"
            drama_text += f"{i}. {name}\n   Kod: {code} | Qism: {parts} | {status_emoji}\n\n"
        await send_text_file(callback.from_user.id, drama_text, "Dramalar_Royxati.txt")
    
    if not anime_list and not drama_list:
        try:
            await callback.message.edit_text("📭 Hozircha media mavjud emas!", parse_mode="HTML")
        except:
            await safe_send_message(callback.from_user.id, "📭 Hozircha media mavjud emas!", parse_mode="HTML")
    
    await callback.answer()

# ================================================================
# 16-MEDIA KO'RISH
# ================================================================
@dp.callback_query(lambda c: c.data.startswith("view_media_"))
async def view_media(callback: CallbackQuery):
    try:
        parts = callback.data.split("_")
        media_id = int(parts[2])
        cursor.execute("SELECT name, type, description, image_url, genre, status, season, total_parts, views, code, voice, sponsor, quality FROM media WHERE id = ?", (media_id,))
        media = cursor.fetchone()
        if not media:
            await callback.answer("Media topilmadi!")
            return
        name, media_type, desc, image, genre, status, season, total_parts, views, code, voice, sponsor, quality = media
        cursor.execute("UPDATE media SET views = views + 1 WHERE id = ?", (media_id,))
        conn.commit()
        
        status_text = {"ongoing": "🟢 Davom etmoqda", "completed": "✅ Tugallangan", "hiatus": "⏸ To'xtatilgan"}.get(status, "❓")
        voice_text = voice if voice else f"{AUTHOR_USERNAME}"
        sponsor_text = sponsor if sponsor else "AniCity Rasmiy"
        
        text = f"""
┌─────────────────────────────────
🎬 <b>{name}</b>
└─────────────────────────────────

┌─────────────────────────────────
• Janr: {genre}
• Sezon: {season}
• Qism: {total_parts} ta
• Holati: {status_text}
• Ovoz: {voice_text}
• Himoy: {sponsor_text}
• Sifat: {quality}
└─────────────────────────────────

🔢 Kod: <code>{code}</code>
📢 Kanal: {MAIN_CHANNEL}
"""
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📺 Tomosha qilish", callback_data=f"watch_parts_{media_id}")],
            [InlineKeyboardButton(text="🔙 Ortga", callback_data="back_to_start")]
        ])
        
        if image and (image.startswith("http") or image.startswith("AgA")):
            await safe_send_photo(callback.from_user.id, photo=image, caption=text, reply_markup=keyboard, parse_mode="HTML")
        else:
            await safe_send_message(callback.from_user.id, text, reply_markup=keyboard, parse_mode="HTML")
        try:
            await callback.message.delete()
        except:
            pass
        await callback.answer()
    except Exception as e:
        logging.error(f"view_media xatosi: {e}")
        await callback.answer("Xatolik yuz berdi!")

# ================================================================
# 17-QISMLARNI KO'RISH VA TOMOSHA QILISH
# ================================================================
@dp.callback_query(lambda c: c.data.startswith("watch_parts_") and not c.data.startswith("watch_parts_page_"))
async def watch_parts(callback: CallbackQuery):
    try:
        media_id = int(callback.data.split("_")[2])
        cursor.execute("SELECT name FROM media WHERE id = ?", (media_id,))
        media_name = cursor.fetchone()[0]
        cursor.execute("SELECT part_number FROM parts WHERE media_id = ? ORDER BY part_number", (media_id,))
        parts = cursor.fetchall()
        if not parts:
            await callback.answer("Hozircha qismlar mavjud emas!")
            return
        text = f"📺 <b>{media_name}</b>\n\n📹 Qismlarni tanlang:"
        try:
            await callback.message.edit_text(text, reply_markup=watch_parts_keyboard(media_id), parse_mode="HTML")
        except:
            await safe_send_message(callback.from_user.id, text, reply_markup=watch_parts_keyboard(media_id), parse_mode="HTML")
        await callback.answer()
    except Exception as e:
        logging.error(f"watch_parts xatosi: {e}")
        await callback.answer("Xatolik yuz berdi!")

@dp.callback_query(lambda c: c.data.startswith("watch_part_"))
async def watch_part(callback: CallbackQuery):
    try:
        parts = callback.data.split("_")
        media_id = int(parts[2])
        part_num = int(parts[3])
        cursor.execute("SELECT file_id, caption FROM parts WHERE media_id = ? AND part_number = ?", (media_id, part_num))
        part = cursor.fetchone()
        if not part:
            await callback.answer("Qism topilmadi!")
            return
        file_id, caption = part
        cursor.execute("SELECT name FROM media WHERE id = ?", (media_id,))
        media_name = cursor.fetchone()[0]
        full_caption = f"🎬 {media_name}\n📹 {part_num}-qism\n\n{caption if caption else ''}"
        
        # Ko'rishlar statistikasini yangilash
        cursor.execute("UPDATE media SET views = views + 1 WHERE id = ?", (media_id,))
        conn.commit()
        
        # Foydalanuvchi tajribasini oshirish
        cursor.execute("UPDATE users SET experience = experience + 10 WHERE user_id=? AND bot_token='main'", (callback.from_user.id,))
        conn.commit()
        
        await safe_send_video(callback.from_user.id, video=file_id, caption=full_caption, parse_mode="HTML")
        await callback.answer()
    except Exception as e:
        logging.error(f"watch_part xatosi: {e}")
        await callback.answer("Xatolik yuz berdi!")

@dp.callback_query(lambda c: c.data.startswith("watch_parts_page_"))
async def watch_parts_page(callback: CallbackQuery):
    try:
        data = callback.data.split("_")
        if len(data) >= 5:
            media_id = int(data[3])
            page = int(data[4])
        else:
            media_id = int(data[3])
            page = 0
        cursor.execute("SELECT name FROM media WHERE id = ?", (media_id,))
        media_name = cursor.fetchone()[0]
        text = f"📺 <b>{media_name}</b>\n\n📹 Qismlarni tanlang:"
        try:
            await callback.message.edit_text(text, reply_markup=watch_parts_keyboard(media_id, page), parse_mode="HTML")
        except:
            await safe_send_message(callback.from_user.id, text, reply_markup=watch_parts_keyboard(media_id, page), parse_mode="HTML")
        await callback.answer()
    except Exception as e:
        logging.error(f"watch_parts_page xatosi: {e}")
        await callback.answer("Xatolik yuz berdi!")

# ================================================================
# 18-ADMIN PANEL
# ================================================================
@dp.callback_query(F.data == "admin_panel")
async def admin_panel_callback(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Siz admin emassiz!", show_alert=True)
        return
    admin_image = get_admin_image()
    admin_text = (
        "🔐 <b>Admin Panel</b> 🔐\n\n"
        f"👑 Adminlar: {cursor.execute('SELECT COUNT(*) FROM admins').fetchone()[0]}\n"
        f"🎬 Media: {cursor.execute('SELECT COUNT(*) FROM media').fetchone()[0]}\n"
        f"📹 Qismlar: {cursor.execute('SELECT COUNT(*) FROM parts').fetchone()[0]}\n"
        f"👥 Foydalanuvchilar: {cursor.execute('SELECT COUNT(*) FROM users').fetchone()[0]}\n"
        f"👁 Ko'rishlar: {get_total_views()}\n\n"
        "⬇️ Quyidagi tugmalardan foydalaning:"
    )
    try:
        await callback.message.delete()
    except:
        pass
    if admin_image:
        await safe_send_photo(callback.from_user.id, photo=admin_image, caption=admin_text, reply_markup=admin_panel_menu(), parse_mode="HTML")
    else:
        await safe_send_message(callback.from_user.id, admin_text, reply_markup=admin_panel_menu(), parse_mode="HTML")
    await callback.answer()

@dp.message(F.text == "🔙 Asosiy menyu")
async def back_to_main_reply(message: Message):
    start_image = get_start_image()
    user_data = get_user_data(message.from_user.id)
    
    welcome_text = f"""
✨ Assalomu alaykum, {message.from_user.first_name}!

📊 Statistika:
🎬 Animelar: {get_total_anime()}
📺 Qismlar: {get_total_episodes()}
👥 Foydalanuvchilar: {get_total_users()}

👤 Profilingiz:
💰 Tangalar: {user_data['coins']}
⭐ Daraja: {user_data['level']}
📈 Tajriba: {user_data['experience']}

{get_welcome_message()}

⬇️ Quyidagi tugmalardan birini tanlang:
"""
    if start_image:
        await safe_send_photo(message.chat.id, photo=start_image, caption=welcome_text, reply_markup=create_main_menu(), parse_mode="HTML")
    else:
        await safe_send_message(message.chat.id, welcome_text, reply_markup=create_main_menu(), parse_mode="HTML")

@dp.callback_query(F.data == "back_to_admin_reply")
async def back_to_admin_reply(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Ruxsat yo'q!")
        return
    try:
        await callback.message.delete()
    except:
        pass
    admin_image = get_admin_image()
    admin_text = (
        "🔐 <b>Admin Panel</b> 🔐\n\n"
        f"👑 Adminlar: {cursor.execute('SELECT COUNT(*) FROM admins').fetchone()[0]}\n"
        f"🎬 Media: {cursor.execute('SELECT COUNT(*) FROM media').fetchone()[0]}\n"
        f"📹 Qismlar: {cursor.execute('SELECT COUNT(*) FROM parts').fetchone()[0]}\n"
        f"👥 Foydalanuvchilar: {cursor.execute('SELECT COUNT(*) FROM users').fetchone()[0]}\n"
        f"👁 Ko'rishlar: {get_total_views()}\n\n"
        "⬇️ Quyidagi tugmalardan foydalaning:"
    )
    if admin_image:
        await safe_send_photo(callback.from_user.id, photo=admin_image, caption=admin_text, reply_markup=admin_panel_menu(), parse_mode="HTML")
    else:
        await safe_send_message(callback.from_user.id, admin_text, reply_markup=admin_panel_menu(), parse_mode="HTML")
    await callback.answer()

# ================================================================
# 19-MEDIA QO'SHISH
# ================================================================
@dp.message(F.text == "📝 Media Qo'shish")
async def add_media_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎬 Anime", callback_data="media_type_anime")],
        [InlineKeyboardButton(text="🎭 Drama", callback_data="media_type_drama")],
        [InlineKeyboardButton(text="🔙 Bekor", callback_data="cancel_add_admin")]
    ])
    await message.answer("Media turini tanlang:", reply_markup=keyboard)
    await state.set_state(AddMediaState.type)

@dp.callback_query(AddMediaState.type, F.data.startswith("media_type_"))
async def add_media_type(callback: CallbackQuery, state: FSMContext):
    media_type = callback.data.split("_")[2]
    await state.update_data(type=media_type)
    try:
        await callback.message.edit_text("Media nomini kiriting:")
    except:
        await safe_send_message(callback.from_user.id, "Media nomini kiriting:")
    await state.set_state(AddMediaState.name)
    await callback.answer()

@dp.message(AddMediaState.name)
async def add_media_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Media kodini kiriting (faqat raqam, masalan: 1, 2, 3...):")
    await state.set_state(AddMediaState.code)

@dp.message(AddMediaState.code)
async def add_media_code(message: Message, state: FSMContext):
    try:
        code = int(message.text.strip())
        cursor.execute("SELECT id FROM media WHERE code = ?", (code,))
        if cursor.fetchone():
            await message.answer(f"❌ '{code}' kodi mavjud! Boshqa kod kiriting:")
            return
        await state.update_data(code=code)
        await message.answer("Media tavsifini kiriting:")
        await state.set_state(AddMediaState.description)
    except ValueError:
        await message.answer("❌ Faqat raqam kiriting!")

@dp.message(AddMediaState.description)
async def add_media_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    await message.answer("Rasm yuboring (jpg/png) yoki URL kiriting:")
    await state.set_state(AddMediaState.image)

@dp.message(AddMediaState.image, F.photo)
async def add_media_image_photo(message: Message, state: FSMContext):
    await state.update_data(image=message.photo[-1].file_id)
    await message.answer("Janrlarini kiriting (vergul bilan):")
    await state.set_state(AddMediaState.genre)

@dp.message(AddMediaState.image, F.text)
async def add_media_image_url(message: Message, state: FSMContext):
    await state.update_data(image=message.text)
    await message.answer("Janrlarini kiriting (vergul bilan):")
    await state.set_state(AddMediaState.genre)

@dp.message(AddMediaState.genre)
async def add_media_genre(message: Message, state: FSMContext):
    await state.update_data(genre=message.text)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟢 Davom etmoqda", callback_data="add_status_ongoing")],
        [InlineKeyboardButton(text="✅ Tugallangan", callback_data="add_status_completed")],
        [InlineKeyboardButton(text="⏸ To'xtatilgan", callback_data="add_status_hiatus")]
    ])
    await message.answer("Media holatini tanlang:", reply_markup=keyboard)
    await state.set_state(AddMediaState.status)

@dp.callback_query(AddMediaState.status, F.data.startswith("add_status_"))
async def add_media_status(callback: CallbackQuery, state: FSMContext):
    status = callback.data.split("_")[2]
    await state.update_data(status=status)
    try:
        await callback.message.edit_text("Sezon raqamini kiriting (masalan: 1):")
    except:
        await safe_send_message(callback.from_user.id, "Sezon raqamini kiriting (masalan: 1):")
    await state.set_state(AddMediaState.season)
    await callback.answer()

@dp.message(AddMediaState.season)
async def add_media_season(message: Message, state: FSMContext):
    try:
        season = int(message.text.strip())
        await state.update_data(season=season)
        await message.answer("Ovoz beruvchi(lar)ni kiriting (masalan: AniCity):")
        await state.set_state(AddMediaState.voice)
    except ValueError:
        await message.answer("❌ Faqat raqam kiriting!")

@dp.message(AddMediaState.voice)
async def add_media_voice(message: Message, state: FSMContext):
    await state.update_data(voice=message.text)
    await message.answer("Himoy (homiy) ni kiriting (masalan: Nuqtacha):")
    await state.set_state(AddMediaState.sponsor)

@dp.message(AddMediaState.sponsor)
async def add_media_sponsor(message: Message, state: FSMContext):
    await state.update_data(sponsor=message.text)
    await message.answer("Sifatni kiriting (masalan: 720p):")
    await state.set_state(AddMediaState.quality)

@dp.message(AddMediaState.quality)
async def add_media_quality(message: Message, state: FSMContext):
    await state.update_data(quality=message.text)
    data = await state.get_data()
    try:
        cursor.execute("INSERT INTO media (code, type, name, description, image_url, genre, status, season, voice, sponsor, quality, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                       (data['code'], data['type'], data['name'], data['description'], data['image'], data['genre'], data['status'], data['season'], data['voice'], data['sponsor'], data['quality'], datetime.now().isoformat()))
        conn.commit()
        await message.answer(f"✅ <b>{data['name']}</b> qo'shildi!\n\n🔢 Kod: <code>{data['code']}</code>", parse_mode="HTML")
    except sqlite3.IntegrityError:
        await message.answer("❌ Bunday nomli media mavjud!")
    await state.clear()

# ================================================================
# 20-QISM QO'SHISH
# ================================================================
@dp.message(F.text == "➕ Qism Qo'shish")
async def add_part_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await message.answer("Qaysi animega qism qo'shmoqchisiz?\nAnime nomi yoki kodini kiriting:", parse_mode="HTML")
    await state.set_state(AddPartState.select_media)

@dp.message(AddPartState.select_media)
async def add_part_select_media(message: Message, state: FSMContext):
    query = message.text.strip()
    try:
        code = int(query)
        cursor.execute("SELECT id, name FROM media WHERE code = ?", (code,))
    except ValueError:
        cursor.execute("SELECT id, name FROM media WHERE name LIKE ?", (f"%{query}%",))
    
    media = cursor.fetchone()
    if not media:
        await message.answer(f"❌ '{query}' bo'yicha media topilmadi! Qayta kiriting:")
        return
    
    media_id, media_name = media
    await state.update_data(media_id=media_id)
    await message.answer(f"📺 <b>{media_name}</b> uchun qism raqamini kiriting:", parse_mode="HTML")
    await state.set_state(AddPartState.part_number)

@dp.message(AddPartState.part_number)
async def add_part_number(message: Message, state: FSMContext):
    try:
        part_num = int(message.text)
        await state.update_data(part_number=part_num)
        data = await state.get_data()
        cursor.execute("SELECT id FROM parts WHERE media_id = ? AND part_number = ?", (data['media_id'], part_num))
        if cursor.fetchone():
            await message.answer(f"⚠️ {part_num}-qism mavjud! Yangi raqam kiriting:")
            return
        await message.answer(f"🎬 {part_num}-qism videosini yuboring:")
        await state.set_state(AddPartState.video)
    except ValueError:
        await message.answer("❌ Faqat raqam kiriting!")

@dp.message(AddPartState.video, F.video)
async def add_part_video(message: Message, state: FSMContext):
    await state.update_data(video_id=message.video.file_id)
    await message.answer("📝 Qism captioni kiriting:")
    await state.set_state(AddPartState.caption)

@dp.message(AddPartState.caption)
async def add_part_caption(message: Message, state: FSMContext):
    data = await state.update_data(caption=message.text)
    cursor.execute("INSERT INTO parts (media_id, part_number, file_id, caption, created_at) VALUES (?, ?, ?, ?, ?)",
                   (data['media_id'], data['part_number'], data['video_id'], data['caption'], datetime.now().isoformat()))
    cursor.execute("UPDATE media SET total_parts = total_parts + 1 WHERE id = ?", (data['media_id'],))
    conn.commit()
    cursor.execute("SELECT name FROM media WHERE id = ?", (data['media_id'],))
    media_name = cursor.fetchone()[0]
    await message.answer(f"✅ <b>{media_name}</b> ning <b>{data['part_number']}-qismi</b> qo'shildi!", parse_mode="HTML")
    await state.clear()

# ================================================================
# 21-KO'P QISM QO'SHISH
# ================================================================
@dp.message(F.text == "➕ Ko'p Qism Qo'shish")
async def add_multiple_parts_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await message.answer("Qaysi animega qism qo'shmoqchisiz?\nAnime nomi yoki kodini kiriting:", parse_mode="HTML")
    await state.set_state(AddMultiplePartsState.select_media)

@dp.message(AddMultiplePartsState.select_media)
async def add_multiple_parts_select_media(message: Message, state: FSMContext):
    query = message.text.strip()
    try:
        code = int(query)
        cursor.execute("SELECT id, name FROM media WHERE code = ?", (code,))
    except ValueError:
        cursor.execute("SELECT id, name FROM media WHERE name LIKE ?", (f"%{query}%",))
    
    media = cursor.fetchone()
    if not media:
        await message.answer(f"❌ '{query}' bo'yicha media topilmadi! Qayta kiriting:")
        return
    
    media_id, media_name = media
    await state.update_data(media_id=media_id)
    await message.answer(
        f"📺 <b>{media_name}</b> uchun qismlarni yuboring!\n\n"
        "⚠️ QO'LLANMA:\n"
        "Videolarni tagiga son qo'yib yuboring. Bot tartib bilan qabul qiladi.\n"
        "Masalan: 1-qism videosiga captionga 1 yozing\n\n"
        "Tugatish uchun /done",
        parse_mode="HTML"
    )
    await state.update_data(videos=[])
    await state.set_state(AddMultiplePartsState.videos)

@dp.message(AddMultiplePartsState.videos, F.video)
async def add_multiple_parts_video(message: Message, state: FSMContext):
    data = await state.get_data()
    videos = data.get('videos', [])
    caption = message.caption or ""
    match = re.search(r'^(\d+)', caption)
    part_number = int(match.group(1)) if match else (max([v.get('part_number', 0) for v in videos]) + 1 if videos else 1)
    videos.append({'part_number': part_number, 'file_id': message.video.file_id, 'caption': caption})
    await state.update_data(videos=videos)
    await message.answer(f"✅ {part_number}-qism qabul qilindi! ({len(videos)} ta qism saqlandi)\nTugatish uchun /done", parse_mode="HTML")

@dp.message(AddMultiplePartsState.videos, Command("done"))
async def add_multiple_parts_done(message: Message, state: FSMContext):
    data = await state.get_data()
    media_id = data['media_id']
    videos = data.get('videos', [])
    if not videos:
        await message.answer("❌ Hech qanday video yuborilmagan!")
        return
    videos.sort(key=lambda x: x['part_number'])
    saved = 0
    for video in videos:
        cursor.execute("SELECT id FROM parts WHERE media_id = ? AND part_number = ?", (media_id, video['part_number']))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO parts (media_id, part_number, file_id, caption, created_at) VALUES (?, ?, ?, ?, ?)",
                           (media_id, video['part_number'], video['file_id'], video['caption'], datetime.now().isoformat()))
            saved += 1
    if saved > 0:
        cursor.execute("UPDATE media SET total_parts = total_parts + ? WHERE id = ?", (saved, media_id))
        conn.commit()
    await message.answer(f"✅ {saved} ta qism qo'shildi!", parse_mode="HTML")
    await state.clear()

# ================================================================
# 22-MEDIA TAHRIRLASH
# ================================================================
@dp.message(F.text == "✏️ Media Tahrirlash")
async def edit_media_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await message.answer("Qaysi animeni tahrirlamoqchisiz?\nAnime nomi yoki kodini kiriting:", parse_mode="HTML")
    await state.set_state(EditMediaState.select)

@dp.message(EditMediaState.select)
async def edit_media_select(message: Message, state: FSMContext):
    query = message.text.strip()
    try:
        code = int(query)
        cursor.execute("SELECT id, name FROM media WHERE code = ?", (code,))
    except ValueError:
        cursor.execute("SELECT id, name FROM media WHERE name LIKE ?", (f"%{query}%",))
    
    media = cursor.fetchone()
    if not media:
        await message.answer(f"❌ '{query}' bo'yicha media topilmadi! Qayta kiriting:")
        return
    
    media_id, media_name = media
    await state.update_data(media_id=media_id)
    await message.answer(f"✏️ <b>{media_name}</b> tahrirlash\n\nQaysi maydonni tahrirlamoqchisiz?", reply_markup=edit_media_fields_keyboard(media_id), parse_mode="HTML")
    await state.set_state(EditMediaState.field)

@dp.callback_query(F.data.startswith("edit_media_"))
async def edit_media_field(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    media_id = int(parts[2])
    field = parts[3]
    await state.update_data(media_id=media_id, field=field)
    
    field_names = {
        "name": "yangi nomini",
        "code": "yangi kodni (faqat raqam)",
        "description": "yangi tavsifini",
        "image": "yangi rasmni",
        "genre": "yangi janrlarini",
        "status": "yangi holatini",
        "season": "yangi sezon raqamini",
        "voice": "yangi ovoz(lar)ni",
        "sponsor": "yangi himoy (homiy) ni",
        "quality": "yangi sifatni"
    }
    
    if field == "status":
        try:
            await callback.message.edit_text("Yangi holatni tanlang:", reply_markup=status_keyboard(media_id))
        except:
            await safe_send_message(callback.from_user.id, "Yangi holatni tanlang:", reply_markup=status_keyboard(media_id))
        await callback.answer()
        return
    
    try:
        await callback.message.edit_text(f"✏️ {field_names.get(field, 'yangi qiymatini')} kiriting:")
    except:
        await safe_send_message(callback.from_user.id, f"✏️ {field_names.get(field, 'yangi qiymatini')} kiriting:")
    await state.set_state(EditMediaState.value)
    await callback.answer()

@dp.callback_query(F.data.startswith("set_status_"))
async def set_media_status(callback: CallbackQuery, state: FSMContext):
    _, media_id, status = callback.data.split("_")
    cursor.execute("UPDATE media SET status = ? WHERE id = ?", (status, int(media_id)))
    conn.commit()
    try:
        await callback.message.edit_text(f"✅ Holat '{status}' ga o'zgartirildi!")
    except:
        await safe_send_message(callback.from_user.id, f"✅ Holat '{status}' ga o'zgartirildi!")
    await state.clear()
    await callback.answer()

@dp.message(EditMediaState.value, F.text)
async def edit_media_value(message: Message, state: FSMContext):
    data = await state.get_data()
    media_id = data['media_id']
    field = data['field']
    value = message.text
    
    if field == "name":
        try:
            cursor.execute("UPDATE media SET name = ? WHERE id = ?", (value, media_id))
            conn.commit()
            await message.answer(f"✅ Nomi '{value}' ga o'zgartirildi!")
        except:
            await message.answer("❌ Bunday nomli media mavjud!")
    elif field == "code":
        try:
            code = int(value)
            cursor.execute("SELECT id FROM media WHERE code = ? AND id != ?", (code, media_id))
            if cursor.fetchone():
                await message.answer("❌ Bunday kod mavjud!")
            else:
                cursor.execute("UPDATE media SET code = ? WHERE id = ?", (code, media_id))
                conn.commit()
                await message.answer(f"✅ Kod '{code}' ga o'zgartirildi!")
        except ValueError:
            await message.answer("❌ Faqat raqam kiriting!")
    elif field == "description":
        cursor.execute("UPDATE media SET description = ? WHERE id = ?", (value, media_id))
        conn.commit()
        await message.answer("✅ Tavsif o'zgartirildi!")
    elif field == "genre":
        cursor.execute("UPDATE media SET genre = ? WHERE id = ?", (value, media_id))
        conn.commit()
        await message.answer("✅ Janr o'zgartirildi!")
    elif field == "season":
        try:
            season = int(value)
            cursor.execute("UPDATE media SET season = ? WHERE id = ?", (season, media_id))
            conn.commit()
            await message.answer(f"✅ Sezon {season} ga o'zgartirildi!")
        except ValueError:
            await message.answer("❌ Faqat raqam kiriting!")
    elif field == "voice":
        cursor.execute("UPDATE media SET voice = ? WHERE id = ?", (value, media_id))
        conn.commit()
        await message.answer("✅ Ovoz o'zgartirildi!")
    elif field == "sponsor":
        cursor.execute("UPDATE media SET sponsor = ? WHERE id = ?", (value, media_id))
        conn.commit()
        await message.answer("✅ Himoy o'zgartirildi!")
    elif field == "quality":
        cursor.execute("UPDATE media SET quality = ? WHERE id = ?", (value, media_id))
        conn.commit()
        await message.answer("✅ Sifat o'zgartirildi!")
    
    await state.clear()

@dp.message(EditMediaState.value, F.photo)
async def edit_media_image_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    cursor.execute("UPDATE media SET image_url = ? WHERE id = ?", (message.photo[-1].file_id, data['media_id']))
    conn.commit()
    await message.answer("✅ Rasm o'zgartirildi!")
    await state.clear()

# ================================================================
# 23-QISMNI TAHRIRLASH
# ================================================================
@dp.message(F.text == "✏️ Qismni Tahrirlash")
async def edit_part_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await message.answer("Qaysi animega tegishli qismni tahrirlamoqchisiz?\nAnime nomi yoki kodini kiriting:", parse_mode="HTML")
    await state.set_state(EditPartState.select_media)

@dp.message(EditPartState.select_media)
async def edit_part_select_media(message: Message, state: FSMContext):
    query = message.text.strip()
    try:
        code = int(query)
        cursor.execute("SELECT id, name FROM media WHERE code = ?", (code,))
    except ValueError:
        cursor.execute("SELECT id, name FROM media WHERE name LIKE ?", (f"%{query}%",))
    
    media = cursor.fetchone()
    if not media:
        await message.answer(f"❌ '{query}' bo'yicha media topilmadi! Qayta kiriting:")
        return
    
    media_id, media_name = media
    await state.update_data(media_id=media_id)
    await message.answer(f"📺 <b>{media_name}</b>\n\nQism tanlang:", reply_markup=parts_list_keyboard(media_id), parse_mode="HTML")
    await state.set_state(EditPartState.select_part)

@dp.callback_query(EditPartState.select_part, F.data.startswith("select_part_"))
async def edit_part_select_part(callback: CallbackQuery, state: FSMContext):
    part_id = int(callback.data.split("_")[2])
    await state.update_data(part_id=part_id)
    cursor.execute("SELECT media_id, part_number FROM parts WHERE id = ?", (part_id,))
    media_id, part_num = cursor.fetchone()
    try:
        await callback.message.edit_text(f"✏️ {part_num}-qismni tahrirlash\n\nQaysi maydonni tahrirlamoqchisiz?", reply_markup=edit_part_fields_keyboard(part_id, media_id), parse_mode="HTML")
    except:
        await safe_send_message(callback.from_user.id, f"✏️ {part_num}-qismni tahrirlash\n\nQaysi maydonni tahrirlamoqchisiz?", reply_markup=edit_part_fields_keyboard(part_id, media_id), parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data.startswith("edit_part_"))
async def edit_part_field(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    part_id = int(parts[2])
    field = parts[3]
    await state.update_data(part_id=part_id, field=field)
    field_names = {"video": "yangi videoni", "caption": "yangi captionni", "number": "yangi qism raqamini"}
    try:
        await callback.message.edit_text(f"✏️ {field_names.get(field, 'yangi qiymatini')} kiriting:")
    except:
        await safe_send_message(callback.from_user.id, f"✏️ {field_names.get(field, 'yangi qiymatini')} kiriting:")
    await state.set_state(EditPartState.value)
    await callback.answer()

@dp.message(EditPartState.value, F.video)
async def edit_part_video(message: Message, state: FSMContext):
    data = await state.get_data()
    cursor.execute("UPDATE parts SET file_id = ? WHERE id = ?", (message.video.file_id, data['part_id']))
    conn.commit()
    await message.answer("✅ Video o'zgartirildi!")
    await state.clear()

@dp.message(EditPartState.value, F.text)
async def edit_part_value(message: Message, state: FSMContext):
    data = await state.get_data()
    part_id = data['part_id']
    field = data['field']
    value = message.text
    if field == "caption":
        cursor.execute("UPDATE parts SET caption = ? WHERE id = ?", (value, part_id))
        conn.commit()
        await message.answer("✅ Caption o'zgartirildi!")
    elif field == "number":
        try:
            part_num = int(value)
            cursor.execute("SELECT media_id FROM parts WHERE id = ?", (part_id,))
            media_id = cursor.fetchone()[0]
            cursor.execute("SELECT id FROM parts WHERE media_id = ? AND part_number = ? AND id != ?", (media_id, part_num, part_id))
            if cursor.fetchone():
                await message.answer(f"⚠️ {part_num}-qism mavjud!")
            else:
                cursor.execute("UPDATE parts SET part_number = ? WHERE id = ?", (part_num, part_id))
                conn.commit()
                await message.answer(f"✅ Qism raqami {part_num} ga o'zgartirildi!")
        except ValueError:
            await message.answer("❌ Faqat raqam kiriting!")
    await state.clear()

# ================================================================
# 24-STATISTIKA
# ================================================================
@dp.message(F.text == "📊 Statistika")
async def show_stats(message: Message):
    if not is_admin(message.from_user.id): return
    users = cursor.execute("SELECT COUNT(*) FROM users WHERE is_blocked = 0").fetchone()[0]
    media = cursor.execute("SELECT COUNT(*) FROM media").fetchone()[0]
    parts = cursor.execute("SELECT COUNT(*) FROM parts").fetchone()[0]
    views = get_total_views()
    admins = cursor.execute("SELECT COUNT(*) FROM admins").fetchone()[0]
    await message.answer(f"📊 <b>Statistika</b>\n\n👥 Foydalanuvchilar: {users}\n🎬 Media: {media}\n📹 Qismlar: {parts}\n👁️ Ko'rishlar: {views}\n👑 Adminlar: {admins}", parse_mode="HTML")

# ================================================================
# 25-XABAR YUBORISH
# ================================================================
@dp.message(F.text == "📢 Xabar Yuborish")
async def broadcast_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await message.answer("📢 Xabar yuborish\n\nXabaringizni kiriting:", parse_mode="HTML")
    await state.set_state(BroadcastState.message)

@dp.message(BroadcastState.message)
async def broadcast_send(message: Message, state: FSMContext):
    users = cursor.execute("SELECT user_id FROM users WHERE is_blocked = 0 AND bot_token='main'").fetchall()
    sent = 0
    for user in users:
        try:
            if message.photo:
                await bot.send_photo(user[0], message.photo[-1].file_id, caption=message.caption, parse_mode="HTML")
            elif message.video:
                await bot.send_video(user[0], message.video.file_id, caption=message.caption, parse_mode="HTML")
            else:
                await bot.send_message(user[0], message.text, parse_mode="HTML")
            sent += 1
        except:
            pass
    await message.answer(f"✅ {sent}/{len(users)} ta foydalanuvchiga yuborildi!")
    await state.clear()

# ================================================================
# 26-MAJBURIY KANAL BOSHQARUVI (MANABU USLUBIDA)
# ================================================================
@dp.message(F.text == "👥 Majburiy Kanal")
async def force_channels_menu(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    channels = get_channels(is_mandatory=1)
    text = "📢 MAJBURIY KANALLAR:\n\n"
    if channels:
        for ch in channels:
            text += f"• {ch[1]}\n{ch[2]}\n\n"
    else:
        text += "Hozircha kanal yo'q!\n\n"
    
    text += f"⚙️ Majburiy obuna: {'✅ YOQILGAN' if get_force_subscribe_status() == 1 else '❌ O\'CHIRILGAN'}\n\n"
    text += "Amallar:"
    
    buttons = [
        [InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="add_channel")],
        [InlineKeyboardButton(text="➖ Kanal o'chirish", callback_data="remove_channel")],
        [InlineKeyboardButton(text="⚙️ Majburiy obunani o'chirish/yoqish", callback_data="toggle_force_subscribe")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_admin_reply")]
    ]
    markup = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(text, reply_markup=markup, parse_mode="HTML")

@dp.callback_query(F.data == "toggle_force_subscribe")
async def toggle_force_subscribe(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q!", show_alert=True)
        return
    
    current = get_force_subscribe_status()
    new_status = 0 if current == 1 else 1
    set_force_subscribe_status(new_status)
    
    status_text = "YOQILGAN" if new_status == 1 else "O'CHIRILGAN"
    await callback.answer(f"✅ Majburiy obuna {status_text}!", show_alert=True)
    
    # Menyuni yangilash
    await force_channels_menu(callback.message)
    await callback.message.delete()

@dp.callback_query(F.data == "add_channel")
async def add_channel_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q!", show_alert=True)
        return
    
    await state.set_state(ChannelState.waiting_for_channel_id)
    await callback.message.edit_text("➕ Kanal ID sini yuboring:\nMasalan: @kanal yoki -1001234567890")
    await callback.answer()

@dp.message(ChannelState.waiting_for_channel_id)
async def add_channel_id(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    channel_id = message.text.strip()
    await state.update_data(channel_id=channel_id)
    await state.set_state(ChannelState.waiting_for_channel_title)
    await message.answer("📝 Kanal nomini yuboring:")

@dp.message(ChannelState.waiting_for_channel_title)
async def add_channel_title(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    channel_title = message.text.strip()
    await state.update_data(channel_title=channel_title)
    await state.set_state(ChannelState.waiting_for_channel_url)
    await message.answer("🔗 Kanal linkini yuboring:\nMasalan: https://t.me/kanal")

@dp.message(ChannelState.waiting_for_channel_url)
async def add_channel_url(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    channel_url = message.text.strip()
    data = await state.get_data()
    
    add_channel(data['channel_id'], data['channel_title'], channel_url, is_mandatory=1)
    await message.answer(f"✅ Kanal qo'shildi:\n{data['channel_title']}\n{channel_url}")
    await state.clear()

@dp.callback_query(F.data == "remove_channel")
async def remove_channel_list(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q!", show_alert=True)
        return
    
    channels = get_channels(is_mandatory=1)
    if not channels:
        await callback.answer("❌ O'chirish uchun kanal yo'q!", show_alert=True)
        return
    
    buttons = []
    for ch in channels:
        buttons.append([InlineKeyboardButton(text=f"❌ {ch[1]}", callback_data=f"remove_channel_{ch[0]}")])
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="force_channels_menu")])
    
    markup = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text("❌ O'chirmoqchi bo'lgan kanalni tanlang:", reply_markup=markup)
    await callback.answer()

@dp.callback_query(F.data.startswith("remove_channel_"))
async def remove_channel_execute(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q!", show_alert=True)
        return
    
    channel_id = callback.data.replace("remove_channel_", "")
    remove_channel(channel_id)
    await callback.answer("✅ Kanal o'chirildi!", show_alert=True)
    await force_channels_menu(callback.message)
    await callback.message.delete()

@dp.callback_query(F.data == "force_channels_menu")
async def back_to_force_menu(callback: CallbackQuery):
    await force_channels_menu(callback.message)
    await callback.message.delete()
    await callback.answer()

# ================================================================
# 27-ADMIN QO'SHISH/CHIQARISH
# ================================================================
@dp.message(F.text == "👑 Admin Qo'shish")
async def admin_manage(message: Message, state: FSMContext):
    if not is_owner(message.from_user.id):
        await message.answer("❌ Faqat ownerlar admin qo'shishi mumkin!")
        return
    await message.answer("Admin boshqaruvi:", reply_markup=admin_manage_buttons(), parse_mode="HTML")
    await state.set_state(AdminManageState.action)

def admin_manage_buttons():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Admin Qo'shish", callback_data="admin_add")],
        [InlineKeyboardButton(text="❌ Admin Chiqarish", callback_data="admin_remove")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_admin_reply")]
    ])

@dp.callback_query(AdminManageState.action, F.data == "admin_add")
async def admin_add_request(callback: CallbackQuery, state: FSMContext):
    if not is_owner(callback.from_user.id):
        await callback.answer("❌ Faqat ownerlar admin qo'shishi mumkin!", show_alert=True)
        return
    await state.update_data(action="add")
    try:
        await callback.message.edit_text("➕ Yangi admin ID sini kiriting:", parse_mode="HTML")
    except:
        await safe_send_message(callback.from_user.id, "➕ Yangi admin ID sini kiriting:", parse_mode="HTML")
    await state.set_state(AdminManageState.user_id)
    await callback.answer()

@dp.callback_query(AdminManageState.action, F.data == "admin_remove")
async def admin_remove_request(callback: CallbackQuery, state: FSMContext):
    if not is_owner(callback.from_user.id):
        await callback.answer("❌ Faqat ownerlar admin chiqarishi mumkin!", show_alert=True)
        return
    await state.update_data(action="remove")
    admins = cursor.execute("SELECT user_id FROM admins WHERE is_owner=0 AND is_co_owner=0").fetchall()
    if admins:
        text = "❌ Admin chiqarish:\n\nMavjud adminlar:\n" + "\n".join([f"• {a[0]}" for a in admins]) + "\n\nO'chirmoqchi bo'lgan ID ni kiriting:"
        try:
            await callback.message.edit_text(text, parse_mode="HTML")
        except:
            await safe_send_message(callback.from_user.id, text, parse_mode="HTML")
    else:
        try:
            await callback.message.edit_text("❌ O'chirish mumkin bo'lgan admin yo'q!")
        except:
            await safe_send_message(callback.from_user.id, "❌ O'chirish mumkin bo'lgan admin yo'q!")
        await state.clear()
    await state.set_state(AdminManageState.user_id)
    await callback.answer()

@dp.message(AdminManageState.user_id)
async def admin_manage_user_id(message: Message, state: FSMContext):
    try:
        user_id = int(message.text)
        data = await state.get_data()
        if data['action'] == "add":
            cursor.execute("INSERT OR IGNORE INTO admins (user_id, added_by, added_at) VALUES (?, ?, ?)", 
                          (user_id, message.from_user.id, datetime.now().isoformat()))
            conn.commit()
            await message.answer(f"✅ {user_id} admin qo'shildi!" if cursor.rowcount > 0 else f"⚠️ {user_id} allaqachon admin!")
            try:
                await bot.send_message(user_id, "🎉 Siz admin etib tayinlandingiz!\nAdmin panelga /start orqali kiring.")
            except:
                pass
        else:
            cursor.execute("DELETE FROM admins WHERE user_id=? AND is_owner=0 AND is_co_owner=0", (user_id,))
            conn.commit()
            await message.answer(f"✅ {user_id} adminlikdan chiqarildi!" if cursor.rowcount > 0 else f"⚠️ {user_id} admin emas!")
    except ValueError:
        await message.answer("❌ Faqat raqam kiriting!")
    await state.clear()

# ================================================================
# 28-BOT STATISTIKASI
# ================================================================
@dp.message(F.text == "📋 Bot statistikasi")
async def show_bot_stats(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    stats = get_bot_full_stats()
    text = f"""
📊 BOT STATISTIKASI

👥 Foydalanuvchilar: {stats['users']}
🎬 Animelar: {stats['animes']}
📺 Qismlar: {stats['episodes']}
👁 Ko'rishlar: {stats['views']}
👑 Adminlar: {stats['admins']}

📅 Yaratilgan: {stats['created_at']}
🕐 So'nggi faol: {datetime.now().strftime('%Y-%m-%d %H:%M')}

💰 Tangalar: {stats['total_coins']}
⭐ O'rtacha daraja: {stats['avg_level']}
"""
    await message.answer(text, parse_mode="HTML")

def get_bot_full_stats() -> dict:
    users = cursor.execute("SELECT COUNT(*) FROM users WHERE bot_token='main'").fetchone()[0]
    animes = cursor.execute("SELECT COUNT(*) FROM media").fetchone()[0]
    episodes = cursor.execute("SELECT COUNT(*) FROM parts").fetchone()[0]
    views = get_total_views()
    admins = cursor.execute("SELECT COUNT(*) FROM admins").fetchone()[0]
    total_coins = cursor.execute("SELECT SUM(coins) FROM users WHERE bot_token='main'").fetchone()[0] or 0
    avg_level = cursor.execute("SELECT AVG(level) FROM users WHERE bot_token='main'").fetchone()[0] or 1
    created_at = cursor.execute("SELECT created_at FROM media ORDER BY created_at LIMIT 1").fetchone()
    
    return {
        'users': users,
        'animes': animes,
        'episodes': episodes,
        'views': views,
        'admins': admins,
        'total_coins': total_coins,
        'avg_level': round(avg_level, 1),
        'created_at': created_at[0][:10] if created_at else "Noma'lum"
    }

# ================================================================
# 29-BACKUP
# ================================================================
@dp.message(F.text == "💾 Backup")
async def create_backup(message: Message):
    if not is_owner(message.from_user.id):
        await message.answer("❌ Faqat ownerlar backup olishi mumkin!")
        return
    
    await message.answer("⏳ Backup olinmoqda...")
    
    backup_file = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    
    # Bazani nusxalash
    import shutil
    try:
        shutil.copy2(DB_NAME, backup_file)
        size = os.path.getsize(backup_file) / 1024
        
        with open(backup_file, 'rb') as f:
            await bot.send_document(message.chat.id, f, caption=f"✅ Backup: {backup_file}\n📦 Hajmi: {size:.2f} KB")
        
        os.remove(backup_file)
    except Exception as e:
        await message.answer(f"❌ Backup olishda xatolik: {e}")

# ================================================================
# 30-POST QILISH
# ================================================================
@dp.message(F.text == "📨 Post Qilish")
async def post_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await message.answer("📨 Post qilish\n\nPost qilmoqchi bo'lgan media nomi yoki kodini kiriting:", parse_mode="HTML")
    await state.set_state(PostState.media_id)

@dp.message(PostState.media_id)
async def post_media_id(message: Message, state: FSMContext):
    query = message.text.strip()
    try:
        code = int(query)
        cursor.execute("SELECT id, name, code, description, total_parts, status, season, genre, voice, sponsor, quality, image_url FROM media WHERE code = ?", (code,))
    except ValueError:
        cursor.execute("SELECT id, name, code, description, total_parts, status, season, genre, voice, sponsor, quality, image_url FROM media WHERE name LIKE ?", (f"%{query}%",))
    media = cursor.fetchone()
    if not media:
        await message.answer(f"❌ '{query}' bo'yicha media topilmadi!")
        return
    media_id, name, code, desc, total_parts, status, season, genre, voice, sponsor, quality, image = media
    await state.update_data(media_id=media_id)
    
    status_text = {"ongoing": "🟢 Davom etmoqda", "completed": "✅ Tugallangan", "hiatus": "⏸ To'xtatilgan"}.get(status, "Noma'lum")
    voice_text = voice if voice else f"{AUTHOR_USERNAME}"
    sponsor_text = sponsor if sponsor else "AniCity Rasmiy"
    
    info_text = (
        f"📨 <b>Post ma'lumotlari</b>\n\n"
        f"🎬 Nomi: {name}\n"
        f"🔢 Kod: {code}\n"
        f"🎭 Janr: {genre}\n"
        f"🎬 Sezon: {season}\n"
        f"📹 Qismlar: {total_parts} ta\n"
        f"📊 Holat: {status_text}\n"
        f"🎙 Ovoz: {voice_text}\n"
        f"🤝 Himoy: {sponsor_text}\n"
        f"📀 Sifat: {quality}\n"
        f"📝 Tavsif: {desc[:100]}...\n\n"
        "Endi post qilmoqchi bo'lgan kanal linkini yuboring:\n"
        "Masalan: @kanal yoki https://t.me/kanal"
    )
    await message.answer(info_text, parse_mode="HTML")
    await state.set_state(PostState.channel)

@dp.message(PostState.channel)
async def post_channel(message: Message, state: FSMContext):
    channel_input = message.text.strip()
    if channel_input.startswith("https://t.me/"):
        parts = channel_input.split("/")
        username = parts[-1].split("?")[0]
        channel = f"@{username}"
    elif channel_input.startswith("@"):
        channel = channel_input
    else:
        channel = f"@{channel_input}"
    
    await state.update_data(channel=channel)
    
    if not is_admin(message.from_user.id):
        await message.answer("❌ Siz admin emassiz!")
        await state.clear()
        return
    
    data = await state.get_data()
    media_id = data['media_id']
    cursor.execute("SELECT name, code, total_parts, status, season, genre, voice, sponsor, quality, image_url FROM media WHERE id = ?", (media_id,))
    name, code, total_parts, status, season, genre, voice, sponsor, quality, image = cursor.fetchone()
    
    status_text = {"ongoing": "🟢 Davom etmoqda", "completed": "✅ Tugallangan", "hiatus": "⏸ To'xtatilgan"}.get(status, "Noma'lum")
    voice_text = voice if voice else f"{AUTHOR_USERNAME}"
    sponsor_text = sponsor if sponsor else "AniCity Rasmiy"
    
    post_text = f"""
┌─────────────────────────────────
🎬 <b>{name}</b>
└─────────────────────────────────

┌─────────────────────────────────
• Janr: {genre}
• Sezon: {season}
• Qism: {total_parts}
• Holati: {status_text}
• Ovoz: {voice_text}
• Himoy: {sponsor_text}
• Sifat: {quality}
└─────────────────────────────────

🔢 Kod: <code>{code}</code>
📢 Kanal: {MAIN_CHANNEL}
"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="confirm_post")],
        [InlineKeyboardButton(text="❌ Rad etish", callback_data="cancel_post")]
    ])
    
    await message.answer(post_text, reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(PostState.confirm)

@dp.callback_query(PostState.confirm, F.data == "confirm_post")
async def post_confirm(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    media_id = data['media_id']
    channel = data['channel']
    cursor.execute("SELECT name, code, total_parts, status, season, genre, voice, sponsor, quality, image_url FROM media WHERE id = ?", (media_id,))
    name, code, total_parts, status, season, genre, voice, sponsor, quality, image = cursor.fetchone()
    
    status_text = {"ongoing": "🟢 Davom etmoqda", "completed": "✅ Tugallangan", "hiatus": "⏸ To'xtatilgan"}.get(status, "Noma'lum")
    voice_text = voice if voice else f"{AUTHOR_USERNAME}"
    sponsor_text = sponsor if sponsor else "AniCity Rasmiy"
    
    post_text = f"""
┌─────────────────────────────────
🎬 <b>{name}</b>
└─────────────────────────────────

┌─────────────────────────────────
• Janr: {genre}
• Sezon: {season}
• Qism: {total_parts}
• Holati: {status_text}
• Ovoz: {voice_text}
• Himoy: {sponsor_text}
• Sifat: {quality}
└─────────────────────────────────

🔢 Kod: <code>{code}</code>
📢 Kanal: {MAIN_CHANNEL}
"""
    
    bot_info = await bot.get_me()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="+ Tomosha qilish", url=f"https://t.me/{bot_info.username}?start=code_{code}")]
    ])
    
    try:
        if image:
            await bot.send_photo(chat_id=channel, photo=image, caption=post_text, reply_markup=keyboard, parse_mode="HTML")
        else:
            await bot.send_message(chat_id=channel, text=post_text, reply_markup=keyboard, parse_mode="HTML")
        try:
            await callback.message.edit_text(f"✅ Post muvaffaqiyatli yuborildi!\n\nKanal: {channel}")
        except:
            await safe_send_message(callback.from_user.id, f"✅ Post muvaffaqiyatli yuborildi!\n\nKanal: {channel}")
    except Exception as e:
        try:
            await callback.message.edit_text(f"❌ Xatolik: {e}")
        except:
            await safe_send_message(callback.from_user.id, f"❌ Xatolik: {e}")
    await state.clear()
    await callback.answer()

@dp.callback_query(PostState.confirm, F.data == "cancel_post")
async def post_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await callback.message.delete()
    except:
        pass
    try:
        await callback.message.answer("❌ Post bekor qilindi.")
    except:
        pass
    await callback.answer()

# ================================================================
# 31-QISMNI POST QILISH
# ================================================================
@dp.message(F.text == "🎬 Qismni Post Qilish")
async def part_post_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await message.answer("🎬 Qismni post qilish\n\nPost qilmoqchi bo'lgan media nomi yoki kodini kiriting:", parse_mode="HTML")
    await state.set_state(PartPostState.media_id)

@dp.message(PartPostState.media_id)
async def part_post_media_id(message: Message, state: FSMContext):
    query = message.text.strip()
    try:
        code = int(query)
        cursor.execute("SELECT id, name, code, image_url FROM media WHERE code = ?", (code,))
    except ValueError:
        cursor.execute("SELECT id, name, code, image_url FROM media WHERE name LIKE ?", (f"%{query}%",))
    media = cursor.fetchone()
    if not media:
        await message.answer(f"❌ '{query}' bo'yicha media topilmadi!")
        return
    media_id, name, code, image = media
    await state.update_data(media_id=media_id)
    await state.update_data(media_image=image)
    await state.update_data(media_name=name)
    await state.update_data(media_code=code)
    await message.answer(f"📺 <b>{name}</b> (Kod: {code})\n\nQaysi qismni post qilmoqchisiz?", reply_markup=parts_list_keyboard(media_id), parse_mode="HTML")
    await state.set_state(PartPostState.part_id)

@dp.callback_query(PartPostState.part_id, F.data.startswith("select_part_"))
async def part_post_select_part(callback: CallbackQuery, state: FSMContext):
    part_id = int(callback.data.split("_")[2])
    await state.update_data(part_id=part_id)
    cursor.execute("SELECT p.part_number, m.name, m.code, m.image_url, m.total_parts, m.status, m.season, m.genre, m.voice, m.sponsor, m.quality FROM parts p JOIN media m ON p.media_id = m.id WHERE p.id = ?", (part_id,))
    part_num, media_name, code, image, total_parts, status, season, genre, voice, sponsor, quality = cursor.fetchone()
    
    status_text = {"ongoing": "🟢 Davom etmoqda", "completed": "✅ Tugallangan", "hiatus": "⏸ To'xtatilgan"}.get(status, "Noma'lum")
    voice_text = voice if voice else f"{AUTHOR_USERNAME}"
    sponsor_text = sponsor if sponsor else "AniCity Rasmiy"
    
    try:
        await callback.message.edit_text(
            f"✅ <b>{media_name}</b> - {part_num}-qism topildi!\n\n"
            f"🎭 Kod: {code}\n"
            f"🎬 Sezon: {season}\n"
            f"📹 Qism: {part_num}/{total_parts}\n"
            f"📊 Holat: {status_text}\n"
            f"🎭 Janr: {genre}\n"
            f"🎙 Ovoz: {voice_text}\n"
            f"🤝 Himoy: {sponsor_text}\n"
            f"📀 Sifat: {quality}\n\n"
            "Endi post qilmoqchi bo'lgan kanal linkini yuboring:\n"
            "Masalan: @kanal yoki https://t.me/kanal",
            parse_mode="HTML"
        )
    except:
        await safe_send_message(callback.from_user.id,
            f"✅ <b>{media_name}</b> - {part_num}-qism topildi!\n\n"
            f"🎭 Kod: {code}\n"
            f"🎬 Sezon: {season}\n"
            f"📹 Qism: {part_num}/{total_parts}\n"
            f"📊 Holat: {status_text}\n"
            f"🎭 Janr: {genre}\n"
            f"🎙 Ovoz: {voice_text}\n"
            f"🤝 Himoy: {sponsor_text}\n"
            f"📀 Sifat: {quality}\n\n"
            "Endi post qilmoqchi bo'lgan kanal linkini yuboring:\n"
            "Masalan: @kanal yoki https://t.me/kanal",
            parse_mode="HTML"
        )
    await state.update_data(part_number=part_num)
    await state.update_data(media_image=image)
    await state.update_data(media_name=media_name)
    await state.update_data(media_code=code)
    await state.set_state(PartPostState.channel)
    await callback.answer()

@dp.message(PartPostState.channel)
async def part_post_channel(message: Message, state: FSMContext):
    channel_input = message.text.strip()
    if channel_input.startswith("https://t.me/"):
        parts = channel_input.split("/")
        username = parts[-1].split("?")[0]
        channel = f"@{username}"
    elif channel_input.startswith("@"):
        channel = channel_input
    else:
        channel = f"@{channel_input}"
    
    await state.update_data(channel=channel)
    
    if not is_admin(message.from_user.id):
        await message.answer("❌ Siz admin emassiz!")
        await state.clear()
        return
    
    data = await state.get_data()
    part_num = data.get('part_number')
    media_name = data.get('media_name')
    media_code = data.get('media_code')
    media_image = data.get('media_image')
    
    post_text = f"""
┌─────────────────────────────────
🎬 <b>{media_name}</b>
└─────────────────────────────────

┌─────────────────────────────────
• {part_num}-qism
• Anime KODI: {media_code}
└─────────────────────────────────

📢 Kanal: {MAIN_CHANNEL}
"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="confirm_part_post")],
        [InlineKeyboardButton(text="❌ Rad etish", callback_data="cancel_post")]
    ])
    
    await message.answer(post_text, reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(PartPostState.confirm)

@dp.callback_query(PartPostState.confirm, F.data == "confirm_part_post")
async def part_post_confirm(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    part_num = data.get('part_number')
    media_name = data.get('media_name')
    media_code = data.get('media_code')
    media_image = data.get('media_image')
    channel = data.get('channel')
    
    bot_info = await bot.get_me()
    
    post_text = f"""
┌─────────────────────────────────
🎬 <b>{media_name}</b>
└─────────────────────────────────

┌─────────────────────────────────
• {part_num}-qism
• Anime KODI: {media_code}
└─────────────────────────────────

📢 Kanal: {MAIN_CHANNEL}
"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"+ {part_num}-qismni tomosha qilish", url=f"https://t.me/{bot_info.username}?start=code_{media_code}&part={part_num}")]
    ])
    
    try:
        if media_image:
            await bot.send_photo(chat_id=channel, photo=media_image, caption=post_text, reply_markup=keyboard, parse_mode="HTML")
        else:
            await bot.send_message(chat_id=channel, text=post_text, reply_markup=keyboard, parse_mode="HTML")
        try:
            await callback.message.edit_text(f"✅ Qism post qilindi!\n\nKanal: {channel}")
        except:
            await safe_send_message(callback.from_user.id, f"✅ Qism post qilindi!\n\nKanal: {channel}")
    except Exception as e:
        try:
            await callback.message.edit_text(f"❌ Xatolik: {e}")
        except:
            await safe_send_message(callback.from_user.id, f"❌ Xatolik: {e}")
    await state.clear()
    await callback.answer()

@dp.callback_query(PartPostState.confirm, F.data == "cancel_post")
async def part_post_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await callback.message.delete()
    except:
        pass
    try:
        await callback.message.answer("❌ Qism post bekor qilindi.")
    except:
        pass
    await callback.answer()

# ================================================================
# 32-BOSHQA CALLBACKLAR
# ================================================================
@dp.callback_query(F.data == "cancel_post")
async def cancel_post(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await callback.message.delete()
    except:
        pass
    try:
        await callback.message.answer("Bekor qilindi.")
    except:
        pass
    await callback.answer()

@dp.callback_query(F.data == "cancel_add_admin")
async def cancel_add_admin(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await callback.message.delete()
    except:
        pass
    admin_image = get_admin_image()
    admin_text = (
        "🔐 <b>Admin Panel</b> 🔐\n\n"
        f"👑 Adminlar: {cursor.execute('SELECT COUNT(*) FROM admins').fetchone()[0]}\n"
        f"🎬 Media: {cursor.execute('SELECT COUNT(*) FROM media').fetchone()[0]}\n"
        f"📹 Qismlar: {cursor.execute('SELECT COUNT(*) FROM parts').fetchone()[0]}\n"
        f"👥 Foydalanuvchilar: {cursor.execute('SELECT COUNT(*) FROM users').fetchone()[0]}\n"
        f"👁 Ko'rishlar: {get_total_views()}\n\n"
        "⬇️ Quyidagi tugmalardan foydalaning:"
    )
    if admin_image:
        await safe_send_photo(callback.from_user.id, photo=admin_image, caption=admin_text, reply_markup=admin_panel_menu(), parse_mode="HTML")
    else:
        await safe_send_message(callback.from_user.id, admin_text, reply_markup=admin_panel_menu(), parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data.startswith("media_page_"))
async def media_page_callback(callback: CallbackQuery):
    parts = callback.data.split("_")
    page = int(parts[2])
    media_type = parts[3] if len(parts) > 3 and parts[3] != 'None' else None
    try:
        await callback.message.edit_text("Media tanlang:", reply_markup=media_list_keyboard(media_type, page))
    except:
        await safe_send_message(callback.from_user.id, "Media tanlang:", reply_markup=media_list_keyboard(media_type, page))
    await callback.answer()

@dp.callback_query(F.data.startswith("parts_page_"))
async def parts_page_callback(callback: CallbackQuery):
    _, media_id, page = callback.data.split("_")
    try:
        await callback.message.edit_text("Qism tanlang:", reply_markup=parts_list_keyboard(int(media_id), int(page)))
    except:
        await safe_send_message(callback.from_user.id, "Qism tanlang:", reply_markup=parts_list_keyboard(int(media_id), int(page)))
    await callback.answer()

@dp.callback_query(F.data.startswith("back_to_media_"))
async def back_to_media_callback(callback: CallbackQuery):
    try:
        await callback.message.edit_text("Media tanlang:", reply_markup=media_list_keyboard())
    except:
        await safe_send_message(callback.from_user.id, "Media tanlang:", reply_markup=media_list_keyboard())
    await callback.answer()

@dp.callback_query(F.data.startswith("back_to_parts_"))
async def back_to_parts_callback(callback: CallbackQuery):
    media_id = int(callback.data.split("_")[3])
    try:
        await callback.message.edit_text("Qism tanlang:", reply_markup=parts_list_keyboard(media_id))
    except:
        await safe_send_message(callback.from_user.id, "Qism tanlang:", reply_markup=parts_list_keyboard(media_id))
    await callback.answer()

# ================================================================
# 33-UNKNOWN HANDLER
# ================================================================
@dp.message()
async def handle_unknown(message: Message):
    # Hech qanday javob qaytarmaydi
    pass

# ================================================================
# 34-BOTNI ISHGA TUSHIRISH
# ================================================================
async def main():
    print("=" * 60)
    print("🤖 ANICITY RASMIY BOT - MANABU USLUBIDAGI MAJBURIY OBUNA BILAN")
    print("=" * 60)
    print(f"👑 Adminlar: {cursor.execute('SELECT user_id FROM admins WHERE is_owner=1').fetchall()}")
    print(f"📢 Majburiy kanallar: {len(get_channels(1))} ta")
    print(f"⚙️ Majburiy obuna: {'✅ YOQILGAN' if get_force_subscribe_status() == 1 else '❌ O\'CHIRILGAN'}")
    print("=" * 60)
    print("✅ Barcha modullar muvaffaqiyatli yuklandi!")
    print("📌 Bot to'liq ishga tushdi!")
    print("=" * 60)
    
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        print("✅ Webhook o'chirildi!")
    except Exception as e:
        print(f"⚠️ Webhook o'chirish xatosi: {e}")
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
