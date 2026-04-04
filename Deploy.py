#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ================================================================
# BOT DEPLOY BOT - AIOGRAM VERSIYA
# Version: 5.0
# Sana: 2026-04-04
# ================================================================
# AIOGRAM BILAN ISHLAYDI - KOPCHILIK BOTLAR SHUNI ISHLATADI
# ================================================================

import asyncio
import os
import sys
import re
import json
import shutil
import time
import random
import subprocess
import threading
import tempfile
import traceback
import hashlib
import sqlite3
import logging
import signal
import socket
import platform
from datetime import datetime, date, timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Dict, List, Tuple, Any

from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ================================================================
# KONFIGURATSIYA
# ================================================================

BOT_TOKEN = "8620689920:AAFq5br1REfWg499X51Lezq8_PXznbvo9rI"
OWNER_ID = 5675087151

DEPLOY_DIR = "deployed_bots"
LOGS_DIR = "bot_logs"
TEMPLATES_DIR = "templates"
MAX_FILE_SIZE = 5 * 1024 * 1024
MIN_FILE_SIZE = 50
PROCESS_CHECK_INTERVAL = 30
AUTO_RESTART = True
AUTO_RESTART_DELAY = 10
MAX_RESTART_ATTEMPTS = 5
PYTHON_CMD = sys.executable
MAX_LOG_LINES = 1000

ALLOWED_EXTENSIONS = {'.py'}
BLOCKED_PATTERNS = [
    r'os\.system\s*\(\s*[\'"]rm\s+-rf',
    r'os\.system\s*\(\s*[\'"]rm\s+-r\s+/',
    r'os\.remove\s*\([\'"]/',
    r'shutil\.rmtree\s*\([\'"]/',
    r'eval\s*\(\s*input',
    r'__import__\s*\(\s*[\'"]os[\'"]\s*\)\.system',
]

LOG_FORMAT = '%(asctime)s | %(levelname)-8s | %(message)s'
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler('deploy_bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
log = logging.getLogger('DeployBot')

BOT_STATUS_RUNNING = "running"
BOT_STATUS_STOPPED = "stopped"
BOT_STATUS_FAILED = "failed"
BOT_STATUS_STARTING = "starting"

# FSM States
class DeployStates(StatesGroup):
    waiting_for_file = State()
    waiting_for_token = State()

# Emojilar
EMOJI_ROCKET = "🚀"
EMOJI_CHECK = "✅"
EMOJI_CROSS = "❌"
EMOJI_WARNING = "⚠️"
EMOJI_FILE = "📁"
EMOJI_KEY = "🔑"
EMOJI_BOT = "🤖"
EMOJI_GREEN = "🟢"
EMOJI_RED = "🔴"
EMOJI_WHITE = "⚪"
EMOJI_CLOCK = "⏱"
EMOJI_CHART = "📊"
EMOJI_LIST = "📋"
EMOJI_RESTART = "🔄"
EMOJI_STOP = "🛑"
EMOJI_TRASH = "🗑"
EMOJI_BACK = "🔙"
EMOJI_STAR = "⭐"
EMOJI_QUESTION = "❓"
EMOJI_PEN = "📝"
EMOJI_HOURGLASS = "⏳"
EMOJI_BOX = "📦"
EMOJI_PAGE = "📄"
EMOJI_SIZE = "💾"
EMOJI_TOOL = "🔧"
EMOJI_ARROW = "➡️"
EMOJI_PLAY = "▶️"
EMOJI_INFO = "ℹ️"
EMOJI_LOCK = "⛔"
EMOJI_MESSAGE = "💬"

YES_TEXT = "✅ Bor"
NO_TEXT = "❌ Yo'q"
UNKNOWN_TEXT = "Noma'lum"
NA_TEXT = "N/A"


# ================================================================
# YORDAMCHI FUNKSIYALAR
# ================================================================

def format_uptime(seconds):
    if seconds is None or seconds < 0:
        return NA_TEXT
    days = int(seconds // 86400)
    hours = int((seconds % 86400) // 3600)
    minutes = int((seconds % 3600) // 60)
    parts = []
    if days > 0:
        parts.append(f"{days}kun")
    if hours > 0:
        parts.append(f"{hours}soat")
    if minutes > 0:
        parts.append(f"{minutes}daq")
    return " ".join(parts) if parts else "0daq"


def format_size(size_bytes):
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.2f} MB"


def safe_filename(filename):
    if not filename:
        return "bot.py"
    safe = re.sub(r'[<>:"/\\|?*]', '_', filename)
    safe = safe.strip('. ')
    if not safe.endswith('.py'):
        safe += '.py'
    return safe or "bot.py"


def generate_id(prefix="dep", length=10):
    raw = str(time.time()) + str(random.random()) + str(os.getpid())
    hashed = hashlib.md5(raw.encode()).hexdigest()
    return f"{prefix}_{hashed[:length]}"


def get_system_info():
    return {
        'platform': platform.system(),
        'platform_release': platform.release(),
        'python_version': platform.python_version(),
        'architecture': platform.machine(),
        'hostname': socket.gethostname(),
    }


def truncate_text(text, max_length=4096):
    if len(text) <= max_length:
        return text
    return text[:max_length - 20] + "\n\n... [davomi kesilgan]"


# ================================================================
# MA'LUMOTLAR BAZASI
# ================================================================

class Database:
    def __init__(self, db_path='deploy_bots.db'):
        self.db_path = db_path
        self.conn = None
        self._lock = threading.Lock()
        self._connect()
        self._create_tables()

    def _connect(self):
        try:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=15)
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA journal_mode=WAL")
            log.info(f"Bazaga ulandi: {self.db_path}")
        except Exception as e:
            log.error(f"Bazaga ulanishda xatolik: {e}")
            raise

    def _create_tables(self):
        tables_sql = """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            username TEXT DEFAULT '',
            first_name TEXT DEFAULT '',
            bot_count INTEGER DEFAULT 0,
            total_deploys INTEGER DEFAULT 0,
            successful_deploys INTEGER DEFAULT 0,
            failed_deploys INTEGER DEFAULT 0,
            registered_at TEXT NOT NULL,
            last_active TEXT,
            is_banned INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS deployments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            deploy_id TEXT UNIQUE NOT NULL,
            user_id INTEGER NOT NULL,
            bot_token TEXT NOT NULL,
            bot_username TEXT DEFAULT '',
            bot_name TEXT DEFAULT '',
            main_file TEXT NOT NULL,
            original_filename TEXT DEFAULT '',
            file_hash TEXT DEFAULT '',
            file_size INTEGER DEFAULT 0,
            code_dir TEXT DEFAULT '',
            framework TEXT DEFAULT '',
            has_requirements INTEGER DEFAULT 0,
            requirements_installed INTEGER DEFAULT 0,
            requirements_list TEXT DEFAULT '',
            status TEXT DEFAULT 'created',
            pid INTEGER DEFAULT NULL,
            started_at TEXT,
            stopped_at TEXT,
            last_restart TEXT,
            restart_count INTEGER DEFAULT 0,
            error_message TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS bot_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            deploy_id TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS daily_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT UNIQUE NOT NULL,
            total_deploys INTEGER DEFAULT 0,
            successful INTEGER DEFAULT 0,
            failed INTEGER DEFAULT 0,
            new_users INTEGER DEFAULT 0,
            total_restarts INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS user_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT DEFAULT '',
            message_text TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TEXT NOT NULL,
            replied_at TEXT
        );
        """
        with self._lock:
            try:
                self.conn.executescript(tables_sql)
                log.info("Jadvallar tayyor")
            except Exception as e:
                log.error(f"Jadvallar yaratishda xatolik: {e}")
                raise

    def execute(self, query, params=()):
        with self._lock:
            try:
                cursor = self.conn.execute(query, params)
                self.conn.commit()
                return cursor
            except Exception as e:
                log.error(f"DB xatosi: {e}")
                return None

    def fetchone(self, query, params=()):
        with self._lock:
            try:
                return self.conn.execute(query, params).fetchone()
            except Exception as e:
                log.error(f"DB fetchone xatosi: {e}")
                return None

    def fetchall(self, query, params=()):
        with self._lock:
            try:
                return self.conn.execute(query, params).fetchall()
            except Exception as e:
                log.error(f"DB fetchall xatosi: {e}")
                return []

    def count(self, table, condition="1=1", params=()):
        row = self.fetchone(f"SELECT COUNT(*) FROM {table} WHERE {condition}", params)
        return row[0] if row else 0

    def get_user(self, user_id):
        return self.fetchone('SELECT * FROM users WHERE user_id=?', (user_id,))

    def is_user_banned(self, user_id):
        user = self.get_user(user_id)
        return bool(user and user['is_banned'])

    def register_user(self, user_id, username, first_name):
        existing = self.get_user(user_id)
        now = str(datetime.now())
        if existing:
            self.execute('UPDATE users SET username=?, first_name=?, last_active=? WHERE user_id=?',
                        (username or '', first_name or '', now, user_id))
            return existing
        self.execute('''INSERT INTO users (user_id, username, first_name, registered_at, last_active)
                        VALUES (?, ?, ?, ?, ?)''',
                     (user_id, username or '', first_name or '', now, now))
        today = str(date.today())
        stat = self.fetchone('SELECT id FROM daily_stats WHERE date=?', (today,))
        if stat:
            self.execute('UPDATE daily_stats SET new_users=new_users+1 WHERE date=?', (today,))
        else:
            self.execute('INSERT INTO daily_stats(date, new_users) VALUES (?, 1)', (today,))
        return self.get_user(user_id)

    def update_user_activity(self, user_id):
        self.execute('UPDATE users SET last_active=? WHERE user_id=?', (str(datetime.now()), user_id))

    def get_deploy(self, deploy_id):
        return self.fetchone('SELECT * FROM deployments WHERE deploy_id=?', (deploy_id,))

    def get_user_deploys(self, user_id, limit=50):
        return self.fetchall('SELECT * FROM deployments WHERE user_id=? ORDER BY created_at DESC LIMIT ?',
                             (user_id, limit))

    def get_all_deploys(self):
        return self.fetchall('SELECT * FROM deployments WHERE status IN (?, ?)',
                             (BOT_STATUS_RUNNING, BOT_STATUS_STARTING))

    def update_deploy_status(self, deploy_id, status, **kwargs):
        now = str(datetime.now())
        sets = ['status=?', 'updated_at=?']
        params = [status, now]
        for key, value in kwargs.items():
            if key in ('pid', 'error_message', 'restart_count', 'last_restart', 'started_at', 'stopped_at'):
                sets.append(f'{key}=?')
                params.append(value)
        params.append(deploy_id)
        self.execute(f"UPDATE deployments SET {', '.join(sets)} WHERE deploy_id=?", params)

    def delete_deploy(self, deploy_id):
        self.execute('DELETE FROM deployments WHERE deploy_id=?', (deploy_id,))
        self.execute('DELETE FROM bot_logs WHERE deploy_id=?', (deploy_id,))

    def get_stats_summary(self):
        total = self.count('deployments')
        running = self.count('deployments', 'status=?', (BOT_STATUS_RUNNING,))
        failed = self.count('deployments', 'status=?', (BOT_STATUS_FAILED,))
        users = self.count('users')
        today = str(date.today())
        today_stats = self.fetchone('SELECT * FROM daily_stats WHERE date=?', (today,))
        return {
            'total': total,
            'running': running,
            'stopped': total - running - failed,
            'failed': failed,
            'users': users,
            'today': dict(today_stats) if today_stats else {}
        }

    def close(self):
        try:
            if self.conn:
                self.conn.close()
        except:
            pass


# ================================================================
# FAYL HANDLER
# ================================================================

class FileHandler:
    def __init__(self):
        self.temp_dirs = []

    def validate_file(self, file_path):
        if not os.path.exists(file_path):
            return False, "Fayl topilmadi"
        file_size = os.path.getsize(file_path)
        if file_size > MAX_FILE_SIZE:
            return False, f"Fayl hajmi juda katta! Maksimal: {format_size(MAX_FILE_SIZE)}"
        if file_size < MIN_FILE_SIZE:
            return False, f"Fayl juda kichik (kamida {MIN_FILE_SIZE} bayt)"
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            return False, f"Faqat .py fayllar qabul qilinadi!"
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            if not content.strip():
                return False, "Fayl bo'sh!"
            for pattern in BLOCKED_PATTERNS:
                if re.search(pattern, content, re.IGNORECASE):
                    return False, "Xavfli kod aniqlandi!"
        except Exception as e:
            return False, f"Faylni o'qishda xato: {str(e)[:100]}"
        return True, "OK"

    def save_file(self, file_path, target_dir):
        try:
            safe_name = safe_filename(os.path.basename(file_path))
            target_path = os.path.join(target_dir, safe_name)
            os.makedirs(target_dir, exist_ok=True)
            shutil.copy2(file_path, target_path)
            return os.path.normpath(target_path)
        except Exception as e:
            log.error(f"Faylni saqlash xatosi: {e}")
            return None

    def get_file_hash(self, file_path):
        hasher = hashlib.sha256()
        try:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    hasher.update(chunk)
            return hasher.hexdigest()[:16]
        except:
            return ""

    def create_temp_dir(self, prefix='deploy_'):
        try:
            path = tempfile.mkdtemp(prefix=prefix)
            self.temp_dirs.append(path)
            return path
        except Exception as e:
            log.error(f"Temp papka yaratish xatosi: {e}")
            return None

    def cleanup(self, path):
        try:
            if path and os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
            elif path and os.path.isfile(path):
                os.remove(path)
        except:
            pass

    def cleanup_all(self):
        for path in self.temp_dirs:
            self.cleanup(path)
        self.temp_dirs.clear()


# ================================================================
# KOD TAHLILCHI (AIoGRAM UCHUN YANGILANDI)
# ================================================================

class CodeAnalyzer:
    def __init__(self):
        self.bot_frameworks = {
            'telebot': 'pyTelegramBotAPI',
            'aiogram': 'aiogram',
            'telegram.ext': 'python-telegram-bot',
        }
        self.token_patterns = [
            (r'BOT_TOKEN\s*=\s*["\']([^"\']+)["\']', 'BOT_TOKEN='),
            (r'bot_token\s*=\s*["\']([^"\']+)["\']', 'bot_token='),
            (r'TOKEN\s*=\s*["\']([^"\']+)["\']', 'TOKEN='),
            (r'API_TOKEN\s*=\s*["\']([^"\']+)["\']', 'API_TOKEN='),
        ]
        self.aiogram_patterns = [
            r'from\s+aiogram\s+import',
            r'import\s+aiogram',
            r'Dispatcher',
            r'Router',
            r'types\.Message',
            r'@.*\.message',
            r'@.*\.callback_query',
        ]

    def analyze_code(self, file_path):
        result = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'framework': UNKNOWN_TEXT,
            'has_token': False,
            'token_pattern': None,
            'has_requirements': False,
            'requirements': [],
            'imports': [],
            'line_count': 0,
            'file_size_kb': 0,
            'code_quality_score': 100,
            'is_aiogram': False,
        }
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception as e:
            result['valid'] = False
            result['errors'].append(f"Faylni o'qishda xato: {e}")
            return result

        file_size = os.path.getsize(file_path)
        result['file_size_kb'] = round(file_size / 1024, 2)
        result['line_count'] = content.count('\n') + 1

        # Framework aniqlash
        for key, name in self.bot_frameworks.items():
            if key in content:
                result['framework'] = name
                if key == 'aiogram':
                    result['is_aiogram'] = True
                break

        # Aiogram patternlarini tekshirish
        if not result['is_aiogram']:
            for pattern in self.aiogram_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    result['framework'] = 'aiogram'
                    result['is_aiogram'] = True
                    break

        # Importlarni topish
        import_matches = re.findall(r'^(?:from|import)\s+([\w.]+)', content, re.MULTILINE)
        result['imports'] = list(set(import_matches))

        # Tokenni topish
        for pattern, name in self.token_patterns:
            match = re.search(pattern, content)
            if match:
                result['has_token'] = True
                result['token_pattern'] = name
                break

        # Requirements.txt ni tekshirish
        req_path = os.path.join(os.path.dirname(file_path), 'requirements.txt')
        if os.path.exists(req_path):
            result['has_requirements'] = True
            try:
                with open(req_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            pkg = line.split('=')[0].split('>')[0].split('<')[0].strip()
                            if pkg:
                                result['requirements'].append(pkg)
            except:
                pass

        # Agar aiogram bo'lsa, requirements ga aiogram qo'shish
        if result['is_aiogram'] and 'aiogram' not in result['requirements']:
            result['requirements'].insert(0, 'aiogram')

        # Sintaksis tekshirish
        try:
            compile(content, file_path, 'exec')
        except SyntaxError as e:
            result['valid'] = False
            result['errors'].append(f"Sintaksis xato: {e.lineno}-qatorda")

        if not result['has_token']:
            result['warnings'].append("Token topilmadi")
            result['code_quality_score'] -= 20

        if result['line_count'] < 10:
            result['code_quality_score'] -= 15

        result['code_quality_score'] = max(0, min(100, result['code_quality_score']))
        return result

    def get_analysis_text(self, analysis):
        if not analysis['valid']:
            return f"{EMOJI_CROSS} KODDA XATOLIKLAR BOR!\n\n" + "\n".join(f"• {e}" for e in analysis['errors'][:3])

        framework_icon = "🤖" if analysis['is_aiogram'] else "📦"
        txt = f"{EMOJI_CHECK} KOD TAHLILI\n\n"
        txt += f"{framework_icon} Framework: {analysis['framework']}\n"
        txt += f"{EMOJI_SIZE} Qatorlar: {analysis['line_count']}\n"
        txt += f"{EMOJI_SIZE} Hajm: {analysis['file_size_kb']} KB\n"
        txt += f"{EMOJI_KEY} Token: {'Bor' if analysis['has_token'] else 'Yo'}"
        if analysis['token_pattern']:
            txt += f" ({analysis['token_pattern']})"
        txt += "\n"
        txt += f"{EMOJI_BOX} Requirements: {'Bor' if analysis['has_requirements'] else 'Yo'}"
        if analysis['requirements']:
            txt += f" ({len(analysis['requirements'])} ta)"
            if 'aiogram' in analysis['requirements']:
                txt += f" [{EMOJI_CHECK} aiogram]"
        txt += "\n"
        txt += f"{EMOJI_ARROW} Importlar: {len(analysis['imports'])} ta\n"
        txt += f"{EMOJI_STAR} Sifat baho: {analysis['code_quality_score']}/100\n"

        if analysis['warnings']:
            txt += f"\n{EMOJI_WARNING} Ogohlantirishlar:\n"
            for w in analysis['warnings'][:3]:
                txt += f"   • {w}\n"
        return txt

    def inject_token(self, file_path, token):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            patterns = [
                r'BOT_TOKEN\s*=\s*["\'][^"\']*["\']',
                r'bot_token\s*=\s*["\'][^"\']*["\']',
                r'TOKEN\s*=\s*["\'][^"\']*["\']',
                r'API_TOKEN\s*=\s*["\'][^"\']*["\']',
            ]

            replaced = False
            for pattern in patterns:
                new_content, count = re.subn(pattern, f'BOT_TOKEN = "{token}"', content, count=1)
                if count > 0:
                    content = new_content
                    replaced = True
                    break

            if not replaced:
                content = f'BOT_TOKEN = "{token}"\n\n' + content

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True, "Token kiritildi"
        except Exception as e:
            return False, f"Token kiritish xatosi: {e}"


# ================================================================
# PROSESS MANAGER
# ================================================================

class ProcessManager:
    def __init__(self):
        self.processes = {}
        self._executor = ThreadPoolExecutor(max_workers=10)
        self._running = True
        self._start_monitor()

    def _start_monitor(self):
        def monitor():
            while self._running:
                try:
                    for deploy_id, info in list(self.processes.items()):
                        proc = info.get('process')
                        if proc and proc.poll() is not None:
                            log.warning(f"Bot {deploy_id} to'xtadi (exit: {proc.returncode})")
                            if AUTO_RESTART and proc.returncode != 0:
                                rc = info.get('restart_count', 0)
                                if rc < MAX_RESTART_ATTEMPTS:
                                    log.info(f"Bot {deploy_id} qayta ishga tushirilmoqda...")
                                    time.sleep(AUTO_RESTART_DELAY)
                                    self.restart(deploy_id)
                                else:
                                    info['status'] = BOT_STATUS_FAILED
                            else:
                                info['status'] = BOT_STATUS_STOPPED
                    time.sleep(PROCESS_CHECK_INTERVAL)
                except Exception as e:
                    log.error(f"Monitor xatosi: {e}")
                    time.sleep(5)
        threading.Thread(target=monitor, daemon=True).start()

    def start_process(self, deploy_id, work_dir, main_file, token):
        if deploy_id in self.processes:
            self.stop(deploy_id, force=True)

        env = os.environ.copy()
        env['BOT_TOKEN'] = token
        env['PYTHONUNBUFFERED'] = '1'
        env['PYTHONIOENCODING'] = 'utf-8'
        env['PYTHONUTF8'] = '1'

        if not os.path.exists(main_file):
            log.error(f"Fayl topilmadi: {main_file}")
            return False, f"Asosiy fayl topilmadi: {main_file}"

        main_file = os.path.abspath(main_file)
        work_dir = os.path.abspath(work_dir)

        log.info(f"Bot ishga tushirilmoqda:")
        log.info(f"  Deploy ID: {deploy_id}")
        log.info(f"  Work dir: {work_dir}")
        log.info(f"  Main file: {main_file}")

        try:
            proc = subprocess.Popen(
                [PYTHON_CMD, main_file],
                cwd=work_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=env,
                text=True,
                bufsize=1,
                encoding='utf-8',
                errors='replace',
                shell=False
            )

            self.processes[deploy_id] = {
                'process': proc,
                'work_dir': work_dir,
                'main_file': main_file,
                'status': BOT_STATUS_RUNNING,
                'started_at': str(datetime.now()),
                'restart_count': 0,
                'logs': [],
                'token': token,
            }
            self._read_logs(deploy_id, proc)
            log.info(f"Bot {deploy_id} ishga tushdi (PID: {proc.pid})")
            return True, f"Bot ishga tushdi (PID: {proc.pid})"
        except Exception as e:
            log.error(f"Bot {deploy_id} ishga tushmadi: {e}")
            return False, f"Ishga tushmadi: {str(e)[:100]}"

    def _read_logs(self, deploy_id, proc):
        def reader():
            while True:
                try:
                    line = proc.stdout.readline()
                    if not line:
                        if proc.poll() is not None:
                            break
                        time.sleep(0.1)
                        continue
                    if deploy_id in self.processes:
                        line = line.rstrip('\n\r')
                        self.processes[deploy_id]['logs'].append(line)
                        short_line = line[:150] if len(line) > 150 else line
                        log.info(f"LOG {deploy_id}: {short_line}")
                        if len(self.processes[deploy_id]['logs']) > MAX_LOG_LINES:
                            self.processes[deploy_id]['logs'] = self.processes[deploy_id]['logs'][-MAX_LOG_LINES//2:]
                except Exception as e:
                    log.error(f"Log reader xatosi: {e}")
                    time.sleep(0.5)
        self._executor.submit(reader)

    def stop(self, deploy_id, force=False):
        if deploy_id not in self.processes:
            return False, "Bot topilmadi"
        info = self.processes[deploy_id]
        proc = info.get('process')
        if not proc or proc.poll() is not None:
            info['status'] = BOT_STATUS_STOPPED
            return True, "Bot to'xtagan"
        try:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        except Exception as e:
            if not force:
                return False, f"To'xtatishda xato: {e}"
        info['status'] = BOT_STATUS_STOPPED
        info['stopped_at'] = str(datetime.now())
        return True, "Bot to'xtatildi"

    def restart(self, deploy_id):
        if deploy_id not in self.processes:
            return False, "Bot topilmadi"
        info = self.processes[deploy_id]
        old_rc = info.get('restart_count', 0)
        self.stop(deploy_id, True)
        time.sleep(1)
        success, msg = self.start_process(deploy_id, info['work_dir'], info['main_file'], info['token'])
        if success and deploy_id in self.processes:
            self.processes[deploy_id]['restart_count'] = old_rc + 1
            self.processes[deploy_id]['last_restart'] = str(datetime.now())
        return success, msg

    def get_status(self, deploy_id):
        if deploy_id not in self.processes:
            return None
        info = self.processes[deploy_id]
        proc = info.get('process')
        is_running = proc and proc.poll() is None
        uptime = 0
        if is_running and info.get('started_at'):
            try:
                started = datetime.strptime(info['started_at'], '%Y-%m-%d %H:%M:%S.%f')
                uptime = int((datetime.now() - started).total_seconds())
            except:
                pass
        return {
            'status': BOT_STATUS_RUNNING if is_running else BOT_STATUS_STOPPED,
            'pid': proc.pid if proc else None,
            'uptime_seconds': uptime,
            'restart_count': info.get('restart_count', 0),
            'log_lines': len(info.get('logs', [])),
        }

    def get_logs(self, deploy_id, limit=50):
        if deploy_id not in self.processes:
            return []
        return self.processes[deploy_id].get('logs', [])[-limit:]

    def get_process_info(self, deploy_id):
        return self.processes.get(deploy_id)

    def restore_all_bots(self, db):
        deploys = db.get_all_deploys()
        log.info(f"Restoring {len(deploys)} bots from database...")
        
        restored = 0
        failed = 0
        
        for deploy in deploys:
            deploy_id = deploy['deploy_id']
            work_dir = deploy['code_dir']
            main_file = os.path.join(work_dir, deploy['main_file'])
            token = deploy['bot_token']
            
            if not os.path.exists(work_dir) or not os.path.exists(main_file):
                log.warning(f"Bot {deploy_id} fayllari topilmadi")
                db.update_deploy_status(deploy_id, BOT_STATUS_FAILED, error_message="Fayllar topilmadi")
                failed += 1
                continue
            
            success, msg = self.start_process(deploy_id, work_dir, main_file, token)
            if success:
                restored += 1
                log.info(f"Bot {deploy_id} qayta tiklandi")
            else:
                failed += 1
                log.error(f"Bot {deploy_id} qayta tiklanmadi: {msg}")
                db.update_deploy_status(deploy_id, BOT_STATUS_FAILED, error_message=msg)
            
            time.sleep(0.5)
        
        log.info(f"Restore complete: {restored} restored, {failed} failed")
        return restored, failed

    def stop_all(self):
        for deploy_id in list(self.processes.keys()):
            self.stop(deploy_id, True)
        self._running = False

    def cleanup(self, deploy_id):
        self.stop(deploy_id, True)
        if deploy_id in self.processes:
            work_dir = self.processes[deploy_id].get('work_dir')
            if work_dir and os.path.exists(work_dir):
                shutil.rmtree(work_dir, ignore_errors=True)
            del self.processes[deploy_id]

    @property
    def active_count(self):
        return sum(1 for info in self.processes.values()
                   if info.get('process') and info['process'].poll() is None)


# ================================================================
# TOKEN VALIDATOR (AIoGRAM UCHUN)
# ================================================================

class TokenValidator:
    def __init__(self):
        self._cache = {}
        self._lock = threading.Lock()

    async def validate(self, token):
        if not token or len(token) < 30:
            return False, "Token juda qisqa!", None
        with self._lock:
            if token in self._cache:
                cached = self._cache[token]
                if time.time() - cached['time'] < 300:
                    return cached['valid'], cached['message'], cached['info']
        try:
            bot = Bot(token=token)
            me = await bot.get_me()
            await bot.session.close()
            result = {'id': me.id, 'username': me.username, 'first_name': me.first_name}
            with self._lock:
                self._cache[token] = {'valid': True, 'message': f"@{me.username}", 'info': result, 'time': time.time()}
            return True, f"@{me.username}", result
        except Exception as e:
            msg = "Token noto'g'ri yoki eskirgan!" if 'Unauthorized' in str(e) else f"Xato: {str(e)[:50]}"
            with self._lock:
                self._cache[token] = {'valid': False, 'message': msg, 'info': None, 'time': time.time()}
            return False, msg, None

    async def get_bot_username(self, token):
        valid, msg, info = await self.validate(token)
        return info.get('username') if valid and info else None


# ================================================================
# DEPLOY ENGINE (ASYNCHRON)
# ================================================================

class DeployEngine:
    def __init__(self, db, pm, tv):
        self.db = db
        self.pm = pm
        self.tv = tv
        self.fh = FileHandler()
        self.ca = CodeAnalyzer()
        self.user_data = {}

    def generate_deploy_id(self):
        return generate_id("dep", 10)

    async def deploy(self, user_id, file_path, bot_token):
        deploy_id = self.generate_deploy_id()

        valid, msg = self.fh.validate_file(file_path)
        if not valid:
            return None, msg, None

        token_valid, token_msg, token_info = await self.tv.validate(bot_token)
        if not token_valid:
            return None, token_msg, None

        bot_username = token_info.get('username', '') if token_info else ''
        bot_name = token_info.get('first_name', '') if token_info else ''

        analysis = self.ca.analyze_code(file_path)
        if not analysis['valid']:
            return None, "Kodda xatoliklar bor", analysis

        deploy_dir = os.path.join(DEPLOY_DIR, deploy_id)
        os.makedirs(deploy_dir, exist_ok=True)

        saved_file = self.fh.save_file(file_path, deploy_dir)
        if not saved_file:
            self.fh.cleanup(deploy_dir)
            return None, "Faylni saqlashda xatolik", analysis

        self.ca.inject_token(saved_file, bot_token)

        req_installed = False
        if analysis['has_requirements'] and analysis['requirements']:
            try:
                result = subprocess.run([PYTHON_CMD, '-m', 'pip', 'install', '-q'] + analysis['requirements'],
                                        cwd=deploy_dir, capture_output=True, text=True, timeout=120)
                req_installed = result.returncode == 0
            except:
                pass

        now = str(datetime.now())
        file_hash = self.fh.get_file_hash(file_path)
        file_size = os.path.getsize(file_path)

        self.db.execute('''INSERT INTO deployments
            (deploy_id, user_id, bot_token, bot_username, bot_name,
             main_file, original_filename, file_hash, file_size,
             code_dir, framework, has_requirements, requirements_installed,
             status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (deploy_id, user_id, bot_token, bot_username, bot_name,
             os.path.basename(saved_file), os.path.basename(file_path),
             file_hash, file_size, deploy_dir,
             analysis['framework'], 1 if analysis['has_requirements'] else 0,
             1 if req_installed else 0, BOT_STATUS_STARTING, now, now))

        success, proc_msg = self.pm.start_process(deploy_id, deploy_dir, saved_file, bot_token)

        if success:
            pid = self.pm.processes[deploy_id]['process'].pid
            self.db.update_deploy_status(deploy_id, BOT_STATUS_RUNNING, pid=pid, started_at=now)
            self.db.execute('UPDATE users SET bot_count=bot_count+1, total_deploys=total_deploys+1, '
                            'successful_deploys=successful_deploys+1, last_active=? WHERE user_id=?', (now, user_id))
            return deploy_id, proc_msg, analysis
        else:
            self.db.update_deploy_status(deploy_id, BOT_STATUS_FAILED, error_message=proc_msg)
            self.db.execute('UPDATE users SET total_deploys=total_deploys+1, failed_deploys=failed_deploys+1, '
                            'last_active=? WHERE user_id=?', (now, user_id))
            return None, proc_msg, analysis

    async def stop_bot(self, deploy_id, user_id):
        deploy = self.db.get_deploy(deploy_id)
        if not deploy or (deploy['user_id'] != user_id and user_id != OWNER_ID):
            return False, "Bot topilmadi yoki sizga tegishli emas"
        success, msg = self.pm.stop(deploy_id)
        if success:
            self.db.update_deploy_status(deploy_id, BOT_STATUS_STOPPED, stopped_at=str(datetime.now()))
        return success, msg

    async def restart_bot(self, deploy_id, user_id):
        deploy = self.db.get_deploy(deploy_id)
        if not deploy or (deploy['user_id'] != user_id and user_id != OWNER_ID):
            return False, "Bot topilmadi"
        proc_info = self.pm.get_process_info(deploy_id)
        if not proc_info:
            return False, "Bot jarayoni topilmadi"
        success, msg = self.pm.restart(deploy_id)
        if success:
            now = str(datetime.now())
            new_count = proc_info.get('restart_count', 0) + 1
            self.db.update_deploy_status(deploy_id, BOT_STATUS_RUNNING, restart_count=new_count, last_restart=now)
        return success, msg

    async def start_bot(self, deploy_id, user_id):
        deploy = self.db.get_deploy(deploy_id)
        if not deploy or (deploy['user_id'] != user_id and user_id != OWNER_ID):
            return False, "Bot topilmadi"
        work_dir = deploy['code_dir']
        main_file = os.path.join(work_dir, deploy['main_file'])
        token = deploy['bot_token']
        if not os.path.exists(main_file):
            return False, "Asosiy fayl topilmadi"
        success, msg = self.pm.start_process(deploy_id, work_dir, main_file, token)
        if success:
            now = str(datetime.now())
            pid = self.pm.processes[deploy_id]['process'].pid
            self.db.update_deploy_status(deploy_id, BOT_STATUS_RUNNING, pid=pid, started_at=now)
        else:
            self.db.update_deploy_status(deploy_id, BOT_STATUS_FAILED, error_message=msg)
        return success, msg

    async def delete_bot(self, deploy_id, user_id):
        deploy = self.db.get_deploy(deploy_id)
        if not deploy or (deploy['user_id'] != user_id and user_id != OWNER_ID):
            return False, "Bot topilmadi"
        self.pm.cleanup(deploy_id)
        self.db.delete_deploy(deploy_id)
        self.db.execute('UPDATE users SET bot_count=MAX(bot_count-1,0), last_active=? WHERE user_id=?',
                        (str(datetime.now()), user_id))
        return True, "Bot o'chirildi"

    async def get_bot_status(self, deploy_id):
        pm_status = self.pm.get_status(deploy_id)
        if not pm_status:
            deploy = self.db.get_deploy(deploy_id)
            if deploy:
                return {'status': deploy['status'], 'pid': deploy['pid'], 'uptime_seconds': 0,
                        'restart_count': deploy['restart_count'], 'log_lines': 0, 'deploy_id': deploy_id,
                        'bot_username': deploy['bot_username'], 'bot_name': deploy['bot_name'],
                        'main_file': deploy['main_file'], 'framework': deploy['framework'],
                        'created_at': deploy['created_at'], 'error_message': deploy['error_message']}
            return None
        deploy = self.db.get_deploy(deploy_id)
        if not deploy:
            return None
        return {**pm_status, 'deploy_id': deploy_id, 'bot_username': deploy['bot_username'],
                'bot_name': deploy['bot_name'], 'main_file': deploy['main_file'],
                'framework': deploy['framework'], 'created_at': deploy['created_at'],
                'error_message': deploy['error_message']}

    async def get_user_bots(self, user_id, limit=50):
        return self.db.get_user_deploys(user_id, limit)

    async def get_logs(self, deploy_id, limit=50):
        return self.pm.get_logs(deploy_id, limit)


# ================================================================
# SHABLONLAR (AIoGRAM UCHUN QO'SHILDI)
# ================================================================

class TemplateManager:
    TEMPLATES = {
        'simple': {
            'name': 'Simple Bot (Telebot)',
            'description': 'Eng oddiy telebot shabloni',
            'framework': 'telebot',
            'code': '''import telebot

BOT_TOKEN = "YOUR_TOKEN_HERE"
bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "Assalomu alaykum! Men simple botman.")

@bot.message_handler(func=lambda m: True)
def echo(message):
    bot.reply_to(message, f"Siz yozdingiz: {message.text}")

if __name__ == "__main__":
    print("Bot ishga tushdi...")
    bot.infinity_polling()
''',
        },
        'aiogram_simple': {
            'name': 'Aiogram Simple Bot',
            'description': 'Eng oddiy aiogram bot shabloni',
            'framework': 'aiogram',
            'code': '''import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

BOT_TOKEN = "YOUR_TOKEN_HERE"
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("Assalomu alaykum! Men aiogram botman!")

@dp.message()
async def echo(message: types.Message):
    await message.answer(f"Siz yozdingiz: {message.text}")

async def main():
    print("Bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
''',
        },
        'aiogram_menu': {
            'name': 'Aiogram Menu Bot',
            'description': 'Menyu bilan aiogram bot',
            'framework': 'aiogram',
            'code': '''import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

BOT_TOKEN = "YOUR_TOKEN_HERE"
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Boshlash"), KeyboardButton(text="Yordam")],
        [KeyboardButton(text="Haqida")]
    ],
    resize_keyboard=True
)

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("Assalomu alaykum! Men menu botman.", reply_markup=menu)

@dp.message(lambda m: m.text == "Boshlash")
async def handle_start(message: types.Message):
    await message.answer("Bot ishga tushdi!")

@dp.message(lambda m: m.text == "Yordam")
async def handle_help(message: types.Message):
    await message.answer("/start - Boshlash\\n/help - Yordam")

@dp.message(lambda m: m.text == "Haqida")
async def handle_about(message: types.Message):
    await message.answer("Bu aiogram bot shabloni.")

async def main():
    print("Aiogram bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
''',
        },
        'aiogram_inline': {
            'name': 'Aiogram Inline Bot',
            'description': 'Inline tugmalar bilan aiogram bot',
            'framework': 'aiogram',
            'code': '''import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = "YOUR_TOKEN_HERE"
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Tugma 1", callback_data="btn1")],
        [InlineKeyboardButton(text="Tugma 2", callback_data="btn2")],
        [InlineKeyboardButton(text="Sayt", url="https://example.com")]
    ])
    await message.answer("Inline tugmalar!", reply_markup=keyboard)

@dp.callback_query()
async def callback(callback: types.CallbackQuery):
    if callback.data == "btn1":
        await callback.answer("Tugma 1 bosildi!")
    elif callback.data == "btn2":
        await callback.answer("Tugma 2 bosildi!")
    await callback.message.answer(f"{callback.data} tanlandi.")

async def main():
    print("Aiogram inline bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
''',
        },
    }

    def get_template_list(self):
        return [{'key': k, 'name': v['name'], 'description': v['description'], 'framework': v.get('framework', 'telebot')} 
                for k, v in self.TEMPLATES.items()]

    def get_template_code(self, key):
        tmpl = self.TEMPLATES.get(key)
        return tmpl['code'] if tmpl else None


# ================================================================
# ASOSIY BOT (AIoGRAM)
# ================================================================

class DeployBot:
    def __init__(self, token, owner_id):
        self.token = token
        self.owner_id = owner_id
        self.bot = Bot(token=token)
        self.dp = Dispatcher(storage=MemoryStorage())
        self.db = Database()
        self.pm = ProcessManager()
        self.tv = TokenValidator()
        self.engine = DeployEngine(self.db, self.pm, self.tv)
        self.templates = TemplateManager()
        self.start_time = datetime.now()
        self._setup_handlers()
        self._init_dirs()
        log.info("DeployBot (Aiogram) ishga tushdi")

    def _init_dirs(self):
        for d in [DEPLOY_DIR, LOGS_DIR, TEMPLATES_DIR]:
            os.makedirs(d, exist_ok=True)

    def _ikb(self, btns, width=2):
        """Inline keyboard yaratish"""
        keyboard = []
        row = []
        for i, (text, callback) in enumerate(btns):
            row.append(InlineKeyboardButton(text=text, callback_data=callback))
            if (i + 1) % width == 0:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        return InlineKeyboardMarkup(inline_keyboard=keyboard)

    def _rkb(self, rows):
        """Reply keyboard yaratish"""
        keyboard = []
        for row in rows:
            keyboard.append([KeyboardButton(text=btn) for btn in row])
        return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

    def _setup_handlers(self):
        dp = self.dp

        # FSM handlerlar
        @dp.message(Command("start"))
        async def start_cmd(message: types.Message, state: FSMContext):
            await self._start(message, state)

        @dp.message(Command("help"))
        async def help_cmd(message: types.Message):
            await self._help(message)

        @dp.message(Command("mybots"))
        async def mybots_cmd(message: types.Message):
            await self._my_bots(message)

        @dp.message(Command("stop"))
        async def stop_cmd(message: types.Message):
            await self._stop_cmd(message)

        @dp.message(Command("restart"))
        async def restart_cmd(message: types.Message):
            await self._restart_cmd(message)

        @dp.message(Command("logs"))
        async def logs_cmd(message: types.Message):
            await self._logs_cmd(message)

        @dp.message(Command("delete"))
        async def delete_cmd(message: types.Message):
            await self._delete_cmd(message)

        @dp.message(Command("stats"))
        async def stats_cmd(message: types.Message):
            await self._stats_cmd(message)

        @dp.message(Command("templates"))
        async def templates_cmd(message: types.Message):
            await self._templates_cmd(message)

        @dp.message(Command("cancel"))
        async def cancel_cmd(message: types.Message, state: FSMContext):
            await self._cancel(message, state)

        @dp.callback_query()
        async def callback_handler(callback: types.CallbackQuery, state: FSMContext):
            await self._callback(callback, state)

        @dp.message(lambda m: m.document)
        async def file_handler(message: types.Message, state: FSMContext):
            await self._handle_file(message, state)

        @dp.message(lambda m: m.text and m.text.startswith(EMOJI_FILE))
        async def upload_request(message: types.Message, state: FSMContext):
            await self._send_upload_request(message, state)

        @dp.message(lambda m: m.text == f"{EMOJI_LIST} Mening botlarim")
        async def my_bots_text(message: types.Message):
            await self._my_bots(message)

        @dp.message(lambda m: m.text == f"{EMOJI_STAR} Shablonlar")
        async def templates_text(message: types.Message):
            await self._templates_cmd(message)

        @dp.message(lambda m: m.text == f"{EMOJI_CHART} Statistika")
        async def stats_text(message: types.Message):
            if message.from_user.id == self.owner_id:
                await self._stats_cmd(message)
            else:
                await message.answer(f"{EMOJI_LOCK} Faqat owner uchun!")

        @dp.message(lambda m: m.text == f"{EMOJI_QUESTION} Yordam")
        async def help_text(message: types.Message):
            await self._help(message)

        @dp.message(lambda m: m.text == f"{EMOJI_PEN} Xabar yozish")
        async def write_message(message: types.Message):
            await message.answer(f"{EMOJI_PEN} XABAR YOZISH\n\nBot egasiga xabar yozing:")
            self.dp.message.register(self._msg_save)

        @dp.message(lambda m: m.text == f"{EMOJI_CROSS} Bekor qilish")
        async def cancel_text(message: types.Message, state: FSMContext):
            await self._cancel(message, state)

        @dp.message()
        async def unknown_message(message: types.Message, state: FSMContext):
            current_state = await state.get_state()
            if current_state == DeployStates.waiting_for_token.state:
                await self._receive_token(message, state)
            else:
                await message.answer(f"{EMOJI_QUESTION} Noma'lum buyruq. Yordam uchun /help")

    async def _start(self, message: types.Message, state: FSMContext):
        uid = message.from_user.id
        self.db.register_user(uid, message.from_user.username, message.from_user.first_name)
        await state.clear()

        if self.db.is_user_banned(uid):
            await message.answer(f"{EMOJI_LOCK} Siz bloklangansiz.")
            return

        self.db.update_user_activity(uid)

        username = message.from_user.username
        ui = f"@{username}" if username else message.from_user.first_name
        bots_count = self.db.count('deployments', 'user_id=?', (uid,))

        text = f"""
{EMOJI_ROCKET} BOT DEPLOY BOT (Aiogram)
{'=' * 35}

Assalomu alaykum, {ui}!

Bu bot orqali o'zingiz yozgan Python kodini Telegram botga aylantirishingiz mumkin!

{EMOJI_CHART} Sizning botlaringiz: {bots_count} ta

{EMOJI_STAR} QADAMLAR:
{'-' * 35}
1. {EMOJI_FILE} .py faylni yuboring
2. {EMOJI_KEY} Bot tokeningizni kiriting
3. {EMOJI_CHECK} Bot avtomatik deploy bo'ladi!
{'-' * 35}

{EMOJI_WARNING} Fayl .py formatda bo'lishi shart!
Maksimal hajm: {format_size(MAX_FILE_SIZE)}
"""

        markup = self._rkb([
            [f"{EMOJI_FILE} Fayl yuborin", f"{EMOJI_STAR} Shablonlar"],
            [f"{EMOJI_LIST} Mening botlarim", f"{EMOJI_CHART} Statistika"],
            [f"{EMOJI_QUESTION} Yordam", f"{EMOJI_PEN} Xabar yozish"]
        ])
        await message.answer(text, reply_markup=markup)

    async def _help(self, message: types.Message):
        text = f"""
{EMOJI_QUESTION} YORDAM
{'=' * 35}

{EMOJI_STAR} QANDAY ISHLAYDI?

1. "{EMOJI_FILE} Fayl yuborin" tugmasini bosing
2. .py faylni yuboring
3. Bot tokenini kiriting
4. Bot avtomatik deploy bo'ladi!

{EMOJI_FILE} FAYL TALABLARI:
  {EMOJI_CHECK} .py fayl bo'lishi shart
  {EMOJI_CHECK} telebot yoki aiogram import bor
  {EMOJI_CHECK} Maksimal hajm: {format_size(MAX_FILE_SIZE)}

{EMOJI_KEY} TOKEN QAYERDAN OLINADI?
  1. @BotFather botiga o'ting
  2. /newbot buyrug'ini yozing
  3. Berilgan tokenni nusxalang

{EMOJI_LIST} BUYRUQLAR:
  /mybots - Mening botlarim
  /stop - Botni to'xtatish
  /restart - Qayta ishga tushirish
  /logs - Loglarni ko'rish
  /delete - Botni o'chirish
  /stats - Statistika
  /templates - Shablonlar
  /cancel - Bekor qilish
"""
        await message.answer(text)

    async def _my_bots(self, message: types.Message):
        uid = message.from_user.id
        bots = await self.engine.get_user_bots(uid)

        if not bots:
            await message.answer(f"{EMOJI_LIST} Sizda hali botlar yo'q!")
            return

        text = f"{EMOJI_LIST} SIZNING BOTLARINGIZ ({len(bots)} ta):\n"
        btns = []

        for b in bots:
            did = b['deploy_id']
            status = b['status']
            bot_uname = b['bot_username'] or 'Bot'
            icon = EMOJI_GREEN if status == BOT_STATUS_RUNNING else EMOJI_RED

            st = await self.engine.get_bot_status(did)
            uptime_str = format_uptime(st['uptime_seconds']) if st else NA_TEXT

            text += f"\n{icon} @{bot_uname}\n"
            text += f"   ID: {did}\n"
            text += f"   {EMOJI_CLOCK} Uptime: {uptime_str}\n"

            btns.append((f"{icon} @{bot_uname}", f"bot_{did}"))

        text += f"\n{EMOJI_ARROW} Botni tanlang:"
        await message.answer(text, reply_markup=self._ikb(btns, 1))

    async def _bot_details(self, callback: types.CallbackQuery, deploy_id: str):
        st = await self.engine.get_bot_status(deploy_id)
        if not st:
            await callback.answer("Bot topilmadi!", show_alert=True)
            return

        if st['status'] == BOT_STATUS_RUNNING:
            status_text = f"{EMOJI_GREEN} Ishlayapti"
        elif st['status'] == BOT_STATUS_STOPPED:
            status_text = f"{EMOJI_RED} To'xtagan"
        else:
            status_text = f"{EMOJI_WHITE} {st['status']}"

        uptime = format_uptime(st['uptime_seconds'])
        bot_uname = st.get('bot_username') or NA_TEXT
        main_file = st.get('main_file') or NA_TEXT
        created = st.get('created_at', NA_TEXT)
        if len(created) > 16:
            created = created[:16]

        text = f"""
{status_text}
{'=' * 30}

{EMOJI_INFO} ID: {deploy_id}
{EMOJI_BOT} Bot: @{bot_uname}
{EMOJI_PAGE} Fayl: {main_file}
{EMOJI_CLOCK} Yaratilgan: {created}

{EMOJI_CHART} HOLAT:
  Status: {status_text}
  PID: {st.get('pid', NA_TEXT)}
  Uptime: {uptime}
  Restarts: {st.get('restart_count', 0)}
  Loglar: {st.get('log_lines', 0)} ta
"""

        btns = []
        if st['status'] == BOT_STATUS_STOPPED:
            btns.append((f"{EMOJI_PLAY} Ishga tushirish", f"start_{deploy_id}"))
        btns.extend([
            (f"{EMOJI_RESTART} Qayta ishga tushirish", f"restart_{deploy_id}"),
            (f"{EMOJI_STOP} To'xtatish", f"stop_{deploy_id}"),
            (f"{EMOJI_LIST} Loglar", f"logs_{deploy_id}"),
            (f"{EMOJI_TRASH} O'chirish", f"del_{deploy_id}"),
            (f"{EMOJI_BACK} Orqaga", "back_to_bots"),
        ])

        await callback.message.edit_text(text, reply_markup=self._ikb(btns, 1))
        await callback.answer()

    async def _bot_action(self, callback: types.CallbackQuery, deploy_id: str, action: str):
        uid = callback.from_user.id

        if action == 'start':
            success, msg = await self.engine.start_bot(deploy_id, uid)
        elif action == 'stop':
            success, msg = await self.engine.stop_bot(deploy_id, uid)
        elif action == 'restart':
            success, msg = await self.engine.restart_bot(deploy_id, uid)
        elif action == 'del':
            success, msg = await self.engine.delete_bot(deploy_id, uid)
            if success:
                await callback.answer(f"{EMOJI_CHECK} Bot o'chirildi!", show_alert=True)
                await callback.message.edit_text(f"{EMOJI_TRASH} Bot o'chirildi!")
                return
            else:
                await callback.answer(f"{EMOJI_CROSS} {msg}", show_alert=True)
                return
        else:
            return

        await callback.answer(f"{EMOJI_CHECK if success else EMOJI_CROSS} {msg}")
        if action in ('start', 'stop', 'restart'):
            await asyncio.sleep(0.5)
            await self._bot_details(callback, deploy_id)

    async def _show_logs(self, callback: types.CallbackQuery, deploy_id: str):
        logs = await self.engine.get_logs(deploy_id, limit=30)
        if not logs:
            await callback.answer("Loglar yo'q!", show_alert=True)
            return

        text = f"{EMOJI_LIST} LOGLAR:\n\n"
        for l in logs[-30:]:
            line = l[:200] if len(l) > 200 else l
            text += f"│ {line}\n"

        await callback.message.edit_text(
            truncate_text(text),
            reply_markup=self._ikb([(f"{EMOJI_BACK} Orqaga", f"bot_{deploy_id}")], 1)
        )
        await callback.answer()

    async def _stats_cmd(self, message: types.Message):
        if message.from_user.id != self.owner_id:
            await message.answer(f"{EMOJI_LOCK} Faqat owner uchun!")
            return

        stats = self.db.get_stats_summary()
        uptime = int((datetime.now() - self.start_time).total_seconds())

        text = f"""
{EMOJI_CHART} UMUMIY STATISTIKA
{'=' * 35}

{EMOJI_BOT} Botlar jami: {stats['total']}
{EMOJI_GREEN} Ishlayotgan: {stats['running']}
{EMOJI_RED} To'xtatilgan: {stats['stopped']}
{EMOJI_CROSS} Muvaffaqiyatsiz: {stats['failed']}
{EMOJI_QUESTION} Foydalanuvchilar: {stats['users']}
{EMOJI_CLOCK} Bot uptime: {format_uptime(uptime)}

{EMOJI_STAR} BUGUN:
  Deploylar: {stats['today'].get('total_deploys', 0)}
  Muvaffaqiyatli: {stats['today'].get('successful', 0)}
  Yangi foydalanuvchilar: {stats['today'].get('new_users', 0)}
"""
        await message.answer(text)

    async def _templates_cmd(self, message: types.Message):
        templates = self.templates.get_template_list()
        text = f"{EMOJI_STAR} BOT SHABLONLARI\n\n"
        btns = []

        for tmpl in templates:
            framework_icon = "🤖" if tmpl['framework'] == 'aiogram' else "📦"
            text += f"{framework_icon} {tmpl['name']}\n   {tmpl['description']}\n\n"
            btns.append((f"{framework_icon} {tmpl['name']}", f"tmpl_{tmpl['key']}"))

        btns.append((f"{EMOJI_BACK} Orqaga", "back_to_menu"))
        await message.answer(text, reply_markup=self._ikb(btns, 1))

    async def _send_template(self, callback: types.CallbackQuery, tmpl_key: str):
        code = self.templates.get_template_code(tmpl_key)
        if not code:
            await callback.answer("Shablon topilmadi!", show_alert=True)
            return

        temp_file = tempfile.mkdtemp(prefix='template_')
        file_path = os.path.join(temp_file, f"{tmpl_key}.py")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(code)

        try:
            with open(file_path, 'rb') as f:
                await callback.message.answer_document(
                    types.FSInputFile(file_path, filename=f"{tmpl_key}.py"),
                    caption=f"{EMOJI_STAR} {tmpl_key}.py shabloni"
                )
        except Exception as e:
            await callback.message.answer(f"{EMOJI_CROSS} Fayl yuborilmadi: {e}\n\n```\n{code}\n```")
        finally:
            shutil.rmtree(temp_file, ignore_errors=True)

        await callback.answer()

    async def _send_upload_request(self, message: types.Message, state: FSMContext):
        await state.set_state(DeployStates.waiting_for_file)

        text = f"""
{EMOJI_FILE} FAYL YUBORISH
{'=' * 30}

Bot kodingizni .py fayl ko'rinishida yuboring.

{EMOJI_STAR} TALABLAR:
{EMOJI_CHECK} .py fayl bo'lishi shart
{EMOJI_CHECK} Maksimal hajm: {format_size(MAX_FILE_SIZE)}

{EMOJI_INFO} Masalan: mybot.py
"""
        markup = self._rkb([[f"{EMOJI_CROSS} Bekor qilish"]])
        await message.answer(text, reply_markup=markup)

    async def _handle_file(self, message: types.Message, state: FSMContext):
        uid = message.from_user.id

        if self.db.is_user_banned(uid):
            await message.answer(f"{EMOJI_LOCK} Siz bloklangansiz.")
            return

        current_state = await state.get_state()
        if current_state != DeployStates.waiting_for_file.state:
            await message.answer(f"{EMOJI_CROSS} Avval \"{EMOJI_FILE} Fayl yuborin\" tugmasini bosing!")
            return

        if not message.document:
            await message.answer(f"{EMOJI_CROSS} Iltimos, fayl yuboring!")
            return

        filename = message.document.file_name or ""
        ext = os.path.splitext(filename)[1].lower()

        if ext not in ALLOWED_EXTENSIONS:
            await message.answer(f"{EMOJI_CROSS} Faqat .py fayllar qabul qilinadi!\nMasalan: mybot.py")
            return

        if message.document.file_size and message.document.file_size > MAX_FILE_SIZE:
            await message.answer(f"{EMOJI_CROSS} Fayl juda katta!\nMaksimal: {format_size(MAX_FILE_SIZE)}")
            return

        temp_dir = tempfile.mkdtemp(prefix='bot_file_')
        file_path = os.path.join(temp_dir, safe_filename(filename))

        try:
            file_info = await self.bot.get_file(message.document.file_id)
            downloaded = await self.bot.download_file(file_info.file_path)
            with open(file_path, 'wb') as f:
                f.write(downloaded.getvalue())
        except Exception as e:
            await message.answer(f"{EMOJI_CROSS} Faylni yuklab bo'lmadi: {str(e)[:80]}")
            shutil.rmtree(temp_dir, ignore_errors=True)
            return

        valid, msg = self.fh.validate_file(file_path)
        if not valid:
            await message.answer(f"{EMOJI_CROSS} {msg}")
            shutil.rmtree(temp_dir, ignore_errors=True)
            return

        analysis = self.ca.analyze_code(file_path)
        analysis_text = self.ca.get_analysis_text(analysis)

        if not analysis['valid']:
            await message.answer(f"{EMOJI_CROSS} Kodda xatoliklar bor:\n\n{analysis_text}")
            shutil.rmtree(temp_dir, ignore_errors=True)
            return

        await message.answer(f"{EMOJI_CHECK} Fayl yuklandi!\n\n{analysis_text}\n\nDavom etish uchun token yuboring.")

        await state.update_data({
            'file_path': file_path,
            'temp_dir': temp_dir,
            'analysis': analysis,
            'filename': filename,
        })
        await state.set_state(DeployStates.waiting_for_token)

        await message.answer(f"{EMOJI_KEY} BOT TOKEN\n\n@BotFather dan olgan tokeningizni yuboring.")

    async def _receive_token(self, message: types.Message, state: FSMContext):
        data = await state.get_data()
        if not data:
            await message.answer(f"{EMOJI_CROSS} Jarayon buzildi. Qaytadan boshlang.")
            await state.clear()
            return

        token = message.text.strip().replace(' ', '').replace('\n', '')

        if not token:
            await message.answer(f"{EMOJI_CROSS} Token bo'sh!")
            return

        if len(token) < 30:
            await message.answer(f"{EMOJI_CROSS} Token juda qisqa!")
            return

        progress = await message.answer(f"{EMOJI_HOURGLASS} Deploy qilinmoqda...")

        try:
            result = await self.engine.deploy(
                message.from_user.id,
                data['file_path'],
                token
            )
        except Exception as e:
            log.error(f"Deploy xatosi: {e}")
            result = (None, f"Xato: {str(e)[:100]}", None)

        temp_dir = data.get('temp_dir')
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)

        deploy_id, proc_msg, analysis = result

        if deploy_id is None:
            await progress.edit_text(
                f"{EMOJI_CROSS} DEPLOY MUVAFFAQIYATSIZ\n\nSabab: {proc_msg}"
            )
        else:
            filename = data.get('filename', 'bot.py')
            lines = analysis['line_count'] if analysis else 0

            await progress.edit_text(
                f"{EMOJI_CHECK} DEPLOY MUVAFFAQIYATLI!\n\n"
                f"{EMOJI_INFO} Bot ID: {deploy_id}\n"
                f"{EMOJI_PAGE} Fayl: {filename}\n"
                f"{EMOJI_SIZE} Qatorlar: {lines}\n\n"
                f"{EMOJI_GREEN} Bot ishga tushdi va tayyor!\n"
                f"{EMOJI_INFO} Loglarni /logs buyrug'i bilan ko'ring.",
                reply_markup=self._ikb([(f"{EMOJI_LIST} Botni ko'rish", f"bot_{deploy_id}")], 1)
            )

        await state.clear()

    async def _cancel(self, message: types.Message, state: FSMContext):
        data = await state.get_data()
        if data and data.get('temp_dir'):
            shutil.rmtree(data['temp_dir'], ignore_errors=True)
        await state.clear()
        await message.answer(
            f"{EMOJI_CROSS} Jarayon bekor qilindi!",
            reply_markup=self._rkb([[f"{EMOJI_FILE} Fayl yuborin"], [f"{EMOJI_LIST} Mening botlarim"], [f"{EMOJI_QUESTION} Yordam"]])
        )

    async def _callback(self, callback: types.CallbackQuery, state: FSMContext):
        data = callback.data

        try:
            if data == "upload_file":
                await self._send_upload_request(callback.message, state)
                await callback.answer()

            elif data == "back_to_bots":
                await self._my_bots(callback.message)
                await callback.answer()

            elif data == "back_to_menu":
                await self._start(callback.message, state)
                await callback.answer()

            elif data.startswith("bot_"):
                await self._bot_details(callback, data[4:])

            elif data.startswith("restart_"):
                await self._bot_action(callback, data[8:], "restart")

            elif data.startswith("stop_"):
                await self._bot_action(callback, data[5:], "stop")

            elif data.startswith("start_"):
                await self._bot_action(callback, data[6:], "start")

            elif data.startswith("del_"):
                await self._bot_action(callback, data[4:], "del")

            elif data.startswith("logs_"):
                await self._show_logs(callback, data[5:])

            elif data.startswith("tmpl_"):
                await self._send_template(callback, data[5:])

            else:
                await callback.answer()

        except Exception as e:
            log.error(f"Callback xatosi: {e}")
            await callback.answer(f"{EMOJI_CROSS} Xatolik!", show_alert=True)

    async def _msg_save(self, message: types.Message):
        if not message.text or not message.text.strip():
            await message.answer(f"{EMOJI_CROSS} Xabar bo'sh!")
            return

        now = str(datetime.now())
        uid = message.from_user.id
        username = message.from_user.username or ''

        self.db.execute(
            'INSERT INTO user_messages (user_id, username, message_text, created_at, status) VALUES (?, ?, ?, ?, ?)',
            (uid, username, message.text.strip(), now, 'pending')
        )

        await message.answer(f"{EMOJI_CHECK} Xabar qabul qilindi!")

        try:
            await self.bot.send_message(
                self.owner_id,
                f"{EMOJI_MESSAGE} YANGI XABAR!\n\n👤 @{username}\n🆔 {uid}\n📝 {message.text.strip()}"
            )
        except Exception:
            pass

    async def _stop_cmd(self, message: types.Message):
        await message.answer(f"{EMOJI_STOP} To'xtatmoqchi bot ID sini yuboring:")
        self.dp.message.register(self._stop_exec, lambda m: m.text and not m.text.startswith('/'))

    async def _stop_exec(self, message: types.Message):
        did = message.text.strip()
        if not did:
            await message.answer(f"{EMOJI_CROSS} ID bo'sh!")
            return
        success, msg = await self.engine.stop_bot(did, message.from_user.id)
        await message.answer(f"{EMOJI_CHECK if success else EMOJI_CROSS} {msg}")

    async def _restart_cmd(self, message: types.Message):
        await message.answer(f"{EMOJI_RESTART} Qayta ishga tushirmoqchi bot ID sini yuboring:")
        self.dp.message.register(self._restart_exec, lambda m: m.text and not m.text.startswith('/'))

    async def _restart_exec(self, message: types.Message):
        did = message.text.strip()
        if not did:
            await message.answer(f"{EMOJI_CROSS} ID bo'sh!")
            return
        success, msg = await self.engine.restart_bot(did, message.from_user.id)
        await message.answer(f"{EMOJI_CHECK if success else EMOJI_CROSS} {msg}")

    async def _logs_cmd(self, message: types.Message):
        await message.answer(f"{EMOJI_LIST} Loglarini ko'rishmoqchi bot ID sini yuboring:")
        self.dp.message.register(self._logs_exec, lambda m: m.text and not m.text.startswith('/'))

    async def _logs_exec(self, message: types.Message):
        did = message.text.strip()
        if not did:
            await message.answer(f"{EMOJI_CROSS} ID bo'sh!")
            return
        logs = await self.engine.get_logs(did, limit=30)
        if not logs:
            await message.answer(f"{EMOJI_LIST} Loglar yo'q!")
            return
        text = f"{EMOJI_LIST} LOGLAR:\n\n" + "\n".join(f"│ {l[:150]}" for l in logs[-30:])
        await message.answer(truncate_text(text))

    async def _delete_cmd(self, message: types.Message):
        await message.answer(f"{EMOJI_TRASH} O'chirmoqchi bot ID sini yuboring:")
        self.dp.message.register(self._delete_exec, lambda m: m.text and not m.text.startswith('/'))

    async def _delete_exec(self, message: types.Message):
        did = message.text.strip()
        if not did:
            await message.answer(f"{EMOJI_CROSS} ID bo'sh!")
            return
        success, msg = await self.engine.delete_bot(did, message.from_user.id)
        await message.answer(f"{EMOJI_CHECK if success else EMOJI_CROSS} {msg}")

    async def on_startup(self):
        log.info("Bot ishga tushmoqda...")
        # Server restartdan keyin avvalgi botlarni qayta ishga tushirish
        log.info("Avvalgi botlarni qayta tiklash boshlanmoqda...")
        restored, failed = self.pm.restore_all_bots(self.db)
        if restored > 0:
            log.info(f"{restored} ta bot qayta tiklandi")
        if failed > 0:
            log.warning(f"{failed} ta bot qayta tiklanmadi")

    async def on_shutdown(self):
        log.info("Bot to'xtatilmoqda...")
        self.pm.stop_all()
        self.fh.cleanup_all()
        self.db.close()
        await self.bot.session.close()
        log.info("Bot to'xtatildi")

    async def run(self):
        await self.on_startup()
        try:
            me = await self.bot.get_me()
            log.info(f"Bot ishga tushdi: @{me.username}")
            print(f"{EMOJI_ROCKET} Bot ishga tushdi: @{me.username}")
            await self.dp.start_polling(self.bot)
        except Exception as e:
            log.error(f"Bot xatosi: {e}")
        finally:
            await self.on_shutdown()


# ================================================================
# BANNER
# ================================================================

def print_banner():
    sys_info = get_system_info()
    banner = f"""
{'=' * 55}
{' ' * 12}{EMOJI_ROCKET} BOT DEPLOY BOT v5.0 (Aiogram)
{'=' * 55}

  Versiya:      5.0 (Aiogram bilan ishlaydi)
  Sana:         2026-04-04
  Platform:     {sys_info['platform']} {sys_info['platform_release']}
  Python:       {sys_info['python_version']}

{'=' * 55}
  XUSUSIYATLAR:
{'=' * 55}
  {EMOJI_CHECK} Aiogram va Telebot bilan ishlaydi
  {EMOJI_CHECK} Oddiy .py fayl qabul qiladi
  {EMOJI_CHECK} Kod tahlili va sifat bahosi
  {EMOJI_CHECK} Xavfli kodlarni bloklash
  {EMOJI_CHECK} Avtomatik qayta ishga tushirish
  {EMOJI_CHECK} Bot shablonlari (Aiogram + Telebot)
  {EMOJI_CHECK} Statistika va monitoring
  {EMOJI_CHECK} Server restartda avvalgi botlar avtomatik tiklanadi

{'=' * 55}
  SOZLAMALAR:
{'=' * 55}
  Maksimal fayl:  {format_size(MAX_FILE_SIZE)}
  Auto-restart:   {'Yoq' if AUTO_RESTART else 'Yo' + "'q"}
  Max restart:    {MAX_RESTART_ATTEMPTS} ta
  DB:             deploy_bots.db

{'=' * 55}
"""
    print(banner)


# ================================================================
# ASOSIY FUNKSIYA
# ================================================================

async def main():
    print_banner()

    bot = DeployBot(BOT_TOKEN, OWNER_ID)
    await bot.run()


def signal_handler(signum, frame):
    log.info(f"Signal qabul qilindi: {signum}")
    print(f"\n{EMOJI_STOP} Bot to'xtatilmoqda...")
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{EMOJI_STOP} Bot to'xtatildi")
    except Exception as e:
        print(f"\n{EMOJI_CROSS} XATOLIK: {e}")
        traceback.print_exc()
