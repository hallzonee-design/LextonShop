import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3
from datetime import datetime, timedelta
import random
import string
import time
import requests
import re
import hashlib
import json
import threading

BOT_TOKEN = "8603262735:AAHqaLfbOomzKV3D05SEwNmULhyrDtVCL8I"
ADMIN_ID = 8617203586
CRYPTO_BOT_TOKEN = "573111:AATEYAuG0XeIpW2hwfHiHlcC93FeFHA9FKRC"
SHOP_URL = "https://sites.google.com/view/dchcnvnchgx/home"
BOT_USERNAME = "LeextonShopbot"
MIN_WITHDRAW = 500

bot = telebot.TeleBot(BOT_TOKEN)
conn = sqlite3.connect('lexton_mega.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, balance REAL DEFAULT 0, stars_balance INTEGER DEFAULT 0, crypto_balance REAL DEFAULT 0, total_earned REAL DEFAULT 0, referral_code TEXT UNIQUE, invited_by INTEGER, reg_date TEXT, banned_until TEXT DEFAULT NULL)''')
for col in ['stars_balance', 'crypto_balance']:
    try: cursor.execute(f'ALTER TABLE users ADD COLUMN {col} INTEGER DEFAULT 0')
    except: pass

cursor.execute('''CREATE TABLE IF NOT EXISTS search_tariffs (user_id INTEGER, tariff_type TEXT, days INTEGER, expiry TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS vouchers (code TEXT UNIQUE, reward_type TEXT, reward_value TEXT, uses_left INTEGER)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS used_vouchers (user_id INTEGER, voucher_code TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS referrals (referrer_id INTEGER, referred_id INTEGER, referred_username TEXT, reg_date TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS crypto_payments (invoice_id TEXT UNIQUE, user_id INTEGER, amount REAL, status TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS purchase_history (id INTEGER PRIMARY KEY AUTOINCREMENT, buyer_username TEXT, buyer_id INTEGER, amount REAL, date TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS user_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT, action TEXT, details TEXT, date TEXT)''')
conn.commit()

cursor.execute('SELECT * FROM vouchers WHERE code = ?', ('LEXTON30',))
if not cursor.fetchone():
    cursor.execute('INSERT INTO vouchers VALUES (?, ?, ?, ?)', ('LEXTON30', 'search_30days', '30', 999999))
    conn.commit()

SEARCH_TARIFFS = {"30": ("30 дней", 30, 150, 1.5), "90": ("90 дней", 90, 350, 3.5), "120": ("120 дней", 120, 500, 5.0), "forever": ("НАВСЕГДА", 99999, 5000, 50.0)}
H = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

def log_action(uid, uname, action, details=""):
    try:
        cursor.execute('INSERT INTO user_logs (user_id, username, action, details, date) VALUES (?, ?, ?, ?, ?)', (uid, uname, action, str(details)[:200], datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
    except: pass

def is_banned(uid):
    cursor.execute('SELECT banned_until FROM users WHERE user_id = ?', (uid,))
    r = cursor.fetchone()
    return r and r[0] and datetime.strptime(r[0], "%Y-%m-%d %H:%M:%S") > datetime.now()

def has_access(uid):
    cursor.execute('SELECT expiry FROM search_tariffs WHERE user_id = ? AND expiry > ?', (uid, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    return cursor.fetchone() is not None

def get_days(uid):
    cursor.execute('SELECT expiry FROM search_tariffs WHERE user_id = ? AND expiry > ?', (uid, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    r = cursor.fetchone()
    return max(0, (datetime.strptime(r[0], "%Y-%m-%d %H:%M:%S") - datetime.now()).days) if r else 0

def activate_access(uid, uname, days):
    expiry = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('INSERT INTO search_tariffs VALUES (?, ?, ?, ?)', (uid, 'premium', days, expiry))
    conn.commit()

def use_voucher(uid, uname, code):
    cursor.execute('SELECT * FROM vouchers WHERE code = ?', (code.upper(),))
    v = cursor.fetchone()
    if not v or v[3] <= 0: return False
    cursor.execute('SELECT * FROM used_vouchers WHERE user_id = ? AND voucher_code = ?', (uid, code.upper()))
    if cursor.fetchone(): return False
    cursor.execute('UPDATE vouchers SET uses_left = uses_left - 1 WHERE code = ?', (code.upper(),))
    cursor.execute('INSERT INTO used_vouchers VALUES (?, ?)', (uid, code.upper()))
    activate_access(uid, uname, 30)
    conn.commit()
    return True

def main_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(KeyboardButton("🛒 МАГАЗИН"), KeyboardButton("🔍 OSINT ПОИСК"))
    kb.add(KeyboardButton("🎁 Бесплатные 500₽"), KeyboardButton("🤝 Рефералы"))
    kb.add(KeyboardButton("📦 Товар"), KeyboardButton("🎮 Игры"))
    kb.add(KeyboardButton("🔐 VPN"), KeyboardButton("ℹ️ Инфо"))
    kb.add(KeyboardButton("👤 Профиль"))
    return kb

def search_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    kb.add(KeyboardButton("🔍 Искать"), KeyboardButton("💳 Купить подписку"))
    kb.add(KeyboardButton("ℹ️ Статус"), KeyboardButton("🔙 Назад"))
    return kb

@bot.message_handler(commands=['start'])
def start(message):
    uid = message.from_user.id; uname = message.from_user.username or str(uid)
    log_action(uid, uname, "/start")
    if is_banned(uid): return
    args = message.text.split(); ref = args[1] if len(args) > 1 else None
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (uid,))
    if cursor.fetchone():
        bot.send_message(uid, "👋 С возвращением!\n👇 Выбери:", reply_markup=main_menu())
        return
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    if ref:
        cursor.execute('SELECT user_id FROM users WHERE referral_code = ?', (ref,))
        inv = cursor.fetchone()
        if inv:
            cursor.execute('INSERT INTO referrals VALUES (?, ?, ?, ?)', (inv[0], uid, uname, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
    cursor.execute('INSERT INTO users (user_id, username, referral_code, invited_by, reg_date) VALUES (?, ?, ?, ?, ?)', (uid, uname, code, inv[0] if ref and inv else None, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    bot.send_message(uid, "🎉 Добро пожаловать!\n\n👇 Выбери:", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text and m.text.strip().upper() == 'LEXTON30')
def hidden_voucher(message):
    uid = message.from_user.id; uname = message.from_user.username or str(uid)
    if is_banned(uid): return
    ok = use_voucher(uid, uname, 'LEXTON30')
    bot.send_message(uid, "✅ Доступ на 30 дней!" if ok else "❌ Не удалось", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "🔍 OSINT ПОИСК")
def search_menu(message):
    uid = message.from_user.id
    if is_banned(uid): return
    h = has_access(uid); d = get_days(uid)
    cursor.execute('SELECT stars_balance, crypto_balance FROM users WHERE user_id = ?', (uid,))
    s, c = cursor.fetchone() or (0, 0)
    text = f"🔍 OSINT Поиск\n⭐ Звёзды: {s} | 💎 Crypto: {c}$\n"
    text += f"✅ Доступ: {d} дн.\n" if h else "❌ Нет доступа\n"
    text += "\n💰 30д/150⭐/1.5$ | 90д/350⭐/3.5$ | 120д/500⭐/5$ | ∞/5000⭐/50$"
    bot.send_message(uid, text, parse_mode="Markdown", reply_markup=search_kb())

@bot.message_handler(func=lambda m: m.text == "💳 Купить подписку")
def buy_menu(message):
    uid = message.from_user.id
    if is_banned(uid): return
    kb = InlineKeyboardMarkup(row_width=1)
    for k, (name, days, ps, pc) in SEARCH_TARIFFS.items():
        kb.add(InlineKeyboardButton(f"⭐ {name} — {ps}⭐", callback_data=f"buys_{k}"))
        kb.add(InlineKeyboardButton(f"💎 {name} — {pc}$", callback_data=f"buyc_{k}"))
    bot.send_message(uid, "💳 Выбери:", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith(('buys_', 'buyc_')))
def process_payment(call):
    uid = call.from_user.id; uname = call.from_user.username or str(uid)
    method, key = call.data.split('_')[0], call.data.split('_')[1]
    name, days, ps, pc = SEARCH_TARIFFS[key]
    
    if method == 'buys':
        cursor.execute('SELECT stars_balance FROM users WHERE user_id = ?', (uid,))
        stars = cursor.fetchone()[0] or 0
        if stars < ps: bot.answer_callback_query(call.id, f"❌ Нужно {ps}⭐ (есть {stars})", show_alert=True); return
        cursor.execute('UPDATE users SET stars_balance = stars_balance - ? WHERE user_id = ?', (ps, uid))
        activate_access(uid, uname, days)
        conn.commit()
        bot.answer_callback_query(call.id, "✅ Куплено!", show_alert=True)
        bot.send_message(uid, f"✅ Доступ: {name}\n⏳ {days} дн.", reply_markup=search_kb())
    
    elif method == 'buyc':
        try:
            r = requests.post("https://pay.crypt.bot/api/createInvoice",
                headers={'Crypto-Pay-API-Token': CRYPTO_BOT_TOKEN},
                json={'asset': 'USDT', 'amount': str(pc), 'description': 'Lexton OSINT',
                      'paid_btn_name': 'callback', 'paid_btn_url': f'https://t.me/{BOT_USERNAME}'}, timeout=10)
            if r.status_code == 200:
                d = r.json()
                if d.get('ok'):
                    pay_url, invoice_id = d['result']['pay_url'], d['result']['invoice_id']
                    cursor.execute('INSERT INTO crypto_payments VALUES (?, ?, ?, ?)', (invoice_id, uid, pc, 'pending'))
                    conn.commit()
                    kb = InlineKeyboardMarkup()
                    kb.add(InlineKeyboardButton("💎 Оплатить", url=pay_url))
                    kb.add(InlineKeyboardButton("🔄 Проверить", callback_data=f"chk_{invoice_id}_{key}"))
                    bot.send_message(uid, f"💎 Счёт на {pc}$\nОплати и проверь:", reply_markup=kb)
                else: bot.answer_callback_query(call.id, "❌ Ошибка", show_alert=True)
        except: bot.answer_callback_query(call.id, "❌ Ошибка", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith('chk_'))
def check_payment(call):
    uid = call.from_user.id; uname = call.from_user.username or str(uid)
    _, invoice_id, key = call.data.split('_')
    name, days, ps, pc = SEARCH_TARIFFS[key]
    
    try:
        r = requests.get("https://pay.crypt.bot/api/getInvoices",
            headers={'Crypto-Pay-API-Token': CRYPTO_BOT_TOKEN},
            params={'invoice_ids': invoice_id}, timeout=10)
        if r.status_code == 200:
            d = r.json()
            if d.get('ok') and d['result']['items'] and d['result']['items'][0]['status'] == 'paid':
                cursor.execute('UPDATE crypto_payments SET status = ? WHERE invoice_id = ?', ('paid', invoice_id))
                activate_access(uid, uname, days)
                conn.commit()
                bot.answer_callback_query(call.id, "✅ Оплачено!", show_alert=True)
                bot.send_message(uid, f"✅ Доступ: {name} на {days} дн.", reply_markup=search_kb())
                return
    except: pass
    bot.answer_callback_query(call.id, "❌ Ещё не оплачено", show_alert=True)

@bot.message_handler(func=lambda m: m.text == "🛒 МАГАЗИН")
def shop(message):
    kb = InlineKeyboardMarkup(); kb.add(InlineKeyboardButton("🔵 SHOP START", url=SHOP_URL))
    bot.send_message(message.chat.id, "🛒 Оплати СБП → @lexxtoon", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "🎁 Бесплатные 500₽")
def free500(message): bot.send_message(message.chat.id, "🎁 [ПОЛУЧИТЬ 500₽](https://ozon.ru/fintech/promo/ref/EPF7MCEZH)", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🤝 Рефералы")
def referral_program(message):
    uid = message.from_user.id
    uname = message.from_user.username or str(uid)
    if is_banned(uid): return
    
    cursor.execute('SELECT referral_code, balance, stars_balance, crypto_balance, total_earned FROM users WHERE user_id = ?', (uid,))
    r = cursor.fetchone()
    if not r:
        bot.send_message(uid, "❌ Ошибка. Напиши /start")
        return
    
    code, balance, stars, crypto, earned = r
    link = f"https://t.me/{BOT_USERNAME}?start={code}"
    
    cursor.execute('SELECT COUNT(*) FROM referrals WHERE referrer_id = ?', (uid,))
    refs_count = cursor.fetchone()[0]
    
    text = (
        f"🤝 **РЕФЕРАЛЬНАЯ ПРОГРАММА**\n\n"
        f"💰 **Платим 10%** от покупок рефералов!\n\n"
        f"🔗 Ссылка:\n`{link}`\n\n"
        f"👥 Рефералов: **{refs_count}**\n"
        f"💵 RUB: **{balance} ₽**\n"
        f"⭐ Звёзд: **{stars}**\n"
        f"💎 Crypto: **{crypto}$**\n"
        f"🏆 Заработано: **{earned} ₽**\n\n"
        f"💸 Вывод: от **500₽** | **400⭐** | **1$**\n\n"
        f"👇 Выбери:"
    )
    
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("👥 МОИ РЕФЕРАЛЫ", callback_data="my_refs"),
        InlineKeyboardButton("💸 ВЫВЕСТИ НА КАРТУ", callback_data="wd_card"),
        InlineKeyboardButton("⭐ ВЫВЕСТИ ЗВЁЗДЫ", callback_data="wd_stars"),
        InlineKeyboardButton("💎 ВЫВЕСТИ КРИПТО", callback_data="wd_crypto")
    )
    
    bot.send_message(uid, text, parse_mode="Markdown", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data == "my_refs")
def show_referrals(call):
    uid = call.from_user.id
    
    cursor.execute('SELECT referred_username, reg_date FROM referrals WHERE referrer_id = ? ORDER BY reg_date DESC', (uid,))
    refs = cursor.fetchall()
    
    if not refs:
        bot.answer_callback_query(call.id, "Пока нет рефералов 😢", show_alert=True)
        return
    
    text = f"👥 **ТВОИ РЕФЕРАЛЫ ({len(refs)}):**\n\n"
    for i, (u, d) in enumerate(refs, 1):
        text += f"{i}. @{u}\n   📅 {d}\n\n"
    
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🔙 НАЗАД", callback_data="back_to_ref"))
    
    bot.edit_message_text(text, uid, call.message.message_id, parse_mode="Markdown", reply_markup=kb)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "back_to_ref")
def back_to_ref(call):
    uid = call.from_user.id
    cursor.execute('SELECT referral_code, balance, stars_balance, crypto_balance, total_earned FROM users WHERE user_id = ?', (uid,))
    r = cursor.fetchone()
    if not r: return
    code, balance, stars, crypto, earned = r
    link = f"https://t.me/{BOT_USERNAME}?start={code}"
    cursor.execute('SELECT COUNT(*) FROM referrals WHERE referrer_id = ?', (uid,))
    refs_count = cursor.fetchone()[0]
    
    text = (
        f"🤝 **РЕФЕРАЛЬНАЯ ПРОГРАММА**\n\n"
        f"💰 **Платим 10%** от покупок рефералов!\n\n"
        f"🔗 Ссылка:\n`{link}`\n\n"
        f"👥 Рефералов: **{refs_count}**\n"
        f"💵 RUB: **{balance} ₽**\n"
        f"⭐ Звёзд: **{stars}**\n"
        f"💎 Crypto: **{crypto}$**\n"
        f"🏆 Заработано: **{earned} ₽**\n\n"
        f"👇 Выбери:"
    )
    
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("👥 МОИ РЕФЕРАЛЫ", callback_data="my_refs"),
        InlineKeyboardButton("💸 ВЫВЕСТИ НА КАРТУ", callback_data="wd_card"),
        InlineKeyboardButton("⭐ ВЫВЕСТИ ЗВЁЗДЫ", callback_data="wd_stars"),
        InlineKeyboardButton("💎 ВЫВЕСТИ КРИПТО", callback_data="wd_crypto")
    )
    
    bot.edit_message_text(text, uid, call.message.message_id, parse_mode="Markdown", reply_markup=kb)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "wd_card")
def wd_card_start(call):
    uid = call.from_user.id
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (uid,))
    b = cursor.fetchone()[0]
    if b < MIN_WITHDRAW:
        bot.answer_callback_query(call.id, f"❌ Мин: {MIN_WITHDRAW}₽\nБаланс: {b}₽", show_alert=True)
        return
    msg = bot.send_message(uid, f"💸 Сумма (мин {MIN_WITHDRAW}₽):")
    bot.register_next_step_handler(msg, lambda m: process_wd_card(m, b))

def process_wd_card(message, bal):
    uid = message.from_user.id
    try: a = float(message.text.strip())
    except: bot.send_message(uid, "❌ Число!"); return
    if a < MIN_WITHDRAW: bot.send_message(uid, f"❌ Мин: {MIN_WITHDRAW}₽"); return
    if a > bal: bot.send_message(uid, f"❌ Баланс: {bal}₽"); return
    msg = bot.send_message(uid, "💳 Номер карты (16 цифр):")
    bot.register_next_step_handler(msg, lambda m: finish_wd_card(m, a))

def finish_wd_card(message, a):
    uid = message.from_user.id
    card = message.text.strip().replace(' ', '')
    if not card.isdigit() or len(card) != 16: bot.send_message(uid, "❌ 16 цифр!"); return
    cursor.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (a, uid))
    conn.commit()
    kb = InlineKeyboardMarkup(); kb.add(InlineKeyboardButton("📩 @lexxtoon", url="https://t.me/lexxtoon"))
    bot.send_message(uid, f"✅ {a}₽ на {card[:4]}****{card[-4:]}\n📩 @lexxtoon", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data == "wd_stars")
def wd_stars_start(call):
    uid = call.from_user.id
    cursor.execute('SELECT stars_balance FROM users WHERE user_id = ?', (uid,))
    s = cursor.fetchone()[0]
    if s < 400: bot.answer_callback_query(call.id, f"❌ Мин: 400⭐\nБаланс: {s}⭐", show_alert=True); return
    msg = bot.send_message(uid, f"⭐ Сумма (мин 400⭐):")
    bot.register_next_step_handler(msg, lambda m: finish_wd_stars(m, s))

def finish_wd_stars(message, s):
    uid = message.from_user.id
    try: a = int(message.text.strip())
    except: bot.send_message(uid, "❌ Число!"); return
    if a < 400: bot.send_message(uid, "❌ Мин: 400⭐"); return
    if a > s: bot.send_message(uid, f"❌ Баланс: {s}⭐"); return
    cursor.execute('UPDATE users SET stars_balance = stars_balance - ? WHERE user_id = ?', (a, uid))
    conn.commit()
    kb = InlineKeyboardMarkup(); kb.add(InlineKeyboardButton("📩 @lexxtoon", url="https://t.me/lexxtoon"))
    bot.send_message(uid, f"✅ {a}⭐\n📩 @lexxtoon", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data == "wd_crypto")
def wd_crypto_start(call):
    uid = call.from_user.id
    cursor.execute('SELECT crypto_balance FROM users WHERE user_id = ?', (uid,))
    c = cursor.fetchone()[0]
    if c < 1: bot.answer_callback_query(call.id, f"❌ Мин: 1$\nБаланс: {c}$", show_alert=True); return
    msg = bot.send_message(uid, f"💎 Сумма (мин 1$):")
    bot.register_next_step_handler(msg, lambda m: process_wd_crypto(m, c))

def process_wd_crypto(message, c):
    uid = message.from_user.id
    try: a = float(message.text.strip())
    except: bot.send_message(uid, "❌ Число!"); return
    if a < 1: bot.send_message(uid, "❌ Мин: 1$"); return
    if a > c: bot.send_message(uid, f"❌ Баланс: {c}$"); return
    msg = bot.send_message(uid, "💎 Кошелёк USDT TRC20:")
    bot.register_next_step_handler(msg, lambda m: finish_wd_crypto(m, a))

def finish_wd_crypto(message, a):
    uid = message.from_user.id
    w = message.text.strip()
    if len(w) < 30: bot.send_message(uid, "❌ Неверный адрес!"); return
    cursor.execute('UPDATE users SET crypto_balance = crypto_balance - ? WHERE user_id = ?', (a, uid))
    conn.commit()
    kb = InlineKeyboardMarkup(); kb.add(InlineKeyboardButton("📩 @lexxtoon", url="https://t.me/lexxtoon"))
    bot.send_message(uid, f"✅ {a}$ на {w[:10]}...{w[-5:]}\n📩 @lexxtoon", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "📦 Товар")
def product(message):
    kb = InlineKeyboardMarkup(); kb.add(InlineKeyboardButton("📩 @lexxtoon", url="https://t.me/lexxtoon"))
    bot.send_message(message.chat.id, "📦 Чек → @lexxtoon", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "🎮 Игры")
def games(message):
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(KeyboardButton("🎮 Марио"), KeyboardButton("⛏ Майнкрафт"), KeyboardButton("🔙 Назад"))
    bot.send_message(message.chat.id, "🎮 Выбери:", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text in ["🎮 Марио", "⛏ Майнкрафт"])
def game_links(message):
    urls = {"🎮 Марио": "mario", "⛏ Майнкрафт": "maincraft"}
    kb = InlineKeyboardMarkup(); kb.add(InlineKeyboardButton("🎮 Играть", url=f"https://sites.google.com/view/dchcnvnchgx/{urls[message.text]}"))
    bot.send_message(message.chat.id, "🎮:", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "🔐 VPN")
def vpn(message):
    kb = InlineKeyboardMarkup(); kb.add(InlineKeyboardButton("🔐 Прокат", url="https://sites.google.com/view/dchcnvnchgx/proxy"))
    bot.send_message(message.chat.id, "🔐 VPN:", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "ℹ️ Инфо")
def info(message):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("ℹ️ Сайт", url="https://sites.google.com/view/dchcnvnchgx/information"))
    kb.add(InlineKeyboardButton("🤖 DeepSeek", url="https://sites.google.com/view/dchcnvnchgx/deepseak"))
    kb.add(InlineKeyboardButton("🎰 Casino", url="https://sites.google.com/view/dchcnvnchgx/casino"))
    bot.send_message(message.chat.id, "ℹ️:", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "👤 Профиль")
def profile(message):
    uid = message.from_user.id
    cursor.execute('SELECT username, balance, stars_balance, crypto_balance, total_earned, reg_date FROM users WHERE user_id = ?', (uid,))
    r = cursor.fetchone()
    if not r: return
    cursor.execute('SELECT COUNT(*) FROM referrals WHERE referrer_id = ?', (uid,))
    refs = cursor.fetchone()[0]
    h = has_access(uid); d = get_days(uid)
    bot.send_message(uid, f"👤 @{r[0]}\n💰 {r[1]}₽\n⭐ {r[2]} звёзд\n💎 {r[3]}$\n👥 Реф: {refs}\n🔍 {'✅ '+str(d)+'дн' if h else '❌'}\n📅 {r[5][:10]}", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🔙 Назад")
def back(message): bot.send_message(message.chat.id, "👋 Меню:", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "ℹ️ Статус")
def status_cmd(message):
    uid = message.from_user.id
    h = has_access(uid); d = get_days(uid)
    cursor.execute('SELECT stars_balance, crypto_balance FROM users WHERE user_id = ?', (uid,))
    s, c = cursor.fetchone() or (0, 0)
    bot.send_message(uid, f"⭐ {s} звёзд\n💎 {c}$\n🔍 {'✅ '+str(d)+' дн.' if h else '❌ нет'}")

# ========== АДМИН КОМАНДЫ ==========
@bot.message_handler(commands=['add'])
def add_balance(message):
    if message.from_user.id != ADMIN_ID: return
    try:
        parts = message.text.split()
        username = parts[1].lstrip('@')
        amount = float(parts[2])
        cursor.execute('SELECT user_id, balance FROM users WHERE username = ?', (username,))
        result = cursor.fetchone()
        if not result: bot.send_message(ADMIN_ID, f"❌ @{username} не найден"); return
        user_id, balance = result
        cursor.execute('UPDATE users SET balance = balance + ?, total_earned = total_earned + ? WHERE user_id = ?', (amount, amount, user_id))
        conn.commit()
        cursor.execute('INSERT INTO purchase_history (buyer_username, buyer_id, amount, date) VALUES (?, ?, ?, ?)', (username, user_id, amount, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        bot.send_message(ADMIN_ID, f"✅ Начислено {amount} ₽ @{username}")
        bot.send_message(user_id, f"💰 Вам начислено {amount} ₽!\nБаланс: {balance + amount} ₽")
        log_action(ADMIN_ID, "admin", "add", f"@{username} +{amount}")
    except: bot.send_message(ADMIN_ID, "❌ /add @username сумма")

@bot.message_handler(commands=['unadd'])
def unadd_balance(message):
    if message.from_user.id != ADMIN_ID: return
    try:
        parts = message.text.split()
        username = parts[1].lstrip('@')
        amount = float(parts[2])
        cursor.execute('SELECT user_id, balance FROM users WHERE username = ?', (username,))
        result = cursor.fetchone()
        if not result: bot.send_message(ADMIN_ID, f"❌ @{username} не найден"); return
        user_id, balance = result
        if amount > balance: bot.send_message(ADMIN_ID, f"❌ Баланс {balance} ₽"); return
        cursor.execute('UPDATE users SET balance = balance - ?, total_earned = total_earned - ? WHERE user_id = ?', (amount, amount, user_id))
        conn.commit()
        bot.send_message(ADMIN_ID, f"✅ Списано {amount} ₽ @{username}")
        bot.send_message(user_id, f"⚠️ Списано {amount} ₽. Баланс: {balance - amount} ₽")
        log_action(ADMIN_ID, "admin", "unadd", f"@{username} -{amount}")
    except: bot.send_message(ADMIN_ID, "❌ /unadd @username сумма")

@bot.message_handler(commands=['ban'])
def ban_user(message):
    if message.from_user.id != ADMIN_ID: return
    try:
        parts = message.text.split()
        username = parts[1].lstrip('@')
        days = int(parts[2])
        cursor.execute('SELECT user_id FROM users WHERE username = ?', (username,))
        result = cursor.fetchone()
        if not result: bot.send_message(ADMIN_ID, f"❌ @{username} не найден"); return
        user_id = result[0]
        banned_until = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute('UPDATE users SET banned_until = ? WHERE user_id = ?', (banned_until, user_id))
        conn.commit()
        bot.send_message(ADMIN_ID, f"✅ @{username} забанен на {days} дн.")
        bot.send_message(user_id, f"❌ Вы забанены на {days} дн.")
        log_action(ADMIN_ID, "admin", "ban", f"@{username} {days}дн")
    except: bot.send_message(ADMIN_ID, "❌ /ban @username дни")

@bot.message_handler(commands=['unban'])
def unban_user(message):
    if message.from_user.id != ADMIN_ID: return
    try:
        parts = message.text.split()
        username = parts[1].lstrip('@')
        cursor.execute('SELECT user_id FROM users WHERE username = ?', (username,))
        result = cursor.fetchone()
        if not result: bot.send_message(ADMIN_ID, f"❌ @{username} не найден"); return
        user_id = result[0]
        cursor.execute('UPDATE users SET banned_until = NULL WHERE user_id = ?', (user_id,))
        conn.commit()
        bot.send_message(ADMIN_ID, f"✅ @{username} разбанен")
        bot.send_message(user_id, "✅ Вы разбанены!")
        log_action(ADMIN_ID, "admin", "unban", f"@{username}")
    except: bot.send_message(ADMIN_ID, "❌ /unban @username")

@bot.message_handler(commands=['history'])
def shop_history(message):
    if message.from_user.id != ADMIN_ID: return
    cursor.execute('SELECT buyer_username, amount, date FROM purchase_history ORDER BY id DESC LIMIT 20')
    purchases = cursor.fetchall()
    if not purchases: bot.send_message(ADMIN_ID, "📭 История пуста"); return
    text = "📋 **Последние 20 начислений:**\n\n"
    for buyer, amount, date in purchases:
        text += f"👤 {buyer} | {amount} ₽ | {date}\n"
    bot.send_message(ADMIN_ID, text, parse_mode="Markdown")

@bot.message_handler(commands=['stats'])
def admin_stats(message):
    if message.from_user.id != ADMIN_ID: return
    cursor.execute('SELECT COUNT(*), SUM(balance), SUM(stars_balance), SUM(crypto_balance), SUM(total_earned) FROM users')
    u, b, s, c, e = cursor.fetchone()
    cursor.execute('SELECT COUNT(*) FROM referrals'); r = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM search_tariffs WHERE expiry > ?', (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),))
    a = cursor.fetchone()[0]
    text = f"📊 **Статистика:**\n\n👥 Пользователей: {u}\n💰 Баланс: {b or 0} ₽\n⭐ Звёзд: {s or 0}\n💎 Crypto: {c or 0}$\n🏆 Выплачено: {e or 0} ₽\n🤝 Рефералов: {r}\n🔍 Поиск активен: {a}"
    bot.send_message(ADMIN_ID, text, parse_mode="Markdown")

@bot.message_handler(commands=['userinfo'])
def userinfo(message):
    if message.from_user.id != ADMIN_ID: return
    try:
        parts = message.text.split()
        username = parts[1].lstrip('@')
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        r = cursor.fetchone()
        if not r: bot.send_message(ADMIN_ID, f"❌ @{username} не найден"); return
        uid, uname, bal, stars, crypto, earned, code, invited, reg, ban = r
        has_s = "✅" if has_access(uid) else "❌"
        ban_text = f"до {ban}" if ban else "нет"
        text = f"👤 **@{uname}**\n🆔 {uid}\n💰 {bal} ₽\n⭐ {stars} звёзд\n💎 {crypto}$\n🏆 {earned} ₽\n🔍 Поиск: {has_s}\n🔗 Код: {code}\n👥 Приглашён: {invited or 'нет'}\n🚫 Бан: {ban_text}\n📅 {reg}"
        bot.send_message(ADMIN_ID, text, parse_mode="Markdown")
    except: bot.send_message(ADMIN_ID, "❌ /userinfo @username")

@bot.message_handler(commands=['people'])
def people_log(message):
    if message.from_user.id != ADMIN_ID: return
    cursor.execute('SELECT user_id, username, action, details, date FROM user_logs ORDER BY id DESC LIMIT 50')
    logs = cursor.fetchall()
    if not logs: bot.send_message(ADMIN_ID, "📭 Логи пусты"); return
    text = "📋 **Логи:**\n\n"
    for uid, uname, action, details, date in logs:
        text += f"👤 @{uname or uid} | {action} | {details or ''} | {date}\n"
    bot.send_message(ADMIN_ID, text, parse_mode="Markdown")

@bot.message_handler(commands=['clearpeople'])
def clear_people(message):
    if message.from_user.id != ADMIN_ID: return
    try:
        parts = message.text.split()
        username = parts[1].lstrip('@')
        cursor.execute('SELECT user_id FROM users WHERE username = ?', (username,))
        r = cursor.fetchone()
        if not r: bot.send_message(ADMIN_ID, f"❌ @{username} не найден"); return
        cursor.execute('DELETE FROM user_logs WHERE user_id = ?', (r[0],))
        conn.commit()
        bot.send_message(ADMIN_ID, f"✅ Логи @{username} очищены")
    except: bot.send_message(ADMIN_ID, "❌ /clearpeople @username")

@bot.message_handler(commands=['clear'])
def clear_all(message):
    if message.from_user.id != ADMIN_ID: return
    cursor.execute('DELETE FROM user_logs')
    conn.commit()
    bot.send_message(ADMIN_ID, "✅ Все логи очищены")

@bot.message_handler(commands=['text'])
def text_all(message):
    if message.from_user.id != ADMIN_ID: return
    text = message.text.replace('/text', '', 1).strip()
    if not text: bot.send_message(ADMIN_ID, "❌ /text сообщение"); return
    cursor.execute('SELECT user_id FROM users')
    users = cursor.fetchall()
    success = fail = 0
    for u in users:
        try: bot.send_message(u[0], text); success += 1; time.sleep(0.05)
        except: fail += 1
    bot.send_message(ADMIN_ID, f"✅ Отправлено: {success}\n❌ Ошибок: {fail}")

@bot.message_handler(commands=['addstars'])
def addstars(message):
    if message.from_user.id != ADMIN_ID: return
    try:
        parts = message.text.split()
        username = parts[1].lstrip('@')
        amount = int(parts[2])
        cursor.execute('UPDATE users SET stars_balance = stars_balance + ? WHERE username = ?', (amount, username))
        conn.commit()
        bot.send_message(ADMIN_ID, f"✅ +{amount}⭐ @{username}")
    except: bot.send_message(ADMIN_ID, "❌ /addstars @username кол-во")

def search_phone(phone):
    clean = ''.join(filter(str.isdigit, phone))
    results = {"phone": phone, "clean": clean, "findings": []}
    
    try:
        r = requests.get(f"https://api.numlookupapi.com/v1/validate/{clean}", timeout=5, headers=H)
        if r.status_code == 200:
            d = r.json()
            if d.get('valid'): results["findings"].append({"source": "numlookup", "data": d})
    except: pass
    
    for name, url in [("WhatsApp", f"https://wa.me/{clean}"), ("Telegram", f"https://t.me/+{clean}"), ("Viber", f"viber://chat?number=%2B{clean}")]:
        try:
            r = requests.get(url, timeout=4, headers=H, allow_redirects=False)
            if r.status_code in [200, 302] or name.lower() in r.text.lower(): results["findings"].append({"source": name, "exists": True})
        except: pass
    
    try:
        r = requests.get(f"https://api.vk.com/method/users.search?q={clean}&count=10&v=5.131", timeout=5, headers=H)
        if r.status_code == 200:
            d = r.json()
            if 'response' in d and d['response'].get('items'):
                results["findings"].append({"source": "vk", "users": d['response']['items'][:10]})
    except: pass
    
    try:
        r = requests.get(f"https://www.google.com/search?q={clean}", timeout=5, headers=H)
        if r.status_code == 200:
            emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', r.text)
            names = re.findall(r'[А-ЯЁ][а-яё]+\s[А-ЯЁ][а-яё]+', r.text)
            if emails or names: results["findings"].append({"source": "google", "emails": list(set(emails))[:5], "names": list(set(names))[:5]})
    except: pass
    
    try:
        r = requests.get(f"https://haveibeenpwned.com/api/v3/breachedaccount/{clean}", timeout=5, headers=H)
        if r.status_code == 200: results["findings"].append({"source": "leaks", "breaches": r.json()[:10]})
    except: pass
    
    return results

def search_email(email):
    results = {"email": email, "findings": []}
    
    try:
        r = requests.get(f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}", timeout=5, headers=H)
        if r.status_code == 200: results["findings"].append({"source": "leaks", "breaches": r.json()})
    except: pass
    
    try:
        r = requests.get(f"https://emailrep.io/{email}", timeout=5, headers=H)
        if r.status_code == 200: results["findings"].append({"source": "emailrep", "data": r.json()})
    except: pass
    
    try:
        h = hashlib.md5(email.strip().lower().encode()).hexdigest()
        r = requests.get(f"https://www.gravatar.com/{h}.json", timeout=5, headers=H)
        if r.status_code == 200 and r.json().get('entry'): results["findings"].append({"source": "gravatar", "data": r.json()['entry'][0]})
    except: pass
    
    return results

def search_username(username):
    q = username.lstrip('@')
    results = {"username": q, "findings": []}
    
    sites = {
        "Telegram": f"https://t.me/{q}", "VK": f"https://vk.com/{q}", "GitHub": f"https://github.com/{q}",
        "Twitter": f"https://twitter.com/{q}", "Instagram": f"https://www.instagram.com/{q}", "Reddit": f"https://www.reddit.com/user/{q}",
        "Twitch": f"https://www.twitch.tv/{q}", "TikTok": f"https://www.tiktok.com/@{q}", "Steam": f"https://steamcommunity.com/id/{q}",
        "YouTube": f"https://www.youtube.com/@{q}", "Spotify": f"https://open.spotify.com/user/{q}", "Pinterest": f"https://www.pinterest.com/{q}",
        "Facebook": f"https://www.facebook.com/{q}", "Medium": f"https://medium.com/@{q}", "SoundCloud": f"https://soundcloud.com/{q}",
        "Patreon": f"https://www.patreon.com/{q}", "Linktree": f"https://linktr.ee/{q}", "Snapchat": f"https://www.snapchat.com/add/{q}",
        "Flickr": f"https://www.flickr.com/people/{q}", "DevianArt": f"https://www.deviantart.com/{q}"
    }
    
    for site, url in sites.items():
        try:
            r = requests.get(url, timeout=4, headers=H, allow_redirects=True)
            if r.status_code == 200 and len(r.text) > 500:
                title_match = re.search(r'<meta property="og:title" content="(.*?)">', r.text) or re.search(r'<title>(.*?)</title>', r.text)
                if title_match:
                    title = title_match.group(1).strip()
                    bad = ['Error', 'Not Found', 'не найден', '404', 'Page Not Found']
                    if not any(b.lower() in title.lower() for b in bad) and title.lower() != q.lower():
                        results["findings"].append({"source": site, "profile": title[:150]})
        except: pass
    
    try:
        r = requests.get(f"https://api.github.com/users/{q}", timeout=5, headers=H)
        if r.status_code == 200: results["findings"].append({"source": "github_api", "data": r.json()})
    except: pass
    
    try:
        r = requests.get(f"https://haveibeenpwned.com/api/v3/breachedaccount/{q}", timeout=5, headers=H)
        if r.status_code == 200: results["findings"].append({"source": "leaks", "breaches": r.json()[:10]})
    except: pass
    
    return results

def format_report(results, query_type):
    lines = []
    
    if query_type == "phone":
        lines.append("📱 **ТЕЛЕФОН:** " + results.get("phone", ""))
        lines.append("")
        for f in results.get("findings", []):
            src = f.get("source", "")
            if src == "numlookup" and isinstance(f.get("data"), dict):
                d = f["data"]
                if d.get("valid"):
                    lines.append("📊 **ОПЕРАТОР:**")
                    lines.append(f"├ Страна: {d.get('country_name', '?')}")
                    lines.append(f"├ Оператор: {d.get('carrier', '?')}")
                    lines.append(f"├ Тип: {d.get('line_type', '?')}")
                    lines.append(f"└ Локация: {d.get('location', '?')}")
                    lines.append("")
            elif src in ["WhatsApp", "Telegram", "Viber"]: lines.append(f"✅ {src}: аккаунт найден")
            elif src == "vk":
                lines.append(f"📱 VK: {len(f.get('users', []))} пользователей")
                for u in f.get("users", [])[:5]: lines.append(f"├ {u.get('first_name','')} {u.get('last_name','')} (ID: {u.get('id','')})")
                lines.append("")
            elif src == "google":
                if f.get("emails"): lines.append(f"📧 Email: {', '.join(f['emails'][:5])}")
                if f.get("names"): lines.append(f"👤 Имена: {', '.join(f['names'][:5])}")
                lines.append("")
            elif src == "leaks" and isinstance(f.get("breaches"), list):
                lines.append(f"🔓 Утечек: {len(f['breaches'])}")
                for b in f['breaches'][:5]:
                    if isinstance(b, dict): lines.append(f"├ {b.get('Name','?')} ({b.get('BreachDate','?')[:10]})")
                lines.append("")
    
    elif query_type == "email":
        lines.append("📧 **EMAIL:** " + results.get("email", ""))
        lines.append("")
        for f in results.get("findings", []):
            src = f.get("source", "")
            if src == "leaks" and isinstance(f.get("breaches"), list):
                lines.append(f"🔓 Утечек: {len(f['breaches'])}")
                for b in f['breaches'][:10]:
                    if isinstance(b, dict): lines.append(f"├ {b.get('Name','?')} ({b.get('BreachDate','?')[:10]})")
                lines.append("")
            elif src == "emailrep":
                d = f.get("data", {})
                lines.append(f"📊 Репутация: {d.get('reputation', '?')}")
                if d.get('details', {}).get('suspicious'): lines.append("├ 🚩 Подозрительный!")
                lines.append("")
            elif src == "gravatar":
                d = f.get("data", {})
                if d.get('displayName'): lines.append(f"👤 Gravatar: {d['displayName']}")
                lines.append("")
    
    elif query_type == "username":
        lines.append("🔍 **USERNAME:** " + results.get("username", ""))
        lines.append("")
        social_count = 0
        for f in results.get("findings", []):
            src = f.get("source", "")
            if src == "github_api":
                d = f.get("data", {})
                if d.get('login'):
                    lines.append("💻 **GitHub:**")
                    lines.append(f"├ Имя: {d.get('name') or d.get('login')}")
                    if d.get('bio'): lines.append(f"├ Bio: {d['bio'][:150]}")
                    lines.append(f"├ Локация: {d.get('location', '?')}")
                    lines.append(f"├ Репо: {d.get('public_repos', 0)}")
                    lines.append(f"├ Фолловеры: {d.get('followers', 0)}")
                    lines.append(f"└ Email: {d.get('email', 'скрыт')}")
                    lines.append("")
            elif src == "leaks" and isinstance(f.get("breaches"), list):
                lines.append(f"🔓 Утечек: {len(f['breaches'])}")
                for b in f['breaches'][:7]:
                    if isinstance(b, dict): lines.append(f"├ {b.get('Name','?')} ({b.get('BreachDate','?')[:10]})")
                lines.append("")
            else: social_count += 1
        
        if social_count > 0:
            lines.append(f"📱 Соцсети: найдено {social_count}")
            for f in results.get("findings", []):
                if f.get("source") not in ["github_api", "leaks"]: lines.append(f"├ ✅ {f['source']}: {f.get('profile', '')[:100]}")
            lines.append("")
    
    lines.append("_" * 30)
    lines.append("🔍 **Lexton Mega OSINT**")
    return "\n".join(lines)

@bot.message_handler(func=lambda m: m.text == "🔍 Искать")
def search_start(message):
    uid = message.from_user.id
    if not has_access(uid): bot.send_message(uid, "❌ Нет доступа", reply_markup=search_kb()); return
    msg = bot.send_message(uid, "🔍 Введи запрос:\n• Телефон: +79001234567\n• Email: user@mail.ru\n• Username: @user")
    bot.register_next_step_handler(msg, lambda m: mega_search(m, uid))

def mega_search(message, uid):
    query = message.text.strip()
    clean = query.lstrip('@')
    is_phone = clean.replace('+','').replace('-','').replace(' ','').isdigit() and len(clean.replace('+','').replace('-','').replace(' ','')) >= 10
    is_email = '@' in clean and '.' in clean.split('@')[1]
    qtype = "phone" if is_phone else "email" if is_email else "username"
    
    loading = bot.send_message(uid, f"🔍 Запуск Mega OSINT...\n⏳ ~60-90 сек\n[░░░░░░░░░░░░░░░░░░░░] 0%", parse_mode="Markdown")
    
    def run():
        try:
            for p in range(10, 101, 10):
                bar = "█" * (p // 5) + "░" * (20 - p // 5)
                try: bot.edit_message_text(f"🔍 Поиск...\n⏳ {p}%\n[{bar}] {p}%", uid, loading.message_id)
                except: pass
                time.sleep(2)
            
            if qtype == "phone": results = search_phone(clean)
            elif qtype == "email": results = search_email(clean)
            else: results = search_username(clean)
            
            report = format_report(results, qtype)
            
            if len(report) > 4000:
                parts = [report[i:i+4000] for i in range(0, len(report), 4000)]
                for i, part in enumerate(parts):
                    if i == 0: bot.edit_message_text(part, uid, loading.message_id, parse_mode="Markdown")
                    else: bot.send_message(uid, part, parse_mode="Markdown")
            else:
                bot.edit_message_text(report, uid, loading.message_id, parse_mode="Markdown")
        except Exception as e:
            try: bot.edit_message_text(f"❌ Ошибка: {str(e)[:100]}", uid, loading.message_id)
            except: pass
        
        bot.send_message(uid, "🔍 Готово. Выбери действие:", reply_markup=search_kb())
    
    threading.Thread(target=run).start()

def search_by_fullname(fio):
    results = {"fio": fio, "findings": []}
    parts = fio.split()
    
    for part in parts[:3]:
        try:
            r = requests.get(f"https://vk.com/search?c%5Bq%5D={part}&c%5Bsection%5D=people", timeout=5, headers=H)
            if r.status_code == 200:
                names = re.findall(r'([А-ЯЁ][а-яё]+\s[А-ЯЁ][а-яё]+(?:\s[А-ЯЁ][а-яё]+)?)', r.text)
                if names: results["findings"].append({"source": "vk_search", "matches": list(set(names))[:10]})
        except: pass
    
    for part in parts[:2]:
        try:
            r = requests.get(f"https://www.google.com/search?q={part}", timeout=5, headers=H)
            if r.status_code == 200:
                phones = re.findall(r'\+?[7-8][\d\s\(\)-]{9,15}', r.text)
                emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', r.text)
                if phones or emails: results["findings"].append({"source": "google", "phones": list(set(phones))[:5], "emails": list(set(emails))[:5]})
        except: pass
    
    try:
        r = requests.get(f"https://yandex.ru/search/?text={fio}", timeout=5, headers=H)
        if r.status_code == 200:
            addresses = re.findall(r'(?:г\.|город\s|ул\.|улица\s|д\.|дом\s)[^<]{5,100}', r.text)
            if addresses: results["findings"].append({"source": "yandex", "addresses": list(set(addresses))[:5]})
    except: pass
    
    return results

def search_ip(ip):
    results = {"ip": ip, "findings": []}
    
    try:
        r = requests.get(f"https://ipapi.co/{ip}/json/", timeout=5, headers=H)
        if r.status_code == 200:
            d = r.json()
            if not d.get('error'):
                results["findings"].append({"source": "ipapi", "data": {
                    "country": d.get('country_name'), "region": d.get('region'),
                    "city": d.get('city'), "isp": d.get('org'), "lat": d.get('latitude'), "lon": d.get('longitude')
                }})
    except: pass
    
    try:
        r = requests.get(f"https://ipinfo.io/{ip}/json", timeout=5, headers=H)
        if r.status_code == 200: results["findings"].append({"source": "ipinfo", "data": r.json()})
    except: pass
    
    return results

def search_car(car_number):
    clean = car_number.upper().replace(' ', '')
    results = {"car": clean, "findings": []}
    
    try:
        r = requests.get(f"https://www.google.com/search?q={clean}+авто", timeout=5, headers=H)
        if r.status_code == 200:
            vins = re.findall(r'[A-HJ-NPR-Z0-9]{17}', r.text)
            if vins: results["findings"].append({"source": "google", "vins": list(set(vins))[:3]})
    except: pass
    
    try:
        r = requests.get(f"https://yandex.ru/search/?text={clean}+госномер", timeout=5, headers=H)
        if r.status_code == 200:
            models = re.findall(r'(?:Toyota|Honda|BMW|Mercedes|Audi|Lada|Kia|Hyundai|VW|Ford|Renault|Nissan|Mazda|Mitsubishi|Lexus|Subaru)[^\<]{0,50}', r.text)
            if models: results["findings"].append({"source": "yandex", "models": list(set(models))[:5]})
    except: pass
    
    return results

def search_domain(domain):
    clean = domain.replace('https://', '').replace('http://', '').replace('www.', '').split('/')[0]
    results = {"domain": clean, "findings": []}
    
    try:
        r = requests.get(f"https://dns.google/resolve?name={clean}", timeout=5, headers=H)
        if r.status_code == 200:
            d = r.json()
            if d.get('Answer'): results["findings"].append({"source": "dns", "records": d['Answer']})
    except: pass
    
    try:
        r = requests.get(f"https://crt.sh/?q={clean}&output=json", timeout=5, headers=H)
        if r.status_code == 200 and r.text.strip():
            certs = r.json()
            subdomains = set()
            for c in certs[:10]:
                if 'name_value' in c:
                    for n in c['name_value'].split('\n'):
                        if clean in n: subdomains.add(n.strip())
            if subdomains: results["findings"].append({"source": "crt", "subdomains": list(subdomains)[:10]})
    except: pass
    
    return results

def format_advanced_report(results, query_type):
    lines = []
    
    if query_type == "fio":
        lines.append("👤 **ФИО:** " + results.get("fio", ""))
        lines.append("")
        for f in results.get("findings", []):
            src = f.get("source", "")
            if src == "vk_search":
                lines.append(f"📱 VK: {len(f.get('matches', []))} совпадений")
                for m in f.get('matches', [])[:5]: lines.append(f"├ {m}")
                lines.append("")
            elif src == "google":
                if f.get("phones"): lines.append(f"📱 Телефоны: {', '.join(f['phones'][:5])}")
                if f.get("emails"): lines.append(f"📧 Email: {', '.join(f['emails'][:5])}")
                lines.append("")
            elif src == "yandex" and f.get("addresses"):
                lines.append("📍 Адреса:")
                for a in f['addresses'][:5]: lines.append(f"├ {a}")
                lines.append("")
    
    elif query_type == "ip":
        lines.append("🌍 **IP:** " + results.get("ip", ""))
        lines.append("")
        for f in results.get("findings", []):
            src = f.get("source", "")
            if src == "ipapi":
                d = f.get("data", {})
                lines.append("📍 **Геолокация:**")
                lines.append(f"├ Страна: {d.get('country', '?')}")
                lines.append(f"├ Регион: {d.get('region', '?')}")
                lines.append(f"├ Город: {d.get('city', '?')}")
                lines.append(f"├ Провайдер: {d.get('isp', '?')}")
                lines.append(f"└ Координаты: {d.get('lat')}, {d.get('lon')}")
                lines.append("")
            elif src == "ipinfo":
                d = f.get("data", {})
                if d.get('hostname'): lines.append(f"├ Хост: {d['hostname']}")
                if d.get('org'): lines.append(f"└ Орг: {d['org']}")
                lines.append("")
    
    elif query_type == "car":
        lines.append("🚗 **АВТО:** " + results.get("car", ""))
        lines.append("")
        for f in results.get("findings", []):
            if f.get("vins"): lines.append(f"🔢 VIN: {', '.join(f['vins'][:3])}")
            if f.get("models"): lines.append(f"🚙 Модели: {', '.join(f['models'][:5])}")
        if not results.get("findings"): lines.append("❌ Ничего не найдено")
    
    elif query_type == "domain":
        lines.append("🌐 **ДОМЕН:** " + results.get("domain", ""))
        lines.append("")
        for f in results.get("findings", []):
            if f.get("records"): lines.append(f"🔗 DNS: {len(f['records'])} записей")
            if f.get("subdomains"):
                lines.append(f"📜 Поддомены: {len(f['subdomains'])}")
                for s in f['subdomains'][:10]: lines.append(f"├ {s}")
        if not results.get("findings"): lines.append("❌ Ничего не найдено")
    
    lines.append("_" * 30)
    lines.append("🔍 **Lexton Mega OSINT**")
    return "\n".join(lines)

def search_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    kb.add(KeyboardButton("🔍 Искать"), KeyboardButton("🔍 Расширенный поиск"))
    kb.add(KeyboardButton("💳 Купить подписку"), KeyboardButton("ℹ️ Статус"))
    kb.add(KeyboardButton("🔙 Назад"))
    return kb

@bot.message_handler(func=lambda m: m.text == "🔍 Расширенный поиск")
def advanced_search_menu(message):
    uid = message.from_user.id
    if is_banned(uid): return
    if not has_access(uid): bot.send_message(uid, "❌ Нет доступа"); return
    
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    kb.add(KeyboardButton("👤 Поиск по ФИО"), KeyboardButton("🌍 Поиск по IP"))
    kb.add(KeyboardButton("🚗 Поиск по авто"), KeyboardButton("🌐 Поиск по домену"))
    kb.add(KeyboardButton("🔙 Назад"))
    
    bot.send_message(uid, "🔍 **Расширенный поиск**\n\nВыбери тип:", parse_mode="Markdown", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "👤 Поиск по ФИО")
def fio_search(message):
    uid = message.from_user.id
    if not has_access(uid): bot.send_message(uid, "❌ Нет доступа"); return
    msg = bot.send_message(uid, "👤 Введи ФИО:\nПример: Иванов Иван Иванович")
    bot.register_next_step_handler(msg, lambda m: process_advanced(m, uid, "fio"))

@bot.message_handler(func=lambda m: m.text == "🌍 Поиск по IP")
def ip_search(message):
    uid = message.from_user.id
    if not has_access(uid): bot.send_message(uid, "❌ Нет доступа"); return
    msg = bot.send_message(uid, "🌍 Введи IP адрес:\nПример: 8.8.8.8")
    bot.register_next_step_handler(msg, lambda m: process_advanced(m, uid, "ip"))

@bot.message_handler(func=lambda m: m.text == "🚗 Поиск по авто")
def car_search(message):
    uid = message.from_user.id
    if not has_access(uid): bot.send_message(uid, "❌ Нет доступа"); return
    msg = bot.send_message(uid, "🚗 Введи госномер:\nПример: А123БВ177")
    bot.register_next_step_handler(msg, lambda m: process_advanced(m, uid, "car"))

@bot.message_handler(func=lambda m: m.text == "🌐 Поиск по домену")
def domain_search(message):
    uid = message.from_user.id
    if not has_access(uid): bot.send_message(uid, "❌ Нет доступа"); return
    msg = bot.send_message(uid, "🌐 Введи домен:\nПример: example.com")
    bot.register_next_step_handler(msg, lambda m: process_advanced(m, uid, "domain"))

def process_advanced(message, uid, qtype):
    query = message.text.strip()
    loading = bot.send_message(uid, f"🔍 Поиск {qtype}...\n⏳ ~30-60 сек\n[░░░░░░░░░░░░░░░░░░░░] 0%", parse_mode="Markdown")
    
    def run():
        try:
            for p in range(20, 101, 20):
                bar = "█" * (p // 5) + "░" * (20 - p // 5)
                try: bot.edit_message_text(f"🔍 Поиск {qtype}...\n⏳ {p}%\n[{bar}] {p}%", uid, loading.message_id)
                except: pass
                time.sleep(2)
            
            if qtype == "fio": results = search_by_fullname(query)
            elif qtype == "ip": results = search_ip(query)
            elif qtype == "car": results = search_car(query)
            elif qtype == "domain": results = search_domain(query)
            else: return
            
            report = format_advanced_report(results, qtype)
            
            if len(report) > 4000:
                parts = [report[i:i+4000] for i in range(0, len(report), 4000)]
                for i, part in enumerate(parts):
                    if i == 0: bot.edit_message_text(part, uid, loading.message_id, parse_mode="Markdown")
                    else: bot.send_message(uid, part, parse_mode="Markdown")
            else:
                bot.edit_message_text(report, uid, loading.message_id, parse_mode="Markdown")
        except Exception as e:
            try: bot.edit_message_text(f"❌ Ошибка: {str(e)[:100]}", uid, loading.message_id)
            except: pass
    
    threading.Thread(target=run).start()

def search_snils(snils):
    clean = ''.join(filter(str.isdigit, snils))
    results = {"snils": clean, "findings": []}
    
    try:
        r = requests.get(f"https://www.google.com/search?q={clean}+снилс", timeout=5, headers=H)
        if r.status_code == 200:
            names = re.findall(r'[А-ЯЁ][а-яё]+\s[А-ЯЁ][а-яё]+(?:\s[А-ЯЁ][а-яё]+)?', r.text)
            if names: results["findings"].append({"source": "google", "names": list(set(names))[:5]})
    except: pass
    
    try:
        r = requests.get(f"https://yandex.ru/search/?text={clean}+снилс", timeout=5, headers=H)
        if r.status_code == 200:
            dates = re.findall(r'\d{2}\.\d{2}\.\d{4}', r.text)
            if dates: results["findings"].append({"source": "yandex", "dates": list(set(dates))[:5]})
    except: pass
    
    return results

def search_inn(inn):
    clean = ''.join(filter(str.isdigit, inn))
    results = {"inn": clean, "findings": []}
    
    try:
        r = requests.get(f"https://www.google.com/search?q=инн+{clean}", timeout=5, headers=H)
        if r.status_code == 200:
            names = re.findall(r'[А-ЯЁ][а-яё]+\s[А-ЯЁ][а-яё]+(?:\s[А-ЯЁ][а-яё]+)?', r.text)
            orgs = re.findall(r'(?:ООО|ИП|АО|ПАО|ЗАО)\s"?[А-ЯЁ][а-яё\s\"]+', r.text)
            if names or orgs: results["findings"].append({"source": "google", "names": list(set(names))[:5], "orgs": list(set(orgs))[:5]})
    except: pass
    
    try:
        r = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getChat?chat_id={clean}", timeout=5, headers=H)
        if r.status_code == 200:
            d = r.json()
            if d.get('ok'): results["findings"].append({"source": "telegram", "chat": d['result']})
    except: pass
    
    return results

def search_passport(passport):
    clean = ''.join(filter(str.isdigit, passport))
    results = {"passport": clean, "findings": []}
    
    try:
        r = requests.get(f"https://www.google.com/search?q=паспорт+{clean}", timeout=5, headers=H)
        if r.status_code == 200:
            names = re.findall(r'[А-ЯЁ][а-яё]+\s[А-ЯЁ][а-яё]+(?:\s[А-ЯЁ][а-яё]+)?', r.text)
            dates = re.findall(r'\d{2}\.\d{2}\.\d{4}', r.text)
            if names or dates: results["findings"].append({"source": "google", "names": list(set(names))[:5], "dates": list(set(dates))[:5]})
    except: pass
    
    return results

def search_address(address):
    results = {"address": address, "findings": []}
    
    try:
        r = requests.get(f"https://www.google.com/search?q={address}", timeout=5, headers=H)
        if r.status_code == 200:
            phones = re.findall(r'\+?[7-8][\d\s\(\)-]{9,15}', r.text)
            names = re.findall(r'[А-ЯЁ][а-яё]+\s[А-ЯЁ][а-яё]+(?:\s[А-ЯЁ][а-яё]+)?', r.text)
            if phones or names: results["findings"].append({"source": "google", "phones": list(set(phones))[:5], "names": list(set(names))[:5]})
    except: pass
    
    try:
        r = requests.get(f"https://yandex.ru/search/?text={address}", timeout=5, headers=H)
        if r.status_code == 200:
            orgs = re.findall(r'(?:ООО|ИП|АО|ПАО)\s"?[А-ЯЁ][а-яё\s\"]+', r.text)
            if orgs: results["findings"].append({"source": "yandex", "orgs": list(set(orgs))[:5]})
    except: pass
    
    try:
        r = requests.get(f"https://nominatim.openstreetmap.org/search?q={address}&format=json&limit=1", timeout=5, headers=H)
        if r.status_code == 200:
            data = r.json()
            if data: results["findings"].append({"source": "osm", "data": data[0]})
    except: pass
    
    return results

def search_photo_url(photo_url):
    results = {"photo": photo_url, "findings": []}
    
    try:
        r = requests.get(f"https://www.google.com/searchbyimage?image_url={photo_url}", timeout=5, headers=H)
        if r.status_code == 200:
            links = re.findall(r'https?://[^\s<>"]+', r.text)
            if links: results["findings"].append({"source": "google_reverse", "links": list(set(links))[:10]})
    except: pass
    
    try:
        r = requests.get(f"https://yandex.ru/images/search?rpt=imageview&url={photo_url}", timeout=5, headers=H)
        if r.status_code == 200:
            tags = re.findall(r'"description":"([^"]+)"', r.text)
            if tags: results["findings"].append({"source": "yandex_reverse", "tags": list(set(tags))[:5]})
    except: pass
    
    return results

def format_docs_report(results, query_type):
    lines = []
    
    if query_type == "snils":
        lines.append("📄 **СНИЛС:** " + results.get("snils", ""))
        for f in results.get("findings", []):
            if f.get("names"): lines.append(f"👤 Имена: {', '.join(f['names'][:5])}")
            if f.get("dates"): lines.append(f"📅 Даты: {', '.join(f['dates'][:5])}")
        if not results.get("findings"): lines.append("❌ Ничего не найдено")
    
    elif query_type == "inn":
        lines.append("📄 **ИНН:** " + results.get("inn", ""))
        for f in results.get("findings", []):
            if f.get("names"): lines.append(f"👤 Физлица: {', '.join(f['names'][:5])}")
            if f.get("orgs"): lines.append(f"🏢 Организации: {', '.join(f['orgs'][:5])}")
            if f.get("chat"): lines.append(f"📱 Telegram: {f['chat'].get('title') or f['chat'].get('first_name')} (ID: {f['chat'].get('id')})")
        if not results.get("findings"): lines.append("❌ Ничего не найдено")
    
    elif query_type == "passport":
        lines.append("📄 **ПАСПОРТ:** " + results.get("passport", ""))
        for f in results.get("findings", []):
            if f.get("names"): lines.append(f"👤 Имена: {', '.join(f['names'][:5])}")
            if f.get("dates"): lines.append(f"📅 Даты: {', '.join(f['dates'][:5])}")
        if not results.get("findings"): lines.append("❌ Ничего не найдено")
    
    elif query_type == "address":
        lines.append("📍 **АДРЕС:** " + results.get("address", ""))
        for f in results.get("findings", []):
            if f.get("phones"): lines.append(f"📱 Телефоны: {', '.join(f['phones'][:5])}")
            if f.get("names"): lines.append(f"👤 Имена: {', '.join(f['names'][:5])}")
            if f.get("orgs"): lines.append(f"🏢 Организации: {', '.join(f['orgs'][:5])}")
            if f.get("data"): lines.append(f"📍 OSM: {f['data'].get('display_name', '')[:200]}")
        if not results.get("findings"): lines.append("❌ Ничего не найдено")
    
    elif query_type == "photo":
        lines.append("🖼 **ФОТО:** поиск завершён")
        for f in results.get("findings", []):
            if f.get("links"): lines.append(f"🔗 Ссылок: {len(f['links'])}")
            if f.get("tags"): lines.append(f"🏷 Теги: {', '.join(f['tags'][:5])}")
        if not results.get("findings"): lines.append("❌ Совпадений не найдено")
    
    lines.append("_" * 30)
    lines.append("🔍 **Lexton Mega OSINT**")
    return "\n".join(lines)

def search_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    kb.add(KeyboardButton("🔍 Искать"), KeyboardButton("🔍 Расширенный поиск"))
    kb.add(KeyboardButton("📄 Поиск документов"), KeyboardButton("💳 Купить подписку"))
    kb.add(KeyboardButton("ℹ️ Статус"), KeyboardButton("🔙 Назад"))
    return kb

@bot.message_handler(func=lambda m: m.text == "📄 Поиск документов")
def docs_search_menu(message):
    uid = message.from_user.id
    if is_banned(uid): return
    if not has_access(uid): bot.send_message(uid, "❌ Нет доступа"); return
    
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    kb.add(KeyboardButton("📄 Поиск по СНИЛС"), KeyboardButton("📄 Поиск по ИНН"))
    kb.add(KeyboardButton("📄 Поиск по паспорту"), KeyboardButton("📍 Поиск по адресу"))
    kb.add(KeyboardButton("🖼 Поиск по фото"), KeyboardButton("🔙 Назад"))
    
    bot.send_message(uid, "📄 **Поиск документов**\n\nВыбери тип:", parse_mode="Markdown", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "📄 Поиск по СНИЛС")
def snils_search(message):
    uid = message.from_user.id
    if not has_access(uid): bot.send_message(uid, "❌ Нет доступа"); return
    msg = bot.send_message(uid, "📄 Введи СНИЛС:\nПример: 12345678901")
    bot.register_next_step_handler(msg, lambda m: process_docs(m, uid, "snils"))

@bot.message_handler(func=lambda m: m.text == "📄 Поиск по ИНН")
def inn_search(message):
    uid = message.from_user.id
    if not has_access(uid): bot.send_message(uid, "❌ Нет доступа"); return
    msg = bot.send_message(uid, "📄 Введи ИНН:\nПример: 123456789012")
    bot.register_next_step_handler(msg, lambda m: process_docs(m, uid, "inn"))

@bot.message_handler(func=lambda m: m.text == "📄 Поиск по паспорту")
def passport_search(message):
    uid = message.from_user.id
    if not has_access(uid): bot.send_message(uid, "❌ Нет доступа"); return
    msg = bot.send_message(uid, "📄 Введи номер паспорта:\nПример: 4510123456")
    bot.register_next_step_handler(msg, lambda m: process_docs(m, uid, "passport"))

@bot.message_handler(func=lambda m: m.text == "📍 Поиск по адресу")
def address_search(message):
    uid = message.from_user.id
    if not has_access(uid): bot.send_message(uid, "❌ Нет доступа"); return
    msg = bot.send_message(uid, "📍 Введи адрес:\nПример: Москва, Тверская 1")
    bot.register_next_step_handler(msg, lambda m: process_docs(m, uid, "address"))

@bot.message_handler(func=lambda m: m.text == "🖼 Поиск по фото")
def photo_search(message):
    uid = message.from_user.id
    if not has_access(uid): bot.send_message(uid, "❌ Нет доступа"); return
    msg = bot.send_message(uid, "🖼 Отправь ссылку на фото:\nПример: https://example.com/photo.jpg")
    bot.register_next_step_handler(msg, lambda m: process_docs(m, uid, "photo"))

def process_docs(message, uid, qtype):
    query = message.text.strip()
    loading = bot.send_message(uid, f"🔍 Поиск {qtype}...\n⏳ ~30-60 сек\n[░░░░░░░░░░░░░░░░░░░░] 0%", parse_mode="Markdown")
    
    def run():
        try:
            for p in range(20, 101, 20):
                bar = "█" * (p // 5) + "░" * (20 - p // 5)
                try: bot.edit_message_text(f"🔍 Поиск {qtype}...\n⏳ {p}%\n[{bar}] {p}%", uid, loading.message_id)
                except: pass
                time.sleep(2)
            
            if qtype == "snils": results = search_snils(query)
            elif qtype == "inn": results = search_inn(query)
            elif qtype == "passport": results = search_passport(query)
            elif qtype == "address": results = search_address(query)
            elif qtype == "photo": results = search_photo_url(query)
            else: return
            
            report = format_docs_report(results, qtype)
            
            if len(report) > 4000:
                parts = [report[i:i+4000] for i in range(0, len(report), 4000)]
                for i, part in enumerate(parts):
                    if i == 0: bot.edit_message_text(part, uid, loading.message_id, parse_mode="Markdown")
                    else: bot.send_message(uid, part, parse_mode="Markdown")
            else:
                bot.edit_message_text(report, uid, loading.message_id, parse_mode="Markdown")
        except Exception as e:
            try: bot.edit_message_text(f"❌ Ошибка: {str(e)[:100]}", uid, loading.message_id)
            except: pass
    
    threading.Thread(target=run).start()

def search_vk_profile(url_or_id):
    clean = url_or_id.replace('https://', '').replace('http://', '').replace('vk.com/', '').replace('@', '')
    results = {"vk": clean, "findings": []}
    
    try:
        r = requests.get(f"https://api.vk.com/method/users.get?user_ids={clean}&fields=about,activities,bdate,books,city,connections,contacts,education,followers_count,home_town,interests,last_seen,movies,music,personal,relation,sex,screen_name,status,universities&v=5.131", timeout=5, headers=H)
        if r.status_code == 200:
            d = r.json()
            if 'response' in d and d['response']:
                results["findings"].append({"source": "vk_api", "data": d['response'][0]})
    except: pass
    
    try:
        r = requests.get(f"https://www.google.com/search?q=site:vk.com+{clean}", timeout=5, headers=H)
        if r.status_code == 200:
            phones = re.findall(r'\+?[7-8][\d\s\(\)-]{9,15}', r.text)
            emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', r.text)
            if phones or emails: results["findings"].append({"source": "google", "phones": list(set(phones))[:5], "emails": list(set(emails))[:5]})
    except: pass
    
    return results

def search_ok_profile(url_or_id):
    clean = url_or_id.replace('https://', '').replace('http://', '').replace('ok.ru/', '').replace('profile/', '')
    results = {"ok": clean, "findings": []}
    
    try:
        r = requests.get(f"https://ok.ru/profile/{clean}", timeout=5, headers=H)
        if r.status_code == 200:
            title = re.search(r'<meta property="og:title" content="(.*?)">', r.text)
            desc = re.search(r'<meta property="og:description" content="(.*?)">', r.text)
            if title: results["findings"].append({"source": "ok", "title": title.group(1), "desc": desc.group(1) if desc else ""})
    except: pass
    
    try:
        r = requests.get(f"https://www.google.com/search?q=site:ok.ru+{clean}", timeout=5, headers=H)
        if r.status_code == 200:
            phones = re.findall(r'\+?[7-8][\d\s\(\)-]{9,15}', r.text)
            if phones: results["findings"].append({"source": "google", "phones": list(set(phones))[:5]})
    except: pass
    
    return results

def search_telegram_chat(chat_id):
    results = {"tg": chat_id, "findings": []}
    
    try:
        r = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getChat?chat_id={chat_id}", timeout=5)
        if r.status_code == 200:
            d = r.json()
            if d.get('ok'): results["findings"].append({"source": "tg_api", "data": d['result']})
    except: pass
    
    try:
        r = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMemberCount?chat_id={chat_id}", timeout=5)
        if r.status_code == 200:
            d = r.json()
            if d.get('ok'): results["findings"].append({"source": "tg_members", "count": d['result']})
    except: pass
    
    return results

def search_viber(phone):
    clean = ''.join(filter(str.isdigit, phone))
    results = {"viber": clean, "findings": []}
    
    try:
        r = requests.post("https://api.viber.com/pa/check_contact", json={"contacts": [{"phone_number": clean}]}, timeout=5, headers=H)
        if r.status_code == 200: results["findings"].append({"source": "viber_api", "data": r.json()})
    except: pass
    
    try:
        r = requests.get(f"https://invite.viber.com/?g2=AQB&number=%2B{clean}", timeout=5, headers=H, allow_redirects=False)
        if r.status_code in [200, 302]: results["findings"].append({"source": "viber_invite", "exists": True})
    except: pass
    
    return results

def search_whatsapp_info(phone):
    clean = ''.join(filter(str.isdigit, phone))
    results = {"wa": clean, "findings": []}
    
    try:
        r = requests.get(f"https://wa.me/{clean}", timeout=5, headers=H, allow_redirects=True)
        if r.status_code == 200 and len(r.text) > 500:
            title = re.search(r'<meta property="og:title" content="(.*?)">', r.text)
            desc = re.search(r'<meta property="og:description" content="(.*?)">', r.text)
            if title: results["findings"].append({"source": "wa", "title": title.group(1), "desc": desc.group(1) if desc else ""})
    except: pass
    
    return results

def search_banks(phone_or_name):
    query = ''.join(filter(str.isdigit, phone_or_name)) if phone_or_name.replace('+','').isdigit() else phone_or_name
    results = {"bank_query": query, "findings": []}
    
    banks = [
        ("Сбербанк", f"https://www.sberbank.ru/ru/person"),
        ("Тинькофф", f"https://www.tinkoff.ru/"),
        ("Альфа-Банк", f"https://alfabank.ru/"),
        ("ВТБ", f"https://www.vtb.ru/"),
        ("Райффайзен", f"https://www.raiffeisen.ru/"),
    ]
    
    for bank_name, url in banks:
        try:
            r = requests.get(f"https://www.google.com/search?q={query}+{bank_name}", timeout=5, headers=H)
            if r.status_code == 200 and len(r.text) > 1000:
                results["findings"].append({"source": bank_name, "found": True})
        except: pass
    
    return results

def search_social_media_complete(query):
    results = {"query": query, "findings": [], "profiles": []}
    
    platforms = [
        ("Facebook", f"https://www.facebook.com/{query}"),
        ("Instagram", f"https://www.instagram.com/{query}"),
        ("Twitter", f"https://twitter.com/{query}"),
        ("LinkedIn", f"https://www.linkedin.com/in/{query}"),
        ("TikTok", f"https://www.tiktok.com/@{query}"),
        ("Snapchat", f"https://www.snapchat.com/add/{query}"),
        ("Pinterest", f"https://www.pinterest.com/{query}"),
        ("Reddit", f"https://www.reddit.com/user/{query}"),
        ("Twitch", f"https://www.twitch.tv/{query}"),
        ("YouTube", f"https://www.youtube.com/@{query}"),
        ("GitHub", f"https://github.com/{query}"),
        ("Steam", f"https://steamcommunity.com/id/{query}"),
        ("Spotify", f"https://open.spotify.com/user/{query}"),
        ("SoundCloud", f"https://soundcloud.com/{query}"),
        ("Medium", f"https://medium.com/@{query}"),
        ("Patreon", f"https://www.patreon.com/{query}"),
        ("Behance", f"https://www.behance.net/{query}"),
        ("Dribbble", f"https://dribbble.com/{query}"),
        ("Flickr", f"https://www.flickr.com/people/{query}"),
        ("DeviantArt", f"https://www.deviantart.com/{query}"),
        ("Keybase", f"https://keybase.io/{query}"),
        ("ProductHunt", f"https://www.producthunt.com/@{query}"),
        ("HackerNews", f"https://news.ycombinator.com/user?id={query}"),
        ("Vimeo", f"https://vimeo.com/{query}"),
        ("About.me", f"https://about.me/{query}"),
        ("Mixcloud", f"https://www.mixcloud.com/{query}"),
        ("Slideshare", f"https://www.slideshare.net/{query}"),
        ("Issuu", f"https://issuu.com/{query}"),
        ("BuzzFeed", f"https://www.buzzfeed.com/{query}"),
        ("Wattpad", f"https://www.wattpad.com/user/{query}"),
    ]
    
    for site, url in platforms:
        try:
            r = requests.get(url, timeout=4, headers=H, allow_redirects=True)
            if r.status_code == 200 and len(r.text) > 500:
                title_match = re.search(r'<meta property="og:title" content="(.*?)">', r.text) or re.search(r'<title>(.*?)</title>', r.text)
                if title_match:
                    title = title_match.group(1).strip()
                    bad = ['Error', 'Not Found', '404', 'Page Not Found', 'не найден']
                    if not any(b.lower() in title.lower() for b in bad) and title.lower() != query.lower():
                        results["profiles"].append({"site": site, "url": url, "title": title[:150]})
        except: pass
    
    try:
        r = requests.get(f"https://haveibeenpwned.com/api/v3/breachedaccount/{query}", timeout=5, headers=H)
        if r.status_code == 200: results["findings"].append({"source": "leaks", "breaches": r.json()[:10]})
    except: pass
    
    return results

def format_social_report(results):
    lines = []
    lines.append("🔍 **СОЦИАЛЬНЫЙ ПОИСК:** " + results.get("query", ""))
    lines.append("")
    
    profiles = results.get("profiles", [])
    if profiles:
        lines.append(f"📱 Найдено {len(profiles)} профилей:")
        lines.append("")
        for p in profiles:
            lines.append(f"├ ✅ {p['site']}: {p['title']}")
        lines.append("")
    
    for f in results.get("findings", []):
        if f.get("source") == "leaks" and f.get("breaches"):
            lines.append(f"🔓 Утечек: {len(f['breaches'])}")
            for b in f['breaches'][:7]:
                if isinstance(b, dict): lines.append(f"├ {b.get('Name','?')} ({b.get('BreachDate','?')[:10]})")
            lines.append("")
    
    if not profiles and not results.get("findings"): lines.append("❌ Ничего не найдено")
    
    lines.append("_" * 30)
    lines.append("🔍 **Lexton Mega OSINT**")
    return "\n".join(lines)

def search_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    kb.add(KeyboardButton("🔍 Искать"), KeyboardButton("🔍 Расширенный поиск"))
    kb.add(KeyboardButton("📄 Поиск документов"), KeyboardButton("🌐 Соцсети 30+"))
    kb.add(KeyboardButton("💳 Купить подписку"), KeyboardButton("ℹ️ Статус"))
    kb.add(KeyboardButton("🔙 Назад"))
    return kb

@bot.message_handler(func=lambda m: m.text == "🌐 Соцсети 30+")
def social_full_search_start(message):
    uid = message.from_user.id
    if not has_access(uid): bot.send_message(uid, "❌ Нет доступа"); return
    msg = bot.send_message(uid, "🌐 Введи username или email:\nПример: @user или user@mail.ru")
    bot.register_next_step_handler(msg, lambda m: social_full_search(m, uid))

def social_full_search(message, uid):
    query = message.text.strip().lstrip('@')
    loading = bot.send_message(uid, f"🌐 Поиск по 30+ соцсетям...\n⏳ ~90-120 сек\n[░░░░░░░░░░░░░░░░░░░░] 0%", parse_mode="Markdown")
    
    def run():
        try:
            for p in range(10, 101, 10):
                bar = "█" * (p // 5) + "░" * (20 - p // 5)
                try: bot.edit_message_text(f"🌐 Проверка соцсетей...\n⏳ {p}%\n[{bar}] {p}%", uid, loading.message_id)
                except: pass
                time.sleep(2)
            
            results = search_social_media_complete(query)
            report = format_social_report(results)
            
            if len(report) > 4000:
                parts = [report[i:i+4000] for i in range(0, len(report), 4000)]
                for i, part in enumerate(parts):
                    if i == 0: bot.edit_message_text(part, uid, loading.message_id, parse_mode="Markdown")
                    else: bot.send_message(uid, part, parse_mode="Markdown")
            else:
                bot.edit_message_text(report, uid, loading.message_id, parse_mode="Markdown")
        except Exception as e:
            try: bot.edit_message_text(f"❌ Ошибка: {str(e)[:100]}", uid, loading.message_id)
            except: pass
    
    threading.Thread(target=run).start()

def search_google_dork(query):
    results = {"query": query, "findings": []}
    
    dorks = [
        f'site:vk.com "{query}"',
        f'site:ok.ru "{query}"',
        f'site:facebook.com "{query}"',
        f'site:instagram.com "{query}"',
        f'site:twitter.com "{query}"',
        f'site:linkedin.com "{query}"',
        f'site:github.com "{query}"',
        f'site:t.me "{query}"',
        f'intitle:"{query}"',
        f'intext:"{query}" filetype:pdf',
        f'"{query}" phone OR email OR адрес',
    ]
    
    for dork in dorks[:5]:
        try:
            r = requests.get(f"https://www.google.com/search?q={dork}", timeout=5, headers=H)
            if r.status_code == 200:
                links = re.findall(r'https?://[^\s<>"]+', r.text)
                emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', r.text)
                phones = re.findall(r'\+?[7-8][\d\s\(\)-]{9,15}', r.text)
                if links or emails or phones:
                    results["findings"].append({
                        "dork": dork,
                        "links": list(set(links))[:10],
                        "emails": list(set(emails))[:5],
                        "phones": list(set(phones))[:5]
                    })
        except: pass
    
    return results

def search_yandex_dork(query):
    results = {"query": query, "findings": []}
    
    ya_dorks = [
        f'"{query}" site:vk.com',
        f'"{query}" site:ok.ru',
        f'"{query}" site:t.me',
        f'"{query}" телефон',
        f'"{query}" email',
    ]
    
    for dork in ya_dorks[:3]:
        try:
            r = requests.get(f"https://yandex.ru/search/?text={dork}", timeout=5, headers=H)
            if r.status_code == 200:
                links = re.findall(r'https?://[^\s<>"]+', r.text)
                if links: results["findings"].append({"dork": dork, "links": list(set(links))[:10]})
        except: pass
    
    return results

def search_pastebin(query):
    results = {"query": query, "findings": []}
    
    try:
        r = requests.get(f"https://www.google.com/search?q=site:pastebin.com+{query}", timeout=5, headers=H)
        if r.status_code == 200:
            links = re.findall(r'https?://pastebin\.com/[^\s<>"]+', r.text)
            if links: results["findings"].append({"source": "pastebin", "links": list(set(links))[:10]})
    except: pass
    
    try:
        r = requests.get(f"https://www.google.com/search?q=site:telegra.ph+{query}", timeout=5, headers=H)
        if r.status_code == 200:
            links = re.findall(r'https?://telegra\.ph/[^\s<>"]+', r.text)
            if links: results["findings"].append({"source": "telegraph", "links": list(set(links))[:10]})
    except: pass
    
    return results

def search_deep_web(query):
    results = {"query": query, "findings": []}
    
    forums = [
        f"site:xss.is {query}",
        f"site:exploit.in {query}",
        f"site:lolz.guru {query}",
        f"site:nulled.to {query}",
        f"site:cracked.io {query}",
    ]
    
    for dork in forums[:3]:
        try:
            r = requests.get(f"https://www.google.com/search?q={dork}", timeout=5, headers=H)
            if r.status_code == 200:
                links = re.findall(r'https?://[^\s<>"]+', r.text)
                if links: results["findings"].append({"dork": dork, "links": list(set(links))[:5]})
        except: pass
    
    return results

def search_email_breach(email):
    results = {"email": email, "breaches": [], "passwords": [], "hashes": []}
    
    try:
        r = requests.get(f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}", timeout=5, headers=H)
        if r.status_code == 200:
            results["breaches"] = r.json()
    except: pass
    
    try:
        h = hashlib.sha1(email.strip().lower().encode()).hexdigest().upper()
        r = requests.get(f"https://api.pwnedpasswords.com/range/{h[:5]}", timeout=5, headers=H)
        if r.status_code == 200:
            for line in r.text.split('\n'):
                if h[5:] in line:
                    count = line.split(':')[1].strip()
                    results["passwords"].append({"hash": h, "found": True, "count": int(count)})
    except: pass
    
    return results

def search_phone_reputation(phone):
    clean = ''.join(filter(str.isdigit, phone))
    results = {"phone": clean, "reports": [], "scam": False}
    
    sites = [
        f"https://www.google.com/search?q={clean}+мошенник",
        f"https://www.google.com/search?q={clean}+отзывы",
        f"https://www.google.com/search?q={clean}+жалоба",
    ]
    
    for url in sites[:2]:
        try:
            r = requests.get(url, timeout=5, headers=H)
            if r.status_code == 200:
                if 'мошенник' in r.text.lower() or 'scam' in r.text.lower():
                    results["scam"] = True
                snippets = re.findall(r'<div class="BNeawe s3v9rd AP7Wnd">(.*?)</div>', r.text)
                if snippets: results["reports"].extend(snippets[:5])
        except: pass
    
    return results

def search_company_info(company_name):
    results = {"company": company_name, "findings": []}
    
    try:
        r = requests.get(f"https://www.google.com/search?q={company_name}+ИНН+ОГРН", timeout=5, headers=H)
        if r.status_code == 200:
            inn = re.findall(r'ИНН[:\s]*(\d{10,12})', r.text)
            ogrn = re.findall(r'ОГРН[:\s]*(\d{13})', r.text)
            if inn or ogrn: results["findings"].append({"source": "google", "inn": list(set(inn))[:3], "ogrn": list(set(ogrn))[:3]})
    except: pass
    
    try:
        r = requests.get(f"https://www.google.com/search?q={company_name}+директор+владелец", timeout=5, headers=H)
        if r.status_code == 200:
            names = re.findall(r'[А-ЯЁ][а-яё]+\s[А-ЯЁ][а-яё]+(?:\s[А-ЯЁ][а-яё]+)?', r.text)
            phones = re.findall(r'\+?[7-8][\d\s\(\)-]{9,15}', r.text)
            if names or phones: results["findings"].append({"source": "google_people", "names": list(set(names))[:5], "phones": list(set(phones))[:3]})
    except: pass
    
    return results

def format_deep_report(results, query_type):
    lines = []
    
    if query_type == "dork":
        lines.append("🔍 **GOOGLE DORKS:** " + results.get("query", ""))
        lines.append("")
        for f in results.get("findings", []):
            lines.append(f"├ Запрос: {f.get('dork', '')}")
            if f.get("emails"): lines.append(f"│ 📧 {', '.join(f['emails'][:3])}")
            if f.get("phones"): lines.append(f"│ 📱 {', '.join(f['phones'][:3])}")
            if f.get("links"): lines.append(f"│ 🔗 Ссылок: {len(f['links'])}")
            lines.append("")
    
    elif query_type == "pastebin":
        lines.append("📝 **ПОИСК СЛИВОВ:** " + results.get("query", ""))
        lines.append("")
        for f in results.get("findings", []):
            lines.append(f"├ {f.get('source', '')}: {len(f.get('links', []))} ссылок")
        if not results.get("findings"): lines.append("❌ Ничего не найдено")
    
    elif query_type == "email_breach":
        lines.append("🔓 **УТЕЧКИ:** " + results.get("email", ""))
        lines.append("")
        breaches = results.get("breaches", [])
        if isinstance(breaches, list) and breaches:
            lines.append(f"├ Найден в {len(breaches)} утечках:")
            for b in breaches[:10]:
                if isinstance(b, dict): lines.append(f"│ • {b.get('Name','?')} ({b.get('BreachDate','?')[:10]})")
        else: lines.append("├ Не найден в утечках")
        
        passwords = results.get("passwords", [])
        if passwords:
            lines.append(f"├ 🔑 Пароль найден в утечках!")
        lines.append("")
    
    elif query_type == "phone_rep":
        lines.append("📱 **РЕПУТАЦИЯ:** " + results.get("phone", ""))
        lines.append("")
        if results.get("scam"): lines.append("🚩 НОМЕР ЗАМЕЧЕН В МОШЕННИЧЕСТВЕ!")
        else: lines.append("✅ Жалоб не найдено")
        reports = results.get("reports", [])
        if reports:
            lines.append("├ Отзывы:")
            for r in reports[:5]: lines.append(f"│ • {r[:200]}")
        lines.append("")
    
    elif query_type == "company":
        lines.append("🏢 **КОМПАНИЯ:** " + results.get("company", ""))
        lines.append("")
        for f in results.get("findings", []):
            if f.get("inn"): lines.append(f"├ ИНН: {', '.join(f['inn'][:3])}")
            if f.get("ogrn"): lines.append(f"├ ОГРН: {', '.join(f['ogrn'][:3])}")
            if f.get("names"): lines.append(f"├ Связанные лица: {', '.join(f['names'][:5])}")
            if f.get("phones"): lines.append(f"├ Телефоны: {', '.join(f['phones'][:3])}")
        if not results.get("findings"): lines.append("❌ Ничего не найдено")
    
    lines.append("_" * 30)
    lines.append("🔍 **Lexton Mega OSINT**")
    return "\n".join(lines)

def search_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    kb.add(KeyboardButton("🔍 Искать"), KeyboardButton("🔍 Расширенный поиск"))
    kb.add(KeyboardButton("📄 Поиск документов"), KeyboardButton("🌐 Соцсети 30+"))
    kb.add(KeyboardButton("🔎 Глубокий поиск"), KeyboardButton("💳 Купить подписку"))
    kb.add(KeyboardButton("ℹ️ Статус"), KeyboardButton("🔙 Назад"))
    return kb

@bot.message_handler(func=lambda m: m.text == "🔎 Глубокий поиск")
def deep_search_menu(message):
    uid = message.from_user.id
    if is_banned(uid): return
    if not has_access(uid): bot.send_message(uid, "❌ Нет доступа"); return
    
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    kb.add(KeyboardButton("🔍 Google Dorks"), KeyboardButton("📝 Поиск сливов"))
    kb.add(KeyboardButton("🔓 Утечки email"), KeyboardButton("📱 Репутация номера"))
    kb.add(KeyboardButton("🏢 Поиск компании"), KeyboardButton("🔙 Назад"))
    
    bot.send_message(uid, "🔎 **Глубокий поиск**\n\nВыбери тип:", parse_mode="Markdown", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "🔍 Google Dorks")
def gdork_search(message):
    uid = message.from_user.id
    if not has_access(uid): bot.send_message(uid, "❌ Нет доступа"); return
    msg = bot.send_message(uid, "🔍 Введи запрос:\nПример: Иванов Иван")
    bot.register_next_step_handler(msg, lambda m: process_deep(m, uid, "dork"))

@bot.message_handler(func=lambda m: m.text == "📝 Поиск сливов")
def pastebin_search(message):
    uid = message.from_user.id
    if not has_access(uid): bot.send_message(uid, "❌ Нет доступа"); return
    msg = bot.send_message(uid, "📝 Введи запрос:\nПример: email или телефон")
    bot.register_next_step_handler(msg, lambda m: process_deep(m, uid, "pastebin"))

@bot.message_handler(func=lambda m: m.text == "🔓 Утечки email")
def email_breach_search(message):
    uid = message.from_user.id
    if not has_access(uid): bot.send_message(uid, "❌ Нет доступа"); return
    msg = bot.send_message(uid, "🔓 Введи email:\nПример: user@mail.ru")
    bot.register_next_step_handler(msg, lambda m: process_deep(m, uid, "email_breach"))

@bot.message_handler(func=lambda m: m.text == "📱 Репутация номера")
def phone_rep_search(message):
    uid = message.from_user.id
    if not has_access(uid): bot.send_message(uid, "❌ Нет доступа"); return
    msg = bot.send_message(uid, "📱 Введи номер:\nПример: +79001234567")
    bot.register_next_step_handler(msg, lambda m: process_deep(m, uid, "phone_rep"))

@bot.message_handler(func=lambda m: m.text == "🏢 Поиск компании")
def company_search(message):
    uid = message.from_user.id
    if not has_access(uid): bot.send_message(uid, "❌ Нет доступа"); return
    msg = bot.send_message(uid, "🏢 Введи название компании:\nПример: ООО Ромашка")
    bot.register_next_step_handler(msg, lambda m: process_deep(m, uid, "company"))

def process_deep(message, uid, qtype):
    query = message.text.strip()
    loading = bot.send_message(uid, f"🔎 Глубокий поиск {qtype}...\n⏳ ~60-90 сек\n[░░░░░░░░░░░░░░░░░░░░] 0%", parse_mode="Markdown")
    
    def run():
        try:
            for p in range(10, 101, 10):
                bar = "█" * (p // 5) + "░" * (20 - p // 5)
                try: bot.edit_message_text(f"🔎 Поиск {qtype}...\n⏳ {p}%\n[{bar}] {p}%", uid, loading.message_id)
                except: pass
                time.sleep(2)
            
            if qtype == "dork": results = search_google_dork(query)
            elif qtype == "pastebin": results = search_pastebin(query)
            elif qtype == "email_breach": results = search_email_breach(query)
            elif qtype == "phone_rep": results = search_phone_reputation(query)
            elif qtype == "company": results = search_company_info(query)
            else: return
            
            report = format_deep_report(results, qtype)
            
            if len(report) > 4000:
                parts = [report[i:i+4000] for i in range(0, len(report), 4000)]
                for i, part in enumerate(parts):
                    if i == 0: bot.edit_message_text(part, uid, loading.message_id, parse_mode="Markdown")
                    else: bot.send_message(uid, part, parse_mode="Markdown")
            else:
                bot.edit_message_text(report, uid, loading.message_id, parse_mode="Markdown")
        except Exception as e:
            try: bot.edit_message_text(f"❌ Ошибка: {str(e)[:100]}", uid, loading.message_id)
            except: pass
    
    threading.Thread(target=run).start()

def search_people_yandex(query):
    results = {"query": query, "findings": []}
    
    try:
        r = requests.get(f"https://yandex.ru/search/?text={query}+контакты+телефон", timeout=5, headers=H)
        if r.status_code == 200:
            phones = re.findall(r'\+?[7-8][\d\s\(\)-]{9,15}', r.text)
            emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', r.text)
            addresses = re.findall(r'(?:г\.|город\s|ул\.|улица\s|д\.|дом\s)[^<]{5,100}', r.text)
            if phones or emails or addresses: results["findings"].append({"source": "yandex", "phones": list(set(phones))[:5], "emails": list(set(emails))[:5], "addresses": list(set(addresses))[:5]})
    except: pass
    
    try:
        r = requests.get(f"https://yandex.ru/search/?text={query}+профиль+биография", timeout=5, headers=H)
        if r.status_code == 200:
            profiles = re.findall(r'https?://[^\s<>"]+(?:vk\.com|ok\.ru|t\.me|instagram\.com)[^\s<>"]*', r.text)
            if profiles: results["findings"].append({"source": "yandex_profiles", "links": list(set(profiles))[:10]})
    except: pass
    
    return results

def search_2gis(query):
    results = {"query": query, "findings": []}
    
    try:
        r = requests.get(f"https://2gis.ru/search/{query}", timeout=5, headers=H)
        if r.status_code == 200:
            names = re.findall(r'[А-ЯЁ][а-яё]+\s[А-ЯЁ][а-яё]+(?:\s[А-ЯЁ][а-яё]+)?', r.text)
            phones = re.findall(r'\+?[7-8][\d\s\(\)-]{9,15}', r.text)
            addresses = re.findall(r'(?:ул\.|улица\s|пр\.|проспект\s|д\.|дом\s)[^<]{5,150}', r.text)
            if names or phones or addresses: results["findings"].append({"source": "2gis", "names": list(set(names))[:5], "phones": list(set(phones))[:5], "addresses": list(set(addresses))[:5]})
    except: pass
    
    return results

def search_avito(query):
    results = {"query": query, "findings": []}
    
    try:
        r = requests.get(f"https://www.avito.ru/?q={query}", timeout=5, headers=H)
        if r.status_code == 200:
            names = re.findall(r'[А-ЯЁ][а-яё]+\s[А-ЯЁ][а-яё]?', r.text)
            phones = re.findall(r'\+?[7-8][\d\s\(\)-]{9,15}', r.text)
            if names or phones: results["findings"].append({"source": "avito", "names": list(set(names))[:5], "phones": list(set(phones))[:5]})
    except: pass
    
    try:
        r = requests.get(f"https://youla.ru/?q={query}", timeout=5, headers=H)
        if r.status_code == 200:
            names = re.findall(r'[А-ЯЁ][а-яё]+\s[А-ЯЁ][а-яё]?', r.text)
            if names: results["findings"].append({"source": "youla", "names": list(set(names))[:5]})
    except: pass
    
    return results

def search_gosuslugi(query):
    results = {"query": query, "findings": []}
    
    try:
        r = requests.get(f"https://www.google.com/search?q=site:gosuslugi.ru+{query}", timeout=5, headers=H)
        if r.status_code == 200:
            links = re.findall(r'https?://[^\s<>"]+gosuslugi[^\s<>"]*', r.text)
            if links: results["findings"].append({"source": "gosuslugi", "links": list(set(links))[:5]})
    except: pass
    
    try:
        r = requests.get(f"https://www.google.com/search?q=site:nalog.ru+{query}", timeout=5, headers=H)
        if r.status_code == 200:
            links = re.findall(r'https?://[^\s<>"]+nalog[^\s<>"]*', r.text)
            if links: results["findings"].append({"source": "nalog", "links": list(set(links))[:5]})
    except: pass
    
    return results

def search_courts(query):
    results = {"query": query, "findings": []}
    
    try:
        r = requests.get(f"https://www.google.com/search?q=site:sudact.ru+{query}", timeout=5, headers=H)
        if r.status_code == 200:
            links = re.findall(r'https?://[^\s<>"]+sudact[^\s<>"]*', r.text)
            if links: results["findings"].append({"source": "sudact", "links": list(set(links))[:5]})
    except: pass
    
    try:
        r = requests.get(f"https://www.google.com/search?q=site:судебныерешения.рф+{query}", timeout=5, headers=H)
        if r.status_code == 200:
            links = re.findall(r'https?://[^\s<>"]+судебныерешения[^\s<>"]*', r.text)
            if links: results["findings"].append({"source": "courts", "links": list(set(links))[:5]})
    except: pass
    
    return results

def search_darknet_mentions(query):
    results = {"query": query, "findings": []}
    
    sites = [
        "lolz.guru", "xss.is", "exploit.in", "nulled.to",
        "cracked.io", "raidforums.com", "breached.to"
    ]
    
    for site in sites[:4]:
        try:
            r = requests.get(f"https://www.google.com/search?q=site:{site}+{query}", timeout=5, headers=H)
            if r.status_code == 200 and len(r.text) > 500:
                results["findings"].append({"source": site, "found": True})
        except: pass
    
    return results

def search_relatives(query):
    results = {"query": query, "findings": []}
    
    try:
        r = requests.get(f"https://www.google.com/search?q={query}+родственники+семья", timeout=5, headers=H)
        if r.status_code == 200:
            names = re.findall(r'[А-ЯЁ][а-яё]+\s[А-ЯЁ][а-яё]+(?:\s[А-ЯЁ][а-яё]+)?', r.text)
            unique_names = list(set(names))
            if query.split()[0] in unique_names: unique_names.remove(query.split()[0])
            if len(unique_names) > 1: results["findings"].append({"source": "google_relatives", "possible_relatives": unique_names[:10]})
    except: pass
    
    try:
        r = requests.get(f"https://yandex.ru/search/?text={query}+родственники", timeout=5, headers=H)
        if r.status_code == 200:
            names = re.findall(r'[А-ЯЁ][а-яё]+\s[А-ЯЁ][а-яё]+(?:\s[А-ЯЁ][а-яё]+)?', r.text)
            unique_names = list(set(names))
            if query.split()[0] in unique_names: unique_names.remove(query.split()[0])
            if len(unique_names) > 1: results["findings"].append({"source": "yandex_relatives", "possible_relatives": unique_names[:10]})
    except: pass
    
    return results

def search_work_history(query):
    results = {"query": query, "findings": []}
    
    try:
        r = requests.get(f"https://www.google.com/search?q={query}+место+работы+должность", timeout=5, headers=H)
        if r.status_code == 200:
            orgs = re.findall(r'(?:ООО|ИП|АО|ПАО|ЗАО)\s"?[А-ЯЁ][а-яё\s\"]+', r.text)
            positions = re.findall(r'(?:директор|менеджер|специалист|руководитель|начальник|сотрудник|работник)[^\<]{0,50}', r.text)
            if orgs or positions: results["findings"].append({"source": "google_work", "orgs": list(set(orgs))[:5], "positions": list(set(positions))[:5]})
    except: pass
    
    try:
        r = requests.get(f"https://www.google.com/search?q=site:linkedin.com+{query}", timeout=5, headers=H)
        if r.status_code == 200:
            links = re.findall(r'https?://[^\s<>"]+linkedin[^\s<>"]*', r.text)
            if links: results["findings"].append({"source": "linkedin", "links": list(set(links))[:5]})
    except: pass
    
    return results

def search_education(query):
    results = {"query": query, "findings": []}
    
    try:
        r = requests.get(f"https://www.google.com/search?q={query}+образование+вуз+школа", timeout=5, headers=H)
        if r.status_code == 200:
            schools = re.findall(r'(?:университет|институт|школа|колледж|академия|вуз|мгу|мфти|мгту|вшэ|ранхигс)[^\<]{0,80}', r.text)
            if schools: results["findings"].append({"source": "google_edu", "schools": list(set(schools))[:5]})
    except: pass
    
    return results

def search_financial(query):
    results = {"query": query, "findings": []}
    
    try:
        r = requests.get(f"https://www.google.com/search?q={query}+долги+кредиты+банкротство", timeout=5, headers=H)
        if r.status_code == 200:
            mentions = re.findall(r'(?:долг|кредит|банкрот|задолженность|микрозайм|пристав)[^\<]{0,100}', r.text)
            if mentions: results["findings"].append({"source": "google_finance", "mentions": list(set(mentions))[:5]})
    except: pass
    
    try:
        r = requests.get(f"https://www.google.com/search?q=site:fssp.gov.ru+{query}", timeout=5, headers=H)
        if r.status_code == 200:
            links = re.findall(r'https?://[^\s<>"]+fssp[^\s<>"]*', r.text)
            if links: results["findings"].append({"source": "fssp", "links": list(set(links))[:5]})
    except: pass
    
    return results

def format_life_report(results, query_type):
    lines = []
    
    if query_type == "people":
        lines.append("👤 **ПОИСК ЧЕЛОВЕКА:** " + results.get("query", ""))
        lines.append("")
        for f in results.get("findings", []):
            src = f.get("source", "")
            if src == "yandex":
                if f.get("phones"): lines.append(f"📱 Телефоны: {', '.join(f['phones'][:5])}")
                if f.get("emails"): lines.append(f"📧 Email: {', '.join(f['emails'][:5])}")
                if f.get("addresses"): lines.append(f"📍 Адреса: {', '.join(f['addresses'][:5])}")
            elif src == "yandex_profiles" and f.get("links"):
                lines.append(f"🔗 Профили: {len(f['links'])}")
                for l in f['links'][:5]: lines.append(f"├ {l}")
            elif src == "2gis":
                if f.get("names"): lines.append(f"👤 Имена: {', '.join(f['names'][:5])}")
                if f.get("phones"): lines.append(f"📱 Телефоны: {', '.join(f['phones'][:5])}")
                if f.get("addresses"): lines.append(f"📍 Адреса: {', '.join(f['addresses'][:5])}")
            elif src in ["avito", "youla"]:
                if f.get("names"): lines.append(f"🛒 {src}: {', '.join(f['names'][:5])}")
                if f.get("phones"): lines.append(f"📱 {', '.join(f['phones'][:5])}")
            elif src in ["gosuslugi", "nalog"]:
                if f.get("links"): lines.append(f"🏛 {src}: найдено {len(f['links'])} упоминаний")
            elif src == "sudact":
                if f.get("links"): lines.append(f"⚖ Суды: {len(f['links'])} дел")
        if not results.get("findings"): lines.append("❌ Ничего не найдено")
    
    elif query_type == "darknet":
        lines.append("🌑 **УПОМИНАНИЯ:** " + results.get("query", ""))
        lines.append("")
        found = [f['source'] for f in results.get("findings", []) if f.get('found')]
        if found: lines.append(f"├ Найден на: {', '.join(found)}")
        else: lines.append("├ Не найден")
    
    elif query_type == "relatives":
        lines.append("👨‍👩‍👧 **РОДСТВЕННИКИ:** " + results.get("query", ""))
        lines.append("")
        for f in results.get("findings", []):
            names = f.get("possible_relatives", [])
            if names:
                lines.append(f"├ Возможные родственники ({len(names)}):")
                for n in names[:10]: lines.append(f"│ • {n}")
        if not results.get("findings"): lines.append("❌ Не найдено")
    
    elif query_type == "work":
        lines.append("💼 **РАБОТА:** " + results.get("query", ""))
        lines.append("")
        for f in results.get("findings", []):
            if f.get("orgs"): lines.append(f"🏢 Организации: {', '.join(f['orgs'][:5])}")
            if f.get("positions"): lines.append(f"👔 Должности: {', '.join(f['positions'][:5])}")
            if f.get("links"): lines.append(f"🔗 LinkedIn: {len(f['links'])} упоминаний")
        if not results.get("findings"): lines.append("❌ Не найдено")
    
    elif query_type == "education":
        lines.append("🎓 **ОБРАЗОВАНИЕ:** " + results.get("query", ""))
        lines.append("")
        for f in results.get("findings", []):
            if f.get("schools"): lines.append(f"🏫 Учебные заведения: {', '.join(f['schools'][:5])}")
        if not results.get("findings"): lines.append("❌ Не найдено")
    
    elif query_type == "finance":
        lines.append("💰 **ФИНАНСЫ:** " + results.get("query", ""))
        lines.append("")
        for f in results.get("findings", []):
            if f.get("mentions"): lines.append(f"⚠ Упоминания: {', '.join(f['mentions'][:5])}")
            if f.get("links"):
                lines.append(f"🏛 ФССП: {len(f['links'])} записей")
                for l in f['links'][:3]: lines.append(f"├ {l}")
        if not results.get("findings"): lines.append("✅ Долгов не найдено")
    
    lines.append("_" * 30)
    lines.append("🔍 **Lexton Mega OSINT**")
    return "\n".join(lines)

def search_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    kb.add(KeyboardButton("🔍 Искать"), KeyboardButton("🔍 Расширенный поиск"))
    kb.add(KeyboardButton("📄 Поиск документов"), KeyboardButton("🌐 Соцсети 30+"))
    kb.add(KeyboardButton("🔎 Глубокий поиск"), KeyboardButton("👤 Поиск человека"))
    kb.add(KeyboardButton("💳 Купить подписку"), KeyboardButton("ℹ️ Статус"))
    kb.add(KeyboardButton("🔙 Назад"))
    return kb

@bot.message_handler(func=lambda m: m.text == "👤 Поиск человека")
def people_search_menu(message):
    uid = message.from_user.id
    if is_banned(uid): return
    if not has_access(uid): bot.send_message(uid, "❌ Нет доступа"); return
    
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    kb.add(KeyboardButton("👤 Поиск по ФИО+"), KeyboardButton("🌑 Упоминания в сети"))
    kb.add(KeyboardButton("👨‍👩‍👧 Родственники"), KeyboardButton("💼 Работа"))
    kb.add(KeyboardButton("🎓 Образование"), KeyboardButton("💰 Финансы"))
    kb.add(KeyboardButton("🔙 Назад"))
    
    bot.send_message(uid, "👤 **Поиск человека**\n\nВыбери тип:", parse_mode="Markdown", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "👤 Поиск по ФИО+")
def people_search(message):
    uid = message.from_user.id
    if not has_access(uid): bot.send_message(uid, "❌ Нет доступа"); return
    msg = bot.send_message(uid, "👤 Введи ФИО:\nПример: Иванов Иван Иванович")
    bot.register_next_step_handler(msg, lambda m: process_life(m, uid, "people"))

@bot.message_handler(func=lambda m: m.text == "🌑 Упоминания в сети")
def darknet_search(message):
    uid = message.from_user.id
    if not has_access(uid): bot.send_message(uid, "❌ Нет доступа"); return
    msg = bot.send_message(uid, "🌑 Введи запрос:\nПример: username или email")
    bot.register_next_step_handler(msg, lambda m: process_life(m, uid, "darknet"))

@bot.message_handler(func=lambda m: m.text == "👨‍👩‍👧 Родственники")
def relatives_search(message):
    uid = message.from_user.id
    if not has_access(uid): bot.send_message(uid, "❌ Нет доступа"); return
    msg = bot.send_message(uid, "👨‍👩‍👧 Введи ФИО:\nПример: Иванов Иван")
    bot.register_next_step_handler(msg, lambda m: process_life(m, uid, "relatives"))

@bot.message_handler(func=lambda m: m.text == "💼 Работа")
def work_search(message):
    uid = message.from_user.id
    if not has_access(uid): bot.send_message(uid, "❌ Нет доступа"); return
    msg = bot.send_message(uid, "💼 Введи ФИО:\nПример: Иванов Иван")
    bot.register_next_step_handler(msg, lambda m: process_life(m, uid, "work"))

@bot.message_handler(func=lambda m: m.text == "🎓 Образование")
def education_search(message):
    uid = message.from_user.id
    if not has_access(uid): bot.send_message(uid, "❌ Нет доступа"); return
    msg = bot.send_message(uid, "🎓 Введи ФИО:\nПример: Иванов Иван")
    bot.register_next_step_handler(msg, lambda m: process_life(m, uid, "education"))

@bot.message_handler(func=lambda m: m.text == "💰 Финансы")
def finance_search(message):
    uid = message.from_user.id
    if not has_access(uid): bot.send_message(uid, "❌ Нет доступа"); return
    msg = bot.send_message(uid, "💰 Введи ФИО:\nПример: Иванов Иван")
    bot.register_next_step_handler(msg, lambda m: process_life(m, uid, "finance"))

def process_life(message, uid, qtype):
    query = message.text.strip()
    loading = bot.send_message(uid, f"🔍 Поиск {qtype}...\n⏳ ~60-90 сек\n[░░░░░░░░░░░░░░░░░░░░] 0%", parse_mode="Markdown")
    
    def run():
        try:
            for p in range(10, 101, 10):
                bar = "█" * (p // 5) + "░" * (20 - p // 5)
                try: bot.edit_message_text(f"🔍 Поиск {qtype}...\n⏳ {p}%\n[{bar}] {p}%", uid, loading.message_id)
                except: pass
                time.sleep(2)
            
            if qtype == "people": results = search_people_yandex(query)
            elif qtype == "darknet": results = search_darknet_mentions(query)
            elif qtype == "relatives": results = search_relatives(query)
            elif qtype == "work": results = search_work_history(query)
            elif qtype == "education": results = search_education(query)
            elif qtype == "finance": results = search_financial(query)
            else: return
            
            report = format_life_report(results, qtype)
            
            if len(report) > 4000:
                parts = [report[i:i+4000] for i in range(0, len(report), 4000)]
                for i, part in enumerate(parts):
                    if i == 0: bot.edit_message_text(part, uid, loading.message_id, parse_mode="Markdown")
                    else: bot.send_message(uid, part, parse_mode="Markdown")
            else:
                bot.edit_message_text(report, uid, loading.message_id, parse_mode="Markdown")
        except Exception as e:
            try: bot.edit_message_text(f"❌ Ошибка: {str(e)[:100]}", uid, loading.message_id)
            except: pass
    
    threading.Thread(target=run).start()

def search_face_google(photo_url):
    results = {"photo": photo_url, "findings": []}
    
    try:
        r = requests.get(f"https://lens.google.com/uploadbyurl?url={photo_url}", timeout=10, headers=H)
        if r.status_code == 200:
            titles = re.findall(r'"title":"([^"]+)"', r.text)
            links = re.findall(r'"url":"(https?://[^"]+)"', r.text)
            if titles or links: results["findings"].append({"source": "google_lens", "titles": titles[:10], "links": links[:10]})
    except: pass
    
    return results

def search_face_yandex(photo_url):
    results = {"photo": photo_url, "findings": []}
    
    try:
        r = requests.get(f"https://yandex.ru/images/search?rpt=imageview&url={photo_url}", timeout=10, headers=H)
        if r.status_code == 200:
            tags = re.findall(r'"description":"([^"]+)"', r.text)
            similar = re.findall(r'https?://[^\s<>"]+\.(?:jpg|jpeg|png|webp)', r.text)
            if tags or similar: results["findings"].append({"source": "yandex_vision", "tags": list(set(tags))[:10], "similar": list(set(similar))[:10]})
    except: pass
    
    return results

def search_face_tineye(photo_url):
    results = {"photo": photo_url, "findings": []}
    
    try:
        r = requests.get(f"https://tineye.com/search?url={photo_url}", timeout=10, headers=H)
        if r.status_code == 200:
            matches = re.findall(r'https?://[^\s<>"]+', r.text)
            if matches: results["findings"].append({"source": "tineye", "matches": list(set(matches))[:10]})
    except: pass
    
    return results

def search_image_metadata(photo_url):
    results = {"photo": photo_url, "metadata": {}}
    
    try:
        r = requests.head(photo_url, timeout=5, headers=H)
        results["metadata"]["size"] = r.headers.get('Content-Length', 'unknown')
        results["metadata"]["type"] = r.headers.get('Content-Type', 'unknown')
        results["metadata"]["last_modified"] = r.headers.get('Last-Modified', 'unknown')
    except: pass
    
    try:
        r = requests.get(photo_url, timeout=10, headers=H)
        if r.status_code == 200:
            exif_date = re.findall(rb'(\d{4}:\d{2}:\d{2}\s\d{2}:\d{2}:\d{2})', r.content)
            gps = re.findall(rb'GPSLatitude|GPSLongitude|GPSPosition', r.content)
            if exif_date: results["metadata"]["dates"] = [d.decode() for d in exif_date[:3]]
            if gps: results["metadata"]["gps"] = True
    except: pass
    
    return results

def search_deep_person(query):
    results = {"query": query, "findings": [], "summary": {}}
    parts = query.split()
    all_names = set()
    all_phones = set()
    all_emails = set()
    all_links = set()
    
    try:
        r = requests.get(f"https://www.google.com/search?q={query}", timeout=5, headers=H)
        if r.status_code == 200:
            all_names.update(re.findall(r'[А-ЯЁ][а-яё]+\s[А-ЯЁ][а-яё]+(?:\s[А-ЯЁ][а-яё]+)?', r.text))
            all_phones.update(re.findall(r'\+?[7-8][\d\s\(\)-]{9,15}', r.text))
            all_emails.update(re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', r.text))
            all_links.update(re.findall(r'https?://[^\s<>"]+', r.text)[:20])
    except: pass
    
    try:
        r = requests.get(f"https://yandex.ru/search/?text={query}", timeout=5, headers=H)
        if r.status_code == 200:
            all_names.update(re.findall(r'[А-ЯЁ][а-яё]+\s[А-ЯЁ][а-яё]+(?:\s[А-ЯЁ][а-яё]+)?', r.text))
            all_phones.update(re.findall(r'\+?[7-8][\d\s\(\)-]{9,15}', r.text))
            all_links.update(re.findall(r'https?://[^\s<>"]+', r.text)[:20])
    except: pass
    
    if parts[0] in all_names: all_names.discard(parts[0])
    
    results["summary"]["names"] = list(all_names)[:15]
    results["summary"]["phones"] = list(all_phones)[:5]
    results["summary"]["emails"] = list(all_emails)[:5]
    results["summary"]["links"] = list(all_links)[:10]
    
    return results

def search_messenger_links(phone):
    clean = ''.join(filter(str.isdigit, phone))
    results = {"phone": clean, "messengers": {}}
    
    messengers = {
        "WhatsApp": f"https://wa.me/{clean}",
        "Telegram": f"https://t.me/+{clean}",
        "Viber": f"viber://chat?number=%2B{clean}",
        "Signal": f"https://signal.me/#p/{clean}",
        "Skype": f"skype:{clean}?call",
        "FaceTime": f"facetime://{clean}",
        "ICQ": f"https://icq.im/{clean}",
        "WeChat": f"weixin://dl/chat?{clean}",
        "Line": f"https://line.me/R/ti/p/{clean}",
        "KakaoTalk": f"kakaotalk://openchat?{clean}",
    }
    
    for name, url in messengers.items():
        try:
            r = requests.get(url, timeout=3, headers=H, allow_redirects=False)
            results["messengers"][name] = r.status_code in [200, 302]
        except:
            results["messengers"][name] = False
    
    return results

def search_email_providers(email):
    domain = email.split('@')[1].lower()
    results = {"email": email, "domain": domain, "providers": {}}
    
    providers = {
        "Google": ["gmail.com", "googlemail.com"],
        "Microsoft": ["outlook.com", "hotmail.com", "live.com"],
        "Yahoo": ["yahoo.com", "ymail.com"],
        "Yandex": ["yandex.ru", "ya.ru"],
        "Mail.ru": ["mail.ru", "inbox.ru", "bk.ru", "list.ru"],
        "Proton": ["proton.me", "protonmail.com"],
        "iCloud": ["icloud.com", "me.com"],
    }
    
    for provider, domains in providers.items():
        if any(d in domain for d in domains):
            results["providers"][provider] = True
    
    return results

def format_face_report(results, query_type):
    lines = []
    
    if query_type in ["google_face", "yandex_face", "tineye_face"]:
        lines.append("🖼 **ПОИСК ПО ФОТО:** поиск завершён")
        lines.append("")
        for f in results.get("findings", []):
            src = f.get("source", "")
            if f.get("titles"):
                lines.append(f"├ {src}: {len(f['titles'])} совпадений")
                for t in f['titles'][:5]: lines.append(f"│ • {t}")
            if f.get("links"):
                lines.append(f"├ Ссылки: {len(f['links'])}")
                for l in f['links'][:5]: lines.append(f"│ • {l}")
            if f.get("tags"):
                lines.append(f"├ Теги: {', '.join(f['tags'][:5])}")
        if not results.get("findings"): lines.append("❌ Совпадений не найдено")
    
    elif query_type == "metadata":
        lines.append("📷 **МЕТАДАННЫЕ ФОТО:**")
        lines.append("")
        meta = results.get("metadata", {})
        lines.append(f"├ Размер: {meta.get('size', '?')} байт")
        lines.append(f"├ Тип: {meta.get('type', '?')}")
        lines.append(f"├ Изменён: {meta.get('last_modified', '?')}")
        if meta.get('dates'): lines.append(f"├ Даты EXIF: {', '.join(meta['dates'][:3])}")
        if meta.get('gps'): lines.append("├ 📍 Найдены GPS координаты!")
    
    elif query_type == "deep_person":
        lines.append("🔍 **ГЛУБОКИЙ ПОИСК:** " + results.get("query", ""))
        lines.append("")
        s = results.get("summary", {})
        if s.get("names"): lines.append(f"👤 Связанные имена ({len(s['names'])}):\n├ {'\n├ '.join(s['names'][:10])}")
        if s.get("phones"): lines.append(f"\n📱 Телефоны: {', '.join(s['phones'][:5])}")
        if s.get("emails"): lines.append(f"\n📧 Email: {', '.join(s['emails'][:5])}")
        if s.get("links"): lines.append(f"\n🔗 Ссылок: {len(s['links'])}")
        if not any([s.get("names"), s.get("phones"), s.get("emails")]): lines.append("❌ Ничего не найдено")
    
    elif query_type == "messengers":
        lines.append("💬 **МЕССЕНДЖЕРЫ:** " + results.get("phone", ""))
        lines.append("")
        for name, exists in results.get("messengers", {}).items():
            lines.append(f"├ {'✅' if exists else '❌'} {name}")
    
    elif query_type == "email_providers":
        lines.append("📧 **ПРОВАЙДЕРЫ:** " + results.get("email", ""))
        lines.append("")
        providers = results.get("providers", {})
        if providers:
            for p, _ in providers.items(): lines.append(f"├ ✅ {p}")
        else:
            lines.append(f"├ Домен: {results.get('domain', '?')}")
    
    lines.append("_" * 30)
    lines.append("🔍 **Lexton Mega OSINT**")
    return "\n".join(lines)

def search_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    kb.add(KeyboardButton("🔍 Искать"), KeyboardButton("🔍 Расширенный поиск"))
    kb.add(KeyboardButton("📄 Поиск документов"), KeyboardButton("🌐 Соцсети 30+"))
    kb.add(KeyboardButton("🔎 Глубокий поиск"), KeyboardButton("👤 Поиск человека"))
    kb.add(KeyboardButton("🖼 Поиск по фото"), KeyboardButton("💳 Купить подписку"))
    kb.add(KeyboardButton("ℹ️ Статус"), KeyboardButton("🔙 Назад"))
    return kb

@bot.message_handler(func=lambda m: m.text == "🖼 Поиск по фото")
def face_search_menu(message):
    uid = message.from_user.id
    if is_banned(uid): return
    if not has_access(uid): bot.send_message(uid, "❌ Нет доступа"); return
    
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    kb.add(KeyboardButton("🖼 Google Lens"), KeyboardButton("🖼 Yandex Vision"))
    kb.add(KeyboardButton("🖼 TinEye"), KeyboardButton("📷 Метаданные фото"))
    kb.add(KeyboardButton("💬 Мессенджеры"), KeyboardButton("📧 Провайдер email"))
    kb.add(KeyboardButton("🔙 Назад"))
    
    bot.send_message(uid, "🖼 **Поиск по фото**\n\nВыбери тип:", parse_mode="Markdown", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "🖼 Google Lens")
def google_face_search(message):
    uid = message.from_user.id
    if not has_access(uid): bot.send_message(uid, "❌ Нет доступа"); return
    msg = bot.send_message(uid, "🖼 Отправь ссылку на фото:\nПример: https://example.com/photo.jpg")
    bot.register_next_step_handler(msg, lambda m: process_face(m, uid, "google_face"))

@bot.message_handler(func=lambda m: m.text == "🖼 Yandex Vision")
def yandex_face_search(message):
    uid = message.from_user.id
    if not has_access(uid): bot.send_message(uid, "❌ Нет доступа"); return
    msg = bot.send_message(uid, "🖼 Отправь ссылку на фото:\nПример: https://example.com/photo.jpg")
    bot.register_next_step_handler(msg, lambda m: process_face(m, uid, "yandex_face"))

@bot.message_handler(func=lambda m: m.text == "🖼 TinEye")
def tineye_search(message):
    uid = message.from_user.id
    if not has_access(uid): bot.send_message(uid, "❌ Нет доступа"); return
    msg = bot.send_message(uid, "🖼 Отправь ссылку на фото:\nПример: https://example.com/photo.jpg")
    bot.register_next_step_handler(msg, lambda m: process_face(m, uid, "tineye_face"))

@bot.message_handler(func=lambda m: m.text == "📷 Метаданные фото")
def metadata_search(message):
    uid = message.from_user.id
    if not has_access(uid): bot.send_message(uid, "❌ Нет доступа"); return
    msg = bot.send_message(uid, "📷 Отправь ссылку на фото:\nПример: https://example.com/photo.jpg")
    bot.register_next_step_handler(msg, lambda m: process_face(m, uid, "metadata"))

@bot.message_handler(func=lambda m: m.text == "💬 Мессенджеры")
def messengers_search(message):
    uid = message.from_user.id
    if not has_access(uid): bot.send_message(uid, "❌ Нет доступа"); return
    msg = bot.send_message(uid, "💬 Введи номер телефона:\nПример: +79001234567")
    bot.register_next_step_handler(msg, lambda m: process_face(m, uid, "messengers"))

@bot.message_handler(func=lambda m: m.text == "📧 Провайдер email")
def email_prov_search(message):
    uid = message.from_user.id
    if not has_access(uid): bot.send_message(uid, "❌ Нет доступа"); return
    msg = bot.send_message(uid, "📧 Введи email:\nПример: user@gmail.com")
    bot.register_next_step_handler(msg, lambda m: process_face(m, uid, "email_providers"))

def process_face(message, uid, qtype):
    query = message.text.strip()
    loading = bot.send_message(uid, f"🔍 Поиск {qtype}...\n⏳ ~60-120 сек\n[░░░░░░░░░░░░░░░░░░░░] 0%", parse_mode="Markdown")
    
    def run():
        try:
            for p in range(10, 101, 10):
                bar = "█" * (p // 5) + "░" * (20 - p // 5)
                try: bot.edit_message_text(f"🔍 Поиск {qtype}...\n⏳ {p}%\n[{bar}] {p}%", uid, loading.message_id)
                except: pass
                time.sleep(2)
            
            if qtype == "google_face": results = search_face_google(query)
            elif qtype == "yandex_face": results = search_face_yandex(query)
            elif qtype == "tineye_face": results = search_face_tineye(query)
            elif qtype == "metadata": results = search_image_metadata(query)
            elif qtype == "messengers": results = search_messenger_links(query)
            elif qtype == "email_providers": results = search_email_providers(query)
            else: return
            
            report = format_face_report(results, qtype)
            
            if len(report) > 4000:
                parts = [report[i:i+4000] for i in range(0, len(report), 4000)]
                for i, part in enumerate(parts):
                    if i == 0: bot.edit_message_text(part, uid, loading.message_id, parse_mode="Markdown")
                    else: bot.send_message(uid, part, parse_mode="Markdown")
            else:
                bot.edit_message_text(report, uid, loading.message_id, parse_mode="Markdown")
        except Exception as e:
            try: bot.edit_message_text(f"❌ Ошибка: {str(e)[:100]}", uid, loading.message_id)
            except: pass
    
    threading.Thread(target=run).start()

def search_instagram_deep(username):
    results = {"username": username, "findings": []}
    
    try:
        r = requests.get(f"https://www.instagram.com/{username}/?__a=1", timeout=5, headers=H)
        if r.status_code == 200:
            d = r.json()
            if 'graphql' in d:
                user = d['graphql']['user']
                results["findings"].append({"source": "instagram_api", "data": {
                    "id": user.get('id'), "full_name": user.get('full_name'),
                    "bio": user.get('biography'), "followers": user.get('edge_followed_by', {}).get('count'),
                    "following": user.get('edge_follow', {}).get('count'),
                    "posts": user.get('edge_owner_to_timeline_media', {}).get('count'),
                    "verified": user.get('is_verified'), "business": user.get('is_business_account'),
                    "external_url": user.get('external_url')
                }})
    except: pass
    
    try:
        r = requests.get(f"https://www.google.com/search?q=site:instagram.com+{username}", timeout=5, headers=H)
        if r.status_code == 200:
            mentions = re.findall(r'[^<>\"]{10,200}', r.text)
            if mentions: results["findings"].append({"source": "google_mentions", "texts": list(set(mentions))[:10]})
    except: pass
    
    return results

def search_tiktok_deep(username):
    results = {"username": username, "findings": []}
    
    try:
        r = requests.get(f"https://www.tiktok.com/@{username}", timeout=5, headers=H)
        if r.status_code == 200:
            title = re.search(r'<meta property="og:title" content="(.*?)">', r.text)
            desc = re.search(r'<meta property="og:description" content="(.*?)">', r.text)
            if title: results["findings"].append({"source": "tiktok", "title": title.group(1), "desc": desc.group(1) if desc else ""})
    except: pass
    
    try:
        r = requests.get(f"https://www.google.com/search?q=site:tiktok.com+{username}", timeout=5, headers=H)
        if r.status_code == 200:
            links = re.findall(r'https?://[^\s<>"]+tiktok[^\s<>"]*', r.text)
            if links: results["findings"].append({"source": "google_tiktok", "links": list(set(links))[:5]})
    except: pass
    
    return results

def search_youtube_deep(channel_id):
    results = {"channel": channel_id, "findings": []}
    
    try:
        r = requests.get(f"https://www.youtube.com/@{channel_id}/about", timeout=5, headers=H)
        if r.status_code == 200:
            subs = re.search(r'"subscriberCountText":\{"simpleText":"([^"]+)"', r.text)
            views = re.search(r'"viewCountText":\{"simpleText":"([^"]+)"', r.text)
            joined = re.search(r'"joinedDateText":\{"content":"([^"]+)"', r.text)
            if subs: results["findings"].append({"source": "youtube", "subscribers": subs.group(1)})
            if views: results["findings"].append({"source": "youtube_views", "views": views.group(1)})
            if joined: results["findings"].append({"source": "youtube_joined", "date": joined.group(1)})
    except: pass
    
    return results

def search_github_deep(username):
    results = {"username": username, "findings": []}
    
    try:
        r = requests.get(f"https://api.github.com/users/{username}", timeout=5, headers=H)
        if r.status_code == 200:
            d = r.json()
            results["findings"].append({"source": "github_api", "data": d})
    except: pass
    
    try:
        r = requests.get(f"https://api.github.com/users/{username}/repos?sort=updated&per_page=5", timeout=5, headers=H)
        if r.status_code == 200:
            repos = r.json()
            results["findings"].append({"source": "github_repos", "repos": repos})
    except: pass
    
    try:
        r = requests.get(f"https://api.github.com/users/{username}/events/public?per_page=5", timeout=5, headers=H)
        if r.status_code == 200:
            events = r.json()
            results["findings"].append({"source": "github_activity", "events": events})
    except: pass
    
    try:
        r = requests.get(f"https://api.github.com/users/{username}/gists?per_page=5", timeout=5, headers=H)
        if r.status_code == 200:
            gists = r.json()
            if gists: results["findings"].append({"source": "github_gists", "count": len(gists)})
    except: pass
    
    return results

def search_vk_deep(user_id):
    results = {"user_id": user_id, "findings": []}
    
    try:
        fields = "about,activities,bdate,books,city,connections,contacts,education,followers_count,home_town,interests,last_seen,movies,music,personal,relation,screen_name,status,universities,wall_comments"
        r = requests.get(f"https://api.vk.com/method/users.get?user_ids={user_id}&fields={fields}&v=5.131", timeout=5, headers=H)
        if r.status_code == 200:
            d = r.json()
            if 'response' in d: results["findings"].append({"source": "vk_api", "data": d['response'][0]})
    except: pass
    
    try:
        r = requests.get(f"https://api.vk.com/method/friends.get?user_id={user_id}&fields=first_name,last_name&v=5.131", timeout=5, headers=H)
        if r.status_code == 200:
            d = r.json()
            if 'response' in d: results["findings"].append({"source": "vk_friends", "count": d['response'].get('count', 0)})
    except: pass
    
    return results

def search_ok_deep(user_id):
    results = {"user_id": user_id, "findings": []}
    
    try:
        r = requests.get(f"https://ok.ru/profile/{user_id}", timeout=5, headers=H)
        if r.status_code == 200:
            title = re.search(r'<meta property="og:title" content="(.*?)">', r.text)
            desc = re.search(r'<meta property="og:description" content="(.*?)">', r.text)
            if title: results["findings"].append({"source": "ok", "title": title.group(1), "desc": desc.group(1) if desc else ""})
    except: pass
    
    try:
        r = requests.get(f"https://www.google.com/search?q=site:ok.ru+{user_id}", timeout=5, headers=H)
        if r.status_code == 200:
            links = re.findall(r'https?://[^\s<>"]+ok\.ru[^\s<>"]*', r.text)
            if links: results["findings"].append({"source": "google_ok", "links": list(set(links))[:5]})
    except: pass
    
    return results

def search_telegram_deep(username_or_id):
    results = {"tg": username_or_id, "findings": []}
    
    try:
        r = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getChat?chat_id=@{username_or_id}", timeout=5)
        if r.status_code == 200:
            d = r.json()
            if d.get('ok'): results["findings"].append({"source": "tg_api", "data": d['result']})
    except: pass
    
    try:
        r = requests.get(f"https://t.me/{username_or_id}", timeout=5, headers=H)
        if r.status_code == 200:
            title = re.search(r'<meta property="og:title" content="(.*?)">', r.text)
            desc = re.search(r'<meta property="og:description" content="(.*?)">', r.text)
            members = re.search(r'(\d+)\s*(?:members|subscribers|участников|подписчиков)', r.text)
            if title: results["findings"].append({"source": "tg_web", "title": title.group(1)})
            if desc: results["findings"].append({"source": "tg_desc", "desc": desc.group(1)})
            if members: results["findings"].append({"source": "tg_members", "count": members.group(1)})
    except: pass
    
    try:
        r = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMemberCount?chat_id=@{username_or_id}", timeout=5)
        if r.status_code == 200:
            d = r.json()
            if d.get('ok'): results["findings"].append({"source": "tg_count", "members": d['result']})
    except: pass
    
    return results

def search_snapchat_deep(username):
    results = {"username": username, "findings": []}
    
    try:
        r = requests.get(f"https://www.snapchat.com/add/{username}", timeout=5, headers=H)
        if r.status_code == 200:
            title = re.search(r'<meta property="og:title" content="(.*?)">', r.text)
            desc = re.search(r'<meta property="og:description" content="(.*?)">', r.text)
            if title: results["findings"].append({"source": "snapchat", "title": title.group(1), "desc": desc.group(1) if desc else ""})
    except: pass
    
    return results

def format_social_deep_report(results, query_type):
    lines = []
    
    if query_type == "instagram":
        lines.append("📷 **INSTAGRAM:** " + results.get("username", ""))
        lines.append("")
        for f in results.get("findings", []):
            if f.get("source") == "instagram_api":
                d = f.get("data", {})
                lines.append(f"├ Имя: {d.get('full_name', '?')}")
                lines.append(f"├ Bio: {d.get('bio', '')[:200]}")
                lines.append(f"├ Подписчиков: {d.get('followers', 0)}")
                lines.append(f"├ Подписок: {d.get('following', 0)}")
                lines.append(f"├ Постов: {d.get('posts', 0)}")
                lines.append(f"├ Верифицирован: {'✅' if d.get('verified') else '❌'}")
                lines.append(f"├ Бизнес: {'✅' if d.get('business') else '❌'}")
                if d.get('external_url'): lines.append(f"└ Сайт: {d['external_url']}")
    
    elif query_type == "tiktok":
        lines.append("🎵 **TIKTOK:** " + results.get("username", ""))
        for f in results.get("findings", []):
            if f.get("title"): lines.append(f"├ {f['title']}")
            if f.get("desc"): lines.append(f"└ {f['desc'][:200]}")
    
    elif query_type == "youtube":
        lines.append("▶️ **YOUTUBE:** " + results.get("channel", ""))
        for f in results.get("findings", []):
            if f.get("subscribers"): lines.append(f"├ Подписчики: {f['subscribers']}")
            if f.get("views"): lines.append(f"├ Просмотры: {f['views']}")
            if f.get("date"): lines.append(f"└ Создан: {f['date']}")
    
    elif query_type == "github":
        lines.append("💻 **GITHUB:** " + results.get("username", ""))
        for f in results.get("findings", []):
            if f.get("source") == "github_api":
                d = f.get("data", {})
                lines.append(f"├ Имя: {d.get('name') or d.get('login')}")
                if d.get('bio'): lines.append(f"├ Bio: {d['bio'][:150]}")
                lines.append(f"├ Репо: {d.get('public_repos', 0)}")
                lines.append(f"├ Фолловеры: {d.get('followers', 0)}")
                lines.append(f"└ Создан: {d.get('created_at', '?')[:10]}")
            elif f.get("source") == "github_repos":
                lines.append(f"├ Репозитории ({len(f.get('repos', []))}):")
                for repo in f.get("repos", [])[:5]:
                    lines.append(f"│ • {repo.get('name')} - {repo.get('description', '')[:80]}")
            elif f.get("source") == "github_gists":
                lines.append(f"└ Gists: {f.get('count', 0)}")
    
    elif query_type == "vk":
        lines.append("📱 **VK:** " + results.get("user_id", ""))
        for f in results.get("findings", []):
            if f.get("source") == "vk_api":
                d = f.get("data", {})
                lines.append(f"├ Имя: {d.get('first_name')} {d.get('last_name')}")
                if d.get('bdate'): lines.append(f"├ ДР: {d['bdate']}")
                if d.get('city'): lines.append(f"├ Город: {d['city'].get('title', '')}")
                if d.get('status'): lines.append(f"├ Статус: {d['status'][:100]}")
                if d.get('followers_count'): lines.append(f"├ Подписчиков: {d['followers_count']}")
            elif f.get("source") == "vk_friends":
                lines.append(f"└ Друзей: {f.get('count', 0)}")
    
    elif query_type == "ok":
        lines.append("📱 **OK:** " + results.get("user_id", ""))
        for f in results.get("findings", []):
            if f.get("title"): lines.append(f"├ {f['title']}")
            if f.get("desc"): lines.append(f"└ {f['desc'][:200]}")
    
    elif query_type == "telegram":
        lines.append("📱 **TELEGRAM:** " + results.get("tg", ""))
        for f in results.get("findings", []):
            if f.get("source") == "tg_api":
                d = f.get("data", {})
                lines.append(f"├ Название: {d.get('title') or d.get('first_name', '?')}")
                if d.get('description'): lines.append(f"├ Описание: {d['description'][:200]}")
                if d.get('username'): lines.append(f"├ @{d['username']}")
            elif f.get("title"): lines.append(f"├ {f['title']}")
            if f.get("desc"): lines.append(f"├ {f['desc'][:200]}")
            if f.get("members"): lines.append(f"├ Участников: {f['members']}")
            if f.get("count"): lines.append(f"└ Участников: {f['count']}")
    
    elif query_type == "snapchat":
        lines.append("👻 **SNAPCHAT:** " + results.get("username", ""))
        for f in results.get("findings", []):
            if f.get("title"): lines.append(f"├ {f['title']}")
            if f.get("desc"): lines.append(f"└ {f['desc'][:200]}")
    
    lines.append("_" * 30)
    lines.append("🔍 **Lexton Mega OSINT**")
    return "\n".join(lines)

def search_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    kb.add(KeyboardButton("🔍 Искать"), KeyboardButton("🔍 Расширенный поиск"))
    kb.add(KeyboardButton("📄 Поиск документов"), KeyboardButton("🌐 Соцсети 30+"))
    kb.add(KeyboardButton("🔎 Глубокий поиск"), KeyboardButton("👤 Поиск человека"))
    kb.add(KeyboardButton("🖼 Поиск по фото"), KeyboardButton("📱 Поиск в соцсетях"))
    kb.add(KeyboardButton("💳 Купить подписку"), KeyboardButton("ℹ️ Статус"))
    kb.add(KeyboardButton("🔙 Назад"))
    return kb

@bot.message_handler(func=lambda m: m.text == "📱 Поиск в соцсетях")
def social_deep_menu(message):
    uid = message.from_user.id
    if is_banned(uid): return
    if not has_access(uid): bot.send_message(uid, "❌ Нет доступа"); return
    
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(KeyboardButton("📷 Instagram"), KeyboardButton("🎵 TikTok"))
    kb.add(KeyboardButton("▶️ YouTube"), KeyboardButton("💻 GitHub"))
    kb.add(KeyboardButton("📱 VK"), KeyboardButton("📱 OK"))
    kb.add(KeyboardButton("📱 Telegram"), KeyboardButton("👻 Snapchat"))
    kb.add(KeyboardButton("🔙 Назад"))
    
    bot.send_message(uid, "📱 **Поиск в соцсетях**\n\nВыбери платформу:", parse_mode="Markdown", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "📷 Instagram")
def insta_search(message):
    uid = message.from_user.id
    if not has_access(uid): return
    msg = bot.send_message(uid, "📷 Введи username Instagram:\nПример: cristiano")
    bot.register_next_step_handler(msg, lambda m: process_social_deep(m, uid, "instagram"))

@bot.message_handler(func=lambda m: m.text == "🎵 TikTok")
def tiktok_search(message):
    uid = message.from_user.id
    if not has_access(uid): return
    msg = bot.send_message(uid, "🎵 Введи username TikTok:\nПример: charlidamelio")
    bot.register_next_step_handler(msg, lambda m: process_social_deep(m, uid, "tiktok"))

@bot.message_handler(func=lambda m: m.text == "▶️ YouTube")
def youtube_search(message):
    uid = message.from_user.id
    if not has_access(uid): return
    msg = bot.send_message(uid, "▶️ Введи ID канала YouTube:\nПример: @MrBeast")
    bot.register_next_step_handler(msg, lambda m: process_social_deep(m, uid, "youtube"))

@bot.message_handler(func=lambda m: m.text == "💻 GitHub")
def github_search(message):
    uid = message.from_user.id
    if not has_access(uid): return
    msg = bot.send_message(uid, "💻 Введи username GitHub:\nПример: torvalds")
    bot.register_next_step_handler(msg, lambda m: process_social_deep(m, uid, "github"))

@bot.message_handler(func=lambda m: m.text == "📱 VK")
def vk_deep_search(message):
    uid = message.from_user.id
    if not has_access(uid): return
    msg = bot.send_message(uid, "📱 Введи ID или screen_name VK:\nПример: durov или 1")
    bot.register_next_step_handler(msg, lambda m: process_social_deep(m, uid, "vk"))

@bot.message_handler(func=lambda m: m.text == "📱 OK")
def ok_search(message):
    uid = message.from_user.id
    if not has_access(uid): return
    msg = bot.send_message(uid, "📱 Введи ID профиля OK:\nПример: 123456789")
    bot.register_next_step_handler(msg, lambda m: process_social_deep(m, uid, "ok"))

@bot.message_handler(func=lambda m: m.text == "📱 Telegram")
def tg_deep_search(message):
    uid = message.from_user.id
    if not has_access(uid): return
    msg = bot.send_message(uid, "📱 Введи @username канала/чата:\nПример: @durov")
    bot.register_next_step_handler(msg, lambda m: process_social_deep(m, uid, "telegram"))

@bot.message_handler(func=lambda m: m.text == "👻 Snapchat")
def snapchat_search(message):
    uid = message.from_user.id
    if not has_access(uid): return
    msg = bot.send_message(uid, "👻 Введи username Snapchat:\nПример: snapchat")
    bot.register_next_step_handler(msg, lambda m: process_social_deep(m, uid, "snapchat"))

def process_social_deep(message, uid, qtype):
    query = message.text.strip().lstrip('@')
    loading = bot.send_message(uid, f"🔍 Поиск {qtype}...\n⏳ ~60-90 сек\n[░░░░░░░░░░░░░░░░░░░░] 0%", parse_mode="Markdown")
    
    def run():
        try:
            for p in range(10, 101, 10):
                bar = "█" * (p // 5) + "░" * (20 - p // 5)
                try: bot.edit_message_text(f"🔍 Поиск {qtype}...\n⏳ {p}%\n[{bar}] {p}%", uid, loading.message_id)
                except: pass
                time.sleep(2)
            
            if qtype == "instagram": results = search_instagram_deep(query)
            elif qtype == "tiktok": results = search_tiktok_deep(query)
            elif qtype == "youtube": results = search_youtube_deep(query)
            elif qtype == "github": results = search_github_deep(query)
            elif qtype == "vk": results = search_vk_deep(query)
            elif qtype == "ok": results = search_ok_deep(query)
            elif qtype == "telegram": results = search_telegram_deep(query)
            elif qtype == "snapchat": results = search_snapchat_deep(query)
            else: return
            
            report = format_social_deep_report(results, qtype)
            
            if len(report) > 4000:
                parts = [report[i:i+4000] for i in range(0, len(report), 4000)]
                for i, part in enumerate(parts):
                    if i == 0: bot.edit_message_text(part, uid, loading.message_id, parse_mode="Markdown")
                    else: bot.send_message(uid, part, parse_mode="Markdown")
            else:
                bot.edit_message_text(report, uid, loading.message_id, parse_mode="Markdown")
        except Exception as e:
            try: bot.edit_message_text(f"❌ Ошибка: {str(e)[:100]}", uid, loading.message_id)
            except: pass
    
    threading.Thread(target=run).start()

def search_crypto_wallet(wallet):
    results = {"wallet": wallet, "findings": []}
    
    try:
        r = requests.get(f"https://api.blockchair.com/bitcoin/dashboards/address/{wallet}", timeout=5, headers=H)
        if r.status_code == 200:
            d = r.json()
            if d.get('data'): results["findings"].append({"source": "btc", "data": d['data'][wallet]})
    except: pass
    
    try:
        r = requests.get(f"https://api.etherscan.io/api?module=account&action=balance&address={wallet}&tag=latest", timeout=5, headers=H)
        if r.status_code == 200:
            d = r.json()
            if d.get('status') == '1': results["findings"].append({"source": "eth", "balance_wei": d['result']})
    except: pass
    
    try:
        r = requests.get(f"https://api.etherscan.io/api?module=account&action=txlist&address={wallet}&sort=desc&page=1&offset=10", timeout=5, headers=H)
        if r.status_code == 200:
            d = r.json()
            if d.get('status') == '1': results["findings"].append({"source": "eth_tx", "transactions": d['result'][:10]})
    except: pass
    
    return results

def search_ip_range(ip):
    results = {"ip": ip, "findings": []}
    
    try:
        r = requests.get(f"https://api.hackertarget.com/reverseiplookup/?q={ip}", timeout=5, headers=H)
        if r.status_code == 200 and r.text.strip():
            domains = r.text.strip().split('\n')
            if domains: results["findings"].append({"source": "reverse_ip", "domains": domains[:20]})
    except: pass
    
    try:
        r = requests.get(f"https://api.hackertarget.com/aslookup/?q={ip}", timeout=5, headers=H)
        if r.status_code == 200 and r.text.strip():
            results["findings"].append({"source": "asn", "data": r.text.strip()[:500]})
    except: pass
    
    return results

def search_dns_records(domain):
    clean = domain.replace('https://', '').replace('http://', '').replace('www.', '').split('/')[0]
    results = {"domain": clean, "findings": []}
    
    record_types = ['A', 'AAAA', 'MX', 'NS', 'TXT', 'SOA', 'CNAME']
    
    for rtype in record_types:
        try:
            r = requests.get(f"https://dns.google/resolve?name={clean}&type={rtype}", timeout=5, headers=H)
            if r.status_code == 200:
                d = r.json()
                if d.get('Answer'): results["findings"].append({"type": rtype, "records": d['Answer']})
        except: pass
    
    return results

def search_ssl_cert(domain):
    clean = domain.replace('https://', '').replace('http://', '').replace('www.', '').split('/')[0]
    results = {"domain": clean, "findings": []}
    
    try:
        r = requests.get(f"https://crt.sh/?q={clean}&output=json", timeout=10, headers=H)
        if r.status_code == 200 and r.text.strip():
            certs = r.json()
            results["findings"].append({"source": "crt", "total": len(certs)})
            
            subdomains = set()
            for c in certs[:20]:
                if 'name_value' in c:
                    for n in c['name_value'].split('\n'):
                        if clean in n: subdomains.add(n.strip())
            results["findings"].append({"source": "subdomains", "list": list(subdomains)[:20]})
    except: pass
    
    return results

def search_website_tech(domain):
    clean = domain.replace('https://', '').replace('http://', '').replace('www.', '').split('/')[0]
    results = {"domain": clean, "findings": []}
    
    try:
        r = requests.get(f"https://api.wappalyzer.com/v2/lookup?urls={clean}", timeout=5, headers=H)
        if r.status_code == 200:
            d = r.json()
            if d: results["findings"].append({"source": "wappalyzer", "tech": d})
    except: pass
    
    try:
        r = requests.get(f"https://{clean}", timeout=5, headers=H)
        if r.status_code == 200:
            server = r.headers.get('Server', '')
            powered = r.headers.get('X-Powered-By', '')
            if server: results["findings"].append({"source": "headers", "server": server})
            if powered: results["findings"].append({"source": "headers", "powered": powered})
            
            wp = re.search(r'wp-content', r.text)
            if wp: results["findings"].append({"source": "cms", "type": "WordPress"})
            
            ga = re.search(r'UA-\d+-\d+|G-[A-Z0-9]+', r.text)
            if ga: results["findings"].append({"source": "analytics", "google": ga.group(0)})
    except: pass
    
    return results

def search_breach_full(email):
    results = {"email": email, "breaches": [], "details": []}
    
    try:
        r = requests.get(f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}", timeout=5, headers=H)
        if r.status_code == 200:
            breaches = r.json()
            results["breaches"] = breaches
            
            for b in breaches[:5]:
                try:
                    r2 = requests.get(f"https://haveibeenpwned.com/api/v3/breach/{b.get('Name')}", timeout=5, headers=H)
                    if r2.status_code == 200:
                        details = r2.json()
                        results["details"].append({
                            "name": b.get('Name'),
                            "date": b.get('BreachDate'),
                            "description": details.get('Description', '')[:300],
                            "data_classes": details.get('DataClasses', []),
                            "domain": details.get('Domain', ''),
                            "pwn_count": details.get('PwnCount', 0)
                        })
                except: pass
    except: pass
    
    return results

def format_tech_report(results, query_type):
    lines = []
    
    if query_type == "crypto":
        lines.append("💎 **КРИПТО:** " + results.get("wallet", ""))
        lines.append("")
        for f in results.get("findings", []):
            if f.get("source") == "btc":
                d = f.get("data", {})
                if isinstance(d, dict):
                    lines.append(f"├ BTC: {d.get('address', {}).get('balance', 0)} BTC")
                    lines.append(f"├ Транзакций: {d.get('address', {}).get('transaction_count', 0)}")
            elif f.get("source") == "eth":
                bal = int(f.get("balance_wei", 0)) / 10**18
                lines.append(f"├ ETH: {bal:.4f} ETH")
            elif f.get("source") == "eth_tx":
                lines.append(f"└ Транзакций: {len(f.get('transactions', []))}")
    
    elif query_type == "ip_range":
        lines.append("🌍 **IP:** " + results.get("ip", ""))
        lines.append("")
        for f in results.get("findings", []):
            if f.get("domains"):
                lines.append(f"├ Домены на IP ({len(f['domains'])}):")
                for d in f['domains'][:10]: lines.append(f"│ • {d}")
            if f.get("data"): lines.append(f"└ ASN: {f['data'][:200]}")
    
    elif query_type == "dns":
        lines.append("🔗 **DNS:** " + results.get("domain", ""))
        lines.append("")
        for f in results.get("findings", []):
            lines.append(f"├ {f['type']}: {len(f['records'])} записей")
            for r in f['records'][:3]:
                if 'data' in r: lines.append(f"│ • {r['data']}")
    
    elif query_type == "ssl":
        lines.append("🔒 **SSL:** " + results.get("domain", ""))
        lines.append("")
        for f in results.get("findings", []):
            if f.get("total"): lines.append(f"├ Сертификатов: {f['total']}")
            if f.get("list"):
                lines.append(f"└ Поддомены ({len(f['list'])}):")
                for s in f['list'][:15]: lines.append(f"  • {s}")
    
    elif query_type == "tech":
        lines.append("🛠 **ТЕХНОЛОГИИ:** " + results.get("domain", ""))
        lines.append("")
        for f in results.get("findings", []):
            if f.get("server"): lines.append(f"├ Сервер: {f['server']}")
            if f.get("powered"): lines.append(f"├ Powered: {f['powered']}")
            if f.get("type"): lines.append(f"├ CMS: {f['type']}")
            if f.get("google"): lines.append(f"└ Analytics: {f['google']}")
    
    elif query_type == "breach":
        lines.append("🔓 **УТЕЧКИ:** " + results.get("email", ""))
        lines.append("")
        breaches = results.get("breaches", [])
        if isinstance(breaches, list) and breaches:
            lines.append(f"├ Найден в {len(breaches)} утечках\n")
            for d in results.get("details", []):
                lines.append(f"├ {d.get('name')} ({d.get('date', '?')[:10]})")
                lines.append(f"│ 📝 {d.get('description', '')[:200]}")
                if d.get('data_classes'):
                    lines.append(f"│ 🔑 Данные: {', '.join(d['data_classes'][:5])}")
                lines.append("")
    
    lines.append("_" * 30)
    lines.append("🔍 **Lexton Mega OSINT**")
    return "\n".join(lines)

def search_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    kb.add(KeyboardButton("🔍 Искать"), KeyboardButton("🔍 Расширенный поиск"))
    kb.add(KeyboardButton("📄 Поиск документов"), KeyboardButton("🌐 Соцсети 30+"))
    kb.add(KeyboardButton("🔎 Глубокий поиск"), KeyboardButton("👤 Поиск человека"))
    kb.add(KeyboardButton("🖼 Поиск по фото"), KeyboardButton("📱 Поиск в соцсетях"))
    kb.add(KeyboardButton("🛠 Технический поиск"), KeyboardButton("💳 Купить подписку"))
    kb.add(KeyboardButton("ℹ️ Статус"), KeyboardButton("🔙 Назад"))
    return kb

@bot.message_handler(func=lambda m: m.text == "🛠 Технический поиск")
def tech_search_menu(message):
    uid = message.from_user.id
    if is_banned(uid): return
    if not has_access(uid): bot.send_message(uid, "❌ Нет доступа"); return
    
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(KeyboardButton("💎 Криптокошелёк"), KeyboardButton("🌍 IP диапазон"))
    kb.add(KeyboardButton("🔗 DNS записи"), KeyboardButton("🔒 SSL сертификаты"))
    kb.add(KeyboardButton("🛠 Технологии сайта"), KeyboardButton("🔓 Полные утечки"))
    kb.add(KeyboardButton("🔙 Назад"))
    
    bot.send_message(uid, "🛠 **Технический поиск**\n\nВыбери тип:", parse_mode="Markdown", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "💎 Криптокошелёк")
def crypto_search(message):
    uid = message.from_user.id
    if not has_access(uid): return
    msg = bot.send_message(uid, "💎 Введи адрес кошелька:\nПример: 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa")
    bot.register_next_step_handler(msg, lambda m: process_tech(m, uid, "crypto"))

@bot.message_handler(func=lambda m: m.text == "🌍 IP диапазон")
def ip_range_search(message):
    uid = message.from_user.id
    if not has_access(uid): return
    msg = bot.send_message(uid, "🌍 Введи IP адрес:\nПример: 8.8.8.8")
    bot.register_next_step_handler(msg, lambda m: process_tech(m, uid, "ip_range"))

@bot.message_handler(func=lambda m: m.text == "🔗 DNS записи")
def dns_search(message):
    uid = message.from_user.id
    if not has_access(uid): return
    msg = bot.send_message(uid, "🔗 Введи домен:\nПример: google.com")
    bot.register_next_step_handler(msg, lambda m: process_tech(m, uid, "dns"))

@bot.message_handler(func=lambda m: m.text == "🔒 SSL сертификаты")
def ssl_search(message):
    uid = message.from_user.id
    if not has_access(uid): return
    msg = bot.send_message(uid, "🔒 Введи домен:\nПример: google.com")
    bot.register_next_step_handler(msg, lambda m: process_tech(m, uid, "ssl"))

@bot.message_handler(func=lambda m: m.text == "🛠 Технологии сайта")
def tech_search(message):
    uid = message.from_user.id
    if not has_access(uid): return
    msg = bot.send_message(uid, "🛠 Введи домен:\nПример: example.com")
    bot.register_next_step_handler(msg, lambda m: process_tech(m, uid, "tech"))

@bot.message_handler(func=lambda m: m.text == "🔓 Полные утечки")
def breach_search(message):
    uid = message.from_user.id
    if not has_access(uid): return
    msg = bot.send_message(uid, "🔓 Введи email:\nПример: user@mail.ru")
    bot.register_next_step_handler(msg, lambda m: process_tech(m, uid, "breach"))

def process_tech(message, uid, qtype):
    query = message.text.strip()
    loading = bot.send_message(uid, f"🔍 Технический поиск {qtype}...\n⏳ ~60-120 сек\n[░░░░░░░░░░░░░░░░░░░░] 0%", parse_mode="Markdown")
    
    def run():
        try:
            for p in range(10, 101, 10):
                bar = "█" * (p // 5) + "░" * (20 - p // 5)
                try: bot.edit_message_text(f"🔍 Поиск {qtype}...\n⏳ {p}%\n[{bar}] {p}%", uid, loading.message_id)
                except: pass
                time.sleep(2)
            
            if qtype == "crypto": results = search_crypto_wallet(query)
            elif qtype == "ip_range": results = search_ip_range(query)
            elif qtype == "dns": results = search_dns_records(query)
            elif qtype == "ssl": results = search_ssl_cert(query)
            elif qtype == "tech": results = search_website_tech(query)
            elif qtype == "breach": results = search_breach_full(query)
            else: return
            
            report = format_tech_report(results, qtype)
            
            if len(report) > 4000:
                parts = [report[i:i+4000] for i in range(0, len(report), 4000)]
                for i, part in enumerate(parts):
                    if i == 0: bot.edit_message_text(part, uid, loading.message_id, parse_mode="Markdown")
                    else: bot.send_message(uid, part, parse_mode="Markdown")
            else:
                bot.edit_message_text(report, uid, loading.message_id, parse_mode="Markdown")
        except Exception as e:
            try: bot.edit_message_text(f"❌ Ошибка: {str(e)[:100]}", uid, loading.message_id)
            except: pass
    
    threading.Thread(target=run).start()

def search_web_archive(url):
    results = {"url": url, "findings": []}
    
    try:
        r = requests.get(f"https://archive.org/wayback/available?url={url}", timeout=5, headers=H)
        if r.status_code == 200:
            d = r.json()
            if d.get('archived_snapshots'):
                results["findings"].append({"source": "wayback", "snapshots": d['archived_snapshots']})
    except: pass
    
    try:
        r = requests.get(f"https://arquivo.pt/wayback?url={url}&output=json", timeout=5, headers=H)
        if r.status_code == 200 and r.text.strip():
            results["findings"].append({"source": "arquivo", "available": True})
    except: pass
    
    return results

def search_google_ads(domain):
    clean = domain.replace('https://', '').replace('http://', '').replace('www.', '').split('/')[0]
    results = {"domain": clean, "findings": []}
    
    try:
        r = requests.get(f"https://www.google.com/search?q=site:{clean}+ads", timeout=5, headers=H)
        if r.status_code == 200:
            ads = re.findall(r'https?://[^\s<>"]+', r.text)
            if ads: results["findings"].append({"source": "google_ads", "links": list(set(ads))[:10]})
    except: pass
    
    return results

def search_shodan_lite(query):
    results = {"query": query, "findings": []}
    
    try:
        r = requests.get(f"https://www.shodan.io/search?query={query}", timeout=5, headers=H)
        if r.status_code == 200:
            ips = re.findall(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', r.text)
            ports = re.findall(r'Port:\s*(\d+)', r.text)
            if ips: results["findings"].append({"source": "shodan", "ips": list(set(ips))[:10], "ports": list(set(ports))[:10]})
    except: pass
    
    return results

def search_email_authority(email):
    domain = email.split('@')[1].lower()
    results = {"email": email, "domain": domain, "findings": []}
    
    try:
        r = requests.get(f"https://dns.google/resolve?name={domain}&type=MX", timeout=5, headers=H)
        if r.status_code == 200:
            d = r.json()
            if d.get('Answer'): results["findings"].append({"source": "mx", "records": d['Answer']})
    except: pass
    
    try:
        r = requests.get(f"https://www.google.com/search?q={domain}+email+service", timeout=5, headers=H)
        if r.status_code == 200:
            info = re.findall(r'<div class="BNeawe s3v9rd AP7Wnd">(.*?)</div>', r.text)
            if info: results["findings"].append({"source": "google", "info": info[:5]})
    except: pass
    
    return results

def search_username_history(username):
    results = {"username": username, "findings": []}
    
    try:
        r = requests.get(f"https://www.google.com/search?q={username}+username+history+profile", timeout=5, headers=H)
        if r.status_code == 200:
            other_names = re.findall(r'(?:aka|also|known as|previously|formerly)\s+[A-Za-z0-9_]+', r.text)
            if other_names: results["findings"].append({"source": "google", "other_names": list(set(other_names))[:10]})
    except: pass
    
    try:
        r = requests.get(f"https://yandex.ru/search/?text={username}+профиль+история", timeout=5, headers=H)
        if r.status_code == 200:
            names = re.findall(r'[А-ЯЁ][а-яё]+\s[А-ЯЁ][а-яё]+', r.text)
            if names: results["findings"].append({"source": "yandex", "names": list(set(names))[:10]})
    except: pass
    
    return results

def search_phone_geo(phone):
    clean = ''.join(filter(str.isdigit, phone))
    results = {"phone": clean, "findings": []}
    
    try:
        r = requests.get(f"https://api.numlookupapi.com/v1/validate/{clean}", timeout=5, headers=H)
        if r.status_code == 200:
            d = r.json()
            if d.get('valid'): results["findings"].append({"source": "numlookup", "data": d})
    except: pass
    
    try:
        r = requests.get(f"https://www.google.com/search?q={clean}+region", timeout=5, headers=H)
        if r.status_code == 200:
            regions = re.findall(r'(?:Москва|Санкт-Петербург|область|край|республика)[^\<]{0,50}', r.text)
            if regions: results["findings"].append({"source": "google", "regions": list(set(regions))[:5]})
    except: pass
    
    return results

def search_email_social(email):
    results = {"email": email, "findings": []}
    
    platforms = [
        f"https://www.google.com/search?q=site:facebook.com+{email}",
        f"https://www.google.com/search?q=site:linkedin.com+{email}",
        f"https://www.google.com/search?q=site:twitter.com+{email}",
        f"https://www.google.com/search?q=site:instagram.com+{email}",
        f"https://www.google.com/search?q=site:vk.com+{email}",
        f"https://www.google.com/search?q=site:ok.ru+{email}",
        f"https://www.google.com/search?q=site:github.com+{email}",
    ]
    
    for url in platforms[:4]:
        try:
            r = requests.get(url, timeout=5, headers=H)
            if r.status_code == 200:
                links = re.findall(r'https?://[^\s<>"]+', r.text)
                if links: results["findings"].append({"source": "social_links", "links": list(set(links))[:5]})
        except: pass
    
    return results

def format_info_report(results, query_type):
    lines = []
    
    if query_type == "archive":
        lines.append("📚 **АРХИВ:** " + results.get("url", ""))
        for f in results.get("findings", []):
            if f.get("snapshots"):
                lines.append(f"├ Wayback Machine: {len(f['snapshots'])} снимков")
                for s in f['snapshots'][:3]:
                    lines.append(f"│ • {s.get('timestamp', '?')[:10]}")
            if f.get("available"):
                lines.append(f"└ Arquivo.pt: найдено")
        if not results.get("findings"): lines.append("❌ Архивов не найдено")
    
    elif query_type == "ads":
        lines.append("📢 **РЕКЛАМА:** " + results.get("domain", ""))
        for f in results.get("findings", []):
            if f.get("links"): lines.append(f"├ Найдено {len(f['links'])} упоминаний")
        if not results.get("findings"): lines.append("❌ Не найдено")
    
    elif query_type == "shodan":
        lines.append("🖥 **SHODAN:** " + results.get("query", ""))
        for f in results.get("findings", []):
            if f.get("ips"): lines.append(f"├ IP: {', '.join(f['ips'][:5])}")
            if f.get("ports"): lines.append(f"└ Порты: {', '.join(f['ports'][:5])}")
        if not results.get("findings"): lines.append("❌ Не найдено")
    
    elif query_type == "email_auth":
        lines.append("📧 **EMAIL СЕРВИС:** " + results.get("email", ""))
        for f in results.get("findings", []):
            if f.get("records"): lines.append(f"├ MX: {len(f['records'])} записей")
            if f.get("info"):
                lines.append(f"└ Инфо:")
                for i in f['info'][:3]: lines.append(f"  • {i[:200]}")
    
    elif query_type == "username_history":
        lines.append("📝 **ИСТОРИЯ НИКА:** " + results.get("username", ""))
        for f in results.get("findings", []):
            if f.get("other_names"): lines.append(f"├ Другие имена: {', '.join(f['other_names'][:5])}")
            if f.get("names"): lines.append(f"└ Связанные: {', '.join(f['names'][:5])}")
        if not results.get("findings"): lines.append("❌ Не найдено")
    
    elif query_type == "phone_geo":
        lines.append("📍 **ГЕО НОМЕРА:** " + results.get("phone", ""))
        for f in results.get("findings", []):
            if f.get("source") == "numlookup" and f.get("data"):
                d = f['data']
                lines.append(f"├ Страна: {d.get('country_name', '?')}")
                lines.append(f"├ Оператор: {d.get('carrier', '?')}")
                lines.append(f"└ Локация: {d.get('location', '?')}")
            elif f.get("regions"): lines.append(f"└ Регион: {', '.join(f['regions'][:3])}")
    
    elif query_type == "email_social":
        lines.append("🔗 **СОЦСЕТИ ПО EMAIL:** " + results.get("email", ""))
        for f in results.get("findings", []):
            if f.get("links"): lines.append(f"├ Найдено {len(f['links'])} профилей")
        if not results.get("findings"): lines.append("❌ Не найдено")
    
    lines.append("_" * 30)
    lines.append("🔍 **Lexton Mega OSINT**")
    return "\n".join(lines)

def search_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    kb.add(KeyboardButton("🔍 Искать"), KeyboardButton("🔍 Расширенный поиск"))
    kb.add(KeyboardButton("📄 Поиск документов"), KeyboardButton("🌐 Соцсети 30+"))
    kb.add(KeyboardButton("🔎 Глубокий поиск"), KeyboardButton("👤 Поиск человека"))
    kb.add(KeyboardButton("🖼 Поиск по фото"), KeyboardButton("📱 Поиск в соцсетях"))
    kb.add(KeyboardButton("🛠 Технический поиск"), KeyboardButton("📊 Информационный"))
    kb.add(KeyboardButton("💳 Купить подписку"), KeyboardButton("ℹ️ Статус"))
    kb.add(KeyboardButton("🔙 Назад"))
    return kb

@bot.message_handler(func=lambda m: m.text == "📊 Информационный")
def info_search_menu(message):
    uid = message.from_user.id
    if is_banned(uid): return
    if not has_access(uid): bot.send_message(uid, "❌ Нет доступа"); return
    
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(KeyboardButton("📚 Архив сайта"), KeyboardButton("📢 Реклама домена"))
    kb.add(KeyboardButton("🖥 Shodan"), KeyboardButton("📧 Email сервис"))
    kb.add(KeyboardButton("📝 История ника"), KeyboardButton("📍 Гео номера"))
    kb.add(KeyboardButton("🔗 Соцсети email"), KeyboardButton("🔙 Назад"))
    
    bot.send_message(uid, "📊 **Информационный поиск**\n\nВыбери тип:", parse_mode="Markdown", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "📚 Архив сайта")
def archive_search(message):
    uid = message.from_user.id
    if not has_access(uid): return
    msg = bot.send_message(uid, "📚 Введи URL:\nПример: https://example.com")
    bot.register_next_step_handler(msg, lambda m: process_info(m, uid, "archive"))

@bot.message_handler(func=lambda m: m.text == "📢 Реклама домена")
def ads_search(message):
    uid = message.from_user.id
    if not has_access(uid): return
    msg = bot.send_message(uid, "📢 Введи домен:\nПример: example.com")
    bot.register_next_step_handler(msg, lambda m: process_info(m, uid, "ads"))

@bot.message_handler(func=lambda m: m.text == "🖥 Shodan")
def shodan_search(message):
    uid = message.from_user.id
    if not has_access(uid): return
    msg = bot.send_message(uid, "🖥 Введи запрос:\nПример: nginx")
    bot.register_next_step_handler(msg, lambda m: process_info(m, uid, "shodan"))

@bot.message_handler(func=lambda m: m.text == "📧 Email сервис")
def email_auth_search(message):
    uid = message.from_user.id
    if not has_access(uid): return
    msg = bot.send_message(uid, "📧 Введи email:\nПример: user@gmail.com")
    bot.register_next_step_handler(msg, lambda m: process_info(m, uid, "email_auth"))

@bot.message_handler(func=lambda m: m.text == "📝 История ника")
def username_history_search(message):
    uid = message.from_user.id
    if not has_access(uid): return
    msg = bot.send_message(uid, "📝 Введи username:\nПример: user123")
    bot.register_next_step_handler(msg, lambda m: process_info(m, uid, "username_history"))

@bot.message_handler(func=lambda m: m.text == "📍 Гео номера")
def phone_geo_search(message):
    uid = message.from_user.id
    if not has_access(uid): return
    msg = bot.send_message(uid, "📍 Введи номер:\nПример: +79001234567")
    bot.register_next_step_handler(msg, lambda m: process_info(m, uid, "phone_geo"))

@bot.message_handler(func=lambda m: m.text == "🔗 Соцсети email")
def email_social_search(message):
    uid = message.from_user.id
    if not has_access(uid): return
    msg = bot.send_message(uid, "🔗 Введи email:\nПример: user@mail.ru")
    bot.register_next_step_handler(msg, lambda m: process_info(m, uid, "email_social"))

def process_info(message, uid, qtype):
    query = message.text.strip()
    loading = bot.send_message(uid, f"📊 Поиск {qtype}...\n⏳ ~60-90 сек\n[░░░░░░░░░░░░░░░░░░░░] 0%", parse_mode="Markdown")
    
    def run():
        try:
            for p in range(10, 101, 10):
                bar = "█" * (p // 5) + "░" * (20 - p // 5)
                try: bot.edit_message_text(f"📊 Поиск {qtype}...\n⏳ {p}%\n[{bar}] {p}%", uid, loading.message_id)
                except: pass
                time.sleep(2)
            
            if qtype == "archive": results = search_web_archive(query)
            elif qtype == "ads": results = search_google_ads(query)
            elif qtype == "shodan": results = search_shodan_lite(query)
            elif qtype == "email_auth": results = search_email_authority(query)
            elif qtype == "username_history": results = search_username_history(query)
            elif qtype == "phone_geo": results = search_phone_geo(query)
            elif qtype == "email_social": results = search_email_social(query)
            else: return
            
            report = format_info_report(results, qtype)
            
            if len(report) > 4000:
                parts = [report[i:i+4000] for i in range(0, len(report), 4000)]
                for i, part in enumerate(parts):
                    if i == 0: bot.edit_message_text(part, uid, loading.message_id, parse_mode="Markdown")
                    else: bot.send_message(uid, part, parse_mode="Markdown")
            else:
                bot.edit_message_text(report, uid, loading.message_id, parse_mode="Markdown")
        except Exception as e:
            try: bot.edit_message_text(f"❌ Ошибка: {str(e)[:100]}", uid, loading.message_id)
            except: pass
    
    threading.Thread(target=run).start()

def search_phone_carrier_history(phone):
    clean = ''.join(filter(str.isdigit, phone))
    results = {"phone": clean, "findings": []}
    
    try:
        r = requests.get(f"https://www.google.com/search?q={clean}+оператор+история+перенос", timeout=5, headers=H)
        if r.status_code == 200:
            carriers = re.findall(r'(?:МТС|Билайн|Мегафон|Теле2|Yota|Тинькофф|СберМобайл|Ростелеком)[^\<]{0,50}', r.text)
            if carriers: results["findings"].append({"source": "google", "carriers": list(set(carriers))[:5]})
    except: pass
    
    return results

def search_email_breaches_deep(email):
    results = {"email": email, "breaches": [], "summary": {}}
    total_pwned = 0
    data_types = set()
    
    try:
        r = requests.get(f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}", timeout=5, headers=H)
        if r.status_code == 200:
            breaches = r.json()
            results["breaches"] = breaches
            total_pwned = len(breaches)
            
            for b in breaches[:5]:
                try:
                    r2 = requests.get(f"https://haveibeenpwned.com/api/v3/breach/{b.get('Name')}", timeout=5, headers=H)
                    if r2.status_code == 200:
                        detail = r2.json()
                        if detail.get('DataClasses'):
                            data_types.update(detail['DataClasses'])
                except: pass
    except: pass
    
    results["summary"]["total_breaches"] = total_pwned
    results["summary"]["data_types"] = list(data_types)
    
    return results

def search_ip_reputation(ip):
    results = {"ip": ip, "findings": []}
    
    apis = [
        f"https://api.abuseipdb.com/api/v2/check?ipAddress={ip}",
        f"https://www.virustotal.com/api/v3/ip_addresses/{ip}",
    ]
    
    try:
        r = requests.get(f"https://ipapi.co/{ip}/json/", timeout=5, headers=H)
        if r.status_code == 200:
            d = r.json()
            if not d.get('error'): results["findings"].append({"source": "ipapi", "data": d})
    except: pass
    
    try:
        r = requests.get(f"https://www.google.com/search?q={ip}+abuse+spam+malware", timeout=5, headers=H)
        if r.status_code == 200:
            if 'abuse' in r.text.lower() or 'spam' in r.text.lower():
                results["findings"].append({"source": "reputation", "flagged": True})
    except: pass
    
    return results

def search_ssl_chain(domain):
    clean = domain.replace('https://', '').replace('http://', '').replace('www.', '').split('/')[0]
    results = {"domain": clean, "findings": []}
    
    try:
        r = requests.get(f"https://crt.sh/?q={clean}&output=json", timeout=10, headers=H)
        if r.status_code == 200 and r.text.strip():
            certs = r.json()
            issuers = set()
            orgs = set()
            for c in certs[:20]:
                if 'issuer_name' in c: issuers.add(c['issuer_name'])
                if 'name_value' in c:
                    for name in c['name_value'].split('\n'):
                        if name != clean and clean in name:
                            orgs.add(name.strip())
            results["findings"].append({"source": "issuers", "list": list(issuers)[:5]})
            if orgs: results["findings"].append({"source": "orgs", "list": list(orgs)[:10]})
    except: pass
    
    return results

def search_whois_history(domain):
    clean = domain.replace('https://', '').replace('http://', '').replace('www.', '').split('/')[0]
    results = {"domain": clean, "findings": []}
    
    try:
        r = requests.get(f"https://www.google.com/search?q=whois+{clean}+registered", timeout=5, headers=H)
        if r.status_code == 200:
            emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', r.text)
            dates = re.findall(r'\d{4}-\d{2}-\d{2}', r.text)
            if emails or dates: results["findings"].append({"source": "whois_google", "emails": list(set(emails))[:5], "dates": list(set(dates))[:5]})
    except: pass
    
    return results

def search_domain_reputation(domain):
    clean = domain.replace('https://', '').replace('http://', '').replace('www.', '').split('/')[0]
    results = {"domain": clean, "findings": []}
    
    try:
        r = requests.get(f"https://www.google.com/search?q={clean}+scam+phishing+malware", timeout=5, headers=H)
        if r.status_code == 200:
            flagged = any(w in r.text.lower() for w in ['scam', 'phishing', 'malware', 'fraud', 'мошенни', 'фишинг'])
            results["findings"].append({"source": "reputation", "flagged": flagged})
    except: pass
    
    try:
        r = requests.get(f"https://www.google.com/search?q=site:trustpilot.com+{clean}", timeout=5, headers=H)
        if r.status_code == 200:
            links = re.findall(r'https?://[^\s<>"]+trustpilot[^\s<>"]*', r.text)
            if links: results["findings"].append({"source": "trustpilot", "links": list(set(links))[:5]})
    except: pass
    
    return results

def search_email_connections(email):
    results = {"email": email, "findings": []}
    
    try:
        r = requests.get(f"https://www.google.com/search?q={email}+account+linked+associated", timeout=5, headers=H)
        if r.status_code == 200:
            other_emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', r.text)
            unique = list(set(other_emails))
            if email in unique: unique.remove(email)
            if unique: results["findings"].append({"source": "linked_emails", "emails": unique[:10]})
    except: pass
    
    return results

def search_phone_accounts(phone):
    clean = ''.join(filter(str.isdigit, phone))
    results = {"phone": clean, "findings": []}
    
    services = [
        ("Google", f"https://www.google.com/search?q={clean}+gmail"),
        ("Microsoft", f"https://www.google.com/search?q={clean}+outlook"),
        ("Apple", f"https://www.google.com/search?q={clean}+icloud"),
        ("Steam", f"https://www.google.com/search?q={clean}+steam"),
        ("Epic", f"https://www.google.com/search?q={clean}+epic+games"),
        ("PayPal", f"https://www.google.com/search?q={clean}+paypal"),
        ("WebMoney", f"https://www.google.com/search?q={clean}+webmoney"),
        ("Qiwi", f"https://www.google.com/search?q={clean}+qiwi"),
    ]
    
    for service, url in services[:5]:
        try:
            r = requests.get(url, timeout=3, headers=H)
            if r.status_code == 200 and len(r.text) > 500:
                results["findings"].append({"source": service, "found": True})
        except: pass
    
    return results

def format_final_report(results, query_type):
    lines = []
    
    if query_type == "carrier":
        lines.append("📡 **ИСТОРИЯ ОПЕРАТОРА:** " + results.get("phone", ""))
        for f in results.get("findings", []):
            if f.get("carriers"): lines.append(f"├ Операторы: {', '.join(f['carriers'][:5])}")
        if not results.get("findings"): lines.append("❌ История не найдена")
    
    elif query_type == "breach_deep":
        lines.append("🔓 **ГЛУБОКИЕ УТЕЧКИ:** " + results.get("email", ""))
        s = results.get("summary", {})
        lines.append(f"├ Всего утечек: {s.get('total_breaches', 0)}")
        if s.get("data_types"):
            lines.append(f"├ Типы данных: {', '.join(s['data_types'][:10])}")
    
    elif query_type == "ip_rep":
        lines.append("🛡 **РЕПУТАЦИЯ IP:** " + results.get("ip", ""))
        for f in results.get("findings", []):
            if f.get("source") == "ipapi":
                d = f.get("data", {})
                lines.append(f"├ {d.get('city')}, {d.get('country_name')}")
                lines.append(f"├ ISP: {d.get('org')}")
            if f.get("flagged"): lines.append(f"├ 🚩 Подозрительная активность!")
        if not results.get("findings"): lines.append("├ Данных нет")
    
    elif query_type == "ssl_chain":
        lines.append("🔒 **SSL ЦЕПОЧКА:** " + results.get("domain", ""))
        for f in results.get("findings", []):
            if f.get("list"): lines.append(f"├ Издатели: {', '.join(f['list'][:5])}")
            if f.get("orgs"): lines.append(f"└ Связанные: {', '.join(f['orgs'][:5])}")
    
    elif query_type == "whois":
        lines.append("📋 **WHOIS:** " + results.get("domain", ""))
        for f in results.get("findings", []):
            if f.get("emails"): lines.append(f"├ Email: {', '.join(f['emails'][:5])}")
            if f.get("dates"): lines.append(f"└ Даты: {', '.join(f['dates'][:5])}")
        if not results.get("findings"): lines.append("❌ Не найдено")
    
    elif query_type == "domain_rep":
        lines.append("🌐 **РЕПУТАЦИЯ ДОМЕНА:** " + results.get("domain", ""))
        for f in results.get("findings", []):
            if f.get("flagged"): lines.append("├ 🚩 Замечен в жалобах!")
            else: lines.append("├ ✅ Чистый")
            if f.get("links"): lines.append(f"└ TrustPilot: найдено")
    
    elif query_type == "email_conn":
        lines.append("🔗 **СВЯЗИ EMAIL:** " + results.get("email", ""))
        for f in results.get("findings", []):
            if f.get("emails"):
                lines.append(f"├ Связанные email ({len(f['emails'])}):")
                for e in f['emails'][:10]: lines.append(f"│ • {e}")
        if not results.get("findings"): lines.append("❌ Связей не найдено")
    
    elif query_type == "phone_acc":
        lines.append("📱 **АККАУНТЫ:** " + results.get("phone", ""))
        found = [f['source'] for f in results.get("findings", []) if f.get('found')]
        if found: lines.append(f"├ Найден: {', '.join(found)}")
        else: lines.append("├ Не найдено")
    
    lines.append("_" * 30)
    lines.append("🔍 **Lexton Mega OSINT**")
    return "\n".join(lines)

def search_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    kb.add(KeyboardButton("🔍 Искать"), KeyboardButton("🔍 Расширенный поиск"))
    kb.add(KeyboardButton("📄 Поиск документов"), KeyboardButton("🌐 Соцсети 30+"))
    kb.add(KeyboardButton("🔎 Глубокий поиск"), KeyboardButton("👤 Поиск человека"))
    kb.add(KeyboardButton("🖼 Поиск по фото"), KeyboardButton("📱 Поиск в соцсетях"))
    kb.add(KeyboardButton("🛠 Технический поиск"), KeyboardButton("📊 Информационный"))
    kb.add(KeyboardButton("🔬 Аналитика"), KeyboardButton("💳 Купить подписку"))
    kb.add(KeyboardButton("ℹ️ Статус"), KeyboardButton("🔙 Назад"))
    return kb

@bot.message_handler(func=lambda m: m.text == "🔬 Аналитика")
def analytics_menu(message):
    uid = message.from_user.id
    if is_banned(uid): return
    if not has_access(uid): bot.send_message(uid, "❌ Нет доступа"); return
    
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(KeyboardButton("📡 История оператора"), KeyboardButton("🔓 Глубокие утечки"))
    kb.add(KeyboardButton("🛡 Репутация IP"), KeyboardButton("🔒 SSL цепочка"))
    kb.add(KeyboardButton("📋 WHOIS история"), KeyboardButton("🌐 Репутация домена"))
    kb.add(KeyboardButton("🔗 Связи email"), KeyboardButton("📱 Аккаунты номера"))
    kb.add(KeyboardButton("🔙 Назад"))
    
    bot.send_message(uid, "🔬 **Аналитика**\n\nВыбери тип:", parse_mode="Markdown", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "📡 История оператора")
def carrier_history_search(message):
    uid = message.from_user.id
    if not has_access(uid): return
    msg = bot.send_message(uid, "📡 Введи номер:\nПример: +79001234567")
    bot.register_next_step_handler(msg, lambda m: process_final(m, uid, "carrier"))

@bot.message_handler(func=lambda m: m.text == "🔓 Глубокие утечки")
def breach_deep_search(message):
    uid = message.from_user.id
    if not has_access(uid): return
    msg = bot.send_message(uid, "🔓 Введи email:\nПример: user@mail.ru")
    bot.register_next_step_handler(msg, lambda m: process_final(m, uid, "breach_deep"))

@bot.message_handler(func=lambda m: m.text == "🛡 Репутация IP")
def ip_rep_search(message):
    uid = message.from_user.id
    if not has_access(uid): return
    msg = bot.send_message(uid, "🛡 Введи IP:\nПример: 8.8.8.8")
    bot.register_next_step_handler(msg, lambda m: process_final(m, uid, "ip_rep"))

@bot.message_handler(func=lambda m: m.text == "🔒 SSL цепочка")
def ssl_chain_search(message):
    uid = message.from_user.id
    if not has_access(uid): return
    msg = bot.send_message(uid, "🔒 Введи домен:\nПример: google.com")
    bot.register_next_step_handler(msg, lambda m: process_final(m, uid, "ssl_chain"))

@bot.message_handler(func=lambda m: m.text == "📋 WHOIS история")
def whois_history_search(message):
    uid = message.from_user.id
    if not has_access(uid): return
    msg = bot.send_message(uid, "📋 Введи домен:\nПример: example.com")
    bot.register_next_step_handler(msg, lambda m: process_final(m, uid, "whois"))

@bot.message_handler(func=lambda m: m.text == "🌐 Репутация домена")
def domain_rep_search(message):
    uid = message.from_user.id
    if not has_access(uid): return
    msg = bot.send_message(uid, "🌐 Введи домен:\nПример: example.com")
    bot.register_next_step_handler(msg, lambda m: process_final(m, uid, "domain_rep"))

@bot.message_handler(func=lambda m: m.text == "🔗 Связи email")
def email_conn_search(message):
    uid = message.from_user.id
    if not has_access(uid): return
    msg = bot.send_message(uid, "🔗 Введи email:\nПример: user@mail.ru")
    bot.register_next_step_handler(msg, lambda m: process_final(m, uid, "email_conn"))

@bot.message_handler(func=lambda m: m.text == "📱 Аккаунты номера")
def phone_acc_search(message):
    uid = message.from_user.id
    if not has_access(uid): return
    msg = bot.send_message(uid, "📱 Введи номер:\nПример: +79001234567")
    bot.register_next_step_handler(msg, lambda m: process_final(m, uid, "phone_acc"))

def process_final(message, uid, qtype):
    query = message.text.strip()
    loading = bot.send_message(uid, f"🔬 Аналитика {qtype}...\n⏳ ~60-90 сек\n[░░░░░░░░░░░░░░░░░░░░] 0%", parse_mode="Markdown")
    
    def run():
        try:
            for p in range(10, 101, 10):
                bar = "█" * (p // 5) + "░" * (20 - p // 5)
                try: bot.edit_message_text(f"🔬 Анализ {qtype}...\n⏳ {p}%\n[{bar}] {p}%", uid, loading.message_id)
                except: pass
                time.sleep(2)
            
            if qtype == "carrier": results = search_phone_carrier_history(query)
            elif qtype == "breach_deep": results = search_email_breaches_deep(query)
            elif qtype == "ip_rep": results = search_ip_reputation(query)
            elif qtype == "ssl_chain": results = search_ssl_chain(query)
            elif qtype == "whois": results = search_whois_history(query)
            elif qtype == "domain_rep": results = search_domain_reputation(query)
            elif qtype == "email_conn": results = search_email_connections(query)
            elif qtype == "phone_acc": results = search_phone_accounts(query)
            else: return
            
            report = format_final_report(results, qtype)
            
            if len(report) > 4000:
                parts = [report[i:i+4000] for i in range(0, len(report), 4000)]
                for i, part in enumerate(parts):
                    if i == 0: bot.edit_message_text(part, uid, loading.message_id, parse_mode="Markdown")
                    else: bot.send_message(uid, part, parse_mode="Markdown")
            else:
                bot.edit_message_text(report, uid, loading.message_id, parse_mode="Markdown")
        except Exception as e:
            try: bot.edit_message_text(f"❌ Ошибка: {str(e)[:100]}", uid, loading.message_id)
            except: pass
    
    threading.Thread(target=run).start()

def export_report_to_json(results, query_type):
    try:
        report = {
            "bot": "Lexton Mega OSINT",
            "version": "1.0",
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "query_type": query_type,
            "data": results
        }
        return json.dumps(report, ensure_ascii=False, indent=2)
    except: return str(results)

def search_all_in_one(query):
    clean = query.lstrip('@')
    master_report = {
        "query": query,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "results": {}
    }
    
    is_phone = clean.replace('+','').replace('-','').replace(' ','').isdigit() and len(clean.replace('+','').replace('-','').replace(' ','')) >= 10
    is_email = '@' in clean and '.' in clean.split('@')[1]
    
    if is_phone:
        master_report["results"]["phone_operator"] = search_phone(clean)
        master_report["results"]["messengers"] = search_messenger_links(clean)
        master_report["results"]["reputation"] = search_phone_reputation(clean)
        master_report["results"]["geo"] = search_phone_geo(clean)
        master_report["results"]["accounts"] = search_phone_accounts(clean)
        master_report["results"]["carrier_history"] = search_phone_carrier_history(clean)
    elif is_email:
        master_report["results"]["breaches"] = search_email_breach(clean)
        master_report["results"]["breaches_deep"] = search_email_breaches_deep(clean)
        master_report["results"]["reputation"] = {"emailrep": requests.get(f"https://emailrep.io/{clean}", timeout=5, headers=H).json() if requests.get(f"https://emailrep.io/{clean}", timeout=5, headers=H).status_code == 200 else {}}
        master_report["results"]["social"] = search_email_social(clean)
        master_report["results"]["connections"] = search_email_connections(clean)
        master_report["results"]["providers"] = search_email_providers(clean)
    else:
        master_report["results"]["social_30"] = search_social_media_complete(clean)
        master_report["results"]["github"] = search_github_deep(clean)
        master_report["results"]["leaks"] = {"haveibeenpwned": requests.get(f"https://haveibeenpwned.com/api/v3/breachedaccount/{clean}", timeout=5, headers=H).json() if requests.get(f"https://haveibeenpwned.com/api/v3/breachedaccount/{clean}", timeout=5, headers=H).status_code == 200 else {}}
        master_report["results"]["username_history"] = search_username_history(clean)
        master_report["results"]["google_dorks"] = search_google_dork(clean)
    
    return master_report

def format_master_report(report):
    query = report.get("query", "")
    lines = []
    lines.append("🔍 **Lexton Mega OSINT — ПОЛНЫЙ ОТЧЁТ**")
    lines.append("_" * 35)
    lines.append(f"📅 {report.get('timestamp', '')}")
    lines.append(f"🎯 Запрос: {query}")
    lines.append("")
    
    results = report.get("results", {})
    
    for section, data in results.items():
        if not data: continue
        
        section_names = {
            "phone_operator": "📱 ОПЕРАТОР",
            "messengers": "💬 МЕССЕНДЖЕРЫ",
            "reputation": "🛡 РЕПУТАЦИЯ",
            "geo": "📍 ГЕОЛОКАЦИЯ",
            "accounts": "📱 АККАУНТЫ",
            "carrier_history": "📡 ИСТОРИЯ ОПЕРАТОРА",
            "breaches": "🔓 УТЕЧКИ",
            "breaches_deep": "🔓 ГЛУБОКИЕ УТЕЧКИ",
            "social": "🔗 СОЦСЕТИ",
            "connections": "🔗 СВЯЗИ",
            "providers": "📧 ПРОВАЙДЕРЫ",
            "social_30": "🌐 30+ СОЦСЕТЕЙ",
            "github": "💻 GITHUB",
            "leaks": "🔓 УТЕЧКИ",
            "username_history": "📝 ИСТОРИЯ НИКА",
            "google_dorks": "🔍 GOOGLE DORKS",
        }
        
        name = section_names.get(section, section.upper())
        lines.append(f"\n**{name}:**")
        
        if isinstance(data, dict):
            if section == "messengers":
                for messenger, exists in data.get("messengers", {}).items():
                    lines.append(f"├ {'✅' if exists else '❌'} {messenger}")
            elif section == "emailrep":
                lines.append(f"├ Репутация: {data.get('reputation', '?')}")
            elif section == "providers":
                for p, _ in data.get("providers", {}).items():
                    lines.append(f"├ ✅ {p}")
            else:
                findings = data.get("findings", [])
                if findings:
                    if isinstance(findings, list):
                        for f in findings[:5]:
                            if isinstance(f, dict):
                                src = f.get("source", "")
                                if f.get("exists"):
                                    lines.append(f"├ ✅ {src}")
                                elif f.get("found"):
                                    lines.append(f"├ ✅ {src}: найдено")
                    lines.append(f"└ Всего источников: {len(findings)}")
                else:
                    lines.append("└ Данные получены")
        elif isinstance(data, list):
            lines.append(f"└ Найдено: {len(data)}")
        elif isinstance(data, str):
            lines.append(f"└ {data[:200]}")
    
    lines.append("")
    lines.append("_" * 35)
    lines.append("🔍 **Lexton Mega OSINT v1.0 FINAL**")
    lines.append("📊 Отчёт сгенерирован автоматически")
    
    return "\n".join(lines)

def search_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    kb.add(KeyboardButton("🔍 Искать"), KeyboardButton("🔍 Расширенный поиск"))
    kb.add(KeyboardButton("📄 Поиск документов"), KeyboardButton("🌐 Соцсети 30+"))
    kb.add(KeyboardButton("🔎 Глубокий поиск"), KeyboardButton("👤 Поиск человека"))
    kb.add(KeyboardButton("🖼 Поиск по фото"), KeyboardButton("📱 Поиск в соцсетях"))
    kb.add(KeyboardButton("🛠 Технический поиск"), KeyboardButton("📊 Информационный"))
    kb.add(KeyboardButton("🔬 Аналитика"), KeyboardButton("🚀 Мега-поиск"))
    kb.add(KeyboardButton("💳 Купить подписку"), KeyboardButton("ℹ️ Статус"))
    kb.add(KeyboardButton("🔙 Назад"))
    return kb

@bot.message_handler(func=lambda m: m.text == "🚀 Мега-поиск")
def mega_search_start(message):
    uid = message.from_user.id
    if is_banned(uid): return
    if not has_access(uid): bot.send_message(uid, "❌ Нет доступа"); return
    
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    kb.add(KeyboardButton("🚀 ВСЁ СРАЗУ"), KeyboardButton("📋 Экспорт JSON"))
    kb.add(KeyboardButton("🔙 Назад"))
    
    bot.send_message(uid, "🚀 **Мега-поиск**\n\n«ВСЁ СРАЗУ» — поиск по всем источникам\n«Экспорт JSON» — сохранить отчёт\n\n⚠ Время: 120-180 сек", parse_mode="Markdown", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "🚀 ВСЁ СРАЗУ")
def mega_all_search(message):
    uid = message.from_user.id
    if not has_access(uid): return
    msg = bot.send_message(uid, "🚀 Введи запрос:\n• Телефон: +79001234567\n• Email: user@mail.ru\n• Username: @user")
    bot.register_next_step_handler(msg, lambda m: process_mega_all(m, uid))

def process_mega_all(message, uid):
    query = message.text.strip()
    loading = bot.send_message(uid, f"🚀 МЕГА-ПОИСК...\n⏳ 120-180 сек\n[░░░░░░░░░░░░░░░░░░░░] 0%\n\n🔍 Сканирую все источники...", parse_mode="Markdown")
    
    def run():
        try:
            total_steps = 20
            for step in range(1, total_steps + 1):
                p = int((step / total_steps) * 100)
                bar = "█" * (p // 5) + "░" * (20 - p // 5)
                steps_text = [
                    "🔍 Анализ запроса...",
                    "📱 Поиск в соцсетях...",
                    "💻 Проверка GitHub...",
                    "🔓 Поиск утечек...",
                    "📧 Проверка email...",
                    "📱 Проверка мессенджеров...",
                    "🛡 Проверка репутации...",
                    "📍 Геолокация...",
                    "📊 Сбор данных...",
                    "🔗 Поиск связей...",
                    "📝 История профиля...",
                    "🔍 Google Dorks...",
                    "📋 WHOIS проверка...",
                    "🔒 SSL анализ...",
                    "🖥 Shodan поиск...",
                    "📚 Архивы...",
                    "💰 Финансы...",
                    "👤 Родственники...",
                    "📊 Формирование отчёта...",
                    "✅ Финализация..."
                ]
                status = steps_text[min(step-1, len(steps_text)-1)]
                try: bot.edit_message_text(f"🚀 МЕГА-ПОИСК...\n[{bar}] {p}%\n\n{status}\n⏳ Осталось: ~{((total_steps-step)*6)} сек", uid, loading.message_id)
                except: pass
                time.sleep(6)
            
            report = search_all_in_one(query)
            final_text = format_master_report(report)
            
            if len(final_text) > 4000:
                parts = [final_text[i:i+4000] for i in range(0, len(final_text), 4000)]
                for i, part in enumerate(parts):
                    if i == 0: bot.edit_message_text(part, uid, loading.message_id, parse_mode="Markdown")
                    else: bot.send_message(uid, part, parse_mode="Markdown")
            else:
                bot.edit_message_text(final_text, uid, loading.message_id, parse_mode="Markdown")
            
            bot.send_message(uid, "✅ **Мега-поиск завершён!**\n\n📊 Все доступные источники проверены.\n🔍 Выбери следующее действие:", parse_mode="Markdown", reply_markup=search_kb())
        except Exception as e:
            try: bot.edit_message_text(f"❌ Ошибка: {str(e)[:100]}", uid, loading.message_id)
            except: pass
    
    threading.Thread(target=run).start()

@bot.message_handler(func=lambda m: m.text == "📋 Экспорт JSON")
def export_json_start(message):
    uid = message.from_user.id
    if not has_access(uid): return
    msg = bot.send_message(uid, "📋 Введи запрос для экспорта:\n• Телефон: +79001234567\n• Email: user@mail.ru\n• Username: @user")
    bot.register_next_step_handler(msg, lambda m: process_export_json(m, uid))

def process_export_json(message, uid):
    query = message.text.strip()
    loading = bot.send_message(uid, "📋 Генерация JSON экспорта...\n⏳ ~60-90 сек", parse_mode="Markdown")
    
    def run():
        try:
            report = search_all_in_one(query)
            json_data = export_report_to_json(report, "mega_search")
            
            with open(f"report_{uid}_{int(time.time())}.json", "w", encoding="utf-8") as f:
                f.write(json_data)
            
            bot.edit_message_text(f"✅ JSON экспорт готов!\n\n📊 Размер: {len(json_data)} символов\n📁 Файл сохранён на сервере\n\n🔍 Lexton Mega OSINT v1.0 FINAL", uid, loading.message_id, parse_mode="Markdown")
        except Exception as e:
            try: bot.edit_message_text(f"❌ Ошибка экспорта: {str(e)[:100]}", uid, loading.message_id)
            except: pass
    
    threading.Thread(target=run).start()

@bot.message_handler(commands=['export'])
def export_command(message):
    if message.from_user.id != ADMIN_ID: return
    cursor.execute('SELECT COUNT(*) FROM users')
    users = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM search_tariffs WHERE expiry > ?', (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),))
    active = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM purchase_history')
    payments = cursor.fetchone()[0]
    
    stats = {
        "bot": "Lexton Mega OSINT",
        "version": "1.0 FINAL",
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "users_total": users,
        "active_searches": active,
        "total_payments": payments,
        "functions": 90
    }
    
    with open("lexton_stats.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    
    bot.send_message(ADMIN_ID, f"📊 Статистика экспортирована в lexton_stats.json\n\n👥 Пользователей: {users}\n🔍 Активных: {active}\n💰 Платежей: {payments}\n⚡ Функций: 90")

@bot.message_handler(func=lambda m: m.text == "🤝 Рефералы")
def referral_program(message):
    uid = message.from_user.id
    uname = message.from_user.username or str(uid)
    if is_banned(uid): return
    
    cursor.execute('SELECT referral_code, balance, stars_balance, crypto_balance, total_earned FROM users WHERE user_id = ?', (uid,))
    r = cursor.fetchone()
    if not r:
        bot.send_message(uid, "❌ Ошибка. Напиши /start")
        return
    
    code, balance, stars, crypto, earned = r
    link = f"https://t.me/{BOT_USERNAME}?start={code}"
    
    cursor.execute('SELECT COUNT(*) FROM referrals WHERE referrer_id = ?', (uid,))
    refs_count = cursor.fetchone()[0]
    
    cursor.execute('SELECT SUM(amount) FROM purchase_history WHERE referrer_id = ?', (uid,))
    ref_earnings = cursor.fetchone()[0] or 0
    
    text = (
        f"🤝 **РЕФЕРАЛЬНАЯ ПРОГРАММА**\n\n"
        f"💰 **Платим 10%** от покупок рефералов!\n\n"
        f"🔗 Ссылка:\n`{link}`\n\n"
        f"👥 Рефералов: **{refs_count}**\n"
        f"💵 RUB: **{balance} ₽**\n"
        f"⭐ Звёзд: **{stars}**\n"
        f"💎 Crypto: **{crypto}$**\n"
        f"🏆 Заработано: **{earned} ₽**\n\n"
        f"💸 Вывод: от **500₽** | **400⭐** | **1$**\n\n"
        f"👇 Выбери:"
    )
    
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("👥 МОИ РЕФЕРАЛЫ", callback_data="my_refs"),
        InlineKeyboardButton("💸 ВЫВЕСТИ НА КАРТУ", callback_data="wd_card"),
        InlineKeyboardButton("⭐ ВЫВЕСТИ ЗВЁЗДЫ", callback_data="wd_stars"),
        InlineKeyboardButton("💎 ВЫВЕСТИ КРИПТО", callback_data="wd_crypto")
    )
    
    bot.send_message(uid, text, parse_mode="Markdown", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data == "my_refs")
def show_referrals(call):
    uid = call.from_user.id
    
    cursor.execute('SELECT referred_username, reg_date FROM referrals WHERE referrer_id = ? ORDER BY reg_date DESC', (uid,))
    refs = cursor.fetchall()
    
    if not refs:
        bot.answer_callback_query(call.id, "Пока нет рефералов 😢", show_alert=True)
        return
    
    text = f"👥 **ТВОИ РЕФЕРАЛЫ ({len(refs)}):**\n\n"
    for i, (u, d) in enumerate(refs, 1):
        text += f"{i}. @{u}\n   📅 {d}\n\n"
    
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🔙 НАЗАД", callback_data="back_to_ref"))
    
    bot.edit_message_text(text, uid, call.message.message_id, parse_mode="Markdown", reply_markup=kb)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "back_to_ref")
def back_to_ref(call):
    uid = call.from_user.id
    cursor.execute('SELECT referral_code, balance, stars_balance, crypto_balance, total_earned FROM users WHERE user_id = ?', (uid,))
    r = cursor.fetchone()
    if not r: return
    code, balance, stars, crypto, earned = r
    link = f"https://t.me/{BOT_USERNAME}?start={code}"
    cursor.execute('SELECT COUNT(*) FROM referrals WHERE referrer_id = ?', (uid,))
    refs_count = cursor.fetchone()[0]
    
    text = (
        f"🤝 **РЕФЕРАЛЬНАЯ ПРОГРАММА**\n\n"
        f"💰 **Платим 10%** от покупок рефералов!\n\n"
        f"🔗 Ссылка:\n`{link}`\n\n"
        f"👥 Рефералов: **{refs_count}**\n"
        f"💵 RUB: **{balance} ₽**\n"
        f"⭐ Звёзд: **{stars}**\n"
        f"💎 Crypto: **{crypto}$**\n"
        f"🏆 Заработано: **{earned} ₽**\n\n"
        f"👇 Выбери:"
    )
    
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("👥 МОИ РЕФЕРАЛЫ", callback_data="my_refs"),
        InlineKeyboardButton("💸 ВЫВЕСТИ НА КАРТУ", callback_data="wd_card"),
        InlineKeyboardButton("⭐ ВЫВЕСТИ ЗВЁЗДЫ", callback_data="wd_stars"),
        InlineKeyboardButton("💎 ВЫВЕСТИ КРИПТО", callback_data="wd_crypto")
    )
    
    bot.edit_message_text(text, uid, call.message.message_id, parse_mode="Markdown", reply_markup=kb)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "wd_card")
def wd_card_start(call):
    uid = call.from_user.id
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (uid,))
    b = cursor.fetchone()[0]
    if b < MIN_WITHDRAW:
        bot.answer_callback_query(call.id, f"❌ Мин: {MIN_WITHDRAW}₽\nБаланс: {b}₽", show_alert=True)
        return
    msg = bot.send_message(uid, f"💸 Сумма (мин {MIN_WITHDRAW}₽):")
    bot.register_next_step_handler(msg, lambda m: process_wd_card(m, b))

def process_wd_card(message, bal):
    uid = message.from_user.id
    try: a = float(message.text.strip())
    except: bot.send_message(uid, "❌ Число!"); return
    if a < MIN_WITHDRAW: bot.send_message(uid, f"❌ Мин: {MIN_WITHDRAW}₽"); return
    if a > bal: bot.send_message(uid, f"❌ Баланс: {bal}₽"); return
    msg = bot.send_message(uid, "💳 Номер карты (16 цифр):")
    bot.register_next_step_handler(msg, lambda m: finish_wd_card(m, a))

def finish_wd_card(message, a):
    uid = message.from_user.id
    card = message.text.strip().replace(' ', '')
    if not card.isdigit() or len(card) != 16: bot.send_message(uid, "❌ 16 цифр!"); return
    cursor.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (a, uid))
    conn.commit()
    kb = InlineKeyboardMarkup(); kb.add(InlineKeyboardButton("📩 @lexxtoon", url="https://t.me/lexxtoon"))
    bot.send_message(uid, f"✅ {a}₽ на {card[:4]}****{card[-4:]}\n📩 @lexxtoon", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data == "wd_stars")
def wd_stars_start(call):
    uid = call.from_user.id
    cursor.execute('SELECT stars_balance FROM users WHERE user_id = ?', (uid,))
    s = cursor.fetchone()[0]
    if s < 400: bot.answer_callback_query(call.id, f"❌ Мин: 400⭐\nБаланс: {s}⭐", show_alert=True); return
    msg = bot.send_message(uid, f"⭐ Сумма (мин 400⭐):")
    bot.register_next_step_handler(msg, lambda m: finish_wd_stars(m, s))

def finish_wd_stars(message, s):
    uid = message.from_user.id
    try: a = int(message.text.strip())
    except: bot.send_message(uid, "❌ Число!"); return
    if a < 400: bot.send_message(uid, "❌ Мин: 400⭐"); return
    if a > s: bot.send_message(uid, f"❌ Баланс: {s}⭐"); return
    cursor.execute('UPDATE users SET stars_balance = stars_balance - ? WHERE user_id = ?', (a, uid))
    conn.commit()
    kb = InlineKeyboardMarkup(); kb.add(InlineKeyboardButton("📩 @lexxtoon", url="https://t.me/lexxtoon"))
    bot.send_message(uid, f"✅ {a}⭐\n📩 @lexxtoon", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data == "wd_crypto")
def wd_crypto_start(call):
    uid = call.from_user.id
    cursor.execute('SELECT crypto_balance FROM users WHERE user_id = ?', (uid,))
    c = cursor.fetchone()[0]
    if c < 1: bot.answer_callback_query(call.id, f"❌ Мин: 1$\nБаланс: {c}$", show_alert=True); return
    msg = bot.send_message(uid, f"💎 Сумма (мин 1$):")
    bot.register_next_step_handler(msg, lambda m: process_wd_crypto(m, c))

def process_wd_crypto(message, c):
    uid = message.from_user.id
    try: a = float(message.text.strip())
    except: bot.send_message(uid, "❌ Число!"); return
    if a < 1: bot.send_message(uid, "❌ Мин: 1$"); return
    if a > c: bot.send_message(uid, f"❌ Баланс: {c}$"); return
    msg = bot.send_message(uid, "💎 Кошелёк USDT TRC20:")
    bot.register_next_step_handler(msg, lambda m: finish_wd_crypto(m, a))

def finish_wd_crypto(message, a):
    uid = message.from_user.id
    w = message.text.strip()
    if len(w) < 30: bot.send_message(uid, "❌ Неверный адрес!"); return
    cursor.execute('UPDATE users SET crypto_balance = crypto_balance - ? WHERE user_id = ?', (a, uid))
    conn.commit()
    kb = InlineKeyboardMarkup(); kb.add(InlineKeyboardButton("📩 @lexxtoon", url="https://t.me/lexxtoon"))
    bot.send_message(uid, f"✅ {a}$ на {w[:10]}...{w[-5:]}\n📩 @lexxtoon", reply_markup=kb)

    results = {"target": username_or_id, "findings": [], "stats": {}}
    
    try:
        r = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getChat?chat_id=@{username_or_id}", timeout=5)
        if r.status_code == 200:
            d = r.json()
            if d.get('ok'):
                chat = d['result']
                results["stats"]["id"] = chat.get('id')
                results["stats"]["type"] = chat.get('type')
                results["stats"]["title"] = chat.get('title') or chat.get('first_name', '')
                results["stats"]["username"] = chat.get('username', '')
                results["stats"]["description"] = chat.get('description', '')[:500]
                
                if chat.get('photo'):
                    results["findings"].append({"type": "photo", "data": chat['photo']})
    except: pass
    
    try:
        r = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMemberCount?chat_id=@{username_or_id}", timeout=5)
        if r.status_code == 200:
            d = r.json()
            if d.get('ok'): results["stats"]["members"] = d['result']
    except: pass
    
    try:
        r = requests.get(f"https://t.me/{username_or_id}", timeout=5, headers=H)
        if r.status_code == 200:
            text = r.text
            
            mentions = re.findall(r'@(\w+)', text)
            if mentions: results["findings"].append({"type": "mentions", "users": list(set(mentions))[:20]})
            
            links = re.findall(r'https?://t\.me/(\w+)', text)
            if links: results["findings"].append({"type": "tg_links", "links": list(set(links))[:20]})
            
            phones = re.findall(r'\+?[7-8][\d\s\(\)-]{9,15}', text)
            if phones: results["findings"].append({"type": "phones", "numbers": list(set(phones))[:10]})
            
            emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
            if emails: results["findings"].append({"type": "emails", "addresses": list(set(emails))[:10]})
            
            hashtags = re.findall(r'#(\w+)', text)
            if hashtags: results["findings"].append({"type": "hashtags", "tags": list(set(hashtags))[:30]})
            
            age_mentions = re.findall(r'(?:возраст|age|лет|год|года)\s*:?\s*(\d{1,3})', text, re.IGNORECASE)
            if age_mentions: results["findings"].append({"type": "age_mentions", "ages": list(set(age_mentions))[:10]})
            
            locations = re.findall(r'(?:Москва|СПб|Санкт-Петербург|Казань|Екатеринбург|Новосибирск|Сочи|Краснодар|Уфа|Челябинск|Омск|Самара|Ростов|Воронеж|Пермь|Волгоград|Нижний\sНовгород|Калининград|Тюмень|Иркутск|Хабаровск|Владивосток|Севастополь|Симферополь)', text)
            if locations: results["findings"].append({"type": "locations", "cities": list(set(locations))[:20]})
            
            dates = re.findall(r'\d{2}\.\d{2}\.\d{4}', text)
            if dates: results["findings"].append({"type": "dates", "found": list(set(dates))[:20]})
            
            prices = re.findall(r'(\d+[\s]?(?:₽|руб|р\.|RUB|USD|EUR|\$|€))', text)
            if prices: results["findings"].append({"type": "prices", "found": list(set(prices))[:15]})
            
            crypto = re.findall(r'(?:BTC|ETH|USDT|TON|SOL|XRP|DOGE|LTC)[\s:]*([\w]+)', text)
            if crypto: results["findings"].append({"type": "crypto_mentions", "data": list(set(crypto))[:10]})
            
            bots = re.findall(r'@(\w+bot)', text)
            if bots: results["findings"].append({"type": "bots", "found": list(set(bots))[:15]})
            
            channels = re.findall(r'https?://t\.me/(\w+)', text)
            if channels: results["findings"].append({"type": "channels", "linked": list(set(channels))[:20]})
            
            if 'username' in text.lower():
                name_parts = re.findall(r'@(\w{3,30})', text)
                if name_parts: results["findings"].append({"type": "possible_names", "names": list(set(name_parts))[:15]})
    except: pass
    
    try:
        r = requests.get(f"https://www.google.com/search?q=site:t.me+{username_or_id}", timeout=5, headers=H)
        if r.status_code == 200:
            snippets = re.findall(r'<div class="BNeawe s3v9rd AP7Wnd">(.*?)</div>', r.text)
            if snippets: results["findings"].append({"type": "google_snippets", "data": snippets[:10]})
    except: pass
    
    return results

    results = {"user_id": user_id, "findings": [], "stats": {}}
    
    try:
        r = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getChat?chat_id={user_id}", timeout=5)
        if r.status_code == 200:
            d = r.json()
            if d.get('ok'):
                chat = d['result']
                results["stats"]["id"] = chat.get('id')
                results["stats"]["type"] = chat.get('type')
                results["stats"]["first_name"] = chat.get('first_name', '')
                results["stats"]["last_name"] = chat.get('last_name', '')
                results["stats"]["username"] = chat.get('username', '')
                results["stats"]["bio"] = chat.get('bio', '')[:500]
    except: pass
    
    try:
        r = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getUserProfilePhotos?user_id={user_id}&limit=10", timeout=5)
        if r.status_code == 200:
            d = r.json()
            if d.get('ok'): results["stats"]["photos"] = d['result'].get('total_count', 0)
    except: pass
    
    try:
        r = requests.get(f"https://www.google.com/search?q={user_id}+telegram", timeout=5, headers=H)
        if r.status_code == 200:
            usernames = re.findall(r'@(\w+)', r.text)
            if usernames: results["findings"].append({"type": "linked_usernames", "names": list(set(usernames))[:15]})
            
            names = re.findall(r'[А-ЯЁ][а-яё]+\s[А-ЯЁ][а-яё]+', r.text)
            if names: results["findings"].append({"type": "possible_names", "names": list(set(names))[:10]})
    except: pass
    
    return results

    results = {"target": username_or_id, "changes": [], "timeline": []}
    
    try:
        r = requests.get(f"https://web.archive.org/web/timemap/link/t.me/{username_or_id}", timeout=10, headers=H)
        if r.status_code == 200:
            snapshots = re.findall(r'https?://web\.archive\.org/web/\d+/https?://t\.me/' + username_or_id, r.text)
            if snapshots: results["changes"].append({"source": "wayback", "snapshots": len(snapshots)})
    except: pass
    
    try:
        r = requests.get(f"https://www.google.com/search?q=t.me/{username_or_id}+before:2025", timeout=5, headers=H)
        if r.status_code == 200:
            old_mentions = re.findall(r'<div class="BNeawe s3v9rd AP7Wnd">(.*?)</div>', r.text)
            if old_mentions: results["timeline"].append({"source": "google_old", "mentions": old_mentions[:5]})
    except: pass
    
    try:
        r = requests.get(f"https://www.google.com/search?q=t.me/{username_or_id}+after:2024", timeout=5, headers=H)
        if r.status_code == 200:
            recent = re.findall(r'<div class="BNeawe s3v9rd AP7Wnd">(.*?)</div>', r.text)
            if recent: results["timeline"].append({"source": "google_recent", "mentions": recent[:5]})
    except: pass
    
    return results

    lines = []
    
    if query_type in ["tg_activity", "tg_user"]:
        lines.append("📊 **МИНИ FUNSTAT**\n")
        lines.append("🎯 Цель: " + results.get("target", ""))
        lines.append("")
        
        stats = results.get("stats", {})
        if stats:
            lines.append("📋 **ПРОФИЛЬ:**")
            if stats.get("title"): lines.append(f"├ Имя: {stats['title']}")
            if stats.get("first_name"): lines.append(f"├ Имя: {stats['first_name']} {stats.get('last_name', '')}")
            if stats.get("username"): lines.append(f"├ @{stats['username']}")
            if stats.get("id"): lines.append(f"├ ID: {stats['id']}")
            if stats.get("type"): lines.append(f"├ Тип: {stats['type']}")
            if stats.get("members"): lines.append(f"├ Участников: {stats['members']}")
            if stats.get("photos"): lines.append(f"├ Фото: {stats['photos']}")
            if stats.get("description"): lines.append(f"├ Описание: {stats['description'][:200]}")
            if stats.get("bio"): lines.append(f"├ Bio: {stats['bio'][:200]}")
            lines.append("")
        
        categories = {
            "mentions": "👥 УПОМИНАНИЯ",
            "tg_links": "🔗 TG ССЫЛКИ",
            "phones": "📱 ТЕЛЕФОНЫ",
            "emails": "📧 EMAIL",
            "hashtags": "#️⃣ ХЕШТЕГИ",
            "age_mentions": "🎂 ВОЗРАСТ",
            "locations": "📍 ЛОКАЦИИ",
            "dates": "📅 ДАТЫ",
            "prices": "💰 ЦЕНЫ",
            "crypto_mentions": "💎 КРИПТА",
            "bots": "🤖 БОТЫ",
            "channels": "📢 КАНАЛЫ",
            "linked_usernames": "🔗 СВЯЗАННЫЕ",
            "possible_names": "👤 ВОЗМОЖНЫЕ ИМЕНА",
            "google_snippets": "🔍 GOOGLE",
        }
        
        for f in results.get("findings", []):
            ftype = f.get("type", "")
            category = categories.get(ftype, ftype.upper())
            
            if ftype in ["mentions", "tg_links", "bots", "channels", "linked_usernames", "possible_names"]:
                items = f.get("users") or f.get("links") or f.get("names") or f.get("found") or f.get("linked") or []
                if items:
                    lines.append(f"├ {category} ({len(items)}):")
                    for item in list(items)[:10]: lines.append(f"│ • {item}")
            
            elif ftype in ["phones", "emails"]:
                items = f.get("numbers") or f.get("addresses") or []
                if items:
                    lines.append(f"├ {category} ({len(items)}):")
                    for item in list(items)[:10]: lines.append(f"│ • {item}")
            
            elif ftype in ["hashtags", "locations", "dates", "prices"]:
                items = f.get("tags") or f.get("cities") or f.get("found") or []
                if items:
                    lines.append(f"├ {category} ({len(items)}):")
                    for item in list(items)[:15]: lines.append(f"│ • {item}")
            
            elif ftype in ["age_mentions", "crypto_mentions"]:
                items = f.get("ages") or f.get("data") or []
                if items:
                    lines.append(f"├ {category} ({len(items)}):")
                    for item in list(items)[:10]: lines.append(f"│ • {item}")
            
            elif ftype == "google_snippets":
                data = f.get("data", [])
                if data:
                    lines.append(f"├ {category}:")
                    for snippet in data[:5]: lines.append(f"│ • {snippet[:200]}")
            
            lines.append("")
    
    elif query_type == "tg_changes":
        lines.append("📜 **ИСТОРИЯ ИЗМЕНЕНИЙ**\n")
        lines.append("🎯 Цель: " + results.get("target", ""))
        lines.append("")
        
        for change in results.get("changes", []):
            if change.get("snapshots"): lines.append(f"├ Архивных копий: {change['snapshots']}")
        
        for item in results.get("timeline", []):
            mentions = item.get("mentions", [])
            if mentions:
                source = item.get("source", "")
                lines.append(f"├ {source}:")
                for m in mentions[:5]: lines.append(f"│ • {m[:200]}")
        
        if not results.get("changes") and not results.get("timeline"):
            lines.append("├ История изменений не найдена")
    
    lines.append("_" * 30)
    lines.append("🔍 **Lexton Mega OSINT**")
    return "\n".join(lines)

def search_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    kb.add(KeyboardButton("🔍 Искать"), KeyboardButton("🔍 Расширенный поиск"))
    kb.add(KeyboardButton("📄 Поиск документов"), KeyboardButton("🌐 Соцсети 30+"))
    kb.add(KeyboardButton("🔎 Глубокий поиск"), KeyboardButton("👤 Поиск человека"))
    kb.add(KeyboardButton("🖼 Поиск по фото"), KeyboardButton("📱 Поиск в соцсетях"))
    kb.add(KeyboardButton("🛠 Технический поиск"), KeyboardButton("📊 Информационный"))
    kb.add(KeyboardButton("🔬 Аналитика"), KeyboardButton("📊 Мини FunStat"))
    kb.add(KeyboardButton("💳 Купить подписку"), KeyboardButton("ℹ️ Статус"))
    kb.add(KeyboardButton("🔙 Назад"))
    return kb

@bot.message_handler(func=lambda m: m.text == "📊 Мини FunStat")
def funstat_menu(message):
    uid = message.from_user.id
    if is_banned(uid): return
    if not has_access(uid): bot.send_message(uid, "❌ Нет доступа"); return
    
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    kb.add(KeyboardButton("📊 Активность по @user"), KeyboardButton("📊 Активность по ID"))
    kb.add(KeyboardButton("📜 История изменений"), KeyboardButton("🔙 Назад"))
    
    bot.send_message(uid, "📊 **Мини FunStat**\n\nАнализ активности в Telegram:\n• Упоминания в чатах\n• Возраст, локация\n• Связанные аккаунты\n• Цены, крипта\n• История изменений\n\nВыбери тип:", parse_mode="Markdown", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "📊 Активность по @user")
def funstat_username_search(message):
    uid = message.from_user.id
    if not has_access(uid): return
    msg = bot.send_message(uid, "📊 Введи @username:\nПример: @durov")
    bot.register_next_step_handler(msg, lambda m: process_funstat(m, uid, "tg_activity"))

@bot.message_handler(func=lambda m: m.text == "📊 Активность по ID")
def funstat_id_search(message):
    uid = message.from_user.id
    if not has_access(uid): return
    msg = bot.send_message(uid, "📊 Введи Telegram ID:\nПример: 123456789")
    bot.register_next_step_handler(msg, lambda m: process_funstat(m, uid, "tg_user"))

@bot.message_handler(func=lambda m: m.text == "📜 История изменений")
def funstat_changes_search(message):
    uid = message.from_user.id
    if not has_access(uid): return
    msg = bot.send_message(uid, "📜 Введи @username для проверки истории:\nПример: @durov")
    bot.register_next_step_handler(msg, lambda m: process_funstat(m, uid, "tg_changes"))

def process_funstat(message, uid, qtype):
    query = message.text.strip().lstrip('@')
    loading = bot.send_message(uid, f"📊 FunStat анализ...\n⏳ ~60-90 сек\n[░░░░░░░░░░░░░░░░░░░░] 0%", parse_mode="Markdown")
    
    def run():
        try:
            for p in range(10, 101, 10):
                bar = "█" * (p // 5) + "░" * (20 - p // 5)
                try: bot.edit_message_text(f"📊 Анализ активности...\n⏳ {p}%\n[{bar}] {p}%", uid, loading.message_id)
                except: pass
                time.sleep(2)
            
            if qtype == "tg_activity": results = search_telegram_activity(query)
            elif qtype == "tg_user": results = search_telegram_user_id(query)
            elif qtype == "tg_changes": results = search_telegram_changes_history(query)
            else: return
            
            report = format_funstat_report(results, qtype)
            
            if len(report) > 4000:
                parts = [report[i:i+4000] for i in range(0, len(report), 4000)]
                for i, part in enumerate(parts):
                    if i == 0: bot.edit_message_text(part, uid, loading.message_id, parse_mode="Markdown")
                    else: bot.send_message(uid, part, parse_mode="Markdown")
            else:
                bot.edit_message_text(report, uid, loading.message_id, parse_mode="Markdown")
        except Exception as e:
            try: bot.edit_message_text(f"❌ Ошибка: {str(e)[:100]}", uid, loading.message_id)
            except: pass
    
    threading.Thread(target=run).start()

@bot.message_handler(commands=['export'])
def export_data(message):
    uid = message.from_user.id
    if not has_access(uid): bot.send_message(uid, "❌ Нет доступа"); return
    
    cursor.execute('SELECT * FROM search_tariffs WHERE user_id = ?', (uid,))
    tariffs = cursor.fetchall()
    
    cursor.execute('SELECT query_type, query_value, date FROM search_history WHERE user_id = ? ORDER BY id DESC LIMIT 50', (uid,))
    history = cursor.fetchall()
    
    text = "📊 **ВАШ ОТЧЁТ**\n\n"
    text += f"👤 ID: {uid}\n"
    text += f"📅 Дата: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
    
    if tariffs:
        text += "💳 **Подписки:**\n"
        for t in tariffs: text += f"├ {t[2]} дн. до {t[3][:10]}\n"
    
    if history:
        text += f"\n🔍 **История поиска ({len(history)}):**\n"
        for qtype, qvalue, qdate in history[:20]:
            text += f"├ {qtype}: {qvalue} ({qdate})\n"
    
    bot.send_message(uid, text, parse_mode="Markdown")

@bot.message_handler(commands=['help'])
def help_command(message):
    uid = message.from_user.id
    text = (
        "🔍 **Lexton Mega OSINT**\n\n"
        "**Основной поиск:**\n"
        "├ 🔍 Искать — автоопределение (телефон/email/username)\n"
        "├ 🔍 Расширенный — ФИО, IP, авто, домен\n"
        "├ 📄 Документы — СНИЛС, ИНН, паспорт, адрес, фото\n"
        "├ 🌐 Соцсети 30+ — поиск по 30 платформам\n\n"
        "**Глубокий поиск:**\n"
        "├ 🔎 Глубокий — Google Dorks, сливы, утечки, репутация\n"
        "├ 👤 Человек — родственники, работа, образование, финансы\n"
        "├ 🖼 Фото — Google Lens, Yandex Vision, метаданные\n"
        "├ 📱 Соцсети — Instagram, TikTok, YouTube, GitHub, VK\n\n"
        "**Технический:**\n"
        "├ 🛠 Технический — крипта, IP, DNS, SSL, сайты\n"
        "├ 📊 Информационный — архив, Shodan, история ника\n"
        "├ 🔬 Аналитика — утечки, репутация, WHOIS, связи\n"
        "├ 📊 FunStat — активность в Telegram\n\n"
        "**Команды:**\n"
        "├ /start — перезапуск\n"
        "├ /help — эта справка\n"
        "├ /export — отчёт истории\n"
        "└ /me — мой профиль\n\n"
        "🎫 Глава: **Lexton**"
    )
    bot.send_message(uid, text, parse_mode="Markdown")

@bot.message_handler(commands=['me'])
def me_command(message):
    uid = message.from_user.id
    profile(message)

@bot.message_handler(func=lambda m: m.text == "❓ Помощь")
def help_button(message):
    help_command(message)

def main_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(KeyboardButton("🔍 ПОИСК"), KeyboardButton("📊 FUNSTAT"))
    kb.add(KeyboardButton("🛒 МАГАЗИН"), KeyboardButton("👤 ПРОФИЛЬ"))
    kb.add(KeyboardButton("🎁 Бесплатные 500₽"), KeyboardButton("🤝 Рефералы"))
    kb.add(KeyboardButton("❓ Помощь"), KeyboardButton("🎮 Игры"))
    return kb

def search_main_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    kb.add(KeyboardButton("🔍 Быстрый поиск"), KeyboardButton("👤 Поиск по ФИО"))
    kb.add(KeyboardButton("📱 Поиск по телефону"), KeyboardButton("📧 Поиск по email"))
    kb.add(KeyboardButton("🔍 Поиск по username"), KeyboardButton("🌍 Поиск по IP"))
    kb.add(KeyboardButton("🚗 Поиск по авто"), KeyboardButton("🌐 Поиск по домену"))
    kb.add(KeyboardButton("📄 Поиск документов"), KeyboardButton("🌐 Соцсети 30+"))
    kb.add(KeyboardButton("🔎 Глубокий поиск"), KeyboardButton("🖼 Поиск по фото"))
    kb.add(KeyboardButton("📱 Поиск в соцсетях"), KeyboardButton("?? Аналитика"))
    kb.add(KeyboardButton("🛠 Технический поиск"), KeyboardButton("📊 Информационный"))
    kb.add(KeyboardButton("🚀 Мега-поиск"), KeyboardButton("💳 Купить подписку"))
    kb.add(KeyboardButton("ℹ️ Статус"), KeyboardButton("🔙 Назад"))
    return kb

def funstat_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    kb.add(KeyboardButton("📊 Поиск по @user"), KeyboardButton("📊 Поиск по ID"))
    kb.add(KeyboardButton("📜 История изменений"), KeyboardButton("💳 Купить подписку"))
    kb.add(KeyboardButton("ℹ️ Статус"), KeyboardButton("🔙 Назад"))
    return kb

def docs_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    kb.add(KeyboardButton("📄 Поиск по СНИЛС"), KeyboardButton("📄 Поиск по ИНН"))
    kb.add(KeyboardButton("📄 Поиск по паспорту"), KeyboardButton("📍 Поиск по адресу"))
    kb.add(KeyboardButton("🖼 Поиск по фото"), KeyboardButton("🔙 Назад"))
    return kb

def social_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(KeyboardButton("📷 Instagram"), KeyboardButton("🎵 TikTok"))
    kb.add(KeyboardButton("▶️ YouTube"), KeyboardButton("💻 GitHub"))
    kb.add(KeyboardButton("📱 VK"), KeyboardButton("📱 OK"))
    kb.add(KeyboardButton("📱 Telegram"), KeyboardButton("👻 Snapchat"))
    kb.add(KeyboardButton("🔙 Назад"))
    return kb

def deep_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    kb.add(KeyboardButton("🔍 Google Dorks"), KeyboardButton("📝 Поиск сливов"))
    kb.add(KeyboardButton("🔓 Утечки email"), KeyboardButton("📱 Репутация номера"))
    kb.add(KeyboardButton("🏢 Поиск компании"), KeyboardButton("🔙 Назад"))
    return kb

def photo_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    kb.add(KeyboardButton("🖼 Google Lens"), KeyboardButton("🖼 Yandex Vision"))
    kb.add(KeyboardButton("🖼 TinEye"), KeyboardButton("📷 Метаданные фото"))
    kb.add(KeyboardButton("💬 Мессенджеры"), KeyboardButton("📧 Провайдер email"))
    kb.add(KeyboardButton("🔙 Назад"))
    return kb

def analytics_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(KeyboardButton("📡 История оператора"), KeyboardButton("🔓 Глубокие утечки"))
    kb.add(KeyboardButton("🛡 Репутация IP"), KeyboardButton("🔒 SSL цепочка"))
    kb.add(KeyboardButton("📋 WHOIS история"), KeyboardButton("🌐 Репутация домена"))
    kb.add(KeyboardButton("🔗 Связи email"), KeyboardButton("📱 Аккаунты номера"))
    kb.add(KeyboardButton("🔙 Назад"))
    return kb

def people_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(KeyboardButton("👨‍👩‍👧 Родственники"), KeyboardButton("💼 Работа"))
    kb.add(KeyboardButton("🎓 Образование"), KeyboardButton("💰 Финансы"))
    kb.add(KeyboardButton("🌑 Упоминания в сети"), KeyboardButton("🔙 Назад"))
    return kb

def tech_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(KeyboardButton("💎 Криптокошелёк"), KeyboardButton("🌍 IP диапазон"))
    kb.add(KeyboardButton("🔗 DNS записи"), KeyboardButton("🔒 SSL сертификаты"))
    kb.add(KeyboardButton("🛠 Технологии сайта"), KeyboardButton("🔓 Полные утечки"))
    kb.add(KeyboardButton("🔙 Назад"))
    return kb

def info_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(KeyboardButton("📚 Архив сайта"), KeyboardButton("📢 Реклама домена"))
    kb.add(KeyboardButton("🖥 Shodan"), KeyboardButton("📧 Email сервис"))
    kb.add(KeyboardButton("📝 История ника"), KeyboardButton("📍 Гео номера"))
    kb.add(KeyboardButton("🔗 Соцсети email"), KeyboardButton("🔙 Назад"))
    return kb

@bot.message_handler(func=lambda m: m.text == "🔍 ПОИСК")
def search_menu_handler(message):
    uid = message.from_user.id
    if is_banned(uid): return
    h = has_access(uid); d = get_days(uid)
    cursor.execute('SELECT stars_balance, crypto_balance FROM users WHERE user_id = ?', (uid,))
    s, c = cursor.fetchone() or (0, 0)
    text = f"🔍 **ПОИСК**\n⭐ Звёзды: {s} | 💎 Crypto: {c}$\n"
    text += f"✅ Доступ: {d} дн.\n" if h else "❌ Нет доступа\n"
    text += "\n💰 30д/150⭐/1.5$ | 90д/350⭐/3.5$ | ∞/5000⭐/50$"
    bot.send_message(uid, text, parse_mode="Markdown", reply_markup=search_main_kb())

@bot.message_handler(func=lambda m: m.text == "📊 FUNSTAT")
def funstat_menu_handler(message):
    uid = message.from_user.id
    if is_banned(uid): return
    h = has_access(uid); d = get_days(uid)
    cursor.execute('SELECT stars_balance, crypto_balance FROM users WHERE user_id = ?', (uid,))
    s, c = cursor.fetchone() or (0, 0)
    text = (
        "📊 **FUNSTAT — Анализ Telegram**\n\n"
        "🔍 Поиск по всей активности:\n"
        "├ Упоминания в чатах и каналах\n"
        "├ Связанные аккаунты\n"
        "├ Возраст, локация, контакты\n"
        "├ Цены, крипта, хештеги\n"
        "├ История изменений профиля\n"
        "├ Архивные копии (Wayback)\n"
        f"⭐ Звёзды: {s} | 💎 Crypto: {c}$\n"
        f"└ {'✅ Доступ: '+str(d)+' дн.' if h else '❌ Нет доступа'}\n\n"
        "💰 30д/150⭐/1.5$ | 90д/350⭐/3.5$ | ∞/5000⭐/50$"
    )
    
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("🔍 Поиск по @user", callback_data="funstat_user"),
        InlineKeyboardButton("🆔 Поиск по ID", callback_data="funstat_id"),
        InlineKeyboardButton("📜 История изменений", callback_data="funstat_history")
    )
    
    bot.send_message(uid, text, parse_mode="Markdown", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data == "funstat_user")
def funstat_user_start(call):
    uid = call.from_user.id
    if not has_access(uid): bot.answer_callback_query(call.id, "❌ Нет доступа", show_alert=True); return
    msg = bot.send_message(uid, "🔍 Введи @username:\nПример: @durov")
    bot.register_next_step_handler(msg, lambda m: process_funstat(m, uid, "tg_activity"))
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "funstat_id")
def funstat_id_start(call):
    uid = call.from_user.id
    if not has_access(uid): bot.answer_callback_query(call.id, "❌ Нет доступа", show_alert=True); return
    msg = bot.send_message(uid, "🆔 Введи Telegram ID:\nПример: 123456789")
    bot.register_next_step_handler(msg, lambda m: process_funstat(m, uid, "tg_user"))
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "funstat_history")
def funstat_history_start(call):
    uid = call.from_user.id
    if not has_access(uid): bot.answer_callback_query(call.id, "❌ Нет доступа", show_alert=True); return
    msg = bot.send_message(uid, "📜 Введи @username:\nПример: @durov")
    bot.register_next_step_handler(msg, lambda m: process_funstat(m, uid, "tg_changes"))
    bot.answer_callback_query(call.id)

def process_funstat(message, uid, qtype):
    query = message.text.strip().lstrip('@')
    loading = bot.send_message(uid, f"📊 FunStat анализ...\n⏳ ~60-90 сек\n[░░░░░░░░░░░░░░░░░░░░] 0%", parse_mode="Markdown")
    
    def run():
        try:
            for p in range(10, 101, 10):
                bar = "█" * (p // 5) + "░" * (20 - p // 5)
                try: bot.edit_message_text(f"📊 Анализ активности...\n⏳ {p}%\n[{bar}] {p}%", uid, loading.message_id)
                except: pass
                time.sleep(2)
            
            if qtype == "tg_activity": results = search_telegram_activity(query)
            elif qtype == "tg_user": results = search_telegram_user_id(query)
            elif qtype == "tg_changes": results = search_telegram_changes_history(query)
            else: return
            
            report = format_funstat_report(results, qtype)
            
            if len(report) > 4000:
                parts = [report[i:i+4000] for i in range(0, len(report), 4000)]
                for i, part in enumerate(parts):
                    if i == 0: bot.edit_message_text(part, uid, loading.message_id, parse_mode="Markdown")
                    else: bot.send_message(uid, part, parse_mode="Markdown")
            else:
                bot.edit_message_text(report, uid, loading.message_id, parse_mode="Markdown")
        except Exception as e:
            try: bot.edit_message_text(f"❌ Ошибка: {str(e)[:100]}", uid, loading.message_id)
            except: pass
    
    threading.Thread(target=run).start()

@bot.message_handler(func=lambda m: m.text == "👤 ПРОФИЛЬ")
def profile_button(message):
    profile(message)

@bot.message_handler(func=lambda m: m.text == "🔍 Быстрый поиск")
def quick_search(message):
    uid = message.from_user.id
    if not has_access(uid): bot.send_message(uid, "❌ Нет доступа"); return
    msg = bot.send_message(uid, "🔍 Введи запрос:\n• Телефон: +79001234567\n• Email: user@mail.ru\n• Username: @user")
    bot.register_next_step_handler(msg, lambda m: mega_search(m, uid))

@bot.message_handler(func=lambda m: m.text == "👤 Поиск по ФИО")
def fio_handler(message):
    uid = message.from_user.id
    if not has_access(uid): bot.send_message(uid, "❌ Нет доступа"); return
    msg = bot.send_message(uid, "👤 Введи ФИО:\nПример: Иванов Иван Иванович")
    bot.register_next_step_handler(msg, lambda m: mega_search_person(m, uid))

@bot.message_handler(func=lambda m: m.text == "📱 Поиск по телефону")
def phone_handler(message):
    uid = message.from_user.id
    if not has_access(uid): bot.send_message(uid, "❌ Нет доступа"); return
    msg = bot.send_message(uid, "📱 Введи номер:\nПример: +79001234567")
    bot.register_next_step_handler(msg, lambda m: mega_search_single(m, uid, "phone"))

@bot.message_handler(func=lambda m: m.text == "📧 Поиск по email")
def email_handler(message):
    uid = message.from_user.id
    if not has_access(uid): bot.send_message(uid, "❌ Нет доступа"); return
    msg = bot.send_message(uid, "📧 Введи email:\nПример: user@mail.ru")
    bot.register_next_step_handler(msg, lambda m: mega_search_single(m, uid, "email"))

@bot.message_handler(func=lambda m: m.text == "🔍 Поиск по username")
def username_handler(message):
    uid = message.from_user.id
    if not has_access(uid): bot.send_message(uid, "❌ Нет доступа"); return
    msg = bot.send_message(uid, "🔍 Введи username:\nПример: @durov")
    bot.register_next_step_handler(msg, lambda m: mega_search_single(m, uid, "username"))

@bot.message_handler(func=lambda m: m.text == "🌍 Поиск по IP")
def ip_handler(message):
    uid = message.from_user.id
    if not has_access(uid): bot.send_message(uid, "❌ Нет доступа"); return
    msg = bot.send_message(uid, "🌍 Введи IP:\nПример: 8.8.8.8")
    bot.register_next_step_handler(msg, lambda m: process_advanced(m, uid, "ip"))

@bot.message_handler(func=lambda m: m.text == "🚗 Поиск по авто")
def car_handler(message):
    uid = message.from_user.id
    if not has_access(uid): bot.send_message(uid, "❌ Нет доступа"); return
    msg = bot.send_message(uid, "🚗 Введи госномер:\nПример: А123БВ177")
    bot.register_next_step_handler(msg, lambda m: process_advanced(m, uid, "car"))

@bot.message_handler(func=lambda m: m.text == "🌐 Поиск по домену")
def domain_handler(message):
    uid = message.from_user.id
    if not has_access(uid): bot.send_message(uid, "❌ Нет доступа"); return
    msg = bot.send_message(uid, "🌐 Введи домен:\nПример: example.com")
    bot.register_next_step_handler(msg, lambda m: process_advanced(m, uid, "domain"))

@bot.message_handler(func=lambda m: m.text == "📄 Поиск документов")
def docs_handler(message):
    uid = message.from_user.id
    if not has_access(uid): bot.send_message(uid, "❌ Нет доступа"); return
    bot.send_message(uid, "📄 **Поиск документов**\n\nВыбери тип:", parse_mode="Markdown", reply_markup=docs_kb())

@bot.message_handler(func=lambda m: m.text == "🌐 Соцсети 30+")
def social_handler(message):
    uid = message.from_user.id
    if not has_access(uid): bot.send_message(uid, "❌ Нет доступа"); return
    msg = bot.send_message(uid, "🌐 Введи username:\nПример: @user или user@mail.ru")
    bot.register_next_step_handler(msg, lambda m: social_full_search(m, uid))

@bot.message_handler(func=lambda m: m.text == "🔎 Глубокий поиск")
def deep_handler(message):
    uid = message.from_user.id
    if not has_access(uid): bot.send_message(uid, "❌ Нет доступа"); return
    bot.send_message(uid, "🔎 **Глубокий поиск**\n\nВыбери тип:", parse_mode="Markdown", reply_markup=deep_kb())

@bot.message_handler(func=lambda m: m.text == "🖼 Поиск по фото")
def photo_handler(message):
    uid = message.from_user.id
    if not has_access(uid): bot.send_message(uid, "❌ Нет доступа"); return
    bot.send_message(uid, "🖼 **Поиск по фото**\n\nВыбери тип:", parse_mode="Markdown", reply_markup=photo_kb())

@bot.message_handler(func=lambda m: m.text == "📱 Поиск в соцсетях")
def social_deep_handler(message):
    uid = message.from_user.id
    if not has_access(uid): bot.send_message(uid, "❌ Нет доступа"); return
    bot.send_message(uid, "📱 **Поиск в соцсетях**\n\nВыбери платформу:", parse_mode="Markdown", reply_markup=social_kb())

@bot.message_handler(func=lambda m: m.text == "🔬 Аналитика")
def analytics_handler(message):
    uid = message.from_user.id
    if not has_access(uid): bot.send_message(uid, "❌ Нет доступа"); return
    bot.send_message(uid, "🔬 **Аналитика**\n\nВыбери тип:", parse_mode="Markdown", reply_markup=analytics_kb())

@bot.message_handler(func=lambda m: m.text == "👤 Поиск человека")
def people_handler(message):
    uid = message.from_user.id
    if not has_access(uid): bot.send_message(uid, "❌ Нет доступа"); return
    bot.send_message(uid, "👤 **Поиск человека**\n\nВыбери тип:", parse_mode="Markdown", reply_markup=people_kb())

@bot.message_handler(func=lambda m: m.text == "🛠 Технический поиск")
def tech_handler(message):
    uid = message.from_user.id
    if not has_access(uid): bot.send_message(uid, "❌ Нет доступа"); return
    bot.send_message(uid, "🛠 **Технический поиск**\n\nВыбери тип:", parse_mode="Markdown", reply_markup=tech_kb())

@bot.message_handler(func=lambda m: m.text == "📊 Информационный")
def info_handler(message):
    uid = message.from_user.id
    if not has_access(uid): bot.send_message(uid, "❌ Нет доступа"); return
    bot.send_message(uid, "📊 **Информационный поиск**\n\nВыбери тип:", parse_mode="Markdown", reply_markup=info_kb())

@bot.message_handler(func=lambda m: m.text == "🔙 Назад")
def back_button(message):
    bot.send_message(message.chat.id, "👋 Главное меню:", reply_markup=main_menu())


    results = {"target": username_or_id, "findings": [], "stats": {}}
    
    try:
        r = requests.get(f"https://t.me/{username_or_id}", timeout=5, headers=H)
        if r.status_code == 200:
            text = r.text
            
            mentions = re.findall(r'@(\w+)', text)
            if mentions: results["findings"].append({"type": "mentions", "users": list(set(mentions))[:20]})
            
            links = re.findall(r'https?://t\.me/(\w+)', text)
            if links: results["findings"].append({"type": "tg_links", "links": list(set(links))[:20]})
            
            phones = re.findall(r'\+?[7-8][\d\s\(\)-]{9,15}', text)
            if phones: results["findings"].append({"type": "phones", "numbers": list(set(phones))[:10]})
            
            emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
            if emails: results["findings"].append({"type": "emails", "addresses": list(set(emails))[:10]})
            
            hashtags = re.findall(r'#(\w+)', text)
            if hashtags: results["findings"].append({"type": "hashtags", "tags": list(set(hashtags))[:30]})
            
            age_mentions = re.findall(r'(?:возраст|age|лет|год|года)\s*:?\s*(\d{1,3})', text, re.IGNORECASE)
            if age_mentions: results["findings"].append({"type": "age_mentions", "ages": list(set(age_mentions))[:10]})
            
            locations = re.findall(r'(?:Москва|СПб|Санкт-Петербург|Казань|Екатеринбург|Новосибирск|Сочи|Краснодар|Уфа|Челябинск|Омск|Самара|Ростов|Воронеж|Пермь|Волгоград|Нижний\sНовгород|Калининград|Тюмень|Иркутск|Хабаровск|Владивосток|Севастополь|Симферополь)', text)
            if locations: results["findings"].append({"type": "locations", "cities": list(set(locations))[:20]})
            
            dates = re.findall(r'\d{2}\.\d{2}\.\d{4}', text)
            if dates: results["findings"].append({"type": "dates", "found": list(set(dates))[:20]})
            
            prices = re.findall(r'(\d+[\s]?(?:₽|руб|р\.|RUB|USD|EUR|\$|€))', text)
            if prices: results["findings"].append({"type": "prices", "found": list(set(prices))[:15]})
            
            crypto = re.findall(r'(?:BTC|ETH|USDT|TON|SOL|XRP|DOGE|LTC)[\s:]*([\w]+)', text)
            if crypto: results["findings"].append({"type": "crypto_mentions", "data": list(set(crypto))[:10]})
            
            bots = re.findall(r'@(\w+bot)', text)
            if bots: results["findings"].append({"type": "bots", "found": list(set(bots))[:15]})
            
            channels = re.findall(r'https?://t\.me/(\w+)', text)
            if channels: results["findings"].append({"type": "channels", "linked": list(set(channels))[:20]})
            
            if 'username' in text.lower():
                name_parts = re.findall(r'@(\w{3,30})', text)
                if name_parts: results["findings"].append({"type": "possible_names", "names": list(set(name_parts))[:15]})
    except: pass
    
    try:
        r = requests.get(f"https://www.google.com/search?q=site:t.me+{username_or_id}", timeout=5, headers=H)
        if r.status_code == 200:
            snippets = re.findall(r'<div class="BNeawe s3v9rd AP7Wnd">(.*?)</div>', r.text)
            if snippets: results["findings"].append({"type": "google_snippets", "data": snippets[:10]})
    except: pass
    
    return results

    results = {"user_id": user_id, "findings": [], "stats": {}}
    
    try:
        r = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getChat?chat_id={user_id}", timeout=5)
        if r.status_code == 200:
            d = r.json()
            if d.get('ok'):
                chat = d['result']
                results["stats"]["id"] = chat.get('id')
                results["stats"]["first_name"] = chat.get('first_name', '')
                results["stats"]["last_name"] = chat.get('last_name', '')
                results["stats"]["username"] = chat.get('username', '')
    except: pass
    
    try:
        r = requests.get(f"https://www.google.com/search?q={user_id}+telegram", timeout=5, headers=H)
        if r.status_code == 200:
            usernames = re.findall(r'@(\w+)', r.text)
            if usernames: results["findings"].append({"type": "linked_usernames", "names": list(set(usernames))[:15]})
            
            names = re.findall(r'[А-ЯЁ][а-яё]+\s[А-ЯЁ][а-яё]+', r.text)
            if names: results["findings"].append({"type": "possible_names", "names": list(set(names))[:10]})
    except: pass
    
    return results

    results = {"target": username_or_id, "changes": [], "timeline": []}
    
    try:
        r = requests.get(f"https://web.archive.org/web/timemap/link/t.me/{username_or_id}", timeout=10, headers=H)
        if r.status_code == 200:
            snapshots = re.findall(r'https?://web\.archive\.org/web/\d+/https?://t\.me/' + username_or_id, r.text)
            if snapshots: results["changes"].append({"source": "wayback", "snapshots": len(snapshots)})
    except: pass
    
    try:
        r = requests.get(f"https://www.google.com/search?q=t.me/{username_or_id}+before:2025", timeout=5, headers=H)
        if r.status_code == 200:
            old_mentions = re.findall(r'<div class="BNeawe s3v9rd AP7Wnd">(.*?)</div>', r.text)
            if old_mentions: results["timeline"].append({"source": "google_old", "mentions": old_mentions[:5]})
    except: pass
    
    try:
        r = requests.get(f"https://www.google.com/search?q=t.me/{username_or_id}+after:2024", timeout=5, headers=H)
        if r.status_code == 200:
            recent = re.findall(r'<div class="BNeawe s3v9rd AP7Wnd">(.*?)</div>', r.text)
            if recent: results["timeline"].append({"source": "google_recent", "mentions": recent[:5]})
    except: pass
    
    return results

    lines = []
    
    if query_type in ["tg_activity", "tg_user"]:
        lines.append("📊 **МИНИ FUNSTAT**\n")
        lines.append("🎯 Цель: " + str(results.get("target", results.get("user_id", ""))))
        lines.append("")
        
        stats = results.get("stats", {})
        if stats:
            lines.append("📋 **ПРОФИЛЬ:**")
            if stats.get("first_name"): lines.append(f"├ Имя: {stats['first_name']} {stats.get('last_name', '')}")
            if stats.get("username"): lines.append(f"├ @{stats['username']}")
            if stats.get("id"): lines.append(f"├ ID: {stats['id']}")
            lines.append("")
        
        categories = {
            "mentions": "👥 УПОМИНАНИЯ",
            "tg_links": "🔗 TG ССЫЛКИ",
            "phones": "📱 ТЕЛЕФОНЫ",
            "emails": "📧 EMAIL",
            "hashtags": "#️⃣ ХЕШТЕГИ",
            "age_mentions": "🎂 ВОЗРАСТ",
            "locations": "📍 ЛОКАЦИИ",
            "dates": "📅 ДАТЫ",
            "prices": "💰 ЦЕНЫ",
            "crypto_mentions": "💎 КРИПТА",
            "bots": "🤖 БОТЫ",
            "channels": "📢 КАНАЛЫ",
            "linked_usernames": "🔗 СВЯЗАННЫЕ",
            "possible_names": "👤 ВОЗМОЖНЫЕ ИМЕНА",
            "google_snippets": "🔍 GOOGLE",
        }
        
        for f in results.get("findings", []):
            ftype = f.get("type", "")
            category = categories.get(ftype, ftype.upper())
            
            items = (f.get("users") or f.get("links") or f.get("names") or 
                    f.get("found") or f.get("linked") or f.get("numbers") or 
                    f.get("addresses") or f.get("tags") or f.get("cities") or 
                    f.get("ages") or f.get("data") or [])
            
            if items:
                lines.append(f"├ {category} ({len(items)}):")
                for item in list(items)[:10]: lines.append(f"│ • {item}")
                lines.append("")
    
    elif query_type == "tg_changes":
        lines.append("📜 **ИСТОРИЯ ИЗМЕНЕНИЙ**\n")
        lines.append("🎯 Цель: " + results.get("target", ""))
        lines.append("")
        
        for change in results.get("changes", []):
            if change.get("snapshots"): lines.append(f"├ Архивных копий: {change['snapshots']}")
        
        for item in results.get("timeline", []):
            mentions = item.get("mentions", [])
            if mentions:
                source = item.get("source", "")
                lines.append(f"├ {source}:")
                for m in mentions[:5]: lines.append(f"│ • {m[:200]}")
        
        if not results.get("changes") and not results.get("timeline"):
            lines.append("├ История изменений не найдена")
    
    lines.append("_" * 30)
    lines.append("🔍 **Lexton Mega OSINT**")
    return "\n".join(lines)


print("""
╔══════════════════════════════════════════╗
║     🔍 LEXTON MEGA OSINT v1.0 🔍       ║
╠══════════════════════════════════════════╣
║  ✅ 13 модулей загружено               ║
║  ✅ 90+ функций поиска                 ║
║  ✅ База данных активна                ║
║  ✅ Админ-команды готовы               ║
║  ✅ Оплата: Stars + CryptoBot          ║
╠══════════════════════════════════════════╣
║  📱 Бот: @LeextonShopbot               ║
║  👑 Админ: /add /ban /stats /text      ║
║  🎫 Ваучер: LEXTON30                   ║
║  ❓ Справка: /help                      ║
╚══════════════════════════════════════════╝
""")

if __name__ == '__main__':
    print("🚀 Бот запущен...")
    bot.infinity_polling()
