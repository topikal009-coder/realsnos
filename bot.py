import asyncio
import sqlite3
import random
import json
import os
import re
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters, ConversationHandler
)

from telethon import TelegramClient
from telethon.tl.functions.account import ReportPeerRequest
from telethon.tl.functions.contacts import AddContactRequest
from telethon.tl.types import InputReportReasonSpam, InputPhoneContact
from telethon.errors import (
    FloodWaitError, PeerFloodError, SessionPasswordNeededError,
    PhoneCodeInvalidError, PhoneCodeExpiredError, PhoneNumberInvalidError,
    PhoneNumberBannedError, ApiIdInvalidError, AccessTokenInvalidError,
    PhoneCodeEmptyError, PhoneCodeHashEmptyError
)

import aiohttp

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== НАСТРОЙКИ ПУТЕЙ ====================
def get_data_dir():
    railway_volume = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", "")
    if railway_volume and os.path.exists(railway_volume) and os.access(railway_volume, os.W_OK):
        return railway_volume
    for path in ["/data", "/app/data"]:
        if os.path.exists(path) and os.access(path, os.W_OK):
            return path
    local_data = os.path.join(os.getcwd(), "data")
    os.makedirs(local_data, exist_ok=True)
    return local_data

DATA_DIR = get_data_dir()
SESSIONS_DIR = os.path.join(DATA_DIR, "sessions")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(SESSIONS_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "users.db")
MODERATORS_FILE = os.path.join(DATA_DIR, "moderators.json")
USERS_FILE = os.path.join(DATA_DIR, "users_list.json")
REPORTER_ACCOUNTS_FILE = os.path.join(DATA_DIR, "reporter_accounts.json")

logger.info(f"📁 Директория данных: {DATA_DIR}")

# ==================== КОНФИГУРАЦИЯ ====================
BOT_TOKEN = "8740017892:AAF2DDdjZvOiCjug7XvMUyIoO76YSmP-JSE"
CRYPTO_PAY_TOKEN = "563714:AAoNQWxKCzZLDkotn5jjJdl0QFwMCAtEbtD"
CRYPTO_PAY_TESTNET = False

ADMIN_IDS = [964442694]

REQUIRED_CHANNEL_INVITE = "https://t.me/+vOgz5RQNSmE5OGE0"
REQUIRED_CHANNEL_USERNAME = None
REQUIRED_CHANNEL_ID = None

PHONE, API_ID, API_HASH, CODE, PASSWORD = range(5)

SUBSCRIPTIONS = {
    "starter": {"reports": 5, "price": 14.99, "emoji": "🔹", "name": "Starter"},
    "standard": {"reports": 15, "price": 29.99, "emoji": "⭐", "name": "Standard"},
    "pro": {"reports": 40, "price": 59.99, "emoji": "🚀", "name": "Pro"},
    "premium": {"reports": 80, "price": 99.99, "emoji": "🏆", "name": "Premium"},
    "vip": {"reports": 150, "price": 149.99, "emoji": "💎", "name": "VIP / Custom"}
}

TEXTS = {
    "ru": {
        "welcome": "🌟 *Добро пожаловать в Report Bot!* 🌟\n\n👇 *Выберите действие:*",
        "profile": "👤 *Мой профиль*\n\n🆔 ID: `{}`\n👑 Роль: {}\n💥 Доступно сносов: *{}*\n📊 Всего куплено: *{}*\n📤 Всего использовано: *{}*\n\n🎫 Активные подписки:\n{}",
        "btn_shop": "🛒 Магазин",
        "btn_profile": "👤 Профиль",
        "btn_start_report": "🎯 Начать снос",
        "btn_history": "📜 История",
        "btn_admin_panel": "👑 Админ панель",
        "btn_back": "🔙 Назад",
        "btn_language": "🌐 Сменить язык",
        "btn_stop": "⏹️ Стоп",
        "no_active_subs": "Нет активных подписок",
        "target_username": "📝 *Введите username цели:*\n\nПример: @username или t.me/username",
        "confirm_report": "🎯 *Подтверждение сноса*\n\nЦель: @{}\nОстанется сносов: {}\n\n✅ Подтверждаете?",
        "no_reports_left": "❌ *Нет сносов!*\n\nКупите подписку в магазине.",
        "buy_subscription": "🛒 *Магазин подписок*\n\n💼 *Прайс:*\n🔹 Starter — $14.99 (5 сносов)\n⭐ Standard — $29.99 (15 сносов)\n🚀 Pro — $59.99 (40 сносов)\n🏆 Premium — $99.99 (80 сносов)\n💎 VIP — от $149+\n\nВыберите подписку:",
        "purchase_success": "✅ *Покупка успешна!*\n\n📦 {}\n🎁 Получено: {} сносов\n💰 Цена: ${}\n\n💥 Всего сносов: {}",
        "history_empty": "📜 *История*\n\nУ вас пока нет операций.",
        "history": "📜 *История операций*\n\n{}",
        "crypto_payment": "🧾 *Оплата через CryptoPay*\n\n💰 Сумма: ${}\n🆔 Invoice: `{}`\n\n💳 Нажмите на кнопку ниже для оплаты",
        "check_payment": "✅ Проверить оплату",
        "payment_error": "❌ Ошибка при создании счета: {}",
        "payment_not_found": "❌ Платеж не найден",
        "sending_reports": "🚀 *Отправка жалоб*\n\n🎯 Цель: @{}\n📊 Прогресс: {}%\n┗━━━━━━━━━━━━━━━━━━━━┛\n█{}█\n\n📨 Отправлено: {} / {}\n\n⏳ Пожалуйста, подождите...",
        "send_success": "✅ *Готово!*\n\n🎯 Цель: @{}\n✅ Успешно отправлено: *{}* / {}\n❌ Ошибок: *{}*\n👥 Запросов на вход: {}\n👥 Использовано аккаунтов: {}\n💥 Осталось сносов: {}",
        "send_stopped": "⏹️ *Отправка остановлена!*\n\n🎯 Цель: @{}\n✅ Успешно отправлено: *{}* / {}\n❌ Ошибок: *{}*\n👥 Запросов на вход: {}\n👥 Использовано аккаунтов: {}\n💥 Осталось сносов: {}",
        "role_user": "👤 Пользователь",
        "role_moder": "🛡️ Модератор",
        "role_admin": "👑 Администратор",
        "admin_give_subscription": "🎫 *Выдача подписки*\n\nВыберите подписку:",
        "subscription_given": "✅ *Подписка выдана!*\n\nПользователь {} получил {} (+{} сносов)",
        "admin_users": "📊 *Список пользователей*\n\n",
        "admin_stats": "📈 *Статистика*\n\n",
        "admin_change_reports": "💰 *Изменение количества сносов*",
        "user_not_found": "❌ Пользователь не найден",
        "no_access": "❌ У вас нет доступа!",
        "error": "❌ Ошибка: {}",
        "must_subscribe": "❌ *Доступ запрещён!*\n\nДля использования бота необходимо подписаться на наш канал:\n👉 [Нажмите здесь, чтобы подписаться]({})\n\nПосле подписки нажмите /start снова.",
        "enter_phone": "📱 *Введите номер телефона*\n\nВ формате: `+380XXXXXXXXX`\n\nДля отмены введите /cancel",
        "enter_api_id": "🔑 *Введите API ID*\n\nПолучить можно на https://my.telegram.org/apps\n\nДля отмены введите /cancel",
        "enter_api_hash": "🔐 *Введите API Hash*\n\nПолучить можно на https://my.telegram.org/apps\n\nДля отмены введите /cancel",
        "enter_code": "📨 *Введите код подтверждения*\n\nКод отправлен в Telegram (проверьте приложение)\n\nЕсли код не приходит, попробуйте войти в приложение Telegram на телефоне\n\nДля отмены введите /cancel",
        "enter_2fa": "🔐 *Введите пароль двухфакторной аутентификации*\n\nДля отмены введите /cancel",
        "session_created": "✅ *Сессия создана!*\n\nАккаунт {} успешно добавлен.\nID аккаунта: {}\n\nТеперь аккаунт готов к использованию.",
        "cancel": "❌ *Действие отменено*",
        "sending_code": "🔄 Отправка кода подтверждения...",
        "connecting": "🔄 Подключение к Telegram...",
        "invalid_phone": "❌ Неверный номер телефона",
        "invalid_api_id": "❌ Неверный API ID",
        "code_sent": "✅ Код подтверждения отправлен в Telegram!\n\nПроверьте приложение Telegram на телефоне",
        "already_authorized": "✅ Аккаунт уже авторизован!\n\nСессия создана, можно использовать."
    },
    "uk": {
        "welcome": "🌟 *Ласкаво просимо!* 🌟\n\n👇 *Оберіть дію:*",
        "profile": "👤 *Мій профіль*\n\n🆔 ID: `{}`\n👑 Роль: {}\n💥 Доступно сносів: *{}*\n📊 Всього куплено: *{}*\n📤 Всього використано: *{}*\n\n🎫 Активні підписки:\n{}",
        "btn_shop": "🛒 Магазин",
        "btn_profile": "👤 Профіль",
        "btn_start_report": "🎯 Почати снос",
        "btn_history": "📜 Історія",
        "btn_admin_panel": "👑 Адмін панель",
        "btn_back": "🔙 Назад",
        "btn_language": "🌐 Змінити мову",
        "btn_stop": "⏹️ Стоп",
        "no_active_subs": "Немає активних підписок",
        "target_username": "📝 *Введіть username цілі:*\n\nПриклад: @username або t.me/username",
        "confirm_report": "🎯 *Підтвердження сносу*\n\nЦіль: @{}\nЗалишиться сносів: {}\n\n✅ Підтверджуєте?",
        "no_reports_left": "❌ *Немає сносів!*\n\nКупіть підписку в магазині.",
        "buy_subscription": "🛒 *Магазин підписок*\n\n💼 *Прайс:*\n🔹 Starter — $14.99 (5 сносов.)\n⭐ Standard — $29.99 (15 сносов.)\n🚀 Pro — $59.99 (40 сносов.)\n🏆 Premium — $99.99 (80 сносов.)\n💎 VIP — від $149+\n\nВиберіть підписку:",
        "purchase_success": "✅ *Покупка успішна!*\n\n📦 {}\n🎁 Отримано: {} сносів\n💰 Ціна: ${}\n\n💥 Всього сносів: {}",
        "history_empty": "📜 *Історія*\n\nУ вас поки що немає операцій.",
        "history": "📜 *Історія операцій*\n\n{}",
        "crypto_payment": "🧾 *Оплата через CryptoPay*\n\n💰 Сума: ${}\n🆔 Invoice: `{}`\n\n💳 Натисніть на кнопку нижче для оплати",
        "check_payment": "✅ Перевірити оплату",
        "payment_error": "❌ Помилка при створенні рахунку: {}",
        "payment_not_found": "❌ Платіж не знайдено",
        "sending_reports": "🚀 *Відправка скарг*\n\n🎯 Ціль: @{}\n📊 Прогрес: {}%\n┗━━━━━━━━━━━━━━━━━━━━┛\n█{}█\n\n📨 Відправлено: {} / {}\n\n⏳ Будь ласка, зачекайте...",
        "send_success": "✅ *Готово!*\n\n🎯 Ціль: @{}\n✅ Успішно відправлено: *{}* / {}\n❌ Помилок: *{}*\n👥 Запитів на вхід: {}\n👥 Використано акаунтів: {}\n💥 Залишилось сносів: {}",
        "send_stopped": "⏹️ *Відправку зупинено!*\n\n🎯 Ціль: @{}\n✅ Успішно відправлено: *{}* / {}\n❌ Помилок: *{}*\n👥 Запитів на вхід: {}\n👥 Використано акаунтів: {}\n💥 Залишилось сносів: {}",
        "role_user": "👤 Користувач",
        "role_moder": "🛡️ Модератор",
        "role_admin": "👑 Адміністратор",
        "admin_give_subscription": "🎫 *Видача підписки*\n\nВиберіть підписку:",
        "subscription_given": "✅ *Підписка видана!*\n\nКористувач {} отримав {} (+{} сносів)",
        "admin_users": "📊 *Список користувачів*\n\n",
        "admin_stats": "📈 *Статистика*\n\n",
        "admin_change_reports": "💰 *Зміна кількості сносів*",
        "user_not_found": "❌ Користувача не знайдено",
        "no_access": "❌ У вас немає доступу!",
        "error": "❌ Помилка: {}",
        "must_subscribe": "❌ *Доступ заборонено!*\n\nДля використання бота необхідно підписатися на наш канал:\n👉 [Натисніть тут, щоб підписатися]({})\n\nПісля підписки натисніть /start знову.",
        "enter_phone": "📱 *Введіть номер телефону*\n\nУ форматі: `+380XXXXXXXXX`\n\nДля скасування введіть /cancel",
        "enter_api_id": "🔑 *Введіть API ID*\n\nОтримати можна на https://my.telegram.org/apps\n\nДля скасування введіть /cancel",
        "enter_api_hash": "🔐 *Введіть API Hash*\n\nОтримати можна на https://my.telegram.org/apps\n\nДля скасування введіть /cancel",
        "enter_code": "📨 *Введіть код підтвердження*\n\nКод надіслано в Telegram (перевірте додаток)\n\nЯкщо код не приходить, спробуйте увійти в додаток Telegram на телефоні\n\nДля скасування введіть /cancel",
        "enter_2fa": "🔐 *Введіть пароль двофакторної аутентифікації*\n\nДля скасування введіть /cancel",
        "session_created": "✅ *Сесію створено!*\n\nАкаунт {} успішно додано.\nID акаунта: {}\n\nТепер акаунт готовий до використання.",
        "cancel": "❌ *Дію скасовано*",
        "sending_code": "🔄 Відправка коду підтвердження...",
        "connecting": "🔄 Підключення до Telegram...",
        "invalid_phone": "❌ Невірний номер телефону",
        "invalid_api_id": "❌ Невірний API ID",
        "code_sent": "✅ Код підтвердження надіслано в Telegram!\n\nПеревірте додаток Telegram на телефоні",
        "already_authorized": "✅ Акаунт вже авторизовано!\n\nСесію створено, можна використовувати."
    },
    "en": {
        "welcome": "🌟 *Welcome!* 🌟\n\n👇 *Choose an action:*",
        "profile": "👤 *My profile*\n\n🆔 ID: `{}`\n👑 Role: {}\n💥 Reports left: *{}*\n📊 Total purchased: *{}*\n📤 Total used: *{}*\n\n🎫 Active subscriptions:\n{}",
        "btn_shop": "🛒 Shop",
        "btn_profile": "👤 Profile",
        "btn_start_report": "🎯 Start report",
        "btn_history": "📜 History",
        "btn_admin_panel": "👑 Admin panel",
        "btn_back": "🔙 Back",
        "btn_language": "🌐 Change language",
        "btn_stop": "⏹️ Stop",
        "no_active_subs": "No active subscriptions",
        "target_username": "📝 *Enter target username:*\n\nExample: @username or t.me/username",
        "confirm_report": "🎯 *Confirm report*\n\nTarget: @{}\nReports left: {}\n\n✅ Confirm?",
        "no_reports_left": "❌ *No reports left!*\n\nBuy a subscription in the shop.",
        "buy_subscription": "🛒 *Subscription shop*\n\n💼 *Pricing:*\n🔹 Starter — $14.99 (5 rep.)\n⭐ Standard — $29.99 (15 rep.)\n🚀 Pro — $59.99 (40 rep.)\n🏆 Premium — $99.99 (80 rep.)\n💎 VIP — from $149+\n\nChoose a subscription:",
        "purchase_success": "✅ *Purchase successful!*\n\n📦 {}\n🎁 Received: {} reports\n💰 Price: ${}\n\n💥 Total reports: {}",
        "history_empty": "📜 *History*\n\nNo transactions yet.",
        "history": "📜 *Transaction history*\n\n{}",
        "crypto_payment": "🧾 *Payment via CryptoPay*\n\n💰 Amount: ${}\n🆔 Invoice: `{}`\n\n💳 Click the button below to pay",
        "check_payment": "✅ Check payment",
        "payment_error": "❌ Error creating invoice: {}",
        "payment_not_found": "❌ Payment not found",
        "sending_reports": "🚀 *Sending reports*\n\n🎯 Target: @{}\n📊 Progress: {}%\n┗━━━━━━━━━━━━━━━━━━━━┛\n█{}█\n\n📨 Sent: {} / {}\n\n⏳ Please wait...",
        "send_success": "✅ *Done!*\n\n🎯 Target: @{}\n✅ Successfully sent: *{}* / {}\n❌ Failed: *{}*\n👥 Contact requests: {}\n👥 Accounts used: {}\n💥 Reports left: {}",
        "send_stopped": "⏹️ *Stopped!*\n\n🎯 Target: @{}\n✅ Successfully sent: *{}* / {}\n❌ Failed: *{}*\n👥 Contact requests: {}\n👥 Accounts used: {}\n💥 Reports left: {}",
        "role_user": "👤 User",
        "role_moder": "🛡️ Moderator",
        "role_admin": "👑 Administrator",
        "admin_give_subscription": "🎫 *Give subscription*\n\nChoose a subscription:",
        "subscription_given": "✅ *Subscription given!*\n\nUser {} received {} (+{} reports)",
        "admin_users": "📊 *User list*\n\n",
        "admin_stats": "📈 *Statistics*\n\n",
        "admin_change_reports": "💰 *Change reports count*",
        "user_not_found": "❌ User not found",
        "no_access": "❌ Access denied!",
        "error": "❌ Error: {}",
        "must_subscribe": "❌ *Access denied!*\n\nYou must subscribe to our channel to use this bot:\n👉 [Click here to subscribe]({})\n\nAfter subscribing, press /start again.",
        "enter_phone": "📱 *Enter phone number*\n\nFormat: `+380XXXXXXXXX`\n\nTo cancel, type /cancel",
        "enter_api_id": "🔑 *Enter API ID*\n\nGet it at https://my.telegram.org/apps\n\nTo cancel, type /cancel",
        "enter_api_hash": "🔐 *Enter API Hash*\n\nGet it at https://my.telegram.org/apps\n\nTo cancel, type /cancel",
        "enter_code": "📨 *Enter confirmation code*\n\nCode sent to Telegram (check the app)\n\nIf code doesn't arrive, try logging into Telegram app on your phone\n\nTo cancel, type /cancel",
        "enter_2fa": "🔐 *Enter 2FA password*\n\nTo cancel, type /cancel",
        "session_created": "✅ *Session created!*\n\nAccount {} successfully added.\nAccount ID: {}\n\nAccount is now ready to use.",
        "cancel": "❌ *Action cancelled*",
        "sending_code": "🔄 Sending confirmation code...",
        "connecting": "🔄 Connecting to Telegram...",
        "invalid_phone": "❌ Invalid phone number",
        "invalid_api_id": "❌ Invalid API ID",
        "code_sent": "✅ Confirmation code sent to Telegram!\n\nCheck the Telegram app on your phone",
        "already_authorized": "✅ Account already authorized!\n\nSession created, ready to use."
    }
}

class Database:
    def __init__(self, db_path: str = None):
        self.db_path = db_path if db_path else DB_PATH
        self._init_db()
    
    def _init_db(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, reports INTEGER DEFAULT 0, total_purchased INTEGER DEFAULT 0, total_used INTEGER DEFAULT 0, language TEXT DEFAULT 'ru')")
                c.execute("CREATE TABLE IF NOT EXISTS subscriptions (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, sub_type TEXT, reports_limit INTEGER, reports_used INTEGER DEFAULT 0, active INTEGER DEFAULT 1, purchased_at TIMESTAMP)")
                c.execute("CREATE TABLE IF NOT EXISTS purchases (purchase_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, item_type TEXT, item_name TEXT, reports_added INTEGER, price REAL, purchased_at TIMESTAMP)")
                c.execute("CREATE TABLE IF NOT EXISTS report_usage (usage_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, target TEXT, used_at TIMESTAMP)")
                c.execute("CREATE TABLE IF NOT EXISTS payment_sessions (user_id INTEGER PRIMARY KEY, invoice_id INTEGER, item_type TEXT, item_key TEXT, amount REAL, created_at TIMESTAMP, expires_at TIMESTAMP)")
                conn.commit()
                logger.info(f"✅ База данных инициализирована: {self.db_path}")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации БД: {e}")
            raise
    
    def get_user(self, user_id: int):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
                row = c.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Ошибка get_user: {e}")
            return None
    
    def get_all_users(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                c.execute("SELECT user_id, reports, total_purchased, total_used, language FROM users")
                return [dict(row) for row in c.fetchall()]
        except Exception as e:
            logger.error(f"Ошибка get_all_users: {e}")
            return []
    
    def create_user(self, user_id: int, lang='ru'):
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute("INSERT INTO users (user_id, language) VALUES (?, ?)", (user_id, lang))
                conn.commit()
                return self.get_user(user_id)
        except Exception as e:
            logger.error(f"Ошибка create_user: {e}")
            return None
    
    def get_or_create_user(self, user_id: int):
        user = self.get_user(user_id)
        if not user:
            user = self.create_user(user_id)
        return user
    
    def update_language(self, user_id: int, lang: str):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("UPDATE users SET language = ? WHERE user_id = ?", (lang, user_id))
            conn.commit()
    
    def add_reports(self, user_id: int, amount: int, item_name: str, price: float):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("UPDATE users SET reports = reports + ?, total_purchased = total_purchased + ? WHERE user_id = ?", (amount, amount, user_id))
            c.execute("INSERT INTO purchases (user_id, item_type, item_name, reports_added, price, purchased_at) VALUES (?, 'subscription', ?, ?, ?, ?)", (user_id, item_name, amount, price, datetime.now()))
            conn.commit()
    
    def use_report(self, user_id: int, target: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("SELECT reports FROM users WHERE user_id = ?", (user_id,))
            row = c.fetchone()
            if not row or row[0] <= 0:
                return False
            c.execute("UPDATE users SET reports = reports - 1, total_used = total_used + 1 WHERE user_id = ?", (user_id,))
            c.execute("INSERT INTO report_usage (user_id, target, used_at) VALUES (?, ?, ?)", (user_id, target, datetime.now()))
            conn.commit()
            return True
    
    def add_subscription(self, user_id: int, sub_type: str, reports_limit: int, price: float = 0):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("INSERT INTO subscriptions (user_id, sub_type, reports_limit, active, purchased_at) VALUES (?, ?, ?, 1, ?)", (user_id, sub_type, reports_limit, datetime.now()))
            c.execute("UPDATE users SET reports = reports + ?, total_purchased = total_purchased + ? WHERE user_id = ?", (reports_limit, reports_limit, user_id))
            if price > 0:
                sub_name = SUBSCRIPTIONS[sub_type]['name']
                c.execute("INSERT INTO purchases (user_id, item_type, item_name, reports_added, price, purchased_at) VALUES (?, 'subscription', ?, ?, ?, ?)", (user_id, sub_name, reports_limit, price, datetime.now()))
            conn.commit()
    
    def get_active_subscriptions(self, user_id: int) -> List[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT * FROM subscriptions WHERE user_id = ? AND active = 1 ORDER BY purchased_at DESC", (user_id,))
            return [dict(row) for row in c.fetchall()]
    
    def get_user_purchases(self, user_id: int, limit=10):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT * FROM purchases WHERE user_id = ? ORDER BY purchased_at DESC LIMIT ?", (user_id, limit))
            return [dict(row) for row in c.fetchall()]
    
    def get_user_usage(self, user_id: int, limit=10):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT * FROM report_usage WHERE user_id = ? ORDER BY used_at DESC LIMIT ?", (user_id, limit))
            return [dict(row) for row in c.fetchall()]
    
    def save_payment_session(self, user_id: int, invoice_id: int, item_type: str, item_key: str, amount: float, expires=1800):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            exp = datetime.now() + timedelta(seconds=expires)
            c.execute("INSERT OR REPLACE INTO payment_sessions (user_id, invoice_id, item_type, item_key, amount, created_at, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?)", (user_id, invoice_id, item_type, item_key, amount, datetime.now(), exp))
            conn.commit()
    
    def get_payment_session(self, user_id: int):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT * FROM payment_sessions WHERE user_id = ? AND expires_at > ?", (user_id, datetime.now()))
            row = c.fetchone()
            return dict(row) if row else None
    
    def delete_payment_session(self, user_id: int):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("DELETE FROM payment_sessions WHERE user_id = ?", (user_id,))
            conn.commit()
    
    def set_reports_direct(self, user_id: int, new_reports: int):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("UPDATE users SET reports = ? WHERE user_id = ?", (new_reports, user_id))
            conn.commit()

db = Database()

class CryptoPayClient:
    def __init__(self, api_token: str, testnet=False):
        self.token = api_token
        self.url = "https://testnet-pay.crypt.bot/api" if testnet else "https://pay.crypt.bot/api"
    
    async def _req(self, method: str, params=None):
        async with aiohttp.ClientSession() as sess:
            async with sess.post(f"{self.url}/{method}", headers={"Crypto-Pay-API-Token": self.token, "Content-Type": "application/json"}, json=params or {}) as resp:
                data = await resp.json()
                if not data.get("ok"):
                    raise Exception(data.get("error"))
                return data["result"]
    
    async def create_invoice(self, asset: str, amount: str, desc=None, payload=None, expires=1800):
        p = {"asset": asset, "amount": str(amount), "expires_in": expires}
        if desc: p["description"] = desc
        if payload: p["payload"] = payload
        return await self._req("createInvoice", p)
    
    async def get_invoices(self, ids: list):
        if not ids: return {"items": []}
        return await self._req("getInvoices", {"invoice_ids": ",".join(map(str, ids))})

crypto = CryptoPayClient(CRYPTO_PAY_TOKEN, testnet=CRYPTO_PAY_TESTNET)

def load_reporter_accounts():
    if os.path.exists(REPORTER_ACCOUNTS_FILE):
        with open(REPORTER_ACCOUNTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_reporter_accounts(accounts):
    with open(REPORTER_ACCOUNTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(accounts, f, ensure_ascii=False, indent=2)

class ReporterManager:
    def __init__(self):
        self.clients = {}
        self.status = {}
        self.by_id = {}
        self.load_accounts()
    
    def load_accounts(self):
        accounts = load_reporter_accounts()
        self.by_id = {a["id"]: a for a in accounts}
        self.status = {}
        for a in accounts:
            self.status[a["id"]] = {
                "phone": a["phone"],
                "is_active": a.get("is_active", True),
                "reports_today": a.get("reports_today", 0),
                "max_reports": a.get("max_reports_per_day", 50),
                "client": None
            }
    
    async def connect(self, acc_id: int):
        acc = self.by_id.get(acc_id)
        if not acc: return False
        os.makedirs(SESSIONS_DIR, exist_ok=True)
        cl = TelegramClient(acc["session_file"], acc["api_id"], acc["api_hash"], proxy=acc.get("proxy"))
        try:
            await cl.start()
            self.clients[acc_id] = cl
            self.status[acc_id]["client"] = cl
            self.status[acc_id]["is_connected"] = True
            logger.info(f"✓ {acc['phone']} подключен")
            return True
        except Exception as e:
            logger.error(f"✗ {acc['phone']}: {e}")
            return False
    
    async def send_report(self, acc_id: int, target: str) -> bool:
        cl = self.clients.get(acc_id)
        if not cl: return False
        try:
            entity = await cl.get_entity(target)
            await cl(ReportPeerRequest(peer=entity, reason=InputReportReasonSpam(), message="Жалоба на спам"))
            self.status[acc_id]["reports_today"] += 1
            return True
        except (FloodWaitError, PeerFloodError):
            self.status[acc_id]["is_active"] = False
            return False
        except:
            return False
    
    async def send_contact(self, acc_id: int, target: str) -> bool:
        cl = self.clients.get(acc_id)
        if not cl: return False
        try:
            entity = await cl.get_entity(target)
            if hasattr(entity, 'phone') and entity.phone:
                contact = InputPhoneContact(client_id=0, phone=entity.phone, first_name=entity.first_name or "", last_name=entity.last_name or "")
                await cl(AddContactRequest(contact))
                return True
            else:
                await cl.send_message(entity, "Привет! 👋")
                return True
        except:
            return False
    
    async def mass_report(self, target: str, count: int, on_progress=None, stop_flag=None):
        results = {"accepted": 0, "rejected": 0, "contact_sent": 0, "accounts_used": []}
        active = [aid for aid, st in self.status.items() if st.get("is_active", False) and st.get("reports_today", 0) < st.get("max_reports", 50)]
        if not active:
            return results
        sent = 0
        idx = 0
        while sent < count and active:
            if stop_flag and stop_flag():
                break
            aid = active[idx % len(active)]
            batch = random.randint(1, 2)
            for _ in range(min(batch, count - sent)):
                if stop_flag and stop_flag():
                    break
                ok = await self.send_report(aid, target)
                if ok:
                    results["accepted"] += 1
                    sent += 1
                    if aid not in results["accounts_used"]:
                        results["accounts_used"].append(aid)
                else:
                    results["rejected"] += 1
                if random.random() < 0.5:
                    if await self.send_contact(aid, target):
                        results["contact_sent"] += 1
                await asyncio.sleep(random.uniform(2, 4))
            if on_progress:
                await on_progress(sent, count)
            await asyncio.sleep(random.uniform(3, 5))
            idx += 1
            active = [aid for aid, st in self.status.items() if st.get("is_active", False) and st.get("reports_today", 0) < st.get("max_reports", 50)]
        return results

reporter = ReporterManager()

def load_moderators():
    if os.path.exists(MODERATORS_FILE):
        with open(MODERATORS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_moderators(mods):
    with open(MODERATORS_FILE, 'w', encoding='utf-8') as f:
        json.dump(mods, f, ensure_ascii=False, indent=2)

def load_users_list():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_users_list(users):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def get_user_role(uid):
    if uid in ADMIN_IDS: return "admin"
    if uid in load_moderators(): return "moder"
    return "user"

def is_admin_or_mod(uid):
    return uid in ADMIN_IDS or uid in load_moderators()

def get_text(uid, key, *args):
    user = db.get_user(uid)
    lang = user['language'] if user else 'ru'
    txt = TEXTS.get(lang, TEXTS['ru']).get(key, TEXTS['ru'][key])
    return txt.format(*args) if args else txt

def active_subs_text(uid):
    subs = db.get_active_subscriptions(uid)
    if not subs:
        return get_text(uid, "no_active_subs")
    res = ""
    for s in subs:
        remaining = s['reports_limit'] - s['reports_used']
        name = SUBSCRIPTIONS.get(s['sub_type'], {}).get('name', s['sub_type'])
        res += f"• {name}: {remaining}/{s['reports_limit']}\n"
    return res

def extract_username(txt):
    txt = txt.strip()
    if txt.startswith('@'): txt = txt[1:]
    if 't.me/' in txt:
        m = re.search(r't\.me/([^/?]+)', txt)
        if m: return m.group(1)
    return txt

def valid_username(u):
    return u and 3 <= len(u) <= 32 and not re.search(r'[\s<>{}[\]\\]', u)

async def check_subscription(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        if REQUIRED_CHANNEL_USERNAME:
            channel = await context.bot.get_chat(f"@{REQUIRED_CHANNEL_USERNAME}")
        elif REQUIRED_CHANNEL_ID:
            channel = await context.bot.get_chat(REQUIRED_CHANNEL_ID)
        else:
            return True
        member = await context.bot.get_chat_member(chat_id=channel.id, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.error(f"Ошибка проверки подписки: {e}")
        return True

async def main_keyboard(uid):
    btns = [
        [InlineKeyboardButton(get_text(uid, "btn_shop"), callback_data="shop")],
        [InlineKeyboardButton(get_text(uid, "btn_profile"), callback_data="profile")],
        [InlineKeyboardButton(get_text(uid, "btn_start_report"), callback_data="start_report")],
        [InlineKeyboardButton(get_text(uid, "btn_language"), callback_data="lang")]
    ]
    if is_admin_or_mod(uid):
        btns.append([InlineKeyboardButton(get_text(uid, "btn_admin_panel"), callback_data="admin_panel")])
    return InlineKeyboardMarkup(btns)

async def shop_keyboard(uid):
    kb = []
    for sid, sub in SUBSCRIPTIONS.items():
        kb.append([InlineKeyboardButton(f"{sub['emoji']} {sub['name']} - ${sub['price']} ({sub['reports']} сносов)", callback_data=f"buy_{sid}")])
    kb.append([InlineKeyboardButton(get_text(uid, "btn_back"), callback_data="main")])
    return InlineKeyboardMarkup(kb)

async def admin_keyboard(uid):
    kb = [
        [InlineKeyboardButton("📊 Пользователи", callback_data="admin_users")],
        [InlineKeyboardButton("💰 Изменить сносы", callback_data="admin_reports")],
        [InlineKeyboardButton("🎫 Выдать подписку", callback_data="admin_give")],
        [InlineKeyboardButton("📈 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton("➕ Добавить модератора", callback_data="admin_add_mod")],
        [InlineKeyboardButton("➖ Удалить модератора", callback_data="admin_rem_mod")],
        [InlineKeyboardButton("🔚 Выйти", callback_data="admin_exit")],
        [InlineKeyboardButton(get_text(uid, "btn_back"), callback_data="main")]
    ]
    return InlineKeyboardMarkup(kb)

async def lang_keyboard(uid):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru")],
        [InlineKeyboardButton("🇺🇦 Українська", callback_data="lang_uk")],
        [InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")],
        [InlineKeyboardButton(get_text(uid, "btn_back"), callback_data="main")]
    ])

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not await check_subscription(uid, ctx):
        text = get_text(uid, "must_subscribe", REQUIRED_CHANNEL_INVITE)
        await update.message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)
        return
    
    db.get_or_create_user(uid)
    users = load_users_list()
    if str(uid) not in users:
        users[str(uid)] = {"id": uid, "username": update.effective_user.username, "first_name": update.effective_user.first_name, "joined_at": str(datetime.now())}
        save_users_list(users)
    await update.message.reply_text(get_text(uid, "welcome"), parse_mode="Markdown", reply_markup=await main_keyboard(uid))

async def add_account_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in ADMIN_IDS:
        await update.message.reply_text(get_text(uid, "no_access"))
        return ConversationHandler.END
    
    await update.message.reply_text(get_text(uid, "enter_phone"), parse_mode="Markdown")
    return PHONE

async def add_account_phone(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    phone = update.message.text.strip()
    
    if phone == "/cancel":
        await update.message.reply_text(get_text(uid, "cancel"), parse_mode="Markdown")
        return ConversationHandler.END
    
    if not phone.startswith('+') or not phone[1:].replace('+', '').isdigit():
        await update.message.reply_text(get_text(uid, "invalid_phone"))
        return PHONE
    
    ctx.user_data["add_phone"] = phone
    await update.message.reply_text(get_text(uid, "enter_api_id"), parse_mode="Markdown")
    return API_ID

async def add_account_api_id(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text.strip()
    
    if text == "/cancel":
        await update.message.reply_text(get_text(uid, "cancel"), parse_mode="Markdown")
        return ConversationHandler.END
    
    try:
        api_id = int(text)
        ctx.user_data["add_api_id"] = api_id
        await update.message.reply_text(get_text(uid, "enter_api_hash"), parse_mode="Markdown")
        return API_HASH
    except ValueError:
        await update.message.reply_text(get_text(uid, "invalid_api_id"))
        return API_ID

async def add_account_api_hash(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    api_hash = update.message.text.strip()
    
    if api_hash == "/cancel":
        await update.message.reply_text(get_text(uid, "cancel"), parse_mode="Markdown")
        return ConversationHandler.END
    
    ctx.user_data["add_api_hash"] = api_hash
    
    status_msg = await update.message.reply_text(get_text(uid, "connecting"), parse_mode="Markdown")
    
    phone = ctx.user_data["add_phone"]
    api_id = ctx.user_data["add_api_id"]
    api_hash = ctx.user_data["add_api_hash"]
    session_file = os.path.join(SESSIONS_DIR, f"acc_{phone.replace('+', '')}")
    
    client = TelegramClient(session_file, api_id, api_hash)
    
    try:
        await client.connect()
        
        # Проверяем, не авторизован ли уже аккаунт
        if await client.is_user_authorized():
            await client.disconnect()
            await status_msg.edit_text(get_text(uid, "already_authorized"), parse_mode="Markdown")
            
            # Сохраняем аккаунт
            accounts = load_reporter_accounts()
            next_id = max([acc.get("id", 0) for acc in accounts], default=0) + 1
            
            new_acc = {
                "id": next_id,
                "phone": phone,
                "api_id": api_id,
                "api_hash": api_hash,
                "session_file": session_file,
                "proxy": None,
                "is_active": True,
                "reports_today": 0,
                "max_reports_per_day": 50
            }
            accounts.append(new_acc)
            save_reporter_accounts(accounts)
            reporter.load_accounts()
            await reporter.connect(next_id)
            
            return ConversationHandler.END
        
        # Отправляем запрос кода
        await status_msg.edit_text(get_text(uid, "sending_code"), parse_mode="Markdown")
        
        result = await client.send_code_request(phone)
        # Сохраняем phone_code_hash для следующего шага
        ctx.user_data["add_phone_code_hash"] = result.phone_code_hash
        ctx.user_data["add_session_file"] = session_file
        
        await client.disconnect()
        
        await status_msg.edit_text(get_text(uid, "code_sent"), parse_mode="Markdown")
        await status_msg.edit_text(get_text(uid, "enter_code"), parse_mode="Markdown")
        return CODE
        
    except Exception as e:
        await status_msg.edit_text(f"❌ Ошибка: {str(e)}\n\nНачните заново: /add_account")
        return ConversationHandler.END

async def add_account_code(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    code = update.message.text.strip()
    
    if code == "/cancel":
        await update.message.reply_text(get_text(uid, "cancel"), parse_mode="Markdown")
        return ConversationHandler.END
    
    phone = ctx.user_data.get("add_phone")
    api_id = ctx.user_data.get("add_api_id")
    api_hash = ctx.user_data.get("add_api_hash")
    phone_code_hash = ctx.user_data.get("add_phone_code_hash")
    session_file = ctx.user_data.get("add_session_file")
    
    if not all([phone, api_id, api_hash, phone_code_hash, session_file]):
        await update.message.reply_text("❌ Данные не найдены. Начните заново: /add_account")
        return ConversationHandler.END
    
    status_msg = await update.message.reply_text(get_text(uid, "connecting"), parse_mode="Markdown")
    
    client = TelegramClient(session_file, api_id, api_hash)
    
    try:
        await client.connect()
        
        try:
            # Вход с кодом и phone_code_hash
            await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
        except SessionPasswordNeededError:
            # Если требуется 2FA
            ctx.user_data["add_need_password"] = True
            await status_msg.edit_text(get_text(uid, "enter_2fa"), parse_mode="Markdown")
            return PASSWORD
        except PhoneCodeInvalidError:
            await status_msg.edit_text("❌ Неверный код. Попробуйте ещё раз.\n\nВведите код из Telegram:")
            return CODE
        except PhoneCodeExpiredError:
            await status_msg.edit_text("❌ Код истёк. Начните добавление заново командой /add_account")
            return ConversationHandler.END
        
        # Успешный вход
        me = await client.get_me()
        await client.disconnect()
        
        accounts = load_reporter_accounts()
        next_id = max([acc.get("id", 0) for acc in accounts], default=0) + 1
        
        new_acc = {
            "id": next_id,
            "phone": phone,
            "api_id": api_id,
            "api_hash": api_hash,
            "session_file": session_file,
            "proxy": None,
            "is_active": True,
            "reports_today": 0,
            "max_reports_per_day": 50
        }
        accounts.append(new_acc)
        save_reporter_accounts(accounts)
        reporter.load_accounts()
        await reporter.connect(next_id)
        
        await status_msg.edit_text(get_text(uid, "session_created", phone, next_id), parse_mode="Markdown")
        return ConversationHandler.END
        
    except Exception as e:
        await status_msg.edit_text(f"❌ Ошибка: {str(e)}\n\nНачните заново: /add_account")
        return ConversationHandler.END

async def add_account_password(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    password = update.message.text.strip()
    
    if password == "/cancel":
        await update.message.reply_text(get_text(uid, "cancel"), parse_mode="Markdown")
        return ConversationHandler.END
    
    phone = ctx.user_data.get("add_phone")
    api_id = ctx.user_data.get("add_api_id")
    api_hash = ctx.user_data.get("add_api_hash")
    session_file = ctx.user_data.get("add_session_file")
    
    if not all([phone, api_id, api_hash, session_file]):
        await update.message.reply_text("❌ Данные не найдены. Начните заново: /add_account")
        return ConversationHandler.END
    
    status_msg = await update.message.reply_text(get_text(uid, "connecting"), parse_mode="Markdown")
    
    client = TelegramClient(session_file, api_id, api_hash)
    
    try:
        await client.connect()
        
        try:
            await client.sign_in(password=password)
            me = await client.get_me()
            await client.disconnect()
            
            accounts = load_reporter_accounts()
            next_id = max([acc.get("id", 0) for acc in accounts], default=0) + 1
            
            new_acc = {
                "id": next_id,
                "phone": phone,
                "api_id": api_id,
                "api_hash": api_hash,
                "session_file": session_file,
                "proxy": None,
                "is_active": True,
                "reports_today": 0,
                "max_reports_per_day": 50
            }
            accounts.append(new_acc)
            save_reporter_accounts(accounts)
            reporter.load_accounts()
            await reporter.connect(next_id)
            
            await status_msg.edit_text(get_text(uid, "session_created", phone, next_id), parse_mode="Markdown")
            return ConversationHandler.END
            
        except Exception as e:
            await status_msg.edit_text(f"❌ Ошибка: {str(e)}\n\nНачните заново: /add_account")
            return ConversationHandler.END
            
    except Exception as e:
        await status_msg.edit_text(f"❌ Ошибка: {str(e)}\n\nНачните заново: /add_account")
        return ConversationHandler.END

async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    await update.message.reply_text(get_text(uid, "cancel"), parse_mode="Markdown")
    return ConversationHandler.END

async def callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    data = query.data
    
    if data not in ["lang", "lang_ru", "lang_uk", "lang_en"] and not is_admin_or_mod(uid):
        if not await check_subscription(uid, ctx):
            text = get_text(uid, "must_subscribe", REQUIRED_CHANNEL_INVITE)
            await query.edit_message_text(text, parse_mode="Markdown", disable_web_page_preview=True)
            return
    
    db.get_or_create_user(uid)
    
    if data == "lang":
        await query.edit_message_text("🌐 *Выберите язык:*", parse_mode="Markdown", reply_markup=await lang_keyboard(uid))
        return
    if data.startswith("lang_"):
        lang = data.split("_")[1]
        db.update_language(uid, lang)
        await query.edit_message_text(get_text(uid, "welcome"), parse_mode="Markdown", reply_markup=await main_keyboard(uid))
        return
    if data == "main":
        await query.edit_message_text(get_text(uid, "welcome"), parse_mode="Markdown", reply_markup=await main_keyboard(uid))
        return
    if data == "shop":
        await query.edit_message_text(get_text(uid, "buy_subscription"), parse_mode="Markdown", reply_markup=await shop_keyboard(uid))
        return
    if data.startswith("buy_"):
        sub_id = data[4:]
        sub = SUBSCRIPTIONS.get(sub_id)
        if sub:
            await create_invoice(query, uid, sub_id, sub['price'])
        return
    if data == "profile":
        user = db.get_user(uid)
        role = get_text(uid, f"role_{get_user_role(uid)}")
        subs_text = active_subs_text(uid)
        text = get_text(uid, "profile", uid, role, user['reports'], user['total_purchased'], user['total_used'], subs_text)
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(get_text(uid, "btn_history"), callback_data="history")],
            [InlineKeyboardButton(get_text(uid, "btn_back"), callback_data="main")]
        ]))
        return
    if data == "history":
        purchases = db.get_user_purchases(uid)
        usage = db.get_user_usage(uid)
        if not purchases and not usage:
            await query.edit_message_text(get_text(uid, "history_empty"), parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(get_text(uid, "btn_back"), callback_data="profile")]]))
            return
        txt = ""
        if purchases:
            txt += "*📦 Покупки:*\n"
            for p in purchases[:5]:
                date = datetime.strptime(p['purchased_at'], '%Y-%m-%d %H:%M:%S.%f').strftime('%d.%m.%Y %H:%M')
                txt += f"• {p['item_name']} (+{p['reports_added']}) - ${p['price']} ({date})\n"
        if usage:
            txt += "\n*🎯 Использование:*\n"
            for u in usage[:5]:
                date = datetime.strptime(u['used_at'], '%Y-%m-%d %H:%M:%S.%f').strftime('%d.%m.%Y %H:%M')
                txt += f"• Снос на @{u['target']} ({date})\n"
        await query.edit_message_text(get_text(uid, "history", txt), parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(get_text(uid, "btn_back"), callback_data="profile")]]))
        return
    if data == "start_report":
        user = db.get_user(uid)
        if user['reports'] <= 0:
            await query.edit_message_text(get_text(uid, "no_reports_left"), parse_mode="Markdown", reply_markup=await main_keyboard(uid))
            return
        ctx.user_data["awaiting_target"] = True
        await query.edit_message_text(get_text(uid, "target_username"), parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(get_text(uid, "btn_back"), callback_data="main")]]))
        return
    if data == "confirm_report":
        target = ctx.user_data.get("target_for_report")
        if not target:
            await query.edit_message_text(get_text(uid, "target_username"), parse_mode="Markdown")
            return
        if db.use_report(uid, target):
            ctx.user_data.pop("target_for_report", None)
            await send_real_reports(query, uid, target, ctx)
        else:
            await query.edit_message_text(get_text(uid, "no_reports_left"), parse_mode="Markdown", reply_markup=await main_keyboard(uid))
        return
    if data == "stop_report":
        ctx.user_data["stop_report"] = True
        await query.answer("Останавливаем отправку...", show_alert=False)
        await query.edit_message_reply_markup(reply_markup=None)
        return
    if data == "admin_panel":
        if not is_admin_or_mod(uid):
            await query.edit_message_text(get_text(uid, "no_access"))
            return
        await query.edit_message_text("👑 *Админ панель*", parse_mode="Markdown", reply_markup=await admin_keyboard(uid))
        return
    if data == "admin_exit":
        await query.edit_message_text(get_text(uid, "welcome"), parse_mode="Markdown", reply_markup=await main_keyboard(uid))
        return
    if data == "admin_users":
        if not is_admin_or_mod(uid): return
        users_list = load_users_list()
        users_data = db.get_all_users()
        mods = load_moderators()
        txt = get_text(uid, "admin_users")
        cnt = 0
        for uid_str, u in users_list.items():
            if cnt >= 20: break
            name = u.get('username') or u.get('first_name') or uid_str
            reports = next((x['reports'] for x in users_data if str(x['user_id']) == uid_str), 0)
            icon = "👑" if int(uid_str) in ADMIN_IDS else ("🛡️" if int(uid_str) in mods else "👤")
            txt += f"• {icon} `{uid_str}` | {name} | 💥 {reports}\n"
            cnt += 1
        txt += f"\nВсего: {len(users_list)}"
        await query.message.reply_text(txt, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]]))
        await query.answer()
        return
    if data == "admin_stats":
        if not is_admin_or_mod(uid): return
        users_data = db.get_all_users()
        users_list = load_users_list()
        mods = load_moderators()
        total_reports = sum(u['reports'] for u in users_data)
        total_purchased = sum(u['total_purchased'] for u in users_data)
        total_used = sum(u['total_used'] for u in users_data)
        txt = get_text(uid, "admin_stats") + f"👥 Пользователей: {len(users_list)}\n👑 Админов: {len(ADMIN_IDS)}\n🛡️ Модераторов: {len(mods)}\n💥 Всего сносов: {total_reports}\n📥 Куплено: {total_purchased}\n📤 Использовано: {total_used}"
        await query.message.reply_text(txt, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]]))
        await query.answer()
        return
    if data == "admin_reports":
        if not is_admin_or_mod(uid): return
        ctx.user_data["admin_waiting_user"] = True
        await query.edit_message_text(get_text(uid, "admin_change_reports") + "\n\nВведите ID пользователя:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]]))
        return
    if data == "admin_give":
        if not is_admin_or_mod(uid): return
        ctx.user_data["admin_giving_sub"] = True
        await query.edit_message_text("🎫 *Выдача подписки*\n\nВведите ID пользователя:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]]))
        return
    if data == "admin_add_mod":
        if uid not in ADMIN_IDS:
            await query.answer("Только администратор", show_alert=True)
            return
        ctx.user_data["admin_add_mod"] = True
        await query.edit_message_text("👮 *Добавление модератора*\n\nВведите ID пользователя:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]]))
        return
    if data == "admin_rem_mod":
        if uid not in ADMIN_IDS:
            await query.answer("Только администратор", show_alert=True)
            return
        mods = load_moderators()
        if not mods:
            await query.edit_message_text("Список модераторов пуст", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]]))
            return
        txt = "📋 *Модераторы:*\n"
        for m in mods:
            txt += f"• ID: `{m}`\n"
        ctx.user_data["admin_rem_mod"] = True
        await query.edit_message_text(txt + "\nВведите ID для удаления:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]]))
        return
    if data.startswith("admin_give_sub_"):
        sub_id = data[16:]
        target_id = ctx.user_data.get("admin_sub_target")
        if target_id:
            sub = SUBSCRIPTIONS.get(sub_id)
            if sub:
                db.add_subscription(target_id, sub_id, sub['reports'])
                await query.edit_message_text(get_text(uid, "subscription_given", target_id, sub['name'], sub['reports']), parse_mode="Markdown", reply_markup=await admin_keyboard(uid))
                try:
                    await query.bot.send_message(target_id, f"🎉 Вам выдана подписка {sub['name']}! +{sub['reports']} сносов", parse_mode="Markdown")
                except:
                    pass
                ctx.user_data.pop("admin_sub_target", None)
        return
    if data.startswith("check_payment_"):
        inv_id = int(data.split("_")[2])
        await check_payment(query, uid, inv_id)
        return

async def create_invoice(query, uid: int, sub_id: str, amount: float):
    try:
        inv = await crypto.create_invoice("USDT", str(amount), desc=f"Подписка {sub_id}", payload=f"sub_{sub_id}_{uid}", expires=1800)
        inv_id = inv["invoice_id"]
        url = inv["bot_invoice_url"]
        db.save_payment_session(uid, inv_id, "subscription", sub_id, amount)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 ОПЛАТИТЬ", url=url)],
            [InlineKeyboardButton(get_text(uid, "check_payment"), callback_data=f"check_payment_{inv_id}")],
            [InlineKeyboardButton(get_text(uid, "btn_back"), callback_data="shop")]
        ])
        await query.edit_message_text(get_text(uid, "crypto_payment", amount, inv_id), parse_mode="Markdown", reply_markup=kb)
    except Exception as e:
        await query.edit_message_text(get_text(uid, "payment_error", str(e)), parse_mode="Markdown", reply_markup=await shop_keyboard(uid))

async def check_payment(query, uid: int, inv_id: int):
    sess = db.get_payment_session(uid)
    if not sess or sess['invoice_id'] != inv_id:
        await query.edit_message_text("❌ Сессия не найдена", reply_markup=await shop_keyboard(uid))
        return
    try:
        res = await crypto.get_invoices([inv_id])
        if res and res.get('items'):
            inv = res['items'][0]
            if inv.get('status') == 'paid':
                sub_id = sess['item_key']
                sub = SUBSCRIPTIONS[sub_id]
                db.add_subscription(uid, sub_id, sub['reports'], sess['amount'])
                db.delete_payment_session(uid)
                user = db.get_user(uid)
                await query.edit_message_text(get_text(uid, "purchase_success", sub['name'], sub['reports'], sess['amount'], user['reports']), parse_mode="Markdown", reply_markup=await main_keyboard(uid))
            else:
                await query.answer("⏳ Платеж не подтвержден", show_alert=True)
        else:
            await query.answer(get_text(uid, "payment_not_found"), show_alert=True)
    except Exception as e:
        await query.answer(f"Ошибка: {e}", show_alert=True)

async def send_real_reports(query, uid: int, target: str, ctx: ContextTypes.DEFAULT_TYPE):
    TOTAL_REPORTS = 200
    ctx.user_data["stop_report"] = False
    msg = await query.edit_message_text(get_text(uid, "sending_reports", target, 0, "░░░░░░░░░░░░░░░░░░░░", 0, TOTAL_REPORTS), parse_mode="Markdown")
    stop_kb = InlineKeyboardMarkup([[InlineKeyboardButton(get_text(uid, "btn_stop"), callback_data="stop_report")]])
    await msg.edit_reply_markup(reply_markup=stop_kb)
    
    async def progress(sent, total):
        pct = int(20 * sent / total)
        bar = "█" * pct + "░" * (20 - pct)
        try:
            await msg.edit_text(get_text(uid, "sending_reports", target, int(100*sent/total), bar, sent, total), parse_mode="Markdown", reply_markup=stop_kb)
        except:
            pass
    
    def check_stop():
        return ctx.user_data.get("stop_report", False)
    
    res = await reporter.mass_report(target, TOTAL_REPORTS, progress, stop_flag=check_stop)
    user = db.get_user(uid)
    
    if ctx.user_data.get("stop_report", False):
        await msg.edit_text(get_text(uid, "send_stopped", target, res['accepted'], TOTAL_REPORTS, res['rejected'], res['contact_sent'], len(res['accounts_used']), user['reports']), parse_mode="Markdown", reply_markup=await main_keyboard(uid))
        ctx.user_data.pop("stop_report", None)
    else:
        await msg.edit_text(get_text(uid, "send_success", target, res['accepted'], TOTAL_REPORTS, res['rejected'], res['contact_sent'], len(res['accounts_used']), user['reports']), parse_mode="Markdown", reply_markup=await main_keyboard(uid))

async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text.strip()
    
    if not is_admin_or_mod(uid) and not await check_subscription(uid, ctx):
        await update.message.reply_text(get_text(uid, "must_subscribe", REQUIRED_CHANNEL_INVITE), parse_mode="Markdown", disable_web_page_preview=True)
        return
    
    db.get_or_create_user(uid)
    
    if ctx.user_data.get("admin_waiting_user"):
        try:
            tid = int(text)
            if not db.get_user(tid):
                await update.message.reply_text(get_text(uid, "user_not_found"))
                return
            ctx.user_data["admin_target"] = tid
            ctx.user_data["admin_waiting_user"] = False
            ctx.user_data["admin_waiting_reports"] = True
            await update.message.reply_text(f"💰 Введите новое количество сносов для `{tid}`:", parse_mode="Markdown")
        except:
            await update.message.reply_text("❌ Введите ID")
        return
    if ctx.user_data.get("admin_waiting_reports"):
        try:
            new_reports = int(text)
            if new_reports < 0:
                await update.message.reply_text("❌ Не может быть отрицательным")
                return
            tid = ctx.user_data["admin_target"]
            db.set_reports_direct(tid, new_reports)
            await update.message.reply_text(f"✅ Сносы изменены на {new_reports}")
            ctx.user_data.pop("admin_waiting_reports", None)
            ctx.user_data.pop("admin_target", None)
        except:
            await update.message.reply_text("❌ Введите число")
        return
    if ctx.user_data.get("admin_giving_sub"):
        try:
            tid = int(text)
            if not db.get_user(tid):
                await update.message.reply_text(get_text(uid, "user_not_found"))
                return
            ctx.user_data["admin_sub_target"] = tid
            ctx.user_data["admin_giving_sub"] = False
            kb = []
            for sid, sub in SUBSCRIPTIONS.items():
                kb.append([InlineKeyboardButton(f"{sub['emoji']} {sub['name']} ({sub['reports']} сносов)", callback_data=f"admin_give_sub_{sid}")])
            kb.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")])
            await update.message.reply_text(get_text(uid, "admin_give_subscription"), parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        except:
            await update.message.reply_text("❌ Введите ID")
        return
    if ctx.user_data.get("admin_add_mod"):
        try:
            mid = int(text)
            if mid in ADMIN_IDS:
                await update.message.reply_text("❌ Нельзя добавить админа")
                return
            mods = load_moderators()
            if mid in mods:
                await update.message.reply_text("❌ Уже модератор")
                return
            mods.append(mid)
            save_moderators(mods)
            await update.message.reply_text(f"✅ Пользователь {mid} добавлен как модератор")
            ctx.user_data.pop("admin_add_mod", None)
        except:
            await update.message.reply_text("❌ Введите ID")
        return
    if ctx.user_data.get("admin_rem_mod"):
        try:
            mid = int(text)
            if mid in ADMIN_IDS:
                await update.message.reply_text("❌ Нельзя удалить админа")
                return
            mods = load_moderators()
            if mid not in mods:
                await update.message.reply_text("❌ Не является модератором")
                return
            mods.remove(mid)
            save_moderators(mods)
            await update.message.reply_text(f"✅ Модератор {mid} удален")
            ctx.user_data.pop("admin_rem_mod", None)
        except:
            await update.message.reply_text("❌ Введите ID")
        return
    if ctx.user_data.get("awaiting_target"):
        target = extract_username(text)
        if not valid_username(target):
            await update.message.reply_text("❌ Неверный формат. Попробуйте еще раз:")
            return
        user = db.get_user(uid)
        if user['reports'] <= 0:
            await update.message.reply_text(get_text(uid, "no_reports_left"), parse_mode="Markdown", reply_markup=await main_keyboard(uid))
            ctx.user_data.pop("awaiting_target", None)
            return
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_report")],
            [InlineKeyboardButton("❌ Отмена", callback_data="main")]
        ])
        ctx.user_data["target_for_report"] = target
        ctx.user_data.pop("awaiting_target", None)
        await update.message.reply_text(get_text(uid, "confirm_report", target, user['reports'] - 1), parse_mode="Markdown", reply_markup=kb)
        return
    await update.message.reply_text(get_text(uid, "welcome"), parse_mode="Markdown", reply_markup=await main_keyboard(uid))

async def run():
    logger.info("🚀 Запуск бота...")
    logger.info(f"📁 Директория данных: {DATA_DIR}")
    logger.info(f"📁 Директория сессий: {SESSIONS_DIR}")
    logger.info(f"📄 База данных: {DB_PATH}")
    
    logger.info("Подключение репортеров...")
    accounts = load_reporter_accounts()
    for acc in accounts:
        await reporter.connect(acc["id"])
    logger.info(f"✅ Подключено {len(reporter.clients)} аккаунтов")
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("add_account", add_account_start)],
        states={
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_account_phone)],
            API_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_account_api_id)],
            API_HASH: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_account_api_hash)],
            CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_account_code)],
            PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_account_password)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    logger.info("🤖 Бот запущен и готов к работе!")
    while True:
        await asyncio.sleep(3600)

def main():
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logger.info("Бот остановлен")

if __name__ == "__main__":
    main()
