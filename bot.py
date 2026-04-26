import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3
from datetime import datetime, timedelta
import random
import string
import time

BOT_TOKEN = "8603262735:AAHqaLfbOomzKV3D05SEwNmULhyrDtVCL8I"
ADMIN_ID = 8617203586
SHOP_URL = "https://sites.google.com/view/dchcnvnchgx/home"
SEARCH_BOT = "https://t.me/LextonSearchbot"
BOT_USERNAME = "LeextonShopbot"
MIN_WITHDRAW = 500

bot = telebot.TeleBot(BOT_TOKEN)
conn = sqlite3.connect('shop.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, balance REAL DEFAULT 0, total_earned REAL DEFAULT 0, referral_code TEXT UNIQUE, invited_by INTEGER, reg_date TEXT, banned_until TEXT DEFAULT NULL)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS referrals (referrer_id INTEGER, referred_id INTEGER, referred_username TEXT, reg_date TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS purchase_history (id INTEGER PRIMARY KEY AUTOINCREMENT, buyer_username TEXT, buyer_id INTEGER, amount REAL, date TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS user_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT, action TEXT, details TEXT, date TEXT)''')
conn.commit()

H = {'User-Agent': 'Mozilla/5.0'}

def log_action(uid, uname, action, details=""):
    try:
        cursor.execute('INSERT INTO user_logs (user_id, username, action, details, date) VALUES (?, ?, ?, ?, ?)',
                       (uid, uname, action, str(details)[:200], datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
    except: pass

def is_banned(uid):
    cursor.execute('SELECT banned_until FROM users WHERE user_id = ?', (uid,))
    r = cursor.fetchone()
    return r and r[0] and datetime.strptime(r[0], "%Y-%m-%d %H:%M:%S") > datetime.now()

def main_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(KeyboardButton("🛒 МАГАЗИН"), KeyboardButton("🔍 ПОИСК ИНФОРМАЦИИ"))
    kb.add(KeyboardButton("🤝 РЕФЕРАЛЬНАЯ ПРОГРАММА"), KeyboardButton("👤 ПРОФИЛЬ"))
    kb.add(KeyboardButton("ℹ️ О БОТЕ"))
    return kb

@bot.message_handler(commands=['start'])
def start(message):
    uid = message.from_user.id; uname = message.from_user.username or str(uid)
    log_action(uid, uname, "/start")
    if is_banned(uid): return
    
    args = message.text.split()
    ref = args[1] if len(args) > 1 else None
    
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (uid,))
    if cursor.fetchone():
        bot.send_message(uid, "👋 С возвращением!\n\nВыбери действие:", reply_markup=main_menu())
        return
    
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    invited = None
    
    if ref:
        cursor.execute('SELECT user_id FROM users WHERE referral_code = ?', (ref,))
        inv = cursor.fetchone()
        if inv:
            invited = inv[0]
            cursor.execute('INSERT INTO referrals VALUES (?, ?, ?, ?)',
                           (invited, uid, uname, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
    
    cursor.execute('INSERT INTO users (user_id, username, referral_code, invited_by, reg_date) VALUES (?, ?, ?, ?, ?)',
                   (uid, uname, code, invited, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    
    link = f"https://t.me/{BOT_USERNAME}?start={code}"
    text = (
        f"🎉 Добро пожаловать в Lexton Shop!\n\n"
        f"🛒 МАГАЗИН — физ аккаунты Telegram\n"
        f"🔍 ПОИСК — перейди в @LextonSearchbot\n"
        f"🤝 РЕФЕРАЛЫ — 10% от покупок друзей\n\n"
        f"Твоя реферальная ссылка:\n`{link}`\n\n"
        f"Выбери действие:"
    )
    bot.send_message(uid, text, parse_mode="Markdown", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "🛒 МАГАЗИН")
def shop(message):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🛒 ПЕРЕЙТИ В МАГАЗИН", url=SHOP_URL))
    bot.send_message(message.chat.id,
        "🛒 **Магазин Lexton Shop**\n\n"
        "Купить физ аккаунты Telegram.\n"
        "Оплата через СБП.\n"
        "После оплаты напиши @lexxtoon с чеком.",
        parse_mode="Markdown", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "🔍 ПОИСК ИНФОРМАЦИИ")
def search(message):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🔍 ПЕРЕЙТИ В БОТ ПОИСКА", url=SEARCH_BOT))
    bot.send_message(message.chat.id,
        "🔍 **Поиск информации**\n\n"
        "Телефон, email, username и другое.\n"
        "Перейди в @LextonSearchbot:",
        parse_mode="Markdown", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "🤝 РЕФЕРАЛЬНАЯ ПРОГРАММА")
def referral_program(message):
    uid = message.from_user.id
    if is_banned(uid): return
    
    cursor.execute('SELECT referral_code, balance, total_earned FROM users WHERE user_id = ?', (uid,))
    r = cursor.fetchone()
    if not r: bot.send_message(uid, "❌ Напиши /start"); return
    
    code, balance, earned = r
    link = f"https://t.me/{BOT_USERNAME}?start={code}"
    cursor.execute('SELECT COUNT(*) FROM referrals WHERE referrer_id = ?', (uid,))
    refs = cursor.fetchone()[0]
    
    text = (
        f"🤝 **РЕФЕРАЛЬНАЯ ПРОГРАММА**\n\n"
        f"💰 Платим **10%** от покупок рефералов!\n\n"
        f"🔗 Твоя ссылка:\n`{link}`\n\n"
        f"👥 Рефералов: **{refs}**\n"
        f"💵 Баланс: **{balance} ₽**\n"
        f"🏆 Заработано: **{earned} ₽**\n\n"
        f"💸 Вывод от **{MIN_WITHDRAW} ₽**"
    )
    
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("👥 МОИ РЕФЕРАЛЫ", callback_data="my_refs"),
        InlineKeyboardButton("💸 ВЫВЕСТИ НА КАРТУ", callback_data="withdraw")
    )
    bot.send_message(uid, text, parse_mode="Markdown", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data == "my_refs")
def show_referrals(call):
    uid = call.from_user.id
    cursor.execute('SELECT referred_username, reg_date FROM referrals WHERE referrer_id = ? ORDER BY reg_date DESC', (uid,))
    refs = cursor.fetchall()
    if not refs: bot.answer_callback_query(call.id, "Пока нет рефералов", show_alert=True); return
    text = f"👥 **ТВОИ РЕФЕРАЛЫ ({len(refs)}):**\n\n"
    for i, (u, d) in enumerate(refs, 1):
        text += f"{i}. @{u}\n   📅 {d}\n\n"
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🔙 НАЗАД", callback_data="back_to_ref"))
    bot.edit_message_text(text, uid, call.message.message_id, parse_mode="Markdown", reply_markup=kb)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "back_to_ref")
def back_to_ref(call):
    referral_program(call.message)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "withdraw")
def withdraw_start(call):
    uid = call.from_user.id
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (uid,))
    b = cursor.fetchone()[0]
    if b < MIN_WITHDRAW: bot.answer_callback_query(call.id, f"❌ Мин: {MIN_WITHDRAW}₽", show_alert=True); return
    msg = bot.send_message(uid, f"💸 Сумма (мин {MIN_WITHDRAW}₽):")
    bot.register_next_step_handler(msg, lambda m: process_withdraw(m, b))

def process_withdraw(message, bal):
    uid = message.from_user.id
    try: a = float(message.text.strip())
    except: bot.send_message(uid, "❌ Число!"); return
    if a < MIN_WITHDRAW: bot.send_message(uid, f"❌ Мин: {MIN_WITHDRAW}₽"); return
    if a > bal: bot.send_message(uid, f"❌ Баланс: {bal}₽"); return
    msg = bot.send_message(uid, "💳 Номер карты (16 цифр):")
    bot.register_next_step_handler(msg, lambda m: finish_withdraw(m, a))

def finish_withdraw(message, a):
    uid = message.from_user.id
    card = message.text.strip().replace(' ', '')
    if not card.isdigit() or len(card) != 16: bot.send_message(uid, "❌ 16 цифр!"); return
    cursor.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (a, uid))
    conn.commit()
    kb = InlineKeyboardMarkup(); kb.add(InlineKeyboardButton("📩 @lexxtoon", url="https://t.me/lexxtoon"))
    bot.send_message(uid, f"✅ {a}₽ на {card[:4]}****{card[-4:]}\n📩 Напиши @lexxtoon", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "👤 ПРОФИЛЬ")
def profile(message):
    uid = message.from_user.id
    cursor.execute('SELECT username, balance, total_earned, referral_code, reg_date FROM users WHERE user_id = ?', (uid,))
    r = cursor.fetchone()
    if not r: bot.send_message(uid, "❌ Напиши /start"); return
    uname, balance, earned, code, reg = r
    cursor.execute('SELECT COUNT(*) FROM referrals WHERE referrer_id = ?', (uid,))
    refs = cursor.fetchone()[0]
    text = (
        f"👤 **ПРОФИЛЬ**\n\n"
        f"📝 @{uname}\n"
        f"💰 Баланс: {balance} ₽\n"
        f"🏆 Заработано: {earned} ₽\n"
        f"👥 Рефералов: {refs}\n"
        f"🔗 Код: `{code}`\n"
        f"📅 Регистрация: {reg[:10]}"
    )
    bot.send_message(uid, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "ℹ️ О БОТЕ")
def about(message):
    text = (
        "ℹ️ **Lexton Shop Bot**\n\n"
        "🛒 **Магазин** — продажа физ аккаунтов Telegram\n"
        "🔍 **Поиск** — @LextonSearchbot\n"
        "🤝 **Рефералы** — 10% от покупок друзей\n\n"
        "💳 Оплата: СБП\n"
        "📩 Контакт: @lexxtoon\n\n"
        "Версия: 1.0"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

# ========== АДМИН КОМАНДЫ ==========
@bot.message_handler(commands=['add'])
def add_balance(message):
    if message.from_user.id != ADMIN_ID: return
    try:
        parts = message.text.split()
        username = parts[1].lstrip('@')
        amount = float(parts[2])
        cursor.execute('SELECT user_id, balance FROM users WHERE username = ?', (username,))
        r = cursor.fetchone()
        if not r: bot.send_message(ADMIN_ID, f"❌ @{username} не найден"); return
        uid, bal = r
        cursor.execute('UPDATE users SET balance = balance + ?, total_earned = total_earned + ? WHERE user_id = ?', (amount, amount, uid))
        conn.commit()
        cursor.execute('INSERT INTO purchase_history (buyer_username, buyer_id, amount, date) VALUES (?, ?, ?, ?)', (username, uid, amount, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        bot.send_message(ADMIN_ID, f"✅ +{amount} ₽ @{username}")
        bot.send_message(uid, f"💰 +{amount} ₽! Баланс: {bal + amount} ₽")
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
        r = cursor.fetchone()
        if not r: bot.send_message(ADMIN_ID, f"❌ @{username} не найден"); return
        uid, bal = r
        if amount > bal: bot.send_message(ADMIN_ID, f"❌ Баланс {bal} ₽"); return
        cursor.execute('UPDATE users SET balance = balance - ?, total_earned = total_earned - ? WHERE user_id = ?', (amount, amount, uid))
        conn.commit()
        bot.send_message(ADMIN_ID, f"✅ -{amount} ₽ @{username}")
        bot.send_message(uid, f"⚠️ -{amount} ₽. Баланс: {bal - amount} ₽")
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
        r = cursor.fetchone()
        if not r: bot.send_message(ADMIN_ID, f"❌ @{username} не найден"); return
        uid = r[0]
        ban_until = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute('UPDATE users SET banned_until = ? WHERE user_id = ?', (ban_until, uid))
        conn.commit()
        bot.send_message(ADMIN_ID, f"✅ @{username} забанен на {days} дн.")
        bot.send_message(uid, f"❌ Забанен на {days} дн.")
        log_action(ADMIN_ID, "admin", "ban", f"@{username} {days}дн")
    except: bot.send_message(ADMIN_ID, "❌ /ban @username дни")

@bot.message_handler(commands=['unban'])
def unban_user(message):
    if message.from_user.id != ADMIN_ID: return
    try:
        parts = message.text.split()
        username = parts[1].lstrip('@')
        cursor.execute('SELECT user_id FROM users WHERE username = ?', (username,))
        r = cursor.fetchone()
        if not r: bot.send_message(ADMIN_ID, f"❌ @{username} не найден"); return
        cursor.execute('UPDATE users SET banned_until = NULL WHERE user_id = ?', (r[0],))
        conn.commit()
        bot.send_message(ADMIN_ID, f"✅ @{username} разбанен")
        bot.send_message(r[0], "✅ Разбанен!")
        log_action(ADMIN_ID, "admin", "unban", f"@{username}")
    except: bot.send_message(ADMIN_ID, "❌ /unban @username")

@bot.message_handler(commands=['history'])
def shop_history(message):
    if message.from_user.id != ADMIN_ID: return
    cursor.execute('SELECT buyer_username, amount, date FROM purchase_history ORDER BY id DESC LIMIT 20')
    purchases = cursor.fetchall()
    if not purchases: bot.send_message(ADMIN_ID, "📭 Пусто"); return
    text = "📋 **Последние 20:**\n\n"
    for buyer, amount, date in purchases:
        text += f"👤 {buyer} | {amount} ₽ | {date}\n"
    bot.send_message(ADMIN_ID, text, parse_mode="Markdown")

@bot.message_handler(commands=['stats'])
def admin_stats(message):
    if message.from_user.id != ADMIN_ID: return
    cursor.execute('SELECT COUNT(*), SUM(balance), SUM(total_earned) FROM users')
    u, b, e = cursor.fetchone()
    cursor.execute('SELECT COUNT(*) FROM referrals')
    r = cursor.fetchone()[0]
    text = f"📊 **Статистика:**\n\n👥 Пользователей: {u}\n💰 Баланс: {b or 0} ₽\n🏆 Выплачено: {e or 0} ₽\n🤝 Рефералов: {r}"
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
        uid, uname, bal, earned, code, invited, reg, ban = r
        ban_text = f"до {ban}" if ban else "нет"
        text = f"👤 **@{uname}**\n🆔 {uid}\n💰 {bal} ₽\n🏆 {earned} ₽\n🔗 {code}\n👥 Приглашён: {invited or 'нет'}\n🚫 Бан: {ban_text}\n📅 {reg}"
        bot.send_message(ADMIN_ID, text, parse_mode="Markdown")
    except: bot.send_message(ADMIN_ID, "❌ /userinfo @username")

@bot.message_handler(commands=['people'])
def people_log(message):
    if message.from_user.id != ADMIN_ID: return
    cursor.execute('SELECT user_id, username, action, details, date FROM user_logs ORDER BY id DESC LIMIT 50')
    logs = cursor.fetchall()
    if not logs: bot.send_message(ADMIN_ID, "📭 Пусто"); return
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

print("✅ Бот Lexton Shop запущен!")
if __name__ == '__main__':
    bot.infinity_polling()