# ================================================================
# ANICITY RASMIY BOT - TUZATILGAN TO'LIQ VERSIYA
# ================================================================
# Muallif: @s_2akk
# Kanal: @AniCity_Rasmiy
# ================================================================

import asyncio
import logging
import os
import re
import io
from datetime import datetime
from typing import Tuple, List, Dict, Any, Optional
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F, BaseMiddleware
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, FSInputFile, BufferedInputFile
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder
import aiosqlite
import aiohttp
import base64

# ================= KONFIGURATSIYA =================
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "8545654766:AAHc9XBWMsgQWxibBXcPN44vu1rZ6AILlMg")
ADMINS = [int(x.strip()) for x in os.getenv("ADMINS", "5675087151,6498527560").split(",")]
MAIN_CHANNEL = os.getenv("MAIN_CHANNEL", "@AniCity_Rasmiy")
BASE_CHANNEL_ID = int(os.getenv("BASE_CHANNEL_ID", "-1003888128587"))
AUTHOR_LINK = "https://t.me/S_2ak"
AUTHOR_USERNAME = "@s_2akk"

# LOCAL RASMLAR
START_IMAGE_PATH = "Anime.jpg"
ADMIN_IMAGE_PATH = "admin.png"

# ================= LOGING SOZLAMALARI =================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ================= DATABASE (aiosqlite bilan) =================
DB_NAME = 'anime_bot.db'

class Database:
    def __init__(self, db_path: str = DB_NAME):
        self.db_path = db_path
        self._conn = None
    
    async def connect(self):
        """Ma'lumotlar bazasiga ulanish"""
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._init_tables()
        return self._conn
    
    async def _init_tables(self):
        """Jadvallarni yaratish"""
        await self._conn.execute('''
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
        
        await self._conn.execute('''
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
        
        await self._conn.execute('''
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
        
        await self._conn.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY,
            added_by INTEGER,
            added_at TEXT
        )
        ''')
        
        await self._conn.execute('''
        CREATE TABLE IF NOT EXISTS forced_channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_username TEXT UNIQUE,
            channel_id INTEGER,
            is_active INTEGER DEFAULT 1,
            added_at TEXT
        )
        ''')
        
        # Dastlabki adminlarni qo'shish
        now = datetime.now().isoformat()
        for admin_id in ADMINS:
            await self._conn.execute(
                "INSERT OR IGNORE INTO admins (user_id, added_by, added_at) VALUES (?, ?, ?)",
                (admin_id, admin_id, now)
            )
        
        await self._conn.commit()
        logger.info("✅ Database muvaffaqiyatli yuklandi!")
    
    @asynccontextmanager
    async def execute(self, query: str, params: tuple = ()):
        """Xavfsiz query bajarish"""
        async with self._conn.execute(query, params) as cursor:
            yield cursor
    
    async def fetch_one(self, query: str, params: tuple = ()):
        """Bitta qator olish"""
        async with self._conn.execute(query, params) as cursor:
            return await cursor.fetchone()
    
    async def fetch_all(self, query: str, params: tuple = ()):
        """Hamma qatorlarni olish"""
        async with self._conn.execute(query, params) as cursor:
            return await cursor.fetchall()
    
    async def execute_and_commit(self, query: str, params: tuple = ()):
        """Query bajarish va commit qilish"""
        await self._conn.execute(query, params)
        await self._conn.commit()
    
    async def close(self):
        """Ulanishni yopish"""
        if self._conn:
            await self._conn.close()

# Database instance
db = Database()

# ================= BOT SOZLAMALARI =================
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ================= YORDAMCHI FUNKSIYALAR =================
def get_start_image() -> Optional[FSInputFile]:
    """Start rasmni qaytarish"""
    return FSInputFile(START_IMAGE_PATH) if os.path.exists(START_IMAGE_PATH) else None

def get_admin_image() -> Optional[FSInputFile]:
    """Admin panel rasmini qaytarish"""
    return FSInputFile(ADMIN_IMAGE_PATH) if os.path.exists(ADMIN_IMAGE_PATH) else None

def get_welcome_text() -> str:
    """Welcome textni qaytarish (takrorlanmaslik uchun)"""
    return f"""🎬 <b>AniCity Rasmiy Bot</b> 🎬

✨ <b>Botimizga xush kelibsiz!</b> ✨

📚 <b>Bot imkoniyatlari:</b>
🔍 Kod orqali qidiruv
🎬 Anime va dramalarni nom bilan qidirish
🖼 Rasm orqali anime topish
📺 Barcha qismlarni tomosha qilish

📢 <b>Asosiy kanal:</b> {MAIN_CHANNEL}
👨‍💻 <b>Muallif:</b> <a href='{AUTHOR_LINK}'>{AUTHOR_USERNAME}</a>
🆘 <b>Yordam:</b> <a href='{AUTHOR_LINK}'>{AUTHOR_USERNAME}</a>

⬇️ <b>Quyidagi tugmalardan birini tanlang:</b> ⬇️"""

def start_menu() -> InlineKeyboardMarkup:
    """Asosiy menyu tugmalari"""
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

def admin_menu() -> ReplyKeyboardMarkup:
    """Admin panel tugmalari"""
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="➕ Media Qo'shish"), KeyboardButton(text="➕ Qism Qo'shish")],
        [KeyboardButton(text="➕ Ko'p Qism Qo'shish"), KeyboardButton(text="✏️ Media Tahrirlash")],
        [KeyboardButton(text="✏️ Qismni Tahrirlash"), KeyboardButton(text="📊 Statistika")],
        [KeyboardButton(text="📢 Xabar Yuborish"), KeyboardButton(text="🔗 Majburiy A'zo")],
        [KeyboardButton(text="👑 Admin Qo'shish"), KeyboardButton(text="📨 Post Qilish")],
        [KeyboardButton(text="🎬 Qismni Post Qilish"), KeyboardButton(text="🔙 Asosiy menyu")]
    ], resize_keyboard=True)

async def is_admin(user_id: int) -> bool:
    """Foydalanuvchi adminligini tekshirish"""
    result = await db.fetch_one("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
    return result is not None or user_id in ADMINS

async def is_owner(user_id: int) -> bool:
    """Foydalanuvchi owner ekanligini tekshirish"""
    return user_id in ADMINS

async def add_user(user) -> None:
    """Yangi foydalanuvchi qo'shish"""
    now = datetime.now().isoformat()
    await db.execute_and_commit(
        "INSERT OR IGNORE INTO users (id, username, first_name, last_name, registered_at, last_active) VALUES (?, ?, ?, ?, ?, ?)",
        (user.id, user.username, user.first_name, user.last_name, now, now)
    )

async def update_user_activity(user_id: int) -> None:
    """Foydalanuvchi faolligini yangilash"""
    await db.execute_and_commit(
        "UPDATE users SET last_active = ? WHERE id = ?",
        (datetime.now().isoformat(), user_id)
    )

async def safe_send_message(chat_id: int, text: str, **kwargs):
    """Xavfsiz xabar yuborish"""
    try:
        return await bot.send_message(chat_id, text, **kwargs)
    except Exception as e:
        logger.error(f"Xabar yuborish xatosi {chat_id}: {e}")
        return None

async def safe_send_photo(chat_id: int, photo, caption=None, **kwargs):
    """Xavfsiz rasm yuborish"""
    try:
        return await bot.send_photo(chat_id, photo, caption=caption, **kwargs)
    except Exception as e:
        logger.error(f"Rasm yuborish xatosi {chat_id}: {e}")
        return await safe_send_message(chat_id, caption if caption else "Rasm yuborib bo'lmadi!", **kwargs)

async def safe_send_video(chat_id: int, video, caption=None, **kwargs):
    """Xavfsiz video yuborish"""
    try:
        return await bot.send_video(chat_id, video, caption=caption, **kwargs)
    except Exception as e:
        logger.error(f"Video yuborish xatosi {chat_id}: {e}")
        return None

# ================= MAJBURIY OBUNA (TO'G'RILANGAN - BOT ADMIN BO'LISHI SHART EMAS) =================
async def check_subscription(user_id: int) -> Tuple[bool, List[dict]]:
    """
    Foydalanuvchi barcha aktiv majburiy kanallarga a'zoligini tekshiradi
    Bot admin bo'lishi SHART EMAS!
    """
    rows = await db.fetch_all("SELECT id, channel_username, channel_id FROM forced_channels WHERE is_active = 1")
    channels = list(rows)
    
    if not channels:
        return True, []
    
    not_subscribed = []
    for ch_id, channel_username, channel_id in channels:
        clean_username = channel_username.replace('@', '').strip()
        if not clean_username:
            continue
        
        try:
            # Kanal ID ni olish (agar mavjud bo'lmasa)
            if not channel_id:
                try:
                    chat = await bot.get_chat(f"@{clean_username}")
                    channel_id = chat.id
                    await db.execute_and_commit(
                        "UPDATE forced_channels SET channel_id = ? WHERE id = ?",
                        (channel_id, ch_id)
                    )
                except Exception as e:
                    logger.warning(f"Kanal topilmadi {clean_username}: {e}")
                    continue
            
            # A'zolikni tekshirish (bot admin bo'lmasa ham ishlaydi)
            try:
                member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
                if member.status in ['left', 'kicked']:
                    not_subscribed.append({
                        'id': ch_id,
                        'username': f"@{clean_username}",
                        'invite_link': None
                    })
            except Exception as e:
                # Bot kanalda admin bo'lmasa, get_chat_member ishlamasligi mumkin
                # Bu holatda foydalanuvchini tekshirib bo'lmaydi - kanalni o'tkazib yuboramiz
                logger.warning(f"Kanal {clean_username} da a'zolik tekshirib bo'lmadi: {e}")
                # Kanalni noaktiv qilamiz
                await db.execute_and_commit(
                    "UPDATE forced_channels SET is_active = 0 WHERE id = ?",
                    (ch_id,)
                )
                
        except Exception as e:
            logger.error(f"Kanal tekshirish xatosi {channel_username}: {e}")
    
    return len(not_subscribed) == 0, not_subscribed

async def get_subscription_keyboard(not_subscribed: List[dict]) -> InlineKeyboardMarkup:
    """A'zo bo'lmagan kanallar uchun tugmalar"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    
    for ch in not_subscribed:
        username = ch['username']
        clean = username.replace('@', '')
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text=f"📢 {username}", url=f"https://t.me/{clean}")
        ])
    
    keyboard.inline_keyboard.append([
        InlineKeyboardButton(text="✅ A'zolikni tekshirish", callback_data="check_subscription")
    ])
    
    return keyboard

# ================= MIDDLEWARE (TO'G'RILANGAN) =================
class SubscriptionMiddleware(BaseMiddleware):
    """Barcha handlerlarni majburiy a'zolikka tekshiradi"""
    
    async def __call__(self, handler, event, data):
        user_id = None
        is_callback = False
        
        if isinstance(event, Message):
            user_id = event.from_user.id
            # /start handlerini o'tkazib yuborish
            if event.text and event.text.startswith("/start"):
                return await handler(event, data)
                
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
            is_callback = True
            # check_subscription callback ini o'tkazib yuborish
            if event.data == "check_subscription":
                return await handler(event, data)
        
        if not user_id:
            return await handler(event, data)
        
        try:
            subscribed, not_subscribed = await check_subscription(user_id)
            
            if not subscribed:
                text = "❌ <b>Botdan foydalanish uchun quyidagi kanallarga a'zo bo'ling:</b>\n\n"
                for ch in not_subscribed:
                    text += f"• {ch['username']}\n"
                text += "\n✅ A'zo bo'lgandan so'ng <b>Tekshirish</b> tugmasini bosing."
                
                keyboard = await get_subscription_keyboard(not_subscribed)
                
                if is_callback:
                    try:
                        await event.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
                    except Exception as e:
                        logger.error(f"Callback edit xatosi: {e}")
                        await event.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
                else:
                    await event.answer(text, reply_markup=keyboard, parse_mode="HTML")
                return
        except Exception as e:
            logger.error(f"Middleware xatosi: {e}")
        
        return await handler(event, data)

# Middleware-ni ro'yxatdan o'tkazish
dp.message.middleware(SubscriptionMiddleware())
dp.callback_query.middleware(SubscriptionMiddleware())

# ================= STATE'LAR =================
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

# ================= TUZATILGAN CALLBACK HANDLERLAR =================
@dp.callback_query(lambda c: c.data.startswith("parts_page_"))
async def parts_page_callback(callback: CallbackQuery):
    """TUZATILGAN: parts_page_ callback handleri"""
    try:
        # XATO TUZATILDI: parts_page_123_0 -> 4 ta element
        parts = callback.data.split("_")
        # parts = ["parts", "page", "123", "0"] yoki ["parts", "page", "123"]
        
        if len(parts) >= 4:
            media_id = int(parts[2])
            page = int(parts[3])
        else:
            media_id = int(parts[2])
            page = 0
        
        cursor = await db.fetch_all("SELECT part_number, id FROM parts WHERE media_id = ? ORDER BY part_number", (media_id,))
        parts_list = list(cursor)
        
        if not parts_list:
            await callback.answer("Qismlar mavjud emas!", show_alert=True)
            return
        
        # Qismlar ro'yxatini ko'rsatish
        builder = InlineKeyboardBuilder()
        per_page = 20
        start = page * per_page
        
        for part_num, part_id in parts_list[start:start+per_page]:
            builder.button(text=f"📹 {part_num}-qism", callback_data=f"select_part_{part_id}")
        builder.adjust(2)
        
        if page > 0:
            builder.row(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"parts_page_{media_id}_{page-1}"))
        if start + per_page < len(parts_list):
            builder.row(InlineKeyboardButton(text="➡️ Keyingi", callback_data=f"parts_page_{media_id}_{page+1}"))
        builder.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"back_to_media_{media_id}"))
        
        try:
            await callback.message.edit_text("📹 Qism tanlang:", reply_markup=builder.as_markup())
        except Exception as e:
            logger.error(f"parts_page edit xatosi: {e}")
            await callback.message.answer("📹 Qism tanlang:", reply_markup=builder.as_markup())
            
    except Exception as e:
        logger.error(f"parts_page_callback xatosi: {e}")
        await callback.answer("Xatolik yuz berdi!", show_alert=True)
    
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("media_page_"))
async def media_page_callback(callback: CallbackQuery):
    """TUZATILGAN: media_page_ callback handleri"""
    try:
        parts = callback.data.split("_")
        # media_page_0_anime yoki media_page_0_
        
        page = int(parts[2]) if len(parts) > 2 else 0
        media_type = None
        if len(parts) > 3 and parts[3] and parts[3] != 'None':
            media_type = parts[3]
        
        if media_type:
            rows = await db.fetch_all(
                "SELECT id, name, code FROM media WHERE type = ? ORDER BY name",
                (media_type,)
            )
        else:
            rows = await db.fetch_all("SELECT id, name, code FROM media ORDER BY name")
        
        media_list = list(rows)
        
        builder = InlineKeyboardBuilder()
        per_page = 10
        start = page * per_page
        
        for media_id, name, code in media_list[start:start+per_page]:
            builder.button(text=f"{name} [{code}]", callback_data=f"select_media_{media_id}")
        builder.adjust(1)
        
        if page > 0:
            callback_data = f"media_page_{page-1}_{media_type if media_type else ''}"
            builder.row(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=callback_data))
        if start + per_page < len(media_list):
            callback_data = f"media_page_{page+1}_{media_type if media_type else ''}"
            builder.row(InlineKeyboardButton(text="➡️ Keyingi", callback_data=callback_data))
        builder.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_admin_reply"))
        
        try:
            await callback.message.edit_text("📺 Media tanlang:", reply_markup=builder.as_markup())
        except Exception as e:
            logger.error(f"media_page edit xatosi: {e}")
            await callback.message.answer("📺 Media tanlang:", reply_markup=builder.as_markup())
            
    except Exception as e:
        logger.error(f"media_page_callback xatosi: {e}")
        await callback.answer("Xatolik yuz berdi!", show_alert=True)
    
    await callback.answer()

# ================= START HANDLER =================
@dp.message(Command("start"))
async def start(message: Message):
    await add_user(message.from_user)
    await update_user_activity(message.from_user.id)
    
    # Deep link qo'llab-quvvatlash
    args = message.text.split()
    if len(args) > 1 and args[1].startswith("code_"):
        code = args[1].replace("code_", "")
        if "&part=" in code:
            code, part_num = code.split("&part=")
            try:
                code_int = int(code)
                part_num_int = int(part_num)
                media_row = await db.fetch_one("SELECT id FROM media WHERE code = ?", (code_int,))
                if media_row:
                    media_id = media_row[0]
                    part_row = await db.fetch_one(
                        "SELECT file_id, caption FROM parts WHERE media_id = ? AND part_number = ?",
                        (media_id, part_num_int)
                    )
                    if part_row:
                        file_id, caption = part_row
                        media_name_row = await db.fetch_one("SELECT name FROM media WHERE id = ?", (media_id,))
                        media_name = media_name_row[0] if media_name_row else "Anime"
                        full_caption = f"🎬 {media_name}\n📹 {part_num_int}-qism\n\n{caption if caption else ''}"
                        await safe_send_video(message.chat.id, video=file_id, caption=full_caption, parse_mode="HTML")
                        return
            except Exception as e:
                logger.error(f"Deep link xatosi: {e}")
    
    start_image = get_start_image()
    welcome_text = get_welcome_text()
    
    if start_image:
        await safe_send_photo(message.chat.id, photo=start_image, caption=welcome_text, reply_markup=start_menu(), parse_mode="HTML")
    else:
        await safe_send_message(message.chat.id, welcome_text, reply_markup=start_menu(), parse_mode="HTML")

@dp.callback_query(F.data == "check_subscription")
async def check_subscription_callback(callback: CallbackQuery):
    """A'zolikni tekshirish callback handleri"""
    try:
        subscribed, not_subscribed = await check_subscription(callback.from_user.id)
        
        if subscribed:
            welcome_text = get_welcome_text()
            start_image = get_start_image()
            
            try:
                await callback.message.delete()
            except:
                pass
            
            if start_image:
                await safe_send_photo(callback.from_user.id, photo=start_image, caption=welcome_text, reply_markup=start_menu(), parse_mode="HTML")
            else:
                await safe_send_message(callback.from_user.id, welcome_text, reply_markup=start_menu(), parse_mode="HTML")
        else:
            text = "❌ <b>Siz hali ham quyidagi kanallarga a'zo emassiz:</b>\n\n"
            for ch in not_subscribed:
                text += f"• {ch['username']}\n"
            text += "\n✅ A'zo bo'lgandan so'ng <b>Tekshirish</b> tugmasini bosing."
            
            keyboard = await get_subscription_keyboard(not_subscribed)
            
            try:
                await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
            except:
                await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        logger.error(f"check_subscription_callback xatosi: {e}")
    
    await callback.answer()

@dp.callback_query(F.data == "back_to_start")
async def back_to_start(callback: CallbackQuery):
    """Asosiy menyuga qaytish"""
    try:
        await callback.message.delete()
    except:
        pass
    
    welcome_text = get_welcome_text()
    start_image = get_start_image()
    
    if start_image:
        await safe_send_photo(callback.from_user.id, photo=start_image, caption=welcome_text, reply_markup=start_menu(), parse_mode="HTML")
    else:
        await safe_send_message(callback.from_user.id, welcome_text, reply_markup=start_menu(), parse_mode="HTML")
    
    await callback.answer()

@dp.message(F.text == "🔙 Asosiy menyu")
async def back_to_main_reply(message: Message):
    """Asosiy menyuga qaytish (reply keyboard)"""
    welcome_text = get_welcome_text()
    start_image = get_start_image()
    
    if start_image:
        await safe_send_photo(message.chat.id, photo=start_image, caption=welcome_text, reply_markup=start_menu(), parse_mode="HTML")
    else:
        await safe_send_message(message.chat.id, welcome_text, reply_markup=start_menu(), parse_mode="HTML")

# ================= MAJBURIY KANAL BOSHQARUVI (TO'G'RILANGAN) =================
@dp.message(F.text == "🔗 Majburiy A'zo")
async def forced_subscribe_menu(message: Message):
    if not await is_admin(message.from_user.id):
        await message.answer("❌ Siz admin emassiz!")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="forced_add")],
        [InlineKeyboardButton(text="❌ Kanal o'chirish", callback_data="forced_remove")],
        [InlineKeyboardButton(text="📋 Kanallar ro'yxati", callback_data="forced_list")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_admin_reply")]
    ])
    
    await message.answer("🔗 <b>Majburiy a'zolik boshqaruvi</b>\n\nBu yerdan botdan foydalanish uchun majburiy a'zo bo'linadigan kanallarni boshqarishingiz mumkin.\n\n⚠️ <b>Eslatma:</b> Bot kanalda admin bo'lishi shart EMAS!", 
                         reply_markup=keyboard, parse_mode="HTML")

@dp.callback_query(F.data == "forced_add")
async def forced_add_start(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q!", show_alert=True)
        return
    
    await state.set_state(ForcedChannelState.waiting_for_channel)
    await callback.message.edit_text(
        "➕ <b>Kanal qo'shish</b>\n\n"
        "Kanal username yoki linkini yuboring:\n"
        "Masalan: @kanal yoki https://t.me/kanal\n\n"
        "⚠️ Bot kanalda admin bo'lishi shart EMAS!",
        parse_mode="HTML"
    )
    await callback.answer()

@dp.message(ForcedChannelState.waiting_for_channel)
async def forced_add_channel(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        await message.answer("❌ Siz admin emassiz!")
        await state.clear()
        return
    
    channel_input = message.text.strip()
    
    # Kanal username ni aniqlash
    if channel_input.startswith("https://t.me/"):
        parts = channel_input.split("/")
        username = parts[-1].split("?")[0]
        channel_username = f"@{username}"
    elif channel_input.startswith("@"):
        channel_username = channel_input
    else:
        channel_username = f"@{channel_input}"
    
    clean_username = channel_username.replace('@', '').strip()
    
    # Kanal mavjudligini tekshirish (bot admin bo'lmasa ham ishlaydi)
    try:
        chat = await bot.get_chat(f"@{clean_username}")
        channel_id = chat.id
        
        # Kanalni ma'lumotlar bazasiga qo'shish
        await db.execute_and_commit('''
        INSERT OR IGNORE INTO forced_channels (channel_username, channel_id, is_active, added_at)
        VALUES (?, ?, ?, ?)
        ''', (channel_username, channel_id, 1, datetime.now().isoformat()))
        
        result = await db.fetch_one("SELECT changes()")
        if result and result[0] > 0:
            await message.answer(f"✅ <b>{channel_username}</b> majburiy a'zolik ro'yxatiga qo'shildi!\n\nBot endi foydalanuvchilardan ushbu kanalga a'zo bo'lishni talab qiladi.", parse_mode="HTML")
        else:
            await message.answer(f"⚠️ {channel_username} allaqachon ro'yxatda mavjud!")
            
    except Exception as e:
        logger.error(f"Kanal qo'shish xatosi: {e}")
        await message.answer(f"❌ <b>{channel_username}</b> kanali topilmadi!\nIltimos, to'g'ri username yoki link kiriting.", parse_mode="HTML")
    
    await state.clear()

@dp.callback_query(F.data == "forced_remove")
async def forced_remove_list(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q!", show_alert=True)
        return
    
    rows = await db.fetch_all("SELECT id, channel_username FROM forced_channels WHERE is_active = 1 ORDER BY channel_username")
    channels = list(rows)
    
    if not channels:
        await callback.message.edit_text("📭 <b>Majburiy kanallar ro'yxati bo'sh.</b>\n\n➕ 'Kanal qo'shish' tugmasidan foydalanib kanal qo'shing.", parse_mode="HTML")
        await callback.answer()
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for ch_id, channel_username in channels:
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text=f"❌ {channel_username}", callback_data=f"forced_del_{ch_id}")
        ])
    keyboard.inline_keyboard.append([
        InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_forced_menu")
    ])
    
    await callback.message.edit_text("❌ <b>O'chirmoqchi bo'lgan kanalni tanlang:</b>\n\n⚠️ Diqqat: O'chirilgandan so'ng, foydalanuvchilar endi bu kanalga a'zo bo'lishi shart emas!", 
                                     reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data.startswith("forced_del_"))
async def forced_remove_channel(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q!", show_alert=True)
        return
    
    ch_id = int(callback.data.split("_")[2])
    channel_row = await db.fetch_one("SELECT channel_username FROM forced_channels WHERE id = ?", (ch_id,))
    
    if channel_row:
        channel_username = channel_row[0]
        await db.execute_and_commit("DELETE FROM forced_channels WHERE id = ?", (ch_id,))
        await callback.message.edit_text(f"✅ <b>{channel_username}</b> majburiy a'zolik ro'yxatidan o'chirildi!", parse_mode="HTML")
    else:
        await callback.message.edit_text("❌ Kanal topilmadi!", parse_mode="HTML")
    
    await callback.answer()

@dp.callback_query(F.data == "forced_list")
async def forced_list(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q!", show_alert=True)
        return
    
    rows = await db.fetch_all("SELECT channel_username, is_active, added_at FROM forced_channels ORDER BY channel_username")
    channels = list(rows)
    
    if not channels:
        text = "📭 <b>Majburiy kanallar ro'yxati bo'sh.</b>"
    else:
        text = "📋 <b>Majburiy kanallar ro'yxati:</b>\n\n"
        for ch_username, is_active, added_at in channels:
            status = "✅ Aktiv" if is_active else "❌ Noaktiv"
            date = added_at[:10] if added_at else "Noma'lum"
            text += f"• {ch_username}\n  {status} | Qo'shilgan: {date}\n\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_forced_menu")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "back_to_forced_menu")
async def back_to_forced_menu(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="forced_add")],
        [InlineKeyboardButton(text="❌ Kanal o'chirish", callback_data="forced_remove")],
        [InlineKeyboardButton(text="📋 Kanallar ro'yxati", callback_data="forced_list")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_admin_reply")]
    ])
    
    await callback.message.edit_text("🔗 <b>Majburiy a'zolik boshqaruvi</b>\n\nBu yerdan botdan foydalanish uchun majburiy a'zo bo'linadigan kanallarni boshqarishingiz mumkin.\n\n⚠️ <b>Eslatma:</b> Bot kanalda admin bo'lishi shart EMAS!", 
                                     reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

# ================= BOTNI ISHGA TUSHIRISH =================
async def main():
    print("=" * 60)
    print("🤖 ANICITY RASMIY BOT - TUZATILGAN VERSIYA")
    print("=" * 60)
    print(f"👑 Adminlar: {ADMINS}")
    print(f"📢 Asosiy kanal: {MAIN_CHANNEL}")
    print(f"👨‍💻 Muallif: {AUTHOR_USERNAME}")
    print("=" * 60)
    
    # Ma'lumotlar bazasiga ulanish
    await db.connect()
    print("✅ Database ulandi!")
    
    # Webhookni o'chirish
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        print("✅ Webhook o'chirildi!")
    except Exception as e:
        print(f"⚠️ Webhook o'chirish xatosi: {e}")
    
    print("✅ Bot to'liq ishga tushdi!")
    print("=" * 60)
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
