# ================================================================
# ANICITY RASMIY BOT - TO'LIQ VERSIYA
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
from datetime import datetime
from typing import Tuple, List, Dict, Any, Callable, Awaitable

from aiogram import Bot, Dispatcher, types, F, BaseMiddleware
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, TelegramObject, FSInputFile, BufferedInputFile
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

# LOCAL RASMLAR (agar mavjud bo'lsa)
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
    id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    is_blocked INTEGER DEFAULT 0,
    registered_at TEXT,
    last_active TEXT
)
''')

# Adminlar jadvali
cursor.execute('''
CREATE TABLE IF NOT EXISTS admins (
    user_id INTEGER PRIMARY KEY,
    added_by INTEGER,
    added_at TEXT
)
''')

# Majburiy kanallar jadvali
cursor.execute('''
CREATE TABLE IF NOT EXISTS forced_channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_username TEXT UNIQUE,
    is_active INTEGER DEFAULT 1
)
''')

# Dastlabki adminlarni qo'shish
now = datetime.now().isoformat()
for admin_id in ADMINS:
    cursor.execute("INSERT OR IGNORE INTO admins (user_id, added_by, added_at) VALUES (?, ?, ?)",
                   (admin_id, admin_id, now))
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
# 5-MAJBURIY A'ZOLIK FUNKSIYALARI
# ================================================================
async def check_subscription(user_id: int) -> Tuple[bool, List[str]]:
    """Foydalanuvchi barcha aktiv majburiy kanallarga a'zoligini tekshiradi"""
    cursor.execute("SELECT id, channel_username FROM forced_channels WHERE is_active = 1")
    channels = cursor.fetchall()
    if not channels:
        return True, []

    not_subscribed = []
    for ch_id, channel_username in channels:
        clean_channel = channel_username.replace('@', '').strip()
        if not clean_channel:
            cursor.execute("UPDATE forced_channels SET is_active = 0 WHERE id = ?", (ch_id,))
            conn.commit()
            continue

        try:
            member = await bot.get_chat_member(chat_id=f"@{clean_channel}", user_id=user_id)
            if member.status in ['left', 'kicked']:
                not_subscribed.append(f"@{clean_channel}")
        except Exception as e:
            error_msg = str(e).lower()
            if "chat not found" in error_msg or "invalid username" in error_msg:
                cursor.execute("UPDATE forced_channels SET is_active = 0 WHERE id = ?", (ch_id,))
                conn.commit()
                logging.warning(f"⚠️ Kanal {channel_username} topilmadi, o'chirildi.")
            elif "bot is not a member" in error_msg:
                cursor.execute("UPDATE forced_channels SET is_active = 0 WHERE id = ?", (ch_id,))
                conn.commit()
                logging.warning(f"⚠️ Bot {channel_username} kanaliga a'zo emas, kanal o'chirildi.")
            else:
                not_subscribed.append(f"@{clean_channel}")
                logging.error(f"Kanal tekshirish xatosi {channel_username}: {e}")
    return len(not_subscribed) == 0, not_subscribed

async def get_subscription_keyboard(not_subscribed: List[str]) -> InlineKeyboardMarkup:
    """A'zo bo'lmagan kanallar uchun tugmalar"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for ch in not_subscribed:
        clean = ch.replace('@', '')
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text=f"📢 {ch}", url=f"https://t.me/{clean}")
        ])
    keyboard.inline_keyboard.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_sub")])
    return keyboard

# ================================================================
# 6-MIDDLEWARE
# ================================================================
class SubscriptionMiddleware(BaseMiddleware):
    """Barcha handlerlarni majburiy a'zolikka tekshiradi"""
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user_id = None
        if isinstance(event, Message):
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
        else:
            return await handler(event, data)

        # Istisnolar: /start va check_sub
        if isinstance(event, Message):
            if event.text and event.text.startswith("/start"):
                return await handler(event, data)
        elif isinstance(event, CallbackQuery):
            if event.data == "check_sub":
                return await handler(event, data)

        subscribed, not_subscribed = await check_subscription(user_id)
        if not subscribed:
            text = "❌ Botdan foydalanish uchun quyidagi kanallarga a'zo bo'ling:\n\n" + "\n".join(not_subscribed)
            keyboard = await get_subscription_keyboard(not_subscribed)
            if isinstance(event, Message):
                await event.answer(text, reply_markup=keyboard, parse_mode="HTML")
            else:
                await event.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
            return
        return await handler(event, data)

# Middleware-ni ro'yxatdan o'tkazish
dp.message.middleware(SubscriptionMiddleware())
dp.callback_query.middleware(SubscriptionMiddleware())

# ================================================================
# 7-STATE'LAR
# ================================================================
class ForcedChannelState(StatesGroup):
    waiting_for_channel = State()

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

# ================================================================
# 8-TUGMALAR
# ================================================================
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

def admin_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="➕ Media Qo'shish"), KeyboardButton(text="➕ Qism Qo'shish")],
        [KeyboardButton(text="➕ Ko'p Qism Qo'shish"), KeyboardButton(text="✏️ Media Tahrirlash")],
        [KeyboardButton(text="✏️ Qismni Tahrirlash"), KeyboardButton(text="📊 Statistika")],
        [KeyboardButton(text="📢 Xabar Yuborish"), KeyboardButton(text="🔗 Majburiy A'zo")],
        [KeyboardButton(text="👑 Admin Qo'shish"), KeyboardButton(text="📨 Post Qilish")],
        [KeyboardButton(text="🎬 Qismni Post Qilish"), KeyboardButton(text="🔙 Asosiy menyu")]
    ], resize_keyboard=True)

def admin_manage_buttons():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Admin Qo'shish", callback_data="admin_add")],
        [InlineKeyboardButton(text="❌ Admin Chiqarish", callback_data="admin_remove")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_admin_reply")]
    ])

def forced_channel_buttons():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="forced_add")],
        [InlineKeyboardButton(text="❌ Kanal o'chirish", callback_data="forced_remove")],
        [InlineKeyboardButton(text="📋 Kanallar ro'yxati", callback_data="forced_list")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_admin_reply")]
    ])

def forced_channel_list_keyboard(page=0):
    cursor.execute("SELECT id, channel_username, is_active FROM forced_channels ORDER BY channel_username")
    channels = cursor.fetchall()
    per_page = 10
    start = page * per_page
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for ch_id, channel, active in channels[start:start+per_page]:
        status = "✅" if active else "❌"
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text=f"{status} {channel}", callback_data=f"forced_del_{ch_id}")
        ])
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"forced_page_{page-1}"))
    if start + per_page < len(channels):
        nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"forced_page_{page+1}"))
    if nav_buttons:
        keyboard.inline_keyboard.append(nav_buttons)
    keyboard.inline_keyboard.append([InlineKeyboardButton(text="🔙 Ortga", callback_data="back_to_forced_menu")])
    return keyboard

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
    return user_id in ADMINS

async def add_user(user) -> None:
    cursor.execute("INSERT OR IGNORE INTO users (id, username, first_name, last_name, registered_at, last_active) VALUES (?, ?, ?, ?, ?, ?)",
                   (user.id, user.username, user.first_name, user.last_name, datetime.now().isoformat(), datetime.now().isoformat()))
    conn.commit()

async def update_user_activity(user_id: int) -> None:
    cursor.execute("UPDATE users SET last_active = ? WHERE id = ?", (datetime.now().isoformat(), user_id))
    conn.commit()

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
# 10-START HANDLER
# ================================================================
@dp.message(Command("start"))
async def start(message: Message):
    await add_user(message.from_user)
    
    args = message.text.split()
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
    
    start_image = get_start_image()
    welcome_text = (
        "🎬 <b>AniCity Rasmiy Bot</b> 🎬\n\n"
        "✨ <b>Botimizga xush kelibsiz!</b> ✨\n\n"
        "📚 <b>Bot imkoniyatlari:</b>\n"
        "🔍 Kod orqali qidiruv\n"
        "🎬 Anime va dramalarni nom bilan qidirish\n"
        "🖼 Rasm orqali anime topish\n"
        "📺 Barcha qismlarni tomosha qilish\n\n"
        f"📢 <b>Asosiy kanal:</b> {MAIN_CHANNEL}\n"
        f"👨‍💻 <b>Muallif:</b> <a href='{AUTHOR_LINK}'>{AUTHOR_USERNAME}</a>\n"
        f"🆘 <b>Yordam:</b> <a href='{SUPPORT_LINK}'>{SUPPORT_USERNAME}</a>\n\n"
        "⬇️ <b>Quyidagi tugmalardan birini tanlang:</b> ⬇️"
    )
    if start_image:
        await safe_send_photo(message.chat.id, photo=start_image, caption=welcome_text, reply_markup=start_menu(), parse_mode="HTML")
    else:
        await safe_send_message(message.chat.id, welcome_text, reply_markup=start_menu(), parse_mode="HTML")

@dp.callback_query(F.data == "check_sub")
async def check_sub_callback(callback: CallbackQuery):
    subscribed, not_subscribed = await check_subscription(callback.from_user.id)
    if subscribed:
        await callback.message.delete()
        start_image = get_start_image()
        welcome_text = (
            "🎬 <b>AniCity Rasmiy Bot</b> 🎬\n\n"
            "✅ Siz barcha kanallarga a'zo bo'ldingiz!\n"
            "Endi botdan foydalanishingiz mumkin."
        )
        if start_image:
            await safe_send_photo(callback.from_user.id, photo=start_image, caption=welcome_text, reply_markup=start_menu(), parse_mode="HTML")
        else:
            await safe_send_message(callback.from_user.id, welcome_text, reply_markup=start_menu(), parse_mode="HTML")
    else:
        text = "❌ Hali ham quyidagi kanallarga a'zo emassiz:\n\n" + "\n".join(not_subscribed)
        keyboard = await get_subscription_keyboard(not_subscribed)
        try:
            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        except:
            await safe_send_message(callback.from_user.id, text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "back_to_start")
async def back_to_start(callback: CallbackQuery):
    start_image = get_start_image()
    welcome_text = (
        "🎬 <b>AniCity Rasmiy Bot</b> 🎬\n\n"
        "✨ <b>Botimizga xush kelibsiz!</b> ✨\n\n"
        "📚 <b>Bot imkoniyatlari:</b>\n"
        "🔍 Kod orqali qidiruv\n"
        "🎬 Anime va dramalarni nom bilan qidirish\n"
        "🖼 Rasm orqali anime topish\n"
        "📺 Barcha qismlarni tomosha qilish\n\n"
        f"📢 <b>Asosiy kanal:</b> {MAIN_CHANNEL}\n"
        f"👨‍💻 <b>Muallif:</b> <a href='{AUTHOR_LINK}'>{AUTHOR_USERNAME}</a>\n"
        f"🆘 <b>Yordam:</b> <a href='{SUPPORT_LINK}'>{SUPPORT_USERNAME}</a>\n\n"
        "⬇️ <b>Quyidagi tugmalardan birini tanlang:</b> ⬇️"
    )
    try:
        await callback.message.delete()
    except:
        pass
    if start_image:
        await safe_send_photo(callback.from_user.id, photo=start_image, caption=welcome_text, reply_markup=start_menu(), parse_mode="HTML")
    else:
        await safe_send_message(callback.from_user.id, welcome_text, reply_markup=start_menu(), parse_mode="HTML")
    await callback.answer()

# ================================================================
# 11-KOD ORQALI QIDIRUV
# ================================================================
@dp.callback_query(F.data == "search_by_code")
async def search_by_code_start(callback: CallbackQuery, state: FSMContext):
    await update_user_activity(callback.from_user.id)
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
    await update_user_activity(message.from_user.id)
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
# 12-NOM BO'YICHA QIDIRUV
# ================================================================
@dp.callback_query(F.data == "search_anime")
async def search_anime_start(callback: CallbackQuery, state: FSMContext):
    await update_user_activity(callback.from_user.id)
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
    await update_user_activity(callback.from_user.id)
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
    search_type = data.get('search_type', 'anime')
    media_type = "anime" if search_type == "anime" else "drama"
    
    cursor.execute("SELECT id, name, type, total_parts, status, code FROM media WHERE type = ? AND name LIKE ? ORDER BY name", (media_type, f"%{query}%"))
    results = cursor.fetchall()
    
    if not results:
        await safe_send_message(message.chat.id, f"❌ '{query}' bo'yicha hech narsa topilmadi!")
        await state.clear()
        return
    
    builder = InlineKeyboardBuilder()
    for media_id, name, m_type, parts, status, code in results:
        status_emoji = "🟢" if status == "ongoing" else "✅" if status == "completed" else "⏸"
        builder.button(text=f"{'🎬' if m_type=='anime' else '🎭'} {name} [{code}] {status_emoji} ({parts} qism)", callback_data=f"view_media_{media_id}")
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_start"))
    
    await safe_send_message(message.chat.id, f"🔍 '{query}' bo'yicha topilganlar ({len(results)}):", reply_markup=builder.as_markup())
    await state.clear()

# ================================================================
# 13-RASM ORQALI QIDIRUV (Haqiqiy API bilan)
# ================================================================
@dp.callback_query(F.data == "search_image")
async def search_image_start(callback: CallbackQuery, state: FSMContext):
    await update_user_activity(callback.from_user.id)
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
    await update_user_activity(message.from_user.id)
    
    await message.answer("🖼 Rasm qabul qilindi! 🔍 Qidiruv boshlanmoqda...")
    
    # Haqiqiy rasm tahlili uchun trace.moe API dan foydalanamiz
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    file_bytes = await bot.download_file(file.file_path)
    
    import aiohttp
    import base64
    
    # Rasmni base64 ga o'tkazish
    image_base64 = base64.b64encode(file_bytes.read()).decode('utf-8')
    
    async with aiohttp.ClientSession() as session:
        try:
            # trace.moe API ga so'rov yuborish
            async with session.post('https://api.trace.moe/search', data={'image': image_base64}) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    if result.get('result') and len(result['result']) > 0:
                        top_result = result['result'][0]
                        anime_name = top_result.get('filename', 'Noma\'lum')
                        similarity = top_result.get('similarity', 0) * 100
                        episode = top_result.get('episode', '?')
                        
                        # Bazadan shu nomdagi animeni qidirish
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
            # API ishlamasa, bazadagi birinchi 10 ta mediadan taklif qilamiz
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
# 14-GUIDE, ADVERTISEMENT, LIST ALL
# ================================================================
@dp.callback_query(F.data == "guide")
async def guide_start(callback: CallbackQuery):
    await update_user_activity(callback.from_user.id)
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
    await update_user_activity(callback.from_user.id)
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
    await update_user_activity(callback.from_user.id)
    
    anime_list = cursor.execute("SELECT name, code, total_parts, status FROM media WHERE type = 'anime' ORDER BY name").fetchall()
    drama_list = cursor.execute("SELECT name, code, total_parts, status FROM media WHERE type = 'drama' ORDER BY name").fetchall()
    
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
# 15-MEDIA KO'RISH
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
# 16-QISMLARNI KO'RISH VA TOMOSHA QILISH
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
# 17-ADMIN PANEL
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
        f"👥 Foydalanuvchilar: {cursor.execute('SELECT COUNT(*) FROM users').fetchone()[0]}\n\n"
        "⬇️ Quyidagi tugmalardan foydalaning:"
    )
    try:
        await callback.message.delete()
    except:
        pass
    if admin_image:
        await safe_send_photo(callback.from_user.id, photo=admin_image, caption=admin_text, reply_markup=admin_menu(), parse_mode="HTML")
    else:
        await safe_send_message(callback.from_user.id, admin_text, reply_markup=admin_menu(), parse_mode="HTML")
    await callback.answer()

@dp.message(F.text == "🔙 Asosiy menyu")
async def back_to_main_reply(message: Message):
    start_image = get_start_image()
    welcome_text = (
        "🎬 <b>AniCity Rasmiy Bot</b> 🎬\n\n"
        "✨ <b>Botimizga xush kelibsiz!</b> ✨\n\n"
        "📚 <b>Bot imkoniyatlari:</b>\n"
        "🔍 Kod orqali qidiruv\n"
        "🎬 Anime va dramalarni nom bilan qidirish\n"
        "🖼 Rasm orqali anime topish\n"
        "📺 Barcha qismlarni tomosha qilish\n\n"
        f"📢 <b>Asosiy kanal:</b> {MAIN_CHANNEL}\n"
        f"👨‍💻 <b>Muallif:</b> <a href='{AUTHOR_LINK}'>{AUTHOR_USERNAME}</a>\n"
        f"🆘 <b>Yordam:</b> <a href='{SUPPORT_LINK}'>{SUPPORT_USERNAME}</a>\n\n"
        "⬇️ <b>Quyidagi tugmalardan birini tanlang:</b> ⬇️"
    )
    if start_image:
        await safe_send_photo(message.chat.id, photo=start_image, caption=welcome_text, reply_markup=start_menu(), parse_mode="HTML")
    else:
        await safe_send_message(message.chat.id, welcome_text, reply_markup=start_menu(), parse_mode="HTML")

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
        f"👥 Foydalanuvchilar: {cursor.execute('SELECT COUNT(*) FROM users').fetchone()[0]}\n\n"
        "⬇️ Quyidagi tugmalardan foydalaning:"
    )
    if admin_image:
        await safe_send_photo(callback.from_user.id, photo=admin_image, caption=admin_text, reply_markup=admin_menu(), parse_mode="HTML")
    else:
        await safe_send_message(callback.from_user.id, admin_text, reply_markup=admin_menu(), parse_mode="HTML")
    await callback.answer()

# ================================================================
# 18-MEDIA QO'SHISH
# ================================================================
@dp.message(F.text == "➕ Media Qo'shish")
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
# 19-QISM QO'SHISH
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
# 20-KO'P QISM QO'SHISH
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
# 21-MEDIA TAHRIRLASH
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
# 22-QISMNI TAHRIRLASH
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
# 23-STATISTIKA
# ================================================================
@dp.message(F.text == "📊 Statistika")
async def show_stats(message: Message):
    if not is_admin(message.from_user.id): return
    users = cursor.execute("SELECT COUNT(*) FROM users WHERE is_blocked = 0").fetchone()[0]
    media = cursor.execute("SELECT COUNT(*) FROM media").fetchone()[0]
    parts = cursor.execute("SELECT COUNT(*) FROM parts").fetchone()[0]
    views = cursor.execute("SELECT SUM(views) FROM media").fetchone()[0] or 0
    admins = cursor.execute("SELECT COUNT(*) FROM admins").fetchone()[0]
    await message.answer(f"📊 <b>Statistika</b>\n\n👥 Foydalanuvchilar: {users}\n🎬 Media: {media}\n📹 Qismlar: {parts}\n👁️ Ko'rishlar: {views}\n👑 Adminlar: {admins}", parse_mode="HTML")

# ================================================================
# 24-XABAR YUBORISH
# ================================================================
@dp.message(F.text == "📢 Xabar Yuborish")
async def broadcast_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await message.answer("📢 Xabar yuborish\n\nXabaringizni kiriting:", parse_mode="HTML")
    await state.set_state(BroadcastState.message)

@dp.message(BroadcastState.message)
async def broadcast_send(message: Message, state: FSMContext):
    users = cursor.execute("SELECT id FROM users WHERE is_blocked = 0").fetchall()
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
# 25-MAJBURIY KANAL BOSHQARUVI (ADMIN PANEL)
# ================================================================
@dp.message(F.text == "🔗 Majburiy A'zo")
async def forced_subscribe_menu(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await message.answer("🔗 Majburiy a'zolik boshqaruvi:", reply_markup=forced_channel_buttons(), parse_mode="HTML")

@dp.callback_query(F.data == "forced_add")
async def forced_add_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q!")
        return
    await state.set_state(ForcedChannelState.waiting_for_channel)
    try:
        await callback.message.edit_text("➕ Kanal username yoki linkini yuboring:\nMasalan: @kanal yoki https://t.me/kanal")
    except:
        await safe_send_message(callback.from_user.id, "➕ Kanal username yoki linkini yuboring:\nMasalan: @kanal yoki https://t.me/kanal")
    await callback.answer()

@dp.message(ForcedChannelState.waiting_for_channel)
async def forced_add_channel(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    channel_input = message.text.strip()
    if channel_input.startswith("https://t.me/"):
        parts = channel_input.split("/")
        username = parts[-1].split("?")[0]
        channel = f"@{username}"
    elif channel_input.startswith("@"):
        channel = channel_input
    else:
        channel = f"@{channel_input}"
    
    clean = channel.replace("@", "")
    try:
        await bot.get_chat(f"@{clean}")
        cursor.execute("INSERT INTO forced_channels (channel_username, is_active) VALUES (?, ?)", (channel, 1))
        conn.commit()
        await message.answer(f"✅ {channel} majburiy a'zolik ro'yxatiga qo'shildi!")
    except Exception as e:
        await message.answer(f"❌ Xatolik: Kanal topilmadi yoki bot a'zo emas.\n{e}")
    await state.clear()

@dp.callback_query(F.data == "forced_remove")
async def forced_remove_list(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q!")
        return
    cursor.execute("SELECT id, channel_username FROM forced_channels ORDER BY channel_username")
    channels = cursor.fetchall()
    if not channels:
        try:
            await callback.message.edit_text("📭 Hozircha majburiy kanal yo'q.")
        except:
            await safe_send_message(callback.from_user.id, "📭 Hozircha majburiy kanal yo'q.")
        await callback.answer()
        return
    try:
        await callback.message.edit_text("❌ O'chirmoqchi bo'lgan kanalni tanlang:", reply_markup=forced_channel_list_keyboard())
    except:
        await safe_send_message(callback.from_user.id, "❌ O'chirmoqchi bo'lgan kanalni tanlang:", reply_markup=forced_channel_list_keyboard())
    await callback.answer()

@dp.callback_query(F.data.startswith("forced_del_"))
async def forced_remove_channel(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q!")
        return
    ch_id = int(callback.data.split("_")[2])
    cursor.execute("DELETE FROM forced_channels WHERE id = ?", (ch_id,))
    conn.commit()
    try:
        await callback.message.edit_text("✅ Kanal o'chirildi!")
    except:
        await safe_send_message(callback.from_user.id, "✅ Kanal o'chirildi!")
    await callback.answer()

@dp.callback_query(F.data.startswith("forced_page_"))
async def forced_page_callback(callback: CallbackQuery):
    page = int(callback.data.split("_")[2])
    try:
        await callback.message.edit_text("❌ O'chirmoqchi bo'lgan kanalni tanlang:", reply_markup=forced_channel_list_keyboard(page))
    except:
        await safe_send_message(callback.from_user.id, "❌ O'chirmoqchi bo'lgan kanalni tanlang:", reply_markup=forced_channel_list_keyboard(page))
    await callback.answer()

@dp.callback_query(F.data == "forced_list")
async def forced_list(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q!")
        return
    cursor.execute("SELECT channel_username, is_active FROM forced_channels ORDER BY channel_username")
    channels = cursor.fetchall()
    if not channels:
        text = "📭 Majburiy kanallar ro'yxati bo'sh."
    else:
        text = "📋 Majburiy kanallar:\n\n"
        for ch_username, active in channels:
            status = "✅ aktiv" if active else "❌ noaktiv"
            text += f"• {ch_username} ({status})\n"
    try:
        await callback.message.edit_text(text)
    except:
        await safe_send_message(callback.from_user.id, text)
    await callback.answer()

@dp.callback_query(F.data == "back_to_forced_menu")
async def back_to_forced_menu(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    try:
        await callback.message.edit_text("🔗 Majburiy a'zolik boshqaruvi:", reply_markup=forced_channel_buttons(), parse_mode="HTML")
    except:
        await safe_send_message(callback.from_user.id, "🔗 Majburiy a'zolik boshqaruvi:", reply_markup=forced_channel_buttons(), parse_mode="HTML")
    await callback.answer()

# ================================================================
# 26-ADMIN QO'SHISH/CHIQARISH
# ================================================================
@dp.message(F.text == "👑 Admin Qo'shish")
async def admin_manage(message: Message, state: FSMContext):
    if not is_owner(message.from_user.id):
        await message.answer("❌ Faqat ownerlar admin qo'shishi mumkin!")
        return
    await message.answer("Admin boshqaruvi:", reply_markup=admin_manage_buttons(), parse_mode="HTML")
    await state.set_state(AdminManageState.action)

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
    admins = cursor.execute("SELECT user_id FROM admins WHERE user_id NOT IN (?, ?)", ADMINS[0], ADMINS[1] if len(ADMINS) > 1 else 0).fetchall()
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
            cursor.execute("INSERT OR IGNORE INTO admins (user_id, added_by, added_at) VALUES (?, ?, ?)", (user_id, message.from_user.id, datetime.now().isoformat()))
            conn.commit()
            await message.answer(f"✅ {user_id} admin qo'shildi!" if cursor.rowcount > 0 else f"⚠️ {user_id} allaqachon admin!")
            try:
                await bot.send_message(user_id, "🎉 Siz admin etib tayinlandingiz!\n/admin orqali panelga kiring.")
            except:
                pass
        else:
            if user_id in ADMINS:
                await message.answer("❌ Ownerlarni o'chirib bo'lmaydi!")
            else:
                cursor.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
                conn.commit()
                await message.answer(f"✅ {user_id} adminlikdan chiqarildi!" if cursor.rowcount > 0 else f"⚠️ {user_id} admin emas!")
    except ValueError:
        await message.answer("❌ Faqat raqam kiriting!")
    await state.clear()

# ================================================================
# 27-POST QILISH
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
📢 Kanal: @AniCity_Rasmiy
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
📢 Kanal: @AniCity_Rasmiy
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
# 28-QISMNI POST QILISH
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

📢 Kanal: @AniCity_Rasmiy
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

📢 Kanal: @AniCity_Rasmiy
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
# 29-BOSHQA CALLBACKLAR
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
        f"👥 Foydalanuvchilar: {cursor.execute('SELECT COUNT(*) FROM users').fetchone()[0]}\n\n"
        "⬇️ Quyidagi tugmalardan foydalaning:"
    )
    if admin_image:
        await safe_send_photo(callback.from_user.id, photo=admin_image, caption=admin_text, reply_markup=admin_menu(), parse_mode="HTML")
    else:
        await safe_send_message(callback.from_user.id, admin_text, reply_markup=admin_menu(), parse_mode="HTML")
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
# 30-UNKNOWN HANDLER
# ================================================================
@dp.message()
async def handle_unknown(message: Message):
    # Hech qanday javob qaytarmaydi
    pass

# ================================================================
# 31-BOTNI ISHGA TUSHIRISH
# ================================================================
async def main():
    print("=" * 60)
    print("🤖 ANICITY RASMIY BOT - TO'LIQ VERSIYA")
    print("=" * 60)
    print(f"👑 Adminlar: {ADMINS}")
    print(f"📢 Asosiy kanal: {MAIN_CHANNEL}")
    print(f"👨‍💻 Muallif: {AUTHOR_USERNAME} ({AUTHOR_LINK})")
    print(f"🆘 Yordam: {SUPPORT_USERNAME} ({SUPPORT_LINK})")
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
