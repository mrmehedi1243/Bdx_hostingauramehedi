import asyncio
import aiohttp
import json
import sqlite3
import time
import logging
import traceback
from datetime import datetime
from typing import Dict, List, Tuple

# Telegram imports placed correctly at the top scope
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Setup logging to see crashes clearly in terminal
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============== CONFIGURATION ==============
BOT_TOKEN = "8748505955:AAFwJE0gxsONHd-ck9tkB7TTsUQtSeBZMWE"
OWNER_ID = 8462313909  # Your Telegram ID

# TWO ADMIN IDs (Add your two admin IDs inside this list)
ADMIN_IDS = [5548613238, 87654321]  

# API URLs
LIKE_API_URL = "https://like-api-ts7p.vercel.app/like?uid={uid}&server_name={region}&key=JMLB"
INFO_API_URL = "http://api.ffbd.store/info?uid={uid}"
BANNER_API_URL = "https://mehedi-x-banner.vercel.app/profile?uid={uid}"

# Image URLs
LIKE_SENT_IMAGE = "https://www.image2url.com/r2/default/images/1783159970376-1959a282-fa3f-4fa0-a943-259b4f408742.png"
LIKE_MAX_IMAGE = "https://www.image2url.com/r2/default/images/1783174094093-207ecedd-9293-4c3b-81fd-1508c422a011.png"

# ============== DATABASE SETUP ==============
class Database:
    def __init__(self, db_file="bot_data.db"):
        self.conn = sqlite3.connect(db_file, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self._create_tables()
        
    def _create_tables(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                is_vip INTEGER DEFAULT 0,
                vip_expiry INTEGER DEFAULT 0,
                joined_date INTEGER DEFAULT 0,
                total_likes INTEGER DEFAULT 0,
                total_info INTEGER DEFAULT 0,
                daily_likes_used INTEGER DEFAULT 0,
                daily_info_used INTEGER DEFAULT 0,
                daily_spam_used INTEGER DEFAULT 0,
                daily_visit_used INTEGER DEFAULT 0,
                last_reset_date INTEGER DEFAULT 0
            )
        """)
        
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY,
                added_by INTEGER,
                added_date INTEGER
            )
        """)
        
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS allowed_groups (
                group_id INTEGER PRIMARY KEY,
                added_by INTEGER,
                added_date INTEGER
            )
        """)
        
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS auto_likes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                region TEXT,
                uid TEXT,
                days INTEGER,
                added_by INTEGER,
                added_date INTEGER,
                total_sent INTEGER DEFAULT 0,
                last_sent INTEGER DEFAULT 0,
                remaining_days INTEGER
            )
        """)
        
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_limits (
                user_type TEXT,
                action_type TEXT,
                limit_value INTEGER,
                PRIMARY KEY (user_type, action_type)
            )
        """)
        
        default_limits = [
            ('free', 'like', 10),
            ('free', 'spam', 5),
            ('free', 'info', 10),
            ('free', 'visit', 5),
            ('vip', 'like', 50),
            ('vip', 'spam', 20),
            ('vip', 'info', 50),
            ('vip', 'visit', 20),
        ]
        
        for user_type, action_type, limit_value in default_limits:
            self.cursor.execute("""
                INSERT OR IGNORE INTO daily_limits (user_type, action_type, limit_value)
                VALUES (?, ?, ?)
            """, (user_type, action_type, limit_value))
        
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS bot_config (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        self.cursor.execute("INSERT OR IGNORE INTO bot_config (key, value) VALUES (?, ?)", ('bot_status', 'on'))
        self.cursor.execute("INSERT OR IGNORE INTO bot_config (key, value) VALUES (?, ?)", ('stats', '{"total_commands": 0, "total_likes": 0, "total_info": 0}'))
        
        self.conn.commit()
    
    def get_bot_status(self) -> bool:
        self.cursor.execute("SELECT value FROM bot_config WHERE key = ?", ('bot_status',))
        result = self.cursor.fetchone()
        return result['value'] == 'on' if result else True
    
    def set_bot_status(self, status: bool):
        self.cursor.execute("UPDATE bot_config SET value = ? WHERE key = ?", ('on' if status else 'off', 'bot_status'))
        self.conn.commit()
    
    def get_stats(self) -> Dict:
        self.cursor.execute("SELECT value FROM bot_config WHERE key = ?", ('stats',))
        result = self.cursor.fetchone()
        if result:
            return json.loads(result['value'])
        return {"total_commands": 0, "total_likes": 0, "total_info": 0}
    
    def update_stats(self, command_type: str):
        stats = self.get_stats()
        stats['total_commands'] = stats.get('total_commands', 0) + 1
        if command_type == 'like':
            stats['total_likes'] = stats.get('total_likes', 0) + 1
        elif command_type == 'info':
            stats['total_info'] = stats.get('total_info', 0) + 1
        self.cursor.execute("UPDATE bot_config SET value = ? WHERE key = ?", (json.dumps(stats), 'stats'))
        self.conn.commit()
    
    def is_group_allowed(self, group_id: int) -> bool:
        self.cursor.execute("SELECT 1 FROM allowed_groups WHERE group_id = ?", (group_id,))
        return self.cursor.fetchone() is not None
    
    def add_allowed_group(self, group_id: int, added_by: int):
        self.cursor.execute("INSERT OR IGNORE INTO allowed_groups VALUES (?, ?, ?)", (group_id, added_by, int(time.time())))
        self.conn.commit()
    
    def remove_allowed_group(self, group_id: int):
        self.cursor.execute("DELETE FROM allowed_groups WHERE group_id = ?", (group_id,))
        self.conn.commit()
    
    def get_allowed_groups(self) -> List[int]:
        self.cursor.execute("SELECT group_id FROM allowed_groups")
        return [row['group_id'] for row in self.cursor.fetchall()]
    
    def is_admin(self, user_id: int) -> bool:
        return user_id == OWNER_ID or user_id in ADMIN_IDS or self._is_admin_in_db(user_id)
    
    def _is_admin_in_db(self, user_id: int) -> bool:
        self.cursor.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
        return self.cursor.fetchone() is not None
    
    def add_admin(self, user_id: int, added_by: int):
        global ADMIN_IDS
        self.cursor.execute("INSERT OR IGNORE INTO admins VALUES (?, ?, ?)", (user_id, added_by, int(time.time())))
        self.conn.commit()
        if user_id not in ADMIN_IDS:
            ADMIN_IDS.append(user_id)
    
    def remove_admin(self, user_id: int):
        global ADMIN_IDS
        self.cursor.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
        self.conn.commit()
        if user_id in ADMIN_IDS:
            ADMIN_IDS.remove(user_id)
    
    def get_admins(self) -> List[int]:
        self.cursor.execute("SELECT user_id FROM admins")
        db_admins = [row['user_id'] for row in self.cursor.fetchall()]
        return list(set(ADMIN_IDS + db_admins))
    
    def get_or_create_user(self, user_id: int, username: str = "", first_name: str = ""):
        self.cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = self.cursor.fetchone()
        if not user:
            self.cursor.execute("""
                INSERT INTO users (user_id, username, first_name, joined_date, last_reset_date)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, username, first_name, int(time.time()), int(time.time())))
            self.conn.commit()
            self.cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            user = self.cursor.fetchone()
        else:
            today = int(time.time()) // 86400
            last_reset = user['last_reset_date'] // 86400 if user['last_reset_date'] else 0
            if last_reset < today:
                self.cursor.execute("""
                    UPDATE users SET 
                        daily_likes_used = 0,
                        daily_info_used = 0,
                        daily_spam_used = 0,
                        daily_visit_used = 0,
                        last_reset_date = ?
                    WHERE user_id = ?
                """, (int(time.time()), user_id))
                self.conn.commit()
                self.cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
                user = self.cursor.fetchone()
        return user
    
    def get_user(self, user_id: int):
        self.cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return self.cursor.fetchone()
    
    def is_vip(self, user_id: int) -> bool:
        user = self.get_user(user_id)
        if not user:
            return False
        if user['is_vip'] == 1:
            expiry = user['vip_expiry']
            if expiry == 0 or expiry > int(time.time()):
                return True
            self.cursor.execute("UPDATE users SET is_vip = 0, vip_expiry = 0 WHERE user_id = ?", (user_id,))
            self.conn.commit()
        return False
    
    def add_vip(self, user_id: int, days: int):
        expiry = int(time.time()) + (days * 86400)
        self.cursor.execute("""
            UPDATE users SET is_vip = 1, vip_expiry = ? WHERE user_id = ?
        """, (expiry, user_id))
        self.conn.commit()
    
    def remove_vip(self, user_id: int):
        self.cursor.execute("UPDATE users SET is_vip = 0, vip_expiry = 0 WHERE user_id = ?", (user_id,))
        self.conn.commit()
    
    def get_vip_list(self) -> List[sqlite3.Row]:
        self.cursor.execute("SELECT user_id, username, first_name, vip_expiry FROM users WHERE is_vip = 1 AND vip_expiry > ?", (int(time.time()),))
        return self.cursor.fetchall()
    
    def get_daily_limit(self, user_type: str, action: str) -> int:
        self.cursor.execute("SELECT limit_value FROM daily_limits WHERE user_type = ? AND action_type = ?", (user_type, action))
        result = self.cursor.fetchone()
        return result['limit_value'] if result else 0
    
    def set_daily_limit(self, user_type: str, action: str, limit_value: int):
        self.cursor.execute("""
            INSERT OR REPLACE INTO daily_limits (user_type, action_type, limit_value)
            VALUES (?, ?, ?)
        """, (user_type, action, limit_value))
        self.conn.commit()
    
    def increment_usage(self, user_id: int, action: str):
        field_map = {
            'like': 'daily_likes_used',
            'info': 'daily_info_used',
            'spam': 'daily_spam_used',
            'visit': 'daily_visit_used'
        }
        field = field_map.get(action)
        if field:
            self.cursor.execute(f"UPDATE users SET {field} = {field} + 1 WHERE user_id = ?", (user_id,))
            self.conn.commit()
    
    def get_usage(self, user_id: int, action: str) -> int:
        field_map = {
            'like': 'daily_likes_used',
            'info': 'daily_info_used',
            'spam': 'daily_spam_used',
            'visit': 'daily_visit_used'
        }
        field = field_map.get(action)
        if field:
            self.cursor.execute(f"SELECT {field} FROM users WHERE user_id = ?", (user_id,))
            result = self.cursor.fetchone()
            return result[field] if result else 0
        return 0
    
    def check_and_increment_usage(self, user_id: int, action: str) -> bool:
        user_type = 'vip' if self.is_vip(user_id) else 'free'
        limit = self.get_daily_limit(user_type, action)
        
        if limit == 0:
            self.increment_usage(user_id, action)
            return True
        
        used = self.get_usage(user_id, action)
        if used >= limit:
            return False
        
        self.increment_usage(user_id, action)
        return True
    
    def add_auto_like(self, region: str, uid: str, days: int, added_by: int):
        self.cursor.execute("""
            INSERT INTO auto_likes (region, uid, days, added_by, added_date, remaining_days)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (region, uid, days, added_by, int(time.time()), days))
        self.conn.commit()
        return self.cursor.lastrowid
    
    def remove_auto_like(self, region: str, uid: str):
        self.cursor.execute("DELETE FROM auto_likes WHERE region = ? AND uid = ?", (region, uid))
        self.conn.commit()
    
    def get_auto_likes(self) -> List[sqlite3.Row]:
        self.cursor.execute("SELECT id, region, uid, days, added_by, added_date, total_sent, last_sent, remaining_days FROM auto_likes")
        return self.cursor.fetchall()
    
    def get_auto_like(self, region: str, uid: str):
        self.cursor.execute("SELECT id, region, uid, days, added_by, added_date, total_sent, last_sent, remaining_days FROM auto_likes WHERE region = ? AND uid = ?", (region, uid))
        return self.cursor.fetchone()
    
    def update_auto_like_sent(self, auto_id: int):
        self.cursor.execute("""
            UPDATE auto_likes SET 
                total_sent = total_sent + 1,
                last_sent = ?,
                remaining_days = remaining_days - 1
            WHERE id = ?
        """, (int(time.time()), auto_id))
        self.conn.commit()
    
    def delete_expired_auto_likes(self):
        self.cursor.execute("DELETE FROM auto_likes WHERE remaining_days <= 0")
        self.conn.commit()
    
    def close(self):
        self.conn.close()

# ============== BOT HANDLERS ==============
db = Database()

async def is_bot_on(update: Update) -> bool:
    if not db.get_bot_status():
        await update.message.reply_text("❌ Bot is currently OFF. Please contact admins.")
        return False
    return True

async def is_group_allowed(update: Update) -> bool:
    if update.message.chat.type in ['group', 'supergroup']:
        if not db.is_group_allowed(update.message.chat_id):
            await update.message.reply_text("❌ This group is not allowed. Please contact admins.")
            return False
    return True

async def is_admin(user_id: int) -> bool:
    return db.is_admin(user_id)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.get_or_create_user(user.id, user.username or "", user.first_name or "")
    
    text = f"""👋 𝐖𝐞𝐥𝐜𝐨𝐦𝐞 𝐭𝐨 𝐅𝐫𝐞𝐞 𝐅𝐢𝐫𝐞 𝐏𝐫𝐞𝐦𝐢𝐮𝐦 𝐁𝐨𝐭!

🌟 𝐅𝐞𝐚𝐭𝐮𝐫𝐞𝐬:
• 𝐅𝐫𝐞𝐞 𝐋𝐢𝐤𝐞𝐬 (𝐌𝐚𝐧𝐮𝐚𝐥 & 𝐀𝐮𝐭𝐨)
• 𝐏𝐫𝐨𝐟𝐢𝐥𝐞 𝐕𝐢𝐬𝐢𝐭𝐬
• 𝐅𝐫𝐢𝐞𝐧𝐝 𝐑𝐞𝐪𝐮𝐞𝐬𝐭𝐬 (𝐒𝐩𝐚𝐦)
• 𝐃𝐞𝐭𝐚𝐢𝐥𝐞𝐝 𝐏𝐥𝐚𝐲𝐞𝐫 𝐈𝐧𝐟𝐨

📌 𝐇𝐨𝐰 𝐭𝐨 𝐔𝐬𝐞:
𝟏. 𝐉𝐨𝐢𝐧 𝐚𝐥𝐥 𝐫𝐞𝐪𝐮𝐢𝐫𝐞𝐝 𝐜𝐡𝐚𝐧𝐧𝐞𝐥𝐬
𝟐. 𝐔𝐬𝐞 /like 𝐨𝐫 /get 𝐜𝐨𝐦𝐦𝐚𝐧𝐝𝐬
𝟑. 𝐂𝐨𝐦𝐩𝐥𝐞𝐭𝐞 𝐝𝐚𝐢𝐥𝐲 𝐯𝐞𝐫𝐢𝐟𝐢𝐜𝐚𝐭𝐢𝐨𝐧
𝟒. 𝐄𝐧𝐣𝐨𝐲 𝐭𝐡𝐞 𝐬𝐞𝐫𝐯𝐢𝐜𝐞!

📊 𝐂𝐡𝐞𝐜𝐤 𝐲𝐨𝐮𝐫 𝐥𝐢𝐦𝐢𝐭𝐬 𝐰𝐢𝐭𝐡 /check
❓ 𝐍𝐞𝐞𝐝 𝐡𝐞𝐥𝐩? 𝐔𝐬𝐞 /help"""
    await update.message.reply_text(text)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """📘 HELP MENU - ALL COMMANDS

👤 USER COMMANDS:
/like {region} {uid} - Send free likes
/get {uid} - Get player info (no likes)
/check - Check your daily limits
/start - Start the bot
/help - Show this help menu

🔄 AUTO LIKE (Admin Only):
/auto {region} {uid} {days} - Add to autolike
/removeauto {region} {uid} - Remove from autolike
/autolist - List all auto likes

🔧 BOT MANAGEMENT (Admin Only):
/on - Turn bot ON
/off - Turn bot OFF
/allow {group_id} - Allow a group
/remove {group_id} - Remove allowed group
/broadcast - Broadcast message
/stats - Bot statistics
/show - Show admins & VIPs
/setlimit {free/vip} {like/spam/info/visit} {limit} - Set daily limit (0=unlimited)

👑 VIP MANAGEMENT (Admin/Owner):
/vip {user_id} {days} - Grant VIP
/removevip {user_id} - Remove VIP
/viplist - List VIP users

👥 USER MANAGEMENT:
/addadmin {user_id} - Add admin (Owner only)
/removeadmin {user_id} - Remove admin (Owner only)
/adminlist - List all admins

💡 Server Codes:
ID - Indonesia, RU - Russia, IN - India, US - America, BR - Brazil"""
    await update.message.reply_text(text)

async def like_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_bot_on(update) or not await is_group_allowed(update):
        return
    
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("⚠️ Correct format: /like {region} {uid}\n\nExample: /like ID 123456789")
        return
    
    region, uid = args[0].upper(), args[1]
    if not uid.isdigit():
        await update.message.reply_text("⚠️ UID must be numbers only!")
        return
    
    user_id = update.effective_user.id
    if not db.check_and_increment_usage(user_id, 'like'):
        user_type = 'VIP' if db.is_vip(user_id) else 'Free'
        limit = db.get_daily_limit('vip' if db.is_vip(user_id) else 'free', 'like')
        await update.message.reply_text(f"⚠️ Daily like limit reached!\n\nUser Type: {user_type}\nDaily Limit: {limit}\nToday's usage completed.\nTry again tomorrow.")
        return
    
    db.update_stats('like')
    wait_msg = await update.message.reply_text(f"⏳ Sending likes...\n\n🎯 UID: {uid}\n🌍 Server: {region}\n⏱️ Please wait...")
    
    try:
        async with aiohttp.ClientSession() as session:
            url = LIKE_API_URL.format(uid=uid, region=region)
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    nickname = data.get('PlayerNickname', 'Unknown')
                    likes_before = data.get('LikesbeforeCommand', 0)
                    likes_after = data.get('LikesafterCommand', 0)
                    likes_given = data.get('LikesGivenByAPI', 0)
                    remains = data.get('remains', '(0/0)')
                    
                    likes_added = likes_given > 0 or (likes_after > likes_before)
                    sender = update.effective_user
                    sender_name = f"@{sender.username}" if sender.username else sender.first_name
                    
                    await wait_msg.delete()
                    if likes_added:
                        image_url = LIKE_SENT_IMAGE
                        result_text = f"🚀 𝐔𝐈𝐃 𝐕𝐚𝐥𝐢𝐝𝐚𝐭𝐞𝐝 - 𝐀𝐏𝐈 𝐜𝐨𝐧𝐧𝐞𝐜𝐭𝐞𝐝\n\n🆔 | 𝐔𝐈𝐃: {uid}\n👤 | 𝐍𝐚𝐦𝐞: {nickname}\n🌍 | 𝐑𝐞𝐠𝐢𝐨𝐧: {region}\n\n🐥 | 𝐋𝐢𝐤𝐞𝐬 𝐁𝐞𝐟𝐨𝐫𝐞: {likes_before}\n🐲 | 𝐋𝐢𝐤𝐞𝐬 𝐀𝐟𝐭𝐞𝐫: {likes_after}\n🐉 | 𝐋𝐢𝐤𝐞𝐬 𝐆𝐢𝐯𝐞𝐧: +{likes_given if likes_given > 0 else likes_after - likes_before}\n\n👤 | 𝐒𝐞𝐧𝐭 𝐁𝐲: {sender_name}\n📋 | 𝐑e𝐦𝐚𝐢𝐧𝐬: {remains}"
                    else:
                        image_url = LIKE_MAX_IMAGE
                        result_text = f"⚠️ 𝐔𝐈𝐃 𝐕𝐚𝐥𝐢𝐝𝐚𝐭𝐞𝐝 - 𝐀𝐏𝐈 𝐜𝐨𝐧𝐧𝐞𝐜𝐭𝐞𝐝\n\n🆔 | 𝐔𝐈𝐃: {uid}\n👤 | 𝐍𝐚𝐦𝐞: {nickname}\n🌍 | 𝐑𝐞𝐠𝐢𝐨𝐧: {region}\n\n❌ | 𝐍𝐨 𝐥𝐢𝐤𝐞𝐬 𝐚𝐝𝐝𝐞𝐝!\n🐥 | 𝐋𝐢𝐤𝐞𝐬 𝐁𝐞𝐟𝐨𝐫𝐞: {likes_before}\n🐲 | 𝐋𝐢𝐤𝐞𝐬 𝐀𝐟𝐭𝐞𝐫: {likes_after}\n\n⚠️ | 𝐌𝐚𝐱 𝐥𝐢𝐦𝐢𝐭 𝐫𝐞𝐚𝐜𝐡𝐞𝐝!\n📋 | 𝐑e𝐦𝐚𝐢𝐧𝐬: {remains}"
                    
                    await update.message.reply_photo(photo=image_url, caption=result_text)
                else:
                    await wait_msg.delete()
                    await update.message.reply_text(f"❌ Error!\n\nLike API error.\nStatus Code: {response.status}")
    except Exception as e:
        await wait_msg.delete()
        await update.message.reply_text(f"❌ Error!\n\n{str(e)}")

# Formats UNIX timestamps cleanly into the format requested
def format_time(timestamp_str) -> str:
    try:
        if not timestamp_str or str(timestamp_str).lower() == "none":
            return "N/A"
        ts = int(timestamp_str)
        return datetime.fromtimestamp(ts).strftime('%d %b %Y at %H:%M:%S')
    except:
        return "N/A"

async def get_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_bot_on(update) or not await is_group_allowed(update):
        return
    
    args = context.args
    if len(args) < 1:
        await update.message.reply_text("⚠️ Correct format: /get {uid}\n\nExample: /get 123456789")
        return
    
    uid = args[0]
    if not uid.isdigit():
        await update.message.reply_text("⚠️ UID must be numbers only!")
        return
    
    user_id = update.effective_user.id
    if not db.check_and_increment_usage(user_id, 'info'):
        user_type = 'VIP' if db.is_vip(user_id) else 'Free'
        limit = db.get_daily_limit('vip' if db.is_vip(user_id) else 'free', 'info')
        await update.message.reply_text(f"⚠️ Daily info limit reached!\n\nUser Type: {user_type}\nDaily Limit: {limit}")
        return
    
    db.update_stats('info')
    wait_msg = await update.message.reply_text(f"⏳ Fetching player info...\n🆔 UID: {uid}")
    
    try:
        async with aiohttp.ClientSession() as session:
            url = INFO_API_URL.format(uid=uid)
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Extracting nodes with safe defaults (.get)
                    basic = data.get('basicInfo', {})
                    social = data.get('socialInfo', {})
                    clan = data.get('clanInfo', {})
                    pet = data.get('petInfo', {})
                    captain = clan.get('clanCaptain', {}) if clan else {}
                    
                    # Account Overview
                    nickname = basic.get('nickname', 'Unknown')
                    region = basic.get('region', 'N/A')
                    level = basic.get('level', 'N/A')
                    exp = basic.get('exp', 'N/A')
                    liked = basic.get('liked', 'N/A')
                    title_id = basic.get('title', 'None')
                    signature = social.get('signature', 'None')
                    
                    # Activity Info
                    created_at = format_time(basic.get('createTime'))
                    last_login = format_time(basic.get('lastLoginTime'))
                    ob_version = basic.get('releaseVersion', 'Unknown')
                    
                    # Rank Info
                    br_rank = basic.get('rank', 'Gold')
                    br_rank_points = basic.get('rankingPoints', '0')
                    cs_rank = basic.get('csRank', 'Gold')
                    cs_rank_points = basic.get('csRankingPoints', '0')
                    br_max_rank = basic.get('maxRank', br_rank_points)
                    cs_max_rank = basic.get('maxCsRank', cs_rank_points)
                    season = basic.get('season', '0')
                    bp_badges = basic.get('badgeCount', '0')
                    bp_id = basic.get('badgeId', title_id)
                    
                    # Avatar & Style
                    avatar_id = basic.get('headPic', 'None')
                    banner_id = basic.get('backgroundPic', 'None')
                    gun_skin = basic.get('weaponPic', 'None')
                    outfits = basic.get('clothesCount', '0')
                    skills = basic.get('skillSetCount', 'None')
                    
                    # Credit Info
                    credit_score = basic.get('creditScore', '100')
                    period_end = format_time(basic.get('creditPeriodEnd'))
                    reward_state = basic.get('creditRewardState', 'REWARD_STATE_UNCLAIMED')
                    
                    # Pet Info
                    has_pet = "✅ Yes" if pet else "❌ No"
                    pet_id = pet.get('petId', 'None') if pet else 'None'
                    pet_exp = pet.get('petExp', 'N/A') if pet else 'N/A'
                    pet_level = pet.get('petLevel', 'N/A') if pet else 'N/A'
                    pet_skill = pet.get('petSkillId', 'N/A') if pet else 'N/A'
                    
                    # Guild Info
                    guild_name = clan.get('clanName', 'None') if clan else 'None'
                    guild_id = clan.get('clanId', 'None') if clan else 'None'
                    guild_level = clan.get('clanLevel', 'N/A') if clan else 'N/A'
                    guild_members = f"{clan.get('memberCount', '0')}/{clan.get('maxMemberCount', '20')}" if clan else '0/20'
                    
                    # Guild Leader
                    leader_name = captain.get('nickname', nickname)
                    leader_uid = captain.get('uid', uid)
                    leader_level = captain.get('level', level)
                    leader_exp = captain.get('exp', exp)
                    leader_likes = captain.get('liked', liked)
                    leader_created = format_time(captain.get('createTime')).split(' at ')[0] if captain.get('createTime') else created_at.split(' at ')[0]
                    leader_login = format_time(captain.get('lastLoginTime')).split(' at ')[0] if captain.get('lastLoginTime') else last_login.split(' at ')[0]
                    leader_badges = captain.get('badgeId', bp_id)
                    leader_br = f"{captain.get('rank', 'Gold')} ({captain.get('rankingPoints', '0')})"
                    leader_cs = f"{captain.get('csRank', 'Gold')} ({captain.get('csRankingPoints', '0')})"

                    # Constructing the Custom Aesthetic Layout
                    text = f"""🎮 𝐀𝐜𝐜𝐨𝐮𝐧𝐭 𝐎𝐯𝐞𝐫𝐯𝐢𝐞𝐰 ───────────────────────
🔹 𝐍𝐢𝐜𝐤𝐧𝐚𝐦𝐞      : {nickname}
🆔 𝐔𝐈𝐃           : {uid}
🌍 𝐑𝐞𝐠𝐢𝐨𝐧        : {region}
📈 𝐋𝐞𝐯𝐞𝐥         : {level} (𝐄𝐱𝐩: {exp})
❤️ 𝐋𝐢𝐤𝐞𝐬         : {liked}
🏷️ 𝐓𝐢𝐭𝐥𝐞 𝐈𝐃      : {title_id}
✍️ 𝐒𝐢𝐠𝐧𝐚𝐭𝐮𝐫𝐞     : {signature}

🕒 𝐀𝐜𝐭𝐢𝐯𝐢𝐭𝐲 𝐈𝐧𝐟𝐨 ──────────────────────────
📅 𝐂𝐫𝐞𝐚𝐭𝐞𝐝 𝐎𝐧     : {created_at}
♻️ 𝐋𝐚𝐬𝐭 𝐋𝐨𝐠𝐢𝐧     : {last_login}
🧾 𝐎𝐁 𝐕𝐞𝐫𝐬𝐢𝐨𝐧     : {ob_version}

🏅 𝐑𝐚𝐧𝐤 𝐈𝐧𝐟𝐨𝐫𝐦𝐚𝐭𝐢𝐨𝐧 ───────────────────────
🏹 𝐁𝐑 𝐑𝐚𝐧𝐤        : {br_rank} ({br_rank_points})
🔫 𝐂𝐒 𝐑𝐚𝐧𝐤        : {cs_rank} ({cs_rank_points})
🎯 𝐁𝐑 𝐌𝐚𝐱 𝐑𝐚𝐧𝐤    : {br_max_rank}
🎯 𝐂𝐒 𝐌𝐚𝐱 𝐑𝐚𝐧𝐤    : {cs_max_rank}
🔁 𝐒𝐞𝐚𝐬𝐨𝐧         : {season}
🎖️ 𝐁𝐏 𝐁𝐚𝐝𝐠𝐞𝐬      : {bp_badges}x
🔥 𝐁𝐏 𝐈𝐃          : {bp_id}

🎨 𝐀𝐯𝐚𝐭𝐚𝐫 & 𝐒𝐭𝐲𝐥𝐞 ────────────────────────
🖼️ 𝐀𝐯𝐚𝐭𝐚𝐫 𝐈𝐃      : {avatar_id}
🪧 𝐁𝐚𝐧𝐧𝐞𝐫 𝐈𝐃      : {banner_id}
🔫 𝐆𝐮𝐧 𝐒𝐤𝐢𝐧       : {gun_skin}
👕 𝐎𝐮𝐭𝐟𝐢𝐭𝐬        : {outfits}
⚡ 𝐒𝐤𝐢𝐥𝐥𝐬         : {skills} sets equipped

💎 𝐂𝐫𝐞𝐝𝐢𝐭 𝐈𝐧𝐟𝐨 ───────────────────────────
💠 𝐂𝐫𝐞𝐝𝐢𝐭 𝐒𝐜𝐨𝐫𝐞   : {credit_score}
⏱️ 𝐏𝐞𝐫𝐢𝐨𝐝 𝐄𝐧𝐝     : {period_end}
🎁 𝐑𝐞𝐰𝐚𝐫𝐝 𝐒𝐭𝐚𝐭𝐞   : {reward_state}

🐾 𝐏𝐞𝐭 𝐈𝐧𝐟𝐨 ──────────────────────────────
🐶 𝐄𝐪𝐮𝐢𝐩𝐩𝐞𝐝       : {has_pet}
🆔 𝐏𝐞𝐭 𝐈𝐃         : {pet_id}
📊 𝐏𝐞𝐭 𝐄𝐱𝐩        : {pet_exp}
📈 𝐏𝐞𝐭 𝐋𝐞𝐯𝐞𝐥      : {pet_level}
🎯 𝐏𝐞𝐭 𝐒𝐤𝐢𝐥𝐥      : {pet_skill}

🏰 𝐆𝐮𝐢𝐥𝐝 𝐈𝐧𝐟𝐨 ─────────────────────────────
🏷️ 𝐆𝐮𝐢𝐥𝐝 𝐍𝐚𝐦𝐞     : {guild_name}
🆔 𝐆𝐮𝐢𝐥𝐝 𝐈𝐃       : {guild_id}
📶 𝐆𝐮𝐢𝐥𝐝 𝐋𝐞𝐯𝐞𝐥    : {guild_level}
👥 𝐌ेंबर𝐬        : {guild_members}

👑 𝐆𝐮𝐢𝐥𝐝 𝐋𝐞𝐚𝐝𝐞𝐫 ──────────────────────────
👤 𝐋𝐞𝐚𝐝𝐞𝐫 𝐍𝐚𝐦𝐞    : {leader_name}
🆔 𝐋𝐞𝐚𝐝𝐞𝐫 𝐔𝐈𝐃     : {leader_uid}
📈 𝐋𝐞𝐚𝐝𝐞𝐫 𝐋𝐞𝐯𝐞𝐥   : {leader_level} (𝐄𝐱𝐩: {leader_exp})
❤️ 𝐋𝐞𝐚𝐝𝐞𝐫 𝐋𝐢𝐤𝐞𝐬   : {leader_likes}
📅 𝐂𝐫𝐞𝐚𝐭𝐞𝐝 𝐀𝐭     : {leader_created}
♻️ 𝐋𝐚𝐬𝐭 𝐋𝐨𝐠𝐢𝐧     : {leader_login}
🎖️ 𝐋𝐞𝐚𝐝𝐞𝐫 𝐁𝐚𝐝𝐠𝐞𝐬  : {leader_badges}
🏹 𝐋𝐞𝐚𝐝𝐞𝐫 𝐁𝐑      : {leader_br}
🔫 𝐋𝐞𝐚𝐝𝐞𝐫 𝐂𝐒      : {leader_cs}"""

                    await wait_msg.delete()
                    await update.message.reply_text(text)
                    
                    # Sending the banner image safely
                    banner_url = BANNER_API_URL.format(uid=uid)
                    try:
                        await update.message.reply_photo(photo=banner_url, caption=f"🖼️ Profile Banner for {nickname}")
                    except Exception as img_err:
                        logger.error(f"Failed to send banner: {img_err}")
                else:
                    await wait_msg.delete()
                    await update.message.reply_text(f"❌ Error!\n\nPlayer info API error.")
    except Exception as e:
        await wait_msg.delete()
        traceback.print_exc()
        await update.message.reply_text(f"❌ Error while formatting layout!\n\n{str(e)}")

async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    db.get_or_create_user(user_id)
    
    is_vip = db.is_vip(user_id)
    user_type = 'VIP' if is_vip else 'Free'
    
    like_limit = db.get_daily_limit('vip' if is_vip else 'free', 'like')
    info_limit = db.get_daily_limit('vip' if is_vip else 'free', 'info')
    like_used = db.get_usage(user_id, 'like')
    info_used = db.get_usage(user_id, 'info')
    
    text = f"📊 𝐘𝐨𝐮𝐫 𝐃𝐚𝐢𝐥𝐲 𝐔𝐬𝐚𝐠𝐞\n\n👤 𝐔𝐬𝐞𝐫 𝐓𝐲𝐩𝐞: {user_type}\n❤️ 𝐋𝐢𝐤𝐞𝐬: {like_used}/{like_limit if like_limit > 0 else '∞'}\n📋 𝐈𝐧𝐟𝐨: {info_used}/{info_limit if info_limit > 0 else '∞'}"
    if is_vip:
        user = db.get_user(user_id)
        if user and user['vip_expiry'] > 0:
            days_left = (user['vip_expiry'] - int(time.time())) // 86400
            text += f"\n⏰ 𝐕𝐈𝐏 𝐄𝐱𝐩𝐢𝐫𝐲: {days_left} days left"
            
    await update.message.reply_text(text)

# ============== ADMIN COMMANDS ==============
async def auto_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ You don't have admin permission!")
        return
    args = context.args
    if len(args) < 3:
        await update.message.reply_text("⚠️ Correct format: /auto {region} {uid} {days}")
        return
    region, uid, days = args[0].upper(), args[1], int(args[2])
    
    if db.get_auto_like(region, uid):
        await update.message.reply_text("⚠️ Auto like already exists for this user!")
        return
        
    db.add_auto_like(region, uid, days, update.effective_user.id)
    await update.message.reply_text(f"✅ Added to auto like!\n🌍 Server: {region}\n🆔 UID: {uid}\n📅 Days: {days}")

async def removeauto_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ You don't have admin permission!")
        return
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("⚠️ Correct format: /removeauto {region} {uid}")
        return
    region, uid = args[0].upper(), args[1]
    db.remove_auto_like(region, uid)
    await update.message.reply_text(f"✅ Removed from auto like!\n🌍 Server: {region}\n🆔 UID: {uid}")

async def autolist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        return
    auto_likes = db.get_auto_likes()
    if not auto_likes:
        await update.message.reply_text("📭 No auto likes found")
        return
    text = "🔄 Auto Like List\n\n"
    for i, row in enumerate(auto_likes, 1):
        text += f"{i}. 🌍 {row['region']} | 🆔 {row['uid']} | 📅 Remaining: {row['remaining_days']} days\n"
    await update.message.reply_text(text)

async def on_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_admin(update.effective_user.id):
        db.set_bot_status(True)
        await update.message.reply_text("✅ Bot turned ON!")

async def off_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_admin(update.effective_user.id):
        db.set_bot_status(False)
        await update.message.reply_text("❌ Bot turned OFF!")

async def allow_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        return
    args = context.args
    if len(args) < 1:
        await update.message.reply_text("⚠️ Correct format: /allow {group_id}")
        return
    db.add_allowed_group(int(args[0]), update.effective_user.id)
    await update.message.reply_text(f"✅ Group allowed: {args[0]}")

async def remove_group_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        return
    args = context.args
    if len(args) < 1:
        return
    db.remove_allowed_group(int(args[0]))
    await update.message.reply_text(f"✅ Group removed: {args[0]}")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        return
    stats = db.get_stats()
    await update.message.reply_text(f"📊 Bot Statistics\n\nTotal Commands: {stats.get('total_commands', 0)}\nTotal Likes: {stats.get('total_likes', 0)}")

async def setlimit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        return
    args = context.args
    if len(args) < 3:
        await update.message.reply_text("⚠️ Format: /setlimit {free/vip} {like/spam/info/visit} {limit}")
        return
    user_type, action, limit = args[0].lower(), args[1].lower(), int(args[2])
    db.set_daily_limit(user_type, action, limit)
    await update.message.reply_text(f"✅ Limit updated for {user_type} {action}: {limit}")

async def vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        return
    args = context.args
    if len(args) < 2:
        return
    target_id, days = int(args[0]), int(args[1])
    db.get_or_create_user(target_id)
    db.add_vip(target_id, days)
    await update.message.reply_text(f"✅ VIP granted to {target_id} for {days} days.")

async def removevip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        return
    args = context.args
    if len(args) < 1:
        return
    db.remove_vip(int(args[0]))
    await update.message.reply_text(f"✅ VIP removed from {args[0]}")

async def viplist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        return
    vips = db.get_vip_list()
    if not vips:
        await update.message.reply_text("📭 No VIP users found")
        return
    text = "👑 VIP User List\n\n"
    for i, row in enumerate(vips, 1):
        text += f"{i}. {row['username'] or row['first_name']} (🆔 {row['user_id']})\n"
    await update.message.reply_text(text)

async def addadmin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    args = context.args
    if len(args) < 1:
        return
    db.add_admin(int(args[0]), update.effective_user.id)
    await update.message.reply_text(f"✅ Admin added: {args[0]}")

async def removeadmin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    args = context.args
    if len(args) < 1:
        return
    db.remove_admin(int(args[0]))
    await update.message.reply_text(f"✅ Admin removed: {args[0]}")

async def adminlist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        return
    admins = db.get_admins()
    text = f"👑 Owner: {OWNER_ID}\n\n🛡️ Admins:\n" + "\n".join(f"• {a}" for a in admins)
    await update.message.reply_text(text)

# ============== ERROR HANDLER ==============
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Exception handled successfully:", exc_info=context.error)
    if update and update.message:
        await update.message.reply_text("❌ An error occurred!\n\nWe are trying to fix it.\nPlease try again.")

# ============== MAIN ==============
def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    # User handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("like", like_command))
    application.add_handler(CommandHandler("get", get_command))
    application.add_handler(CommandHandler("check", check_command))
    
    # Auto like handlers
    application.add_handler(CommandHandler("auto", auto_command))
    application.add_handler(CommandHandler("removeauto", removeauto_command))
    application.add_handler(CommandHandler("autolist", autolist_command))
    
    # Management handlers
    application.add_handler(CommandHandler("on", on_command))
    application.add_handler(CommandHandler("off", off_command))
    application.add_handler(CommandHandler("allow", allow_command))
    application.add_handler(CommandHandler("remove", remove_group_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("setlimit", setlimit_command))
    
    # VIP handlers
    application.add_handler(CommandHandler("vip", vip_command))
    application.add_handler(CommandHandler("removevip", removevip_command))
    application.add_handler(CommandHandler("viplist", viplist_command))
    
    # Owner handlers
    application.add_handler(CommandHandler("addadmin", addadmin_command))
    application.add_handler(CommandHandler("removeadmin", removeadmin_command))
    application.add_handler(CommandHandler("adminlist", adminlist_command))
    
    application.add_error_handler(error_handler)
    
    print("🤖 Bot is starting cleanly...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
