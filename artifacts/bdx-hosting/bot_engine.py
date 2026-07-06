"""
T10-MEHEDI — Telegram bot fleet engine.

The admin panel can register one or more Telegram bots (token + owner admin
telegram-id). Each registered bot runs its own long-polling loop in a
background thread. Regular users who /start a bot get a referral link; once
they've referred 3 people, they can create their own hosting panel account
right from the chat. The bot's owner (matched by telegram user id) gets an
extra "Owner Panel" menu for broadcasting and stats.
"""
import os
import sqlite3
import threading
import time
import uuid
import hashlib
from datetime import datetime, timedelta

import telebot
from telebot import types

DB_PATH = None
DATA_DIR = None

BOT_INSTANCES = {}   # bot_id -> {"bot": TeleBot, "thread": Thread}
REFERRAL_GOAL = 3    # referrals needed per panel-creation unlock


def init(db_path, data_dir):
    global DB_PATH, DATA_DIR
    DB_PATH = db_path
    DATA_DIR = data_dir


def _db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()


def _panel_dir(pid):
    d = os.path.join(DATA_DIR, pid)
    os.makedirs(d, exist_ok=True)
    return d


def _get_or_create_user(bot_id, tg_user, referred_by=None):
    uid = str(tg_user.id)
    with _db() as db:
        row = db.execute(
            "SELECT * FROM tg_bot_users WHERE bot_id=? AND tg_user_id=?", (bot_id, uid)
        ).fetchone()
        if row:
            return dict(row), False
        rb = referred_by if (referred_by and referred_by != uid) else None
        if rb:
            exists = db.execute(
                "SELECT 1 FROM tg_bot_users WHERE bot_id=? AND tg_user_id=?", (bot_id, rb)
            ).fetchone()
            if not exists:
                rb = None
        db.execute(
            """INSERT INTO tg_bot_users (bot_id, tg_user_id, tg_username, referred_by,
                ref_count, panels_created, created_at)
               VALUES (?,?,?,?,0,0,?)""",
            (bot_id, uid, tg_user.username or "", rb, datetime.now().isoformat()),
        )
        if rb:
            db.execute(
                "UPDATE tg_bot_users SET ref_count = ref_count + 1 WHERE bot_id=? AND tg_user_id=?",
                (bot_id, rb),
            )
        db.commit()
        row = db.execute(
            "SELECT * FROM tg_bot_users WHERE bot_id=? AND tg_user_id=?", (bot_id, uid)
        ).fetchone()
        return dict(row), True


def _main_menu(bot_id, tg_user_id, owner_admin_id):
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("🔗 আমার রেফার লিংক", callback_data="ref_link"))
    kb.add(types.InlineKeyboardButton("📊 আমার স্ট্যাটাস", callback_data="my_stats"))
    kb.add(types.InlineKeyboardButton("🛠️ প্যানেল তৈরি করুন", callback_data="create_panel"))
    if str(tg_user_id) == str(owner_admin_id):
        kb.add(types.InlineKeyboardButton("⚙️ Owner Panel", callback_data="owner_panel"))
    return kb


def _back_menu():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("⬅️ মেনুতে ফিরুন", callback_data="back_menu"))
    return kb


def start_bot(bot_id, token, owner_admin_id):
    if bot_id in BOT_INSTANCES:
        return True, "Already running"
    try:
        bot = telebot.TeleBot(token, threaded=True)
        me = bot.get_me()
    except Exception as e:
        return False, f"Invalid token: {e}"

    @bot.message_handler(commands=["start"])
    def _start(message):
        parts = (message.text or "").split(maxsplit=1)
        ref = parts[1].strip() if len(parts) > 1 else None
        user, _ = _get_or_create_user(bot_id, message.from_user, referred_by=ref)
        bot.send_message(
            message.chat.id,
            f"👋 স্বাগতম, <b>{message.from_user.first_name}</b>!\n\n"
            f"🤖 এই বট দিয়ে আপনি ৩ জন বন্ধুকে রেফার করে নিজের হোস্টিং প্যানেল ফ্রি তৈরি করতে পারবেন।\n"
            f"নিচের মেনু থেকে বেছে নিন 👇",
            parse_mode="HTML",
            reply_markup=_main_menu(bot_id, message.from_user.id, owner_admin_id),
        )

    def _render_menu(chat_id, tg_user_id, message_id=None):
        text = "🏠 <b>মূল মেনু</b>\nনিচের অপশন থেকে বেছে নিন 👇"
        kb = _main_menu(bot_id, tg_user_id, owner_admin_id)
        if message_id:
            bot.edit_message_text(text, chat_id, message_id, parse_mode="HTML", reply_markup=kb)
        else:
            bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb)

    @bot.callback_query_handler(func=lambda c: c.data == "back_menu")
    def _cb_back(c):
        _render_menu(c.message.chat.id, c.from_user.id, c.message.message_id)

    @bot.callback_query_handler(func=lambda c: c.data == "ref_link")
    def _cb_reflink(c):
        _get_or_create_user(bot_id, c.from_user)
        link = f"https://t.me/{me.username}?start={c.from_user.id}"
        bot.edit_message_text(
            f"🔗 <b>আপনার রেফার লিংক</b>\n\n<code>{link}</code>\n\n"
            f"এই লিংক বন্ধুদের পাঠান — {REFERRAL_GOAL} জন জয়েন করলে আপনি প্যানেল তৈরি করতে পারবেন!",
            c.message.chat.id, c.message.message_id, parse_mode="HTML", reply_markup=_back_menu(),
        )

    @bot.callback_query_handler(func=lambda c: c.data == "my_stats")
    def _cb_stats(c):
        user, _ = _get_or_create_user(bot_id, c.from_user)
        unlocked = user["ref_count"] // REFERRAL_GOAL - user["panels_created"]
        bot.edit_message_text(
            f"📊 <b>আপনার স্ট্যাটাস</b>\n\n"
            f"👥 মোট রেফার: <b>{user['ref_count']}</b>\n"
            f"🖥️ তৈরি করা প্যানেল: <b>{user['panels_created']}</b>\n"
            f"🔓 এখন তৈরি করা যাবে: <b>{max(0, unlocked)}</b> টি প্যানেল\n\n"
            f"প্রতি {REFERRAL_GOAL} জন রেফারে ১টি ফ্রি প্যানেল পাবেন।",
            c.message.chat.id, c.message.message_id, parse_mode="HTML", reply_markup=_back_menu(),
        )

    @bot.callback_query_handler(func=lambda c: c.data == "create_panel")
    def _cb_create(c):
        user, _ = _get_or_create_user(bot_id, c.from_user)
        unlocked = user["ref_count"] // REFERRAL_GOAL - user["panels_created"]
        if unlocked <= 0:
            need = REFERRAL_GOAL - (user["ref_count"] % REFERRAL_GOAL)
            bot.answer_callback_query(c.id, "❌ এখনো আনলক হয়নি!", show_alert=True)
            bot.edit_message_text(
                f"🔒 <b>প্যানেল তৈরি লক করা আছে</b>\n\n"
                f"আরও <b>{need}</b> জন রেফার করলে আনলক হবে।\n"
                f"'🔗 আমার রেফার লিংক' থেকে লিংক নিন।",
                c.message.chat.id, c.message.message_id, parse_mode="HTML", reply_markup=_back_menu(),
            )
            return
        bot.edit_message_text(
            "🛠️ <b>প্যানেল তৈরি</b>\n\nইউজারনেম লিখে পাঠান (শুধু চ্যাটে টাইপ করুন):",
            c.message.chat.id, c.message.message_id, parse_mode="HTML",
        )
        bot.register_next_step_handler_by_chat_id(c.message.chat.id, _ask_username, c.from_user.id)

    def _ask_username(message, tg_user_id):
        username = (message.text or "").strip()
        if not username:
            bot.send_message(message.chat.id, "❌ খালি রাখা যাবে না। আবার চেষ্টা করুন — ইউজারনেম লিখুন:")
            bot.register_next_step_handler_by_chat_id(message.chat.id, _ask_username, tg_user_id)
            return
        bot.send_message(message.chat.id, "🔑 এখন পাসওয়ার্ড লিখে পাঠান:")
        bot.register_next_step_handler_by_chat_id(message.chat.id, _ask_password, tg_user_id, username)

    def _ask_password(message, tg_user_id, username):
        password = (message.text or "").strip()
        if not password:
            bot.send_message(message.chat.id, "❌ খালি রাখা যাবে না। আবার পাসওয়ার্ড লিখুন:")
            bot.register_next_step_handler_by_chat_id(message.chat.id, _ask_password, tg_user_id, username)
            return
        with _db() as db:
            user_row = db.execute(
                "SELECT * FROM tg_bot_users WHERE bot_id=? AND tg_user_id=?", (bot_id, str(tg_user_id))
            ).fetchone()
        unlocked = (user_row["ref_count"] // REFERRAL_GOAL - user_row["panels_created"]) if user_row else 0
        if unlocked <= 0:
            bot.send_message(message.chat.id, "🔒 আপনার আনলক শেষ হয়ে গেছে — আরও রেফার করুন।")
            return
        pid = uuid.uuid4().hex
        sid = uuid.uuid4().hex[:8]
        exp = (datetime.now() + timedelta(days=15)).isoformat()
        try:
            with _db() as db:
                db.execute(
                    """INSERT INTO panels
                        (id,username,password,server_id,type,ram_limit,disk_limit,start_command,status,expires_at,created_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (pid, username, _hash_pw(password), sid, "python", 512, 1024,
                     "python main.py", "stopped", exp, datetime.now().isoformat()),
                )
                db.execute(
                    "UPDATE tg_bot_users SET panels_created = panels_created + 1 WHERE bot_id=? AND tg_user_id=?",
                    (bot_id, str(tg_user_id)),
                )
                db.commit()
            _panel_dir(pid)
            bot.send_message(
                message.chat.id,
                f"✅ <b>প্যানেল তৈরি হয়ে গেছে!</b>\n\n"
                f"👤 ইউজারনেম: <code>{username}</code>\n"
                f"🔑 পাসওয়ার্ড: <code>{password}</code>\n"
                f"📅 মেয়াদ: ১৫ দিন\n\n"
                f"এখন প্যানেলে লগইন করে বট আপলোড করুন।",
                parse_mode="HTML",
            )
        except sqlite3.IntegrityError:
            bot.send_message(message.chat.id, "❌ এই ইউজারনেম আগে থেকেই আছে — অন্য একটা ইউজারনেম দিয়ে আবার '🛠️ প্যানেল তৈরি করুন' চাপুন।")

    @bot.callback_query_handler(func=lambda c: c.data == "owner_panel")
    def _cb_owner(c):
        if str(c.from_user.id) != str(owner_admin_id):
            bot.answer_callback_query(c.id, "⛔ শুধুমাত্র মালিকের জন্য।", show_alert=True)
            return
        with _db() as db:
            total_users = db.execute("SELECT COUNT(*) n FROM tg_bot_users WHERE bot_id=?", (bot_id,)).fetchone()["n"]
            total_panels = db.execute("SELECT COALESCE(SUM(panels_created),0) n FROM tg_bot_users WHERE bot_id=?", (bot_id,)).fetchone()["n"]
        kb = types.InlineKeyboardMarkup(row_width=1)
        kb.add(types.InlineKeyboardButton("📢 সবাইকে মেসেজ পাঠান", callback_data="broadcast"))
        kb.add(types.InlineKeyboardButton("⬅️ মেনুতে ফিরুন", callback_data="back_menu"))
        bot.edit_message_text(
            f"⚙️ <b>Owner Panel</b>\n\n👥 মোট ইউজার: <b>{total_users}</b>\n🖥️ মোট প্যানেল তৈরি: <b>{total_panels}</b>",
            c.message.chat.id, c.message.message_id, parse_mode="HTML", reply_markup=kb,
        )

    @bot.callback_query_handler(func=lambda c: c.data == "broadcast")
    def _cb_broadcast(c):
        if str(c.from_user.id) != str(owner_admin_id):
            bot.answer_callback_query(c.id, "⛔ শুধুমাত্র মালিকের জন্য।", show_alert=True)
            return
        bot.edit_message_text("📢 যে মেসেজটি সবাইকে পাঠাতে চান তা লিখুন:", c.message.chat.id, c.message.message_id)
        bot.register_next_step_handler_by_chat_id(c.message.chat.id, _do_broadcast)

    def _do_broadcast(message):
        text = message.text or ""
        with _db() as db:
            rows = db.execute("SELECT tg_user_id FROM tg_bot_users WHERE bot_id=?", (bot_id,)).fetchall()
        sent = 0
        for r in rows:
            try:
                bot.send_message(int(r["tg_user_id"]), f"📢 {text}")
                sent += 1
            except Exception:
                pass
        bot.send_message(message.chat.id, f"✅ {sent} জনকে পাঠানো হয়েছে।")

    def _poll():
        with _db() as db:
            db.execute("UPDATE tg_bots SET status='running', bot_username=? WHERE id=?", (me.username, bot_id))
            db.commit()
        while bot_id in BOT_INSTANCES:
            try:
                bot.infinity_polling(skip_pending=True, timeout=30, long_polling_timeout=30)
            except Exception as e:
                print(f"[T10-BOT-{bot_id}] polling error: {e}", flush=True)
                time.sleep(5)
            else:
                break

    t = threading.Thread(target=_poll, daemon=True)
    BOT_INSTANCES[bot_id] = {"bot": bot, "thread": t, "username": me.username}
    t.start()
    return True, me.username


def stop_bot(bot_id):
    inst = BOT_INSTANCES.pop(bot_id, None)
    if inst:
        try:
            inst["bot"].stop_polling()
        except Exception:
            pass
    with _db() as db:
        db.execute("UPDATE tg_bots SET status='stopped' WHERE id=?", (bot_id,))
        db.commit()


def resume_all():
    try:
        with _db() as db:
            rows = db.execute("SELECT * FROM tg_bots WHERE status='running'").fetchall()
        for row in rows:
            start_bot(row["id"], row["token"], row["owner_admin_id"])
    except Exception as e:
        print(f"[T10-BOT] resume_all error: {e}", flush=True)
