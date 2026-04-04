#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ================================================================
# BOT DEPLOY BOT - TO'LIQ ISHLATILADIGAN VERSIYA
# Version: 4.6
# Sana: 2026-03-31
# ================================================================
# TUZATILDI: Server qayta ishga tushganda avvalgi botlar avtomatik ishga tushadi
# ================================================================

import telebot
from telebot import types
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

STATE_IDLE = "idle"
STATE_AWAITING_FILE = "awaiting_file"
STATE_AWAITING_TOKEN = "awaiting_token"

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
        """Barcha deploylarni olish (server restartda ishlatiladi)"""
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
# KOD TAHLILCHI
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

        for key, name in self.bot_frameworks.items():
            if key in content:
                result['framework'] = name
                break

        import_matches = re.findall(r'^(?:from|import)\s+([\w.]+)', content, re.MULTILINE)
        result['imports'] = list(set(import_matches))

        for pattern, name in self.token_patterns:
            match = re.search(pattern, content)
            if match:
                result['has_token'] = True
                result['token_pattern'] = name
                break

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

        txt = f"{EMOJI_CHECK} KOD TAHLILI\n\n"
        txt += f"{EMOJI_PAGE} Framework: {analysis['framework']}\n"
        txt += f"{EMOJI_SIZE} Qatorlar: {analysis['line_count']}\n"
        txt += f"{EMOJI_SIZE} Hajm: {analysis['file_size_kb']} KB\n"
        txt += f"{EMOJI_KEY} Token: {'Bor' if analysis['has_token'] else 'Yo'}"
        if analysis['token_pattern']:
            txt += f" ({analysis['token_pattern']})"
        txt += "\n"
        txt += f"{EMOJI_BOX} Requirements: {'Bor' if analysis['has_requirements'] else 'Yo'}"
        if analysis['requirements']:
            txt += f" ({len(analysis['requirements'])} ta)"
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
# PROSESS MANAGER (UTF-8 QO'LLAB-QUVVATLANADI + AUTO RESTORE)
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
            if sys.platform == 'win32':
                proc = subprocess.Popen(
                    [PYTHON_CMD, '-X', 'utf8', main_file],
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
            else:
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
        """Server restartdan keyin barcha botlarni qayta ishga tushirish"""
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
                log.warning(f"Bot {deploy_id} fayllari topilmadi, o'tkazib yuboriladi")
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
            
            time.sleep(0.5)  # Rate limiting
        
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
# TOKEN VALIDATOR
# ================================================================

class TokenValidator:
    def __init__(self):
        self._cache = {}
        self._lock = threading.Lock()

    def validate(self, token):
        if not token or len(token) < 30:
            return False, "Token juda qisqa!", None
        with self._lock:
            if token in self._cache:
                cached = self._cache[token]
                if time.time() - cached['time'] < 300:
                    return cached['valid'], cached['message'], cached['info']
        try:
            bot = telebot.TeleBot(token)
            info = bot.get_me()
            result = {'id': info.id, 'username': info.username, 'first_name': info.first_name}
            with self._lock:
                self._cache[token] = {'valid': True, 'message': f"@{info.username}", 'info': result, 'time': time.time()}
            return True, f"@{info.username}", result
        except Exception as e:
            msg = "Token noto'g'ri yoki eskirgan!" if 'Unauthorized' in str(e) else f"Xato: {str(e)[:50]}"
            with self._lock:
                self._cache[token] = {'valid': False, 'message': msg, 'info': None, 'time': time.time()}
            return False, msg, None

    def get_bot_username(self, token):
        valid, msg, info = self.validate(token)
        return info.get('username') if valid and info else None


# ================================================================
# DEPLOY ENGINE
# ================================================================

class DeployEngine:
    def __init__(self, db, pm, tv):
        self.db = db
        self.pm = pm
        self.tv = tv
        self.fh = FileHandler()
        self.ca = CodeAnalyzer()
        self.user_states = {}
        self._lock = threading.Lock()

    def generate_deploy_id(self):
        return generate_id("dep", 10)

    def deploy(self, user_id, file_path, bot_token):
        deploy_id = self.generate_deploy_id()

        valid, msg = self.fh.validate_file(file_path)
        if not valid:
            return None, msg, None

        token_valid, token_msg, token_info = self.tv.validate(bot_token)
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

    def stop_bot(self, deploy_id, user_id):
        deploy = self.db.get_deploy(deploy_id)
        if not deploy or (deploy['user_id'] != user_id and user_id != OWNER_ID):
            return False, "Bot topilmadi yoki sizga tegishli emas"
        success, msg = self.pm.stop(deploy_id)
        if success:
            self.db.update_deploy_status(deploy_id, BOT_STATUS_STOPPED, stopped_at=str(datetime.now()))
        return success, msg

    def restart_bot(self, deploy_id, user_id):
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

    def start_bot(self, deploy_id, user_id):
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

    def delete_bot(self, deploy_id, user_id):
        deploy = self.db.get_deploy(deploy_id)
        if not deploy or (deploy['user_id'] != user_id and user_id != OWNER_ID):
            return False, "Bot topilmadi"
        self.pm.cleanup(deploy_id)
        self.db.delete_deploy(deploy_id)
        self.db.execute('UPDATE users SET bot_count=MAX(bot_count-1,0), last_active=? WHERE user_id=?',
                        (str(datetime.now()), user_id))
        return True, "Bot o'chirildi"

    def get_bot_status(self, deploy_id):
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

    def get_user_bots(self, user_id, limit=50):
        return self.db.get_user_deploys(user_id, limit)

    def get_logs(self, deploy_id, limit=50):
        return self.pm.get_logs(deploy_id, limit)

    def set_user_state(self, user_id, state, data=None):
        with self._lock:
            self.user_states[user_id] = {'state': state, 'data': data or {}, 'updated': str(datetime.now())}

    def get_user_state(self, user_id):
        with self._lock:
            return self.user_states.get(user_id)

    def clear_user_state(self, user_id):
        with self._lock:
            state = self.user_states.get(user_id)
            if state and state.get('data', {}).get('temp_dir'):
                self.fh.cleanup(state['data']['temp_dir'])
            if user_id in self.user_states:
                del self.user_states[user_id]


# ================================================================
# SHABLONLAR
# ================================================================

class TemplateManager:
    TEMPLATES = {
        'simple': {
            'name': 'Simple Bot',
            'description': 'Eng oddiy bot shabloni',
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
        'menu': {
            'name': 'Menu Bot',
            'description': 'Menyu bilan bot shabloni',
            'code': '''import telebot
from telebot import types

BOT_TOKEN = "YOUR_TOKEN_HERE"
bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("Boshlash", "Yordam")
    markup.row("Haqida")
    bot.send_message(message.chat.id, "Assalomu alaykum!", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "Boshlash")
def handle_start(m):
    bot.send_message(m.chat.id, "Bot ishga tushdi!")

@bot.message_handler(func=lambda m: m.text == "Yordam")
def handle_help(m):
    bot.send_message(m.chat.id, "Yordam bo'limi")

if __name__ == "__main__":
    bot.infinity_polling()
''',
        },
        'inline': {
            'name': 'Inline Bot',
            'description': 'Inline tugmalar bilan bot',
            'code': '''import telebot
from telebot import types

BOT_TOKEN = "YOUR_TOKEN_HERE"
bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['start'])
def start(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Tugma", callback_data="btn"))
    bot.send_message(message.chat.id, "Inline tugmalar!", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: True)
def callback(c):
    bot.answer_callback_query(c.id, "Bosildi!")

if __name__ == "__main__":
    bot.infinity_polling()
''',
        },
    }

    def get_template_list(self):
        return [{'key': k, 'name': v['name'], 'description': v['description']} for k, v in self.TEMPLATES.items()]

    def get_template_code(self, key):
        tmpl = self.TEMPLATES.get(key)
        return tmpl['code'] if tmpl else None


# ================================================================
# ASOSIY BOT
# ================================================================

class DeployBot:
    def __init__(self, token, owner_id):
        self.token = token
        self.owner_id = owner_id
        self.bot = telebot.TeleBot(token)
        self.db = Database()
        self.pm = ProcessManager()
        self.tv = TokenValidator()
        self.engine = DeployEngine(self.db, self.pm, self.tv)
        self.templates = TemplateManager()
        self._start_time = datetime.now()
        self._setup_handlers()
        self._init_dirs()
        # Server restartdan keyin avvalgi botlarni qayta ishga tushirish
        self._restore_previous_bots()
        log.info("DeployBot ishga tushdi")

    def _init_dirs(self):
        for d in [DEPLOY_DIR, LOGS_DIR, TEMPLATES_DIR]:
            os.makedirs(d, exist_ok=True)

    def _restore_previous_bots(self):
        """Server restartdan keyin avvalgi botlarni qayta ishga tushirish"""
        log.info("Avvalgi botlarni qayta tiklash boshlanmoqda...")
        restored, failed = self.pm.restore_all_bots(self.db)
        if restored > 0:
            log.info(f"{restored} ta bot qayta tiklandi")
        if failed > 0:
            log.warning(f"{failed} ta bot qayta tiklanmadi")

    def _setup_handlers(self):
        bot = self.bot

        @bot.message_handler(commands=['start'])
        def _(m): self._start(m)

        @bot.message_handler(commands=['help'])
        def _(m): self._help(m)

        @bot.message_handler(commands=['mybots'])
        def _(m): self._my_bots(m)

        @bot.message_handler(commands=['stop'])
        def _(m): self._stop_cmd(m)

        @bot.message_handler(commands=['restart'])
        def _(m): self._restart_cmd(m)

        @bot.message_handler(commands=['logs'])
        def _(m): self._logs_cmd(m)

        @bot.message_handler(commands=['delete'])
        def _(m): self._delete_cmd(m)

        @bot.message_handler(commands=['stats'])
        def _(m): self._stats_cmd(m)

        @bot.message_handler(commands=['templates'])
        def _(m): self._templates_cmd(m)

        @bot.message_handler(commands=['cancel'])
        def _(m): self._cancel(m)

        @bot.callback_query_handler(func=lambda c: True)
        def _(c): self._callback(c)

        @bot.message_handler(content_types=['document'])
        def _(m): self._handle_file(m)

        @bot.message_handler(func=lambda m: True, content_types=['text'])
        def _(m): self._handle_text(m)

    def _ikb(self, btns, width=2):
        markup = types.InlineKeyboardMarkup(row_width=width)
        for b in btns:
            if isinstance(b, list):
                markup.row(*[types.InlineKeyboardButton(t, callback_data=d) for t, d in b])
            elif isinstance(b, tuple):
                markup.add(types.InlineKeyboardButton(b[0], callback_data=b[1]))
        return markup

    def _rkb(self, rows):
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        for r in rows:
            markup.row(*r)
        return markup

    def _start(self, m):
        uid = m.from_user.id
        self.db.register_user(uid, m.from_user.username, m.from_user.first_name)
        self.engine.clear_user_state(uid)

        if self.db.is_user_banned(uid):
            self.bot.reply_to(m, f"{EMOJI_LOCK} Siz bloklangansiz.")
            return

        self.db.update_user_activity(uid)

        username = m.from_user.username
        ui = f"@{username}" if username else m.from_user.first_name
        bots_count = self.db.count('deployments', 'user_id=?', (uid,))

        text = f"""
{EMOJI_ROCKET} BOT DEPLOY BOT
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
        self.bot.send_message(m.chat.id, text, reply_markup=markup)

    def _help(self, m):
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
  {EMOJI_CHECK} telebot import bor
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
        self.bot.reply_to(m, text)

    def _my_bots(self, m):
        uid = m.from_user.id
        bots = self.engine.get_user_bots(uid)

        if not bots:
            self.bot.reply_to(m, f"{EMOJI_LIST} Sizda hali botlar yo'q!")
            return

        text = f"{EMOJI_LIST} SIZNING BOTLARINGIZ ({len(bots)} ta):\n"
        btns = []

        for b in bots:
            did = b['deploy_id']
            status = b['status']
            bot_uname = b['bot_username'] or 'Bot'
            icon = EMOJI_GREEN if status == BOT_STATUS_RUNNING else EMOJI_RED

            st = self.engine.get_bot_status(did)
            uptime_str = format_uptime(st['uptime_seconds']) if st else NA_TEXT

            text += f"\n{icon} @{bot_uname}\n"
            text += f"   ID: {did}\n"
            text += f"   {EMOJI_CLOCK} Uptime: {uptime_str}\n"

            btns.append([(f"{icon} @{bot_uname}", f"bot_{did}")])

        text += f"\n{EMOJI_ARROW} Botni tanlang:"
        self.bot.send_message(m.chat.id, text, reply_markup=self._ikb(btns, 1))

    def _bot_details(self, c, deploy_id):
        st = self.engine.get_bot_status(deploy_id)
        if not st:
            self.bot.answer_callback_query(c.id, "Bot topilmadi!")
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
            btns.append([(f"{EMOJI_PLAY} Ishga tushirish", f"start_{deploy_id}")])
        btns.extend([
            [(f"{EMOJI_RESTART} Qayta ishga tushirish", f"restart_{deploy_id}")],
            [(f"{EMOJI_STOP} To'xtatish", f"stop_{deploy_id}")],
            [(f"{EMOJI_LIST} Loglar", f"logs_{deploy_id}")],
            [(f"{EMOJI_TRASH} O'chirish", f"del_{deploy_id}")],
            [(f"{EMOJI_BACK} Orqaga", "back_to_bots")],
        ])

        try:
            self.bot.edit_message_text(text, c.message.chat.id, c.message.message_id, reply_markup=self._ikb(btns, 1))
        except Exception:
            self.bot.send_message(c.message.chat.id, text, reply_markup=self._ikb(btns, 1))
        self.bot.answer_callback_query(c.id)

    def _bot_action(self, c, deploy_id, action):
        uid = c.from_user.id

        if action == 'start':
            success, msg = self.engine.start_bot(deploy_id, uid)
        elif action == 'stop':
            success, msg = self.engine.stop_bot(deploy_id, uid)
        elif action == 'restart':
            success, msg = self.engine.restart_bot(deploy_id, uid)
        elif action == 'del':
            success, msg = self.engine.delete_bot(deploy_id, uid)
            if success:
                self.bot.answer_callback_query(c.id, f"{EMOJI_CHECK} Bot o'chirildi!")
                try:
                    self.bot.edit_message_text(f"{EMOJI_TRASH} Bot o'chirildi!", c.message.chat.id, c.message.message_id)
                except Exception:
                    pass
                return
            else:
                self.bot.answer_callback_query(c.id, f"{EMOJI_CROSS} {msg}")
                return
        else:
            return

        self.bot.answer_callback_query(c.id, f"{EMOJI_CHECK if success else EMOJI_CROSS} {msg}")
        if action in ('start', 'stop', 'restart'):
            time.sleep(0.5)
            self._bot_details(c, deploy_id)

    def _show_logs(self, c, deploy_id):
        logs = self.engine.get_logs(deploy_id, limit=30)
        if not logs:
            self.bot.answer_callback_query(c.id, "Loglar yo'q!")
            return

        text = f"{EMOJI_LIST} LOGLAR:\n\n"
        for l in logs[-30:]:
            line = l[:200] if len(l) > 200 else l
            text += f"│ {line}\n"

        try:
            self.bot.edit_message_text(truncate_text(text), c.message.chat.id, c.message.message_id,
                                       reply_markup=self._ikb([(f"{EMOJI_BACK} Orqaga", f"bot_{deploy_id}")], 1))
        except Exception:
            self.bot.send_message(c.message.chat.id, truncate_text(text),
                                  reply_markup=self._ikb([(f"{EMOJI_BACK} Orqaga", f"bot_{deploy_id}")], 1))
        self.bot.answer_callback_query(c.id)

    def _stats_cmd(self, m):
        if m.from_user.id != self.owner_id:
            self.bot.reply_to(m, f"{EMOJI_LOCK} Faqat owner uchun!")
            return

        stats = self.db.get_stats_summary()
        uptime = int((datetime.now() - self._start_time).total_seconds())

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
        self.bot.reply_to(m, text)

    def _templates_cmd(self, m):
        templates = self.templates.get_template_list()
        text = f"{EMOJI_STAR} BOT SHABLONLARI\n\n"
        btns = []

        for tmpl in templates:
            text += f"{EMOJI_PAGE} {tmpl['name']}\n   {tmpl['description']}\n\n"
            btns.append([(f"{EMOJI_STAR} {tmpl['name']}", f"tmpl_{tmpl['key']}")])

        btns.append([(f"{EMOJI_BACK} Orqaga", "back_to_menu")])
        self.bot.send_message(m.chat.id, text, reply_markup=self._ikb(btns, 1))

    def _send_template(self, c, tmpl_key):
        code = self.templates.get_template_code(tmpl_key)
        if not code:
            self.bot.answer_callback_query(c.id, "Shablon topilmadi!")
            return

        temp_file = self.engine.fh.create_temp_dir('template_')
        file_path = os.path.join(temp_file, f"{tmpl_key}.py")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(code)

        try:
            with open(file_path, 'rb') as f:
                self.bot.send_document(c.message.chat.id, f, caption=f"{EMOJI_STAR} {tmpl_key}.py shabloni")
        except Exception as e:
            self.bot.send_message(c.message.chat.id, f"{EMOJI_CROSS} Fayl yuborilmadi: {e}\n\n```\n{code}\n```")
        finally:
            self.engine.fh.cleanup(temp_file)

        self.bot.answer_callback_query(c.id)

    def _send_upload_request(self, m):
        self.engine.set_user_state(m.from_user.id, STATE_AWAITING_FILE)

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
        self.bot.send_message(m.chat.id, text, reply_markup=markup)

    def _handle_file(self, m):
        uid = m.from_user.id

        if self.db.is_user_banned(uid):
            self.bot.reply_to(m, f"{EMOJI_LOCK} Siz bloklangansiz.")
            return

        state = self.engine.get_user_state(uid)
        if not state or state.get('state') != STATE_AWAITING_FILE:
            self.bot.reply_to(m, f"{EMOJI_CROSS} Avval \"{EMOJI_FILE} Fayl yuborin\" tugmasini bosing!")
            return

        if not m.document:
            self.bot.reply_to(m, f"{EMOJI_CROSS} Iltimos, fayl yuboring!")
            return

        filename = m.document.file_name or ""
        ext = os.path.splitext(filename)[1].lower()

        if ext not in ALLOWED_EXTENSIONS:
            self.bot.reply_to(m, f"{EMOJI_CROSS} Faqat .py fayllar qabul qilinadi!\nMasalan: mybot.py")
            return

        if m.document.file_size and m.document.file_size > MAX_FILE_SIZE:
            self.bot.reply_to(m, f"{EMOJI_CROSS} Fayl juda katta!\nMaksimal: {format_size(MAX_FILE_SIZE)}")
            return

        temp_dir = self.engine.fh.create_temp_dir('bot_file_')
        if not temp_dir:
            self.bot.reply_to(m, f"{EMOJI_CROSS} Vaqtinchalik papka yaratilmadi!")
            return

        file_path = os.path.join(temp_dir, safe_filename(filename))

        try:
            file_info = self.bot.get_file(m.document.file_id)
            downloaded = self.bot.download_file(file_info.file_path)
            with open(file_path, 'wb') as f:
                f.write(downloaded)
        except Exception as e:
            self.bot.reply_to(m, f"{EMOJI_CROSS} Faylni yuklab bo'lmadi: {str(e)[:80]}")
            self.engine.fh.cleanup(temp_dir)
            return

        valid, msg = self.engine.fh.validate_file(file_path)
        if not valid:
            self.bot.reply_to(m, f"{EMOJI_CROSS} {msg}")
            self.engine.fh.cleanup(temp_dir)
            return

        analysis = self.engine.ca.analyze_code(file_path)
        analysis_text = self.engine.ca.get_analysis_text(analysis)

        if not analysis['valid']:
            self.bot.reply_to(m, f"{EMOJI_CROSS} Kodda xatoliklar bor:\n\n{analysis_text}")
            self.engine.fh.cleanup(temp_dir)
            return

        self.bot.send_message(m.chat.id, f"{EMOJI_CHECK} Fayl yuklandi!\n\n{analysis_text}\n\nDavom etish uchun token yuboring.")

        self.engine.set_user_state(uid, STATE_AWAITING_TOKEN, {
            'file_path': file_path,
            'temp_dir': temp_dir,
            'analysis': analysis,
            'filename': filename,
        })

        self.bot.send_message(m.chat.id, f"{EMOJI_KEY} BOT TOKEN\n\n@BotFather dan olgan tokeningizni yuboring.")

    def _receive_token(self, m):
        uid = m.from_user.id
        state = self.engine.get_user_state(uid)

        if not state or state.get('state') != STATE_AWAITING_TOKEN:
            self.bot.reply_to(m, f"{EMOJI_CROSS} Jarayon buzildi. Qaytadan boshlang.")
            return

        token = m.text.strip().replace(' ', '').replace('\n', '')

        if not token:
            self.bot.reply_to(m, f"{EMOJI_CROSS} Token bo'sh!")
            return

        if len(token) < 30:
            self.bot.reply_to(m, f"{EMOJI_CROSS} Token juda qisqa!")
            return

        progress = self.bot.send_message(m.chat.id, f"{EMOJI_HOURGLASS} Deploy qilinmoqda...")

        try:
            result = self.engine.deploy(uid, state['data']['file_path'], token)
        except Exception as e:
            log.error(f"Deploy xatosi: {e}")
            result = (None, f"Xato: {str(e)[:100]}", None)

        temp_dir = state['data'].get('temp_dir')
        if temp_dir and os.path.exists(temp_dir):
            self.engine.fh.cleanup(temp_dir)

        deploy_id, proc_msg, analysis = result

        if deploy_id is None:
            self.bot.edit_message_text(
                f"{EMOJI_CROSS} DEPLOY MUVAFFAQIYATSIZ\n\nSabab: {proc_msg}",
                progress.chat.id, progress.message_id
            )
        else:
            filename = state['data'].get('filename', 'bot.py')
            lines = analysis['line_count'] if analysis else 0

            self.bot.edit_message_text(
                f"{EMOJI_CHECK} DEPLOY MUVAFFAQIYATLI!\n\n"
                f"{EMOJI_INFO} Bot ID: {deploy_id}\n"
                f"{EMOJI_PAGE} Fayl: {filename}\n"
                f"{EMOJI_SIZE} Qatorlar: {lines}\n\n"
                f"{EMOJI_GREEN} Bot ishga tushdi va tayyor!\n"
                f"{EMOJI_INFO} Loglarni /logs buyrug'i bilan ko'ring.",
                progress.chat.id, progress.message_id,
                reply_markup=self._ikb([(f"{EMOJI_LIST} Botni ko'rish", f"bot_{deploy_id}")], 1)
            )

        self.engine.clear_user_state(uid)

    def _cancel(self, m):
        self.engine.clear_user_state(m.from_user.id)
        self.bot.reply_to(m, f"{EMOJI_CROSS} Jarayon bekor qilindi!",
                          reply_markup=self._rkb([[f"{EMOJI_FILE} Fayl yuborin"], [f"{EMOJI_LIST} Mening botlarim"], [f"{EMOJI_QUESTION} Yordam"]]))

    def _callback(self, c):
        data = c.data

        try:
            if data == "upload_file":
                self._send_upload_request(c.message)
                self.bot.answer_callback_query(c.id)

            elif data == "back_to_bots":
                self._my_bots(c.message)
                self.bot.answer_callback_query(c.id)

            elif data == "back_to_menu":
                self._start(c.message)
                self.bot.answer_callback_query(c.id)

            elif data.startswith("bot_"):
                self._bot_details(c, data[4:])

            elif data.startswith("restart_"):
                self._bot_action(c, data[8:], "restart")

            elif data.startswith("stop_"):
                self._bot_action(c, data[5:], "stop")

            elif data.startswith("start_"):
                self._bot_action(c, data[6:], "start")

            elif data.startswith("del_"):
                self._bot_action(c, data[4:], "del")

            elif data.startswith("logs_"):
                self._show_logs(c, data[5:])

            elif data.startswith("tmpl_"):
                self._send_template(c, data[5:])

            else:
                self.bot.answer_callback_query(c.id)

        except Exception as e:
            log.error(f"Callback xatosi: {e}")
            self.bot.answer_callback_query(c.id, f"{EMOJI_CROSS} Xatolik!")

    def _handle_text(self, m):
        uid = m.from_user.id
        state = self.engine.get_user_state(uid)
        text = m.text

        if text == "/cancel":
            self._cancel(m)
            return

        if state and state.get('state') == STATE_AWAITING_TOKEN:
            self._receive_token(m)
            return

        if text == f"{EMOJI_FILE} Fayl yuborin":
            self._send_upload_request(m)
            return

        if text == f"{EMOJI_LIST} Mening botlarim":
            self._my_bots(m)
            return

        if text == f"{EMOJI_STAR} Shablonlar":
            self._templates_cmd(m)
            return

        if text == f"{EMOJI_CHART} Statistika":
            if uid == self.owner_id:
                self._stats_cmd(m)
            else:
                self.bot.reply_to(m, f"{EMOJI_LOCK} Faqat owner uchun!")
            return

        if text == f"{EMOJI_QUESTION} Yordam":
            self._help(m)
            return

        if text == f"{EMOJI_PEN} Xabar yozish":
            msg = self.bot.reply_to(m, f"{EMOJI_PEN} XABAR YOZISH\n\nBot egasiga xabar yozing:")
            self.bot.register_next_step_handler(msg, self._msg_save)
            return

        if text == f"{EMOJI_CROSS} Bekor qilish":
            self._cancel(m)
            return

        if text and text.startswith('/'):
            return

        self.bot.reply_to(m, f"{EMOJI_QUESTION} Noma'lum buyruq. Yordam uchun /help")

    def _msg_save(self, m):
        if not m.text or not m.text.strip():
            self.bot.reply_to(m, f"{EMOJI_CROSS} Xabar bo'sh!")
            return

        now = str(datetime.now())
        uid = m.from_user.id
        username = m.from_user.username or ''

        self.db.execute(
            'INSERT INTO user_messages (user_id, username, message_text, created_at, status) VALUES (?, ?, ?, ?, ?)',
            (uid, username, m.text.strip(), now, 'pending')
        )

        self.bot.reply_to(m, f"{EMOJI_CHECK} Xabar qabul qilindi!")

        try:
            self.bot.send_message(self.owner_id,
                f"{EMOJI_MESSAGE} YANGI XABAR!\n\n👤 @{username}\n🆔 {uid}\n📝 {m.text.strip()}")
        except Exception:
            pass

    def _stop_cmd(self, m):
        msg = self.bot.reply_to(m, f"{EMOJI_STOP} To'xtatmoqchi bot ID sini yuboring:")
        self.bot.register_next_step_handler(msg, self._stop_exec)

    def _stop_exec(self, m):
        did = m.text.strip()
        if not did:
            self.bot.reply_to(m, f"{EMOJI_CROSS} ID bo'sh!")
            return
        success, msg = self.engine.stop_bot(did, m.from_user.id)
        self.bot.reply_to(m, f"{EMOJI_CHECK if success else EMOJI_CROSS} {msg}")

    def _restart_cmd(self, m):
        msg = self.bot.reply_to(m, f"{EMOJI_RESTART} Qayta ishga tushirmoqchi bot ID sini yuboring:")
        self.bot.register_next_step_handler(msg, self._restart_exec)

    def _restart_exec(self, m):
        did = m.text.strip()
        if not did:
            self.bot.reply_to(m, f"{EMOJI_CROSS} ID bo'sh!")
            return
        success, msg = self.engine.restart_bot(did, m.from_user.id)
        self.bot.reply_to(m, f"{EMOJI_CHECK if success else EMOJI_CROSS} {msg}")

    def _logs_cmd(self, m):
        msg = self.bot.reply_to(m, f"{EMOJI_LIST} Loglarini ko'rishmoqchi bot ID sini yuboring:")
        self.bot.register_next_step_handler(msg, self._logs_exec)

    def _logs_exec(self, m):
        did = m.text.strip()
        if not did:
            self.bot.reply_to(m, f"{EMOJI_CROSS} ID bo'sh!")
            return
        logs = self.engine.get_logs(did, limit=30)
        if not logs:
            self.bot.reply_to(m, f"{EMOJI_LIST} Loglar yo'q!")
            return
        text = f"{EMOJI_LIST} LOGLAR:\n\n" + "\n".join(f"│ {l[:150]}" for l in logs[-30:])
        self.bot.reply_to(m, truncate_text(text))

    def _delete_cmd(self, m):
        msg = self.bot.reply_to(m, f"{EMOJI_TRASH} O'chirmoqchi bot ID sini yuboring:")
        self.bot.register_next_step_handler(msg, self._delete_exec)

    def _delete_exec(self, m):
        did = m.text.strip()
        if not did:
            self.bot.reply_to(m, f"{EMOJI_CROSS} ID bo'sh!")
            return
        success, msg = self.engine.delete_bot(did, m.from_user.id)
        self.bot.reply_to(m, f"{EMOJI_CHECK if success else EMOJI_CROSS} {msg}")

    def run(self):
        try:
            me = self.bot.get_me()
            log.info(f"Bot ishga tushdi: @{me.username}")
            print(f"{EMOJI_ROCKET} Bot ishga tushdi: @{me.username}")
            self.bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            log.error(f"Bot xatosi: {e}")

    def shutdown(self):
        log.info("Bot to'xtatilmoqda...")
        self.pm.stop_all()
        self.engine.fh.cleanup_all()
        self.db.close()
        log.info("Bot to'xtatildi")


# ================================================================
# SIGNAL HANDLER
# ================================================================

def signal_handler(signum, frame):
    log.info(f"Signal qabul qilindi: {signum}")
    if 'bot_instance' in globals():
        bot_instance.shutdown()
    sys.exit(0)


# ================================================================
# BANNER
# ================================================================

def print_banner():
    sys_info = get_system_info()
    banner = f"""
{'=' * 55}
{' ' * 15}{EMOJI_ROCKET} BOT DEPLOY BOT v4.6
{'=' * 55}

  Versiya:      4.6 (Auto-restore qo'shilgan)
  Sana:         2026-03-31
  Platform:     {sys_info['platform']} {sys_info['platform_release']}
  Python:       {sys_info['python_version']}

{'=' * 55}
  XUSUSIYATLAR:
{'=' * 55}
  {EMOJI_CHECK} Oddiy .py fayl qabul qiladi
  {EMOJI_CHECK} Kod tahlili va sifat bahosi
  {EMOJI_CHECK} Xavfli kodlarni bloklash
  {EMOJI_CHECK} Avtomatik qayta ishga tushirish
  {EMOJI_CHECK} Bot shablonlari
  {EMOJI_CHECK} Statistika va monitoring
  {EMOJI_CHECK} Windows UTF-8 qo'llab-quvvatlanadi
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

def main():
    print_banner()

    global bot_instance

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        bot_instance = DeployBot(BOT_TOKEN, OWNER_ID)
        bot_instance.run()
    except KeyboardInterrupt:
        print(f"\n{EMOJI_STOP} Bot to'xtatildi")
        if 'bot_instance' in globals():
            bot_instance.shutdown()
    except Exception as e:
        print(f"\n{EMOJI_CROSS} XATOLIK: {e}")
        traceback.print_exc()
        if 'bot_instance' in globals():
            try:
                bot_instance.shutdown()
            except:
                pass
        sys.exit(1)


if __name__ == "__main__":
    main()
