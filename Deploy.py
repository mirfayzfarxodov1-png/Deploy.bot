import asyncio
import logging
import json
import os
import sqlite3
from datetime import datetime
from typing import Optional, Dict, List, Tuple
from pathlib import Path

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, FSInputFile,
    InputMediaPhoto
)
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, Float, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

# ================= KONFIGURATSIYA =================
TOKEN = "8545654766:AAHc9XBWMsgQWxibBXcPN44vu1rZ6AILlMg"
OWNER_IDS = [6498527560, 5675087151]
BASE_CHANNEL_ID = -1003888128587  # Media saqlanadigan kanal

# Bot haqida ma'lumot
BOT_USERNAME = "AniCityBot"
CHANNEL_LINK = "https://t.me/AniCity_Rasmiy"
AUTHOR_LINK = "https://t.me/S_2ak"

# ================= DATABASE =================
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, unique=True, nullable=False)
    username = Column(String(255))
    full_name = Column(String(255))
    join_date = Column(DateTime, default=datetime.now)
    is_admin = Column(Boolean, default=False)
    is_owner = Column(Boolean, default=False)

class Anime(Base):
    __tablename__ = 'animes'
    id = Column(Integer, primary_key=True)
    code = Column(String(50), unique=True, nullable=False)
    name = Column(String(500), nullable=False)
    name_uz = Column(String(500))
    name_ru = Column(String(500))
    janr = Column(String(500))
    season = Column(Integer, default=1)
    total_episodes = Column(Integer, default=0)
    status = Column(String(50), default="Tugallangan")  # Tugallangan, Davom etmoqda
    dublyaj = Column(String(200), default="@AniCity_Rasmiy")
    quality = Column(String(50), default="720p")
    image_url = Column(String(500))
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.now)

class Episode(Base):
    __tablename__ = 'episodes'
    id = Column(Integer, primary_key=True)
    anime_code = Column(String(50), ForeignKey('animes.code'), nullable=False)
    episode_number = Column(Integer, nullable=False)
    video_url = Column(String(500), nullable=False)
    file_id = Column(String(500))
    message_id = Column(Integer)
    created_at = Column(DateTime, default=datetime.now)

class Media(Base):
    __tablename__ = 'media'
    id = Column(Integer, primary_key=True)
    file_id = Column(String(500), unique=True, nullable=False)
    file_type = Column(String(50))  # video, photo
    anime_code = Column(String(50))
    episode_number = Column(Integer)
    created_at = Column(DateTime, default=datetime.now)

# ================= DATABASE SOZLAMALARI =================
engine = create_engine('sqlite:///anime_bot.db', echo=False)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

# ================= BOT SOZLAMALARI =================
logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ================= STATE LAR =================
class SearchState(StatesGroup):
    waiting_for_anime_code = State()
    waiting_for_anime_name = State()
    waiting_for_drama_name = State()
    waiting_for_anime_image = State()

class AdminState(StatesGroup):
    waiting_for_anime_name_or_code = State()
    waiting_for_multiple_episodes = State()
    waiting_for_episode_video = State()
    waiting_for_episode_number = State()
    waiting_for_edit_anime_code = State()
    waiting_for_edit_field = State()
    waiting_for_edit_value = State()
    waiting_for_post_message = State()
    waiting_for_post_channel = State()
    waiting_for_add_admin_id = State()
    waiting_for_anime_to_post = State()
    waiting_for_episode_to_post = State()
    waiting_for_media_edit_anime = State()
    waiting_for_media_edit_episode = State()
    waiting_for_new_media = State()

# ================= KLAVIATURALAR =================
def get_main_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📝 Kod orqali qidiruv"),
                KeyboardButton(text="🎬 Anime Qidiruv")
            ],
            [
                KeyboardButton(text="🎭 Drama Qidiruv"),
                KeyboardButton(text="🖼 Rasm Orqali Anime Qidiruv")
            ],
            [
                KeyboardButton(text="📓 Ro'yxat"),
                KeyboardButton(text="💸 Reklama")
            ],
            [
                KeyboardButton(text="👑 Admin Panel")
            ]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_back_button():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_main")]
    ])
    return keyboard

def get_admin_main_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📊 Statistika"),
                KeyboardButton(text="➕ Media Qo'shish")
            ],
            [
                KeyboardButton(text="✏️ Media Tahrirlash"),
                KeyboardButton(text="📨 Xabar Yuborish")
            ],
            [
                KeyboardButton(text="👥 Admin Qo'shish"),
                KeyboardButton(text="📢 Post Qilish")
            ],
            [
                KeyboardButton(text="🔙 Asosiy menyu")
            ]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_media_add_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🎬 Ko'p Qism Qo'shish"),
                KeyboardButton(text="📀 Qism Qo'shish")
            ],
            [
                KeyboardButton(text="🔙 Asosiy menyu")
            ]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_episode_actions_keyboard(anime_code: str, episode_num: int):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="▶️ Tomosha qilish", callback_data=f"watch_ep_{anime_code}_{episode_num}")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"back_to_anime_{anime_code}")]
    ])
    return keyboard

def get_anime_actions_keyboard(anime_code: str):
    builder = InlineKeyboardBuilder()
    builder.button(text="▶️ Tomosha qilish", callback_data=f"watch_anime_{anime_code}")
    builder.button(text="🔙 Orqaga", callback_data="back_to_main")
    builder.adjust(1)
    return builder.as_markup()

# ================= DATABASE FUNKSIYALARI =================
def add_user(user_id: int, username: str = None, full_name: str = None):
    session = Session()
    try:
        existing = session.query(User).filter_by(user_id=user_id).first()
        if not existing:
            user = User(
                user_id=user_id,
                username=username,
                full_name=full_name,
                is_admin=user_id in OWNER_IDS,
                is_owner=user_id in OWNER_IDS
            )
            session.add(user)
            session.commit()
    finally:
        session.close()

def is_admin(user_id: int) -> bool:
    session = Session()
    try:
        user = session.query(User).filter_by(user_id=user_id).first()
        return user.is_admin if user else (user_id in OWNER_IDS)
    finally:
        session.close()

def is_owner(user_id: int) -> bool:
    return user_id in OWNER_IDS

def add_anime(code: str, name: str, janr: str = "", season: int = 1, 
              status: str = "Tugallangan", quality: str = "720p", image_url: str = ""):
    session = Session()
    try:
        anime = Anime(
            code=code,
            name=name,
            janr=janr,
            season=season,
            status=status,
            quality=quality,
            image_url=image_url
        )
        session.add(anime)
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        print(f"Error adding anime: {e}")
        return False
    finally:
        session.close()

def get_anime_by_code(code: str):
    session = Session()
    try:
        return session.query(Anime).filter_by(code=code).first()
    finally:
        session.close()

def get_anime_by_name(name: str):
    session = Session()
    try:
        return session.query(Anime).filter(Anime.name.ilike(f"%{name}%")).first()
    finally:
        session.close()

def search_anime_by_name(name: str):
    session = Session()
    try:
        return session.query(Anime).filter(Anime.name.ilike(f"%{name}%")).all()
    finally:
        session.close()

def get_all_animes():
    session = Session()
    try:
        return session.query(Anime).all()
    finally:
        session.close()

def add_episode(anime_code: str, episode_num: int, file_id: str = None, video_url: str = None):
    session = Session()
    try:
        episode = Episode(
            anime_code=anime_code,
            episode_number=episode_num,
            file_id=file_id,
            video_url=video_url
        )
        session.add(episode)
        
        anime = session.query(Anime).filter_by(code=anime_code).first()
        if anime:
            count = session.query(Episode).filter_by(anime_code=anime_code).count()
            anime.total_episodes = count
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        print(f"Error adding episode: {e}")
        return False
    finally:
        session.close()

def get_episodes(anime_code: str):
    session = Session()
    try:
        return session.query(Episode).filter_by(anime_code=anime_code).order_by(Episode.episode_number).all()
    finally:
        session.close()

def get_episode(anime_code: str, episode_num: int):
    session = Session()
    try:
        return session.query(Episode).filter_by(anime_code=anime_code, episode_number=episode_num).first()
    finally:
        session.close()

def delete_episode(episode_id: int):
    session = Session()
    try:
        episode = session.query(Episode).filter_by(id=episode_id).first()
        if episode:
            session.delete(episode)
            anime = session.query(Anime).filter_by(code=episode.anime_code).first()
            if anime:
                count = session.query(Episode).filter_by(anime_code=episode.anime_code).count()
                anime.total_episodes = count
            session.commit()
            return True
        return False
    except Exception as e:
        session.rollback()
        return False
    finally:
        session.close()

def get_stats():
    session = Session()
    try:
        admin_count = session.query(User).filter_by(is_admin=True).count()
        media_count = session.query(Media).count()
        episodes_count = session.query(Episode).count()
        users_count = session.query(User).count()
        return {
            'admins': admin_count,
            'media': media_count,
            'episodes': episodes_count,
            'users': users_count
        }
    finally:
        session.close()

# ================= HANDLERLAR =================
@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    add_user(user_id, message.from_user.username, message.from_user.full_name)
    
    # Rasm bilan salomlashish
    start_text = f"""🎬 <b>AniCity Rasmiy bot</b>

<b>Botimizga xush kelibsiz!</b>

<b>✨ Bot imkoniyatlari:</b>
• 📝 Kod orqali qidiruv
• 🎬 Anime va dramalarni nom bilan qidirish
• 🖼 Rasm orqali anime topish
• 📺 Barcha qismlarni tomosha qilish

<b>📢 Asosiy kanal:</b> <a href="{CHANNEL_LINK}">@AniCity_Rasmiy</a>
<b>👨‍💻 Muallif:</b> <a href="{AUTHOR_LINK}">@_2akk</a>
<b>🆘 Yordam:</b> <a href="{AUTHOR_LINK}">@_2akk</a>

👇 <b>Quyidagi tugmalardan birini tanlang:</b>"""

    # Rasmni yuborish (agar mavjud bo'lsa)
    try:
        # Anime.jpg rasmni yuborish
        photo = FSInputFile("Anime.jpg")
        await message.answer_photo(
            photo=photo,
            caption=start_text,
            parse_mode="HTML",
            reply_markup=get_main_keyboard()
        )
    except:
        # Rasm topilmasa faqat matn
        await message.answer(
            start_text,
            parse_mode="HTML",
            reply_markup=get_main_keyboard()
        )

@dp.message(F.text == "📝 Kod orqali qidiruv")
async def search_by_code(message: Message, state: FSMContext):
    await message.answer(
        "🔍 Qidirilishi kerak bo'lgan anime yoki drama kodini yuboring",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="🔙 Orqaga")]],
            resize_keyboard=True
        )
    )
    await state.set_state(SearchState.waiting_for_anime_code)

@dp.message(SearchState.waiting_for_anime_code)
async def process_code_search(message: Message, state: FSMContext):
    if message.text == "🔙 Orqaga":
        await state.clear()
        await cmd_start(message)
        return
    
    code = message.text.strip()
    anime = get_anime_by_code(code)
    
    if anime:
        await show_anime_details(message, anime)
    else:
        await message.answer(
            "❌ Bunday kodli anime topilmadi!\nIltimos, to'g'ri kod yuboring yoki 🔙 Orqaga bosing.",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="🔙 Orqaga")]],
                resize_keyboard=True
            )
        )

@dp.message(F.text == "🎬 Anime Qidiruv")
async def search_anime(message: Message, state: FSMContext):
    await message.answer(
        "🔍 Qidirilishi kerak bo'lgan anime nomini yuboring",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="🔙 Orqaga")]],
            resize_keyboard=True
        )
    )
    await state.set_state(SearchState.waiting_for_anime_name)

@dp.message(SearchState.waiting_for_anime_name)
async def process_anime_search(message: Message, state: FSMContext):
    if message.text == "🔙 Orqaga":
        await state.clear()
        await cmd_start(message)
        return
    
    name = message.text.strip()
    animes = search_anime_by_name(name)
    
    if animes:
        if len(animes) == 1:
            await show_anime_details(message, animes[0])
        else:
            text = "🔍 Topilgan animelar:\n\n"
            for anime in animes:
                text += f"📺 <b>{anime.name}</b>\n🔢 Kod: <code>{anime.code}</code>\n\n"
            await message.answer(text, parse_mode="HTML", reply_markup=get_back_button())
    else:
        await message.answer(
            "❌ Bunday nomli anime topilmadi!\nIltimos, boshqa nom yuboring.",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="🔙 Orqaga")]],
                resize_keyboard=True
            )
        )

@dp.message(F.text == "🎭 Drama Qidiruv")
async def search_drama(message: Message, state: FSMContext):
    await message.answer(
        "🔍 Qidirilishi kerak bo'lgan drama nomini yuboring",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="🔙 Orqaga")]],
            resize_keyboard=True
        )
    )
    await state.set_state(SearchState.waiting_for_drama_name)

@dp.message(SearchState.waiting_for_drama_name)
async def process_drama_search(message: Message, state: FSMContext):
    if message.text == "🔙 Orqaga":
        await state.clear()
        await cmd_start(message)
        return
    
    name = message.text.strip()
    # Drama ham anime jadvalida saqlanadi, farqlash uchun janr yoki maxsus field qo'shilishi mumkin
    dramas = search_anime_by_name(name)
    
    if dramas:
        if len(dramas) == 1:
            await show_anime_details(message, dramas[0])
        else:
            text = "🔍 Topilgan dramalar:\n\n"
            for drama in dramas:
                text += f"🎭 <b>{drama.name}</b>\n🔢 Kod: <code>{drama.code}</code>\n\n"
            await message.answer(text, parse_mode="HTML", reply_markup=get_back_button())
    else:
        await message.answer(
            "❌ Bunday nomli drama topilmadi!\nIltimos, boshqa nom yuboring.",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="🔙 Orqaga")]],
                resize_keyboard=True
            )
        )

@dp.message(F.text == "🖼 Rasm Orqali Anime Qidiruv")
async def search_by_image(message: Message, state: FSMContext):
    text = """🖼 <b>RASM ORQALI ANIME QIDIRUV</b>

Qidirmoqchi bo'lgan animening rasmni yuboring.

📌 <b>QO'LLANMA:</b>
• Animening skrinshotini yuboring
• Anime posteri yoki banneri EMAS

Bot rasmni tahlil qilib, eng mos animeni topadi."""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📚 Qo'llanma", callback_data="guide")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_main")]
    ])
    
    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)
    await state.set_state(SearchState.waiting_for_anime_image)

@dp.message(SearchState.waiting_for_anime_image)
async def process_image_search(message: Message, state: FSMContext):
    if message.text and message.text == "🔙 Orqaga":
        await state.clear()
        await cmd_start(message)
        return
    
    if not message.photo:
        await message.answer("❌ Iltimos, rasm yuboring!")
        return
    
    # Rasm orqali anime qidirish uchun API kerak (masalan: trace.moe)
    # Bu yerda soddalashtirilgan versiya
    await message.answer("🔄 Rasm tahlil qilinmoqda...")
    
    # API call qilish kerak (trace.moe yoki boshqa)
    # Hozircha demo javob:
    await message.answer(
        "⚠️ Hozircha bu funksiya ishlab chiqilmoqda.\n"
        "Tez orada ishga tushadi!",
        reply_markup=get_back_button()
    )
    await state.clear()

@dp.message(F.text == "📓 Ro'yxat")
async def show_list(message: Message):
    animes = get_all_animes()
    
    if not animes:
        await message.answer("❌ Hozircha botda hech qanday anime yoki drama mavjud emas!")
        return
    
    # Fayl ko'rinishida chiqarish
    file_path = "anime_list.txt"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("📚 ANIME VA DRAMALAR RO'YXATI\n")
        f.write("=" * 50 + "\n\n")
        for anime in animes:
            f.write(f"📺 Nomi: {anime.name}\n")
            f.write(f"🔢 Kod: {anime.code}\n")
            f.write(f"🎬 Janr: {anime.janr or 'Noma\'lum'}\n")
            f.write(f"📀 Qismlar: {anime.total_episodes}\n")
            f.write(f"📊 Holati: {anime.status}\n")
            f.write("-" * 30 + "\n")
    
    document = FSInputFile(file_path)
    await message.answer_document(
        document=document,
        caption="📋 Botdagi barcha anime va dramalar ro'yxati",
        reply_markup=get_back_button()
    )
    
    # Faylni o'chirish
    os.remove(file_path)

@dp.message(F.text == "💸 Reklama")
async def show_advertising(message: Message):
    text = """📌 <b>Reklama va homiylik masalasida admin bilan bog'laning</b>

👨‍💻 <b>Muallif:</b> <a href="https://t.me/S_2ak">@s_2akk</a>"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨‍💻 Admin bilan bog'lanish", url="https://t.me/S_2ak")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_main")]
    ])
    
    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)

@dp.message(F.text == "👑 Admin Panel")
async def admin_panel(message: Message):
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        await message.answer("❌ Siz admin emassiz! Bu bo'lim faqat adminlar uchun.")
        return
    
    stats = get_stats()
    
    text = f"""<b>👑 Admin Panel</b>

👥 Adminlar: {stats['admins']}
🎬 Media: {stats['media']}
📀 Qismlar: {stats['episodes']}
👤 Foydalanuvchilar: {stats['users']}

<b>Quyidagi tugmalardan foydalaning:</b>"""

    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=get_admin_main_keyboard()
    )

@dp.message(F.text == "📊 Statistika")
async def show_statistics(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Siz admin emassiz!")
        return
    
    stats = get_stats()
    
    text = f"""📊 <b>Bot Statistikasi</b>

👥 <b>Foydalanuvchilar:</b> {stats['users']}
👑 <b>Adminlar:</b> {stats['admins']}
🎬 <b>Media fayllar:</b> {stats['media']}
📀 <b>Qismlar:</b> {stats['episodes']}
🎭 <b>Animelar:</b> {len(get_all_animes())}

📅 <b>Sana:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}"""

    await message.answer(text, parse_mode="HTML")

@dp.message(F.text == "➕ Media Qo'shish")
async def add_media_menu(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("Media qo'shish bo'limi:", reply_markup=get_media_add_keyboard())

@dp.message(F.text == "🎬 Ko'p Qism Qo'shish")
async def add_multiple_episodes(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    await message.answer(
        "📝 Qaysi animega qism qo'shmoqchisiz?\nAnime nomi yoki kodini kiriting:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="🔙 Asosiy menyu")]],
            resize_keyboard=True
        )
    )
    await state.set_state(AdminState.waiting_for_multiple_episodes)

@dp.message(AdminState.waiting_for_multiple_episodes)
async def process_multiple_episodes_anime(message: Message, state: FSMContext):
    if message.text == "🔙 Asosiy menyu":
        await state.clear()
        await admin_panel(message)
        return
    
    search_term = message.text.strip()
    anime = get_anime_by_code(search_term) or get_anime_by_name(search_term)
    
    if not anime:
        await message.answer("❌ Anime topilmadi! Qaytadan kiriting yoki asosiy menyuga qayting.")
        return
    
    await state.update_data(anime_code=anime.code)
    await message.answer(
        f"✅ Anime: {anime.name}\n\n"
        f"📀 Qism video fayllarni yuboring (video fayllar ketma-ket yuboriladi)\n"
        f"1-qismdan boshlab yuboring.\n\n"
        f"✅ Barcha qismlarni yuborganingizdan so'ng /done buyrug'ini yuboring."
    )
    await state.set_state(AdminState.waiting_for_episode_video)

@dp.message(AdminState.waiting_for_episode_video)
async def process_episode_video(message: Message, state: FSMContext):
    if message.text == "/done":
        data = await state.get_data()
        count = data.get('episode_count', 0)
        await message.answer(f"✅ Jami {count} ta qism qo'shildi!")
        await state.clear()
        await admin_panel(message)
        return
    
    if not message.video:
        await message.answer("❌ Iltimos, video fayl yuboring yoki /done bilan tugating.")
        return
    
    data = await state.get_data()
    anime_code = data.get('anime_code')
    episode_count = data.get('episode_count', 0) + 1
    
    # Videoni kanalga yuborish
    try:
        sent = await bot.send_video(
            chat_id=BASE_CHANNEL_ID,
            video=message.video.file_id,
            caption=f"{anime_code} - {episode_count}-qism"
        )
        
        # Ma'lumotlar bazasiga saqlash
        add_episode(anime_code, episode_count, file_id=sent.video.file_id)
        
        await state.update_data(episode_count=episode_count)
        await message.answer(f"✅ {episode_count}-qism qo'shildi! Keyingi qismni yuboring yoki /done")
        
    except Exception as e:
        await message.answer(f"❌ Xatolik: {str(e)}")

@dp.message(F.text == "📀 Qism Qo'shish")
async def add_single_episode(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    await message.answer(
        "📝 Qaysi animega qism qo'shmoqchisiz?\nAnime nomi yoki kodini kiriting:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="🔙 Asosiy menyu")]],
            resize_keyboard=True
        )
    )
    await state.set_state(AdminState.waiting_for_anime_name_or_code)

@dp.message(AdminState.waiting_for_anime_name_or_code)
async def process_episode_anime(message: Message, state: FSMContext):
    if message.text == "🔙 Asosiy menyu":
        await state.clear()
        await admin_panel(message)
        return
    
    search_term = message.text.strip()
    anime = get_anime_by_code(search_term) or get_anime_by_name(search_term)
    
    if not anime:
        await message.answer("❌ Anime topilmadi!")
        return
    
    await state.update_data(anime_code=anime.code, anime_name=anime.name)
    await message.answer(f"✅ Anime: {anime.name}\n\n📀 Qism raqamini kiriting:")
    await state.set_state(AdminState.waiting_for_episode_number)

@dp.message(AdminState.waiting_for_episode_number)
async def process_episode_number(message: Message, state: FSMContext):
    try:
        episode_num = int(message.text.strip())
        await state.update_data(episode_num=episode_num)
        await message.answer(f"📀 {episode_num}-qism video faylini yuboring:")
        await state.set_state(AdminState.waiting_for_new_media)
    except ValueError:
        await message.answer("❌ Iltimos, to'g'ri qism raqamini kiriting!")

@dp.message(AdminState.waiting_for_new_media)
async def process_new_episode_video(message: Message, state: FSMContext):
    if not message.video:
        await message.answer("❌ Iltimos, video fayl yuboring!")
        return
    
    data = await state.get_data()
    anime_code = data.get('anime_code')
    episode_num = data.get('episode_num')
    
    try:
        sent = await bot.send_video(
            chat_id=BASE_CHANNEL_ID,
            video=message.video.file_id,
            caption=f"{anime_code} - {episode_num}-qism"
        )
        
        add_episode(anime_code, episode_num, file_id=sent.video.file_id)
        await message.answer(f"✅ {episode_num}-qism muvaffaqiyatli qo'shildi!")
        await state.clear()
        await admin_panel(message)
        
    except Exception as e:
        await message.answer(f"❌ Xatolik: {str(e)}")

@dp.message(F.text == "✏️ Media Tahrirlash")
async def edit_media(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    await message.answer(
        "📝 Qaysi animeni tahrirlamoqchisiz?\nAnime kodini kiriting:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="🔙 Asosiy menyu")]],
            resize_keyboard=True
        )
    )
    await state.set_state(AdminState.waiting_for_edit_anime_code)

@dp.message(AdminState.waiting_for_edit_anime_code)
async def process_edit_anime_code(message: Message, state: FSMContext):
    if message.text == "🔙 Asosiy menyu":
        await state.clear()
        await admin_panel(message)
        return
    
    code = message.text.strip()
    anime = get_anime_by_code(code)
    
    if not anime:
        await message.answer("❌ Bunday kodli anime topilmadi!")
        return
    
    await state.update_data(anime_code=code)
    
    text = f"""📺 <b>{anime.name}</b>

🔢 Kod: {anime.code}
🎬 Janr: {anime.janr or '❌'}
📀 Sezon: {anime.season}
📊 Holati: {anime.status}
🎚 Sifat: {anime.quality}
📀 Qismlar: {anime.total_episodes}

<b>Qaysi ma'lumotni tahrirlamoqchisiz?</b>"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Nomi", callback_data="edit_name")],
        [InlineKeyboardButton(text="🎬 Janr", callback_data="edit_janr")],
        [InlineKeyboardButton(text="📊 Holati", callback_data="edit_status")],
        [InlineKeyboardButton(text="🎚 Sifat", callback_data="edit_quality")],
        [InlineKeyboardButton(text="🔙 Asosiy menyu", callback_data="back_to_admin")]
    ])
    
    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)
    await state.set_state(AdminState.waiting_for_edit_field)

@dp.callback_query(lambda c: c.data.startswith("edit_"))
async def process_edit_field(callback: CallbackQuery, state: FSMContext):
    field = callback.data.replace("edit_", "")
    field_names = {
        "name": "yangi nom",
        "janr": "yangi janr",
        "status": "yangi holat (Tugallangan/Davom etmoqda)",
        "quality": "yangi sifat (720p/1080p)"
    }
    
    await state.update_data(edit_field=field)
    await callback.message.answer(f"✏️ {field_names.get(field, field)}ni kiriting:")
    await callback.answer()
    await state.set_state(AdminState.waiting_for_edit_value)

@dp.message(AdminState.waiting_for_edit_value)
async def process_edit_value(message: Message, state: FSMContext):
    data = await state.get_data()
    anime_code = data.get('anime_code')
    field = data.get('edit_field')
    new_value = message.text.strip()
    
    session = Session()
    try:
        anime = session.query(Anime).filter_by(code=anime_code).first()
        if anime:
            setattr(anime, field, new_value)
            session.commit()
            await message.answer(f"✅ {field} muvaffaqiyatli o'zgartirildi: {new_value}")
        else:
            await message.answer("❌ Anime topilmadi!")
    except Exception as e:
        session.rollback()
        await message.answer(f"❌ Xatolik: {str(e)}")
    finally:
        session.close()
    
    await state.clear()
    await admin_panel(message)

@dp.message(F.text == "📨 Xabar Yuborish")
async def broadcast_message(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    await message.answer(
        "📨 Barcha foydalanuvchilarga yuboriladigan xabarni kiriting:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="🔙 Asosiy menyu")]],
            resize_keyboard=True
        )
    )
    await state.set_state(AdminState.waiting_for_post_message)

@dp.message(AdminState.waiting_for_post_message)
async def process_broadcast(message: Message, state: FSMContext):
    if message.text == "🔙 Asosiy menyu":
        await state.clear()
        await admin_panel(message)
        return
    
    await state.update_data(broadcast_text=message.text)
    await message.answer("📢 Xabar yuborilsinmi? (Ha/Yo'q)")
    await state.set_state(AdminState.waiting_for_post_channel)

@dp.message(AdminState.waiting_for_post_channel)
async def confirm_broadcast(message: Message, state: FSMContext):
    if message.text.lower() == "ha":
        data = await state.get_data()
        broadcast_text = data.get('broadcast_text')
        
        session = Session()
        try:
            users = session.query(User).all()
            success = 0
            fail = 0
            
            await message.answer(f"📨 Xabar {len(users)} ta foydalanuvchiga yuborilmoqda...")
            
            for user in users:
                try:
                    await bot.send_message(user.user_id, broadcast_text)
                    success += 1
                    await asyncio.sleep(0.05)
                except:
                    fail += 1
            
            await message.answer(f"✅ Xabar yuborildi!\n✅ Muvaffaqiyatli: {success}\n❌ Muvaffaqiyatsiz: {fail}")
        finally:
            session.close()
    else:
        await message.answer("❌ Xabar yuborish bekor qilindi!")
    
    await state.clear()
    await admin_panel(message)

@dp.message(F.text == "👥 Admin Qo'shish")
async def add_admin(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if not is_owner(user_id):
        await message.answer("❌ Bu funksiya faqat bot egasi uchun!")
        return
    
    await message.answer(
        "👤 Admin qilmoqchi bo'lgan foydalanuvchining ID sini kiriting:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="🔙 Asosiy menyu")]],
            resize_keyboard=True
        )
    )
    await state.set_state(AdminState.waiting_for_add_admin_id)

@dp.message(AdminState.waiting_for_add_admin_id)
async def process_add_admin(message: Message, state: FSMContext):
    if message.text == "🔙 Asosiy menyu":
        await state.clear()
        await admin_panel(message)
        return
    
    try:
        admin_id = int(message.text.strip())
        
        session = Session()
        try:
            user = session.query(User).filter_by(user_id=admin_id).first()
            if user:
                user.is_admin = True
                session.commit()
                await message.answer(f"✅ Foydalanuvchi {admin_id} admin qilindi!")
            else:
                new_admin = User(
                    user_id=admin_id,
                    is_admin=True,
                    is_owner=False
                )
                session.add(new_admin)
                session.commit()
                await message.answer(f"✅ Yangi foydalanuvchi {admin_id} admin qilindi!")
        finally:
            session.close()
    except ValueError:
        await message.answer("❌ Noto'g'ri ID formati!")
    
    await state.clear()
    await admin_panel(message)

@dp.message(F.text == "📢 Post Qilish")
async def post_to_channel(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎬 Anime post qilish", callback_data="post_anime")],
        [InlineKeyboardButton(text="📀 Qism post qilish", callback_data="post_episode")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_admin")]
    ])
    
    await message.answer("📢 Nima post qilmoqchisiz?", reply_markup=keyboard)

@dp.callback_query(lambda c: c.data == "post_anime")
async def post_anime_select(callback: CallbackQuery, state: FSMContext):
    animes = get_all_animes()
    
    if not animes:
        await callback.message.answer("❌ Hozircha hech qanday anime mavjud emas!")
        await callback.answer()
        return
    
    text = "📺 Post qilmoqchi bo'lgan animeni tanlang:\n\n"
    for anime in animes:
        text += f"🔢 Kod: {anime.code} - {anime.name}\n"
    
    await callback.message.answer(text)
    await callback.message.answer("Anime kodini kiriting:")
    await callback.answer()
    await state.set_state(AdminState.waiting_for_anime_to_post)

@dp.message(AdminState.waiting_for_anime_to_post)
async def process_anime_post(message: Message, state: FSMContext):
    code = message.text.strip()
    anime = get_anime_by_code(code)
    
    if not anime:
        await message.answer("❌ Bunday kodli anime topilmadi!")
        return
    
    # Post matnini tayyorlash
    post_text = f"""┌─────────────────────────────────
🎬 {anime.name}
└─────────────────────────────────

┌─────────────────────────────────
• Janr: {anime.janr or 'Noma\'lum'}
• Sezon: {anime.season}
• Qism: {anime.total_episodes}
• Holati: ✅ {anime.status}
• Ovoz: {anime.dublyaj}
• Himoy: Nuqtacha
• Sifat: {anime.quality}
└─────────────────────────────────

🔢 Kod: {anime.code}
📢 Kanal: @AniCity_Rasmiy"""

    # Kanal username ni so'rash
    await message.answer("📢 Post qilmoqchi bo'lgan kanal usernameini kiriting (masalan: @MyChannel):")
    await state.update_data(post_anime_code=code, post_text=post_text)
    await state.set_state(AdminState.waiting_for_post_channel)

@dp.callback_query(lambda c: c.data == "post_episode")
async def post_episode_select(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Anime kodini kiriting:")
    await callback.answer()
    await state.set_state(AdminState.waiting_for_episode_to_post)

@dp.message(AdminState.waiting_for_episode_to_post)
async def process_episode_post_anime(message: Message, state: FSMContext):
    code = message.text.strip()
    anime = get_anime_by_code(code)
    
    if not anime:
        await message.answer("❌ Bunday kodli anime topilmadi!")
        return
    
    episodes = get_episodes(code)
    if not episodes:
        await message.answer("❌ Bu animeda hech qanday qism mavjud emas!")
        return
    
    await state.update_data(post_anime_code=code, anime_name=anime.name)
    
    text = f"📀 Qism raqamini kiriting (1-{len(episodes)}):"
    await message.answer(text)
    await state.set_state(AdminState.waiting_for_post_channel)

@dp.message(AdminState.waiting_for_post_channel)
async def process_channel_post(message: Message, state: FSMContext):
    data = await state.get_data()
    channel = message.text.strip()
    
    if not channel.startswith("@"):
        channel = "@" + channel
    
    post_text = data.get('post_text')
    anime_code = data.get('post_anime_code')
    anime_name = data.get('anime_name')
    
    if post_text:  # Anime post
        try:
            await bot.send_message(
                chat_id=channel,
                text=post_text,
                parse_mode="HTML"
            )
            await message.answer(f"✅ Post {channel} ga yuborildi!")
        except Exception as e:
            await message.answer(f"❌ Xatolik: {str(e)}")
    else:  # Episode post
        try:
            episode_num = int(message.text.strip())
            episode = get_episode(anime_code, episode_num)
            
            if not episode:
                await message.answer("❌ Bunday qism topilmadi!")
                return
            
            episode_text = f"""┌─────────────────────────────────
🎬 {anime_name}
└─────────────────────────────────

┌─────────────────────────────────
• {episode_num}-qism
• Anime KODI: {anime_code}
└─────────────────────────────────

📢 Kanal: @AniCity_Rasmiy"""
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="▶️ Tomosha qilish", url=f"https://t.me/{BOT_USERNAME}?start=ep_{anime_code}_{episode_num}")]
            ])
            
            await bot.send_message(
                chat_id=channel,
                text=episode_text,
                parse_mode="HTML",
                reply_markup=keyboard
            )
            await message.answer(f"✅ {episode_num}-qism posti {channel} ga yuborildi!")
        except ValueError:
            await message.answer("❌ Noto'g'ri qism raqami!")
        except Exception as e:
            await message.answer(f"❌ Xatolik: {str(e)}")
    
    await state.clear()
    await admin_panel(message)

@dp.message(F.text == "🔙 Asosiy menyu")
async def back_to_main_menu(message: Message):
    await cmd_start(message)

@dp.callback_query(lambda c: c.data == "back_to_main")
async def back_to_main_callback(callback: CallbackQuery):
    await callback.message.delete()
    await cmd_start(callback.message)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "back_to_admin")
async def back_to_admin_callback(callback: CallbackQuery):
    await callback.message.delete()
    await admin_panel(callback.message)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "guide")
async def show_guide(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    text = f"""📚 <b>Botni ishlatish bo'yicha qo'llanma:</b>

🔍 <b>Kod orqali qidiruv</b> - Anime kodini yuborib topish
🎬 <b>Anime Qidirish</b> - Botda mavjud bo'lgan animelarni qidirish
🎭 <b>Drama Qidirish</b> - Botda mavjud bo'lgan dramalarni qidirish
🖼 <b>Rasm Orqali Anime Qidiruv</b> - Nomini topa olmayotgan animeingizni rasm orqali topish
💸 <b>Reklama</b> - bot adminlari bilan reklama yoki homiylik yuzasidan aloqaga chiqish
📓 <b>Ro'yxat</b> - Botga joylangan Anime va Dramalar ro'yxati

👨‍💻 <b>Muallif:</b> @s_2akk
🆘 <b>Yordam:</b> @s_2akk

🆔 <b>Botdagi ID ingiz:</b> <code>{user_id}</code>"""
    
    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("watch_anime_"))
async def watch_anime(callback: CallbackQuery):
    anime_code = callback.data.replace("watch_anime_", "")
    anime = get_anime_by_code(anime_code)
    
    if not anime:
        await callback.answer("Anime topilmadi!")
        return
    
    episodes = get_episodes(anime_code)
    
    if not episodes:
        await callback.answer("Hozircha qismlar mavjud emas!")
        return
    
    # Qismlar ro'yxatini ko'rsatish
    text = f"🎬 {anime.name}\n\n📀 Qismlar:\n"
    keyboard = InlineKeyboardBuilder()
    
    for ep in episodes[:20]:  # 20 tagacha qism
        keyboard.button(text=f"{ep.episode_number}-qism", callback_data=f"watch_ep_{anime_code}_{ep.episode_number}")
    
    keyboard.adjust(5)
    keyboard.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_main"))
    
    await callback.message.answer(text, reply_markup=keyboard.as_markup())
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("watch_ep_"))
async def watch_episode(callback: CallbackQuery):
    parts = callback.data.split("_")
    anime_code = parts[2]
    episode_num = int(parts[3])
    
    episode = get_episode(anime_code, episode_num)
    anime = get_anime_by_code(anime_code)
    
    if not episode or not anime:
        await callback.answer("Qism topilmadi!")
        return
    
    text = f"""🎬 <b>{anime.name}</b>

┌─────────────────────────────────
• {episode_num}-qism
• Anime KODI: {anime_code}
└─────────────────────────────────

📢 Kanal: @AniCity_Rasmiy"""
    
    try:
        if episode.file_id:
            await callback.message.answer_video(
                video=episode.file_id,
                caption=text,
                parse_mode="HTML"
            )
        elif episode.video_url:
            await callback.message.answer_video(
                video=episode.video_url,
                caption=text,
                parse_mode="HTML"
            )
        else:
            await callback.message.answer("❌ Video topilmadi!")
    except Exception as e:
        await callback.message.answer(f"❌ Xatolik: {str(e)}")
    
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("back_to_anime_"))
async def back_to_anime(callback: CallbackQuery):
    anime_code = callback.data.replace("back_to_anime_", "")
    await watch_anime(callback)

# ================= ANIME MA'LUMOTLARINI KO'RSATISH =================
async def show_anime_details(message: Message, anime):
    episodes = get_episodes(anime.code)
    
    text = f"""┌─────────────────────────────────
🎬 <b>{anime.name}</b>
└─────────────────────────────────

┌─────────────────────────────────
• Janr: {anime.janr or 'Noma\'lum'}
• Sezon: {anime.season}
• Qism: {anime.total_episodes}
• Holati: ✅ {anime.status}
• Ovoz: {anime.dublyaj}
• Himoy: Nuqtacha
• Sifat: {anime.quality}
└─────────────────────────────────

🔢 Kod: {anime.code}
📢 Kanal: @AniCity_Rasmiy"""
    
    keyboard = get_anime_actions_keyboard(anime.code)
    
    if anime.image_url:
        try:
            await message.answer_photo(
                photo=anime.image_url,
                caption=text,
                parse_mode="HTML",
                reply_markup=keyboard
            )
        except:
            await message.answer(text, parse_mode="HTML", reply_markup=keyboard)
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=keyboard)

# ================= BOTNI ISHGA TUSHIRISH =================
async def main():
    print("Bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
