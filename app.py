import os
import sqlite3
from datetime import datetime, timedelta
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask
import threading
import time

# ==================== CONFIGURATION ====================
BOT_TOKEN = "7593433447:AAF1XGZI3budBP3LN3NtY1ThVnIkssHbV9I"
ADMIN_ID = 5095867558
CHANNEL_USERNAME = "@PllushNFt"
CHANNEL_URL = "https://t.me/PllushNFt"

# ==================== INITIALIZE ====================
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# ==================== DATABASE ====================
def init_db():
    conn = sqlite3.connect('bot_database.db', check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            join_date TEXT,
            balance REAL DEFAULT 0.0,
            last_bonus_date TEXT,
            referral_code TEXT UNIQUE,
            invited_by INTEGER DEFAULT 0,
            channel_joined INTEGER DEFAULT 0
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            order_code TEXT,
            item_name TEXT,
            amount REAL,
            status TEXT DEFAULT 'pending',
            request_date TEXT,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER,
            referred_id INTEGER,
            date TEXT,
            UNIQUE(referred_id),
            FOREIGN KEY (referrer_id) REFERENCES users (user_id),
            FOREIGN KEY (referred_id) REFERENCES users (user_id)
        )
    ''')
    
    conn.commit()
    return conn

db = init_db()

# ==================== HELPER FUNCTIONS ====================
def get_user(user_id):
    cursor = db.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    if user:
        return {
            'user_id': user[0],
            'username': user[1],
            'first_name': user[2],
            'join_date': user[3],
            'balance': user[4],
            'last_bonus_date': user[5],
            'referral_code': user[6],
            'invited_by': user[7],
            'channel_joined': user[8]
        }
    return None

def check_channel_membership(user_id):
    try:
        chat_member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return chat_member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        print(f"⚠️ Could not check channel membership: {e}")
        return False

def update_channel_status(user_id, status):
    cursor = db.cursor()
    cursor.execute('UPDATE users SET channel_joined = ? WHERE user_id = ?', (status, user_id))
    db.commit()

def check_previous_referral(user_id):
    cursor = db.cursor()
    cursor.execute('SELECT COUNT(*) FROM referrals WHERE referred_id = ?', (user_id,))
    count = cursor.fetchone()[0]
    return count > 0

def create_user(user_id, username, first_name, referral_code=None):
    cursor = db.cursor()
    join_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user_referral_code = f"REF{user_id}"
    
    channel_member = check_channel_membership(user_id)
    
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    existing_user = cursor.fetchone()
    
    if existing_user:
        cursor.execute('''
            UPDATE users 
            SET username = ?, first_name = ?, channel_joined = ?
            WHERE user_id = ?
        ''', (username, first_name, 1 if channel_member else 0, user_id))
        
        if existing_user[7] != 0:
            print(f"⚠️ User {user_id} already has a referrer: {existing_user[7]}")
            db.commit()
            return channel_member
        
        if referral_code and not check_previous_referral(user_id):
            cursor.execute('SELECT user_id FROM users WHERE referral_code = ?', (referral_code,))
            referrer = cursor.fetchone()
            
            if referrer and referrer[0] != user_id:
                cursor.execute('UPDATE users SET invited_by = ? WHERE user_id = ?', (referrer[0], user_id))
                cursor.execute('UPDATE users SET balance = balance + 0.3 WHERE user_id = ?', (referrer[0],))
                
                try:
                    cursor.execute('''
                        INSERT INTO referrals (referrer_id, referred_id, date)
                        VALUES (?, ?, ?)
                    ''', (referrer[0], user_id, join_date))
                    
                    bot.send_message(
                        referrer[0], 
                        f"🎉 *New Referral!*\n\n{first_name} joined using your link.\n+0.3 TON added to your balance!",
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    print(f"❌ Error inserting referral: {e}")
    else:
        cursor.execute('''
            INSERT INTO users 
            (user_id, username, first_name, join_date, referral_code, channel_joined) 
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, username, first_name, join_date, user_referral_code, 1 if channel_member else 0))
        
        if referral_code and not check_previous_referral(user_id):
            cursor.execute('SELECT user_id FROM users WHERE referral_code = ?', (referral_code,))
            referrer = cursor.fetchone()
            
            if referrer and referrer[0] != user_id:
                cursor.execute('UPDATE users SET invited_by = ? WHERE user_id = ?', (referrer[0], user_id))
                cursor.execute('UPDATE users SET balance = balance + 0.3 WHERE user_id = ?', (referrer[0],))
                
                try:
                    cursor.execute('''
                        INSERT INTO referrals (referrer_id, referred_id, date)
                        VALUES (?, ?, ?)
                    ''', (referrer[0], user_id, join_date))
                    
                    bot.send_message(
                        referrer[0], 
                        f"🎉 *New Referral!*\n\n{first_name} joined using your link.\n+0.3 TON added to your balance!",
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    print(f"❌ Error inserting referral: {e}")
    
    db.commit()
    return channel_member

# ==================== KEYBOARDS ====================
def join_channel_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("✅ Join Channel", url=CHANNEL_URL))
    keyboard.add(InlineKeyboardButton("🔍 I've Joined", callback_data="check_membership"))
    return keyboard

def main_menu_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("👤 Profile", callback_data="menu_profile"),
        InlineKeyboardButton("💰 Balance", callback_data="menu_balance"),
        InlineKeyboardButton("🎁 Daily Bonus", callback_data="menu_bonus"),
        InlineKeyboardButton("📤 Withdraw", callback_data="menu_withdraw"),
        InlineKeyboardButton("🔗 Referral", callback_data="menu_referral"),
        InlineKeyboardButton("🆘 Help", callback_data="menu_help")
    )
    return keyboard

def back_to_main_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_main"))
    return keyboard

WITHDRAWAL_ITEMS = [
    {"name": "Vintage Cigar", "price": 20, "order_code": "order_2348"},
    {"name": "Snoop Cigar", "price": 7, "order_code": "order_2349"},
    {"name": "Snoop Dogg", "price": 3, "order_code": "order_2350"},
    {"name": "Evil Eye", "price": 5, "order_code": "order_2351"},
    {"name": "Star Notepad", "price": 2.5, "order_code": "order_2352"},
    {"name": "Jester Hat", "price": 2, "order_code": "order_2353"},
    {"name": "Pet Snake", "price": 2, "order_code": "order_2354"},
    {"name": "Lunar Snake", "price": 1.5, "order_code": "order_2355"}
]

def withdrawal_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)
    for item in WITHDRAWAL_ITEMS:
        keyboard.add(InlineKeyboardButton(
            f"{item['name']} - {item['price']} TON",
            callback_data=f"withdraw_{item['order_code']}"
        ))
    keyboard.add(InlineKeyboardButton("🔙 Back to Main", callback_data="back_to_main"))
    return keyboard

def admin_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("📊 Statistics", callback_data="admin_stats"),
        InlineKeyboardButton("💰 Add to All Users", callback_data="admin_add_all"),
        InlineKeyboardButton("👤 Add to Specific User", callback_data="admin_add_user"),
        InlineKeyboardButton("📢 Broadcast Message", callback_data="admin_broadcast"),
        InlineKeyboardButton("👥 User List", callback_data="admin_user_list"),
        InlineKeyboardButton("🔙 Main Menu", callback_data="back_to_main")
    )
    return keyboard

# ==================== BOT HANDLERS ====================
@bot.message_handler(commands=['start'])
def handle_start(message):
    try:
        user_id = message.from_user.id
        username = message.from_user.username or "NoUsername"
        first_name = message.from_user.first_name or "User"
        
        print(f"🚀 User {user_id} ({first_name}) started the bot")
        
        referral_code = None
        if len(message.text.split()) > 1:
            referral_code = message.text.split()[1]
            print(f"📝 Referral code: {referral_code}")
            
            if check_previous_referral(user_id):
                print(f"⚠️ User {user_id} already has a referral, ignoring new referral code")
                referral_code = None
        
        is_member = create_user(user_id, username, first_name, referral_code)
        
        if is_member:
            welcome_text = f"""
✨ *Welcome to Plush NFT Bot, {first_name}!* ✨

✅ *Channel verification successful!*

Now you can access all features:

🎁 *Daily Bonus* - Claim 0.3 TON every 24h
👥 *Referral Program* - Earn 0.3 TON per referral
💰 *Withdraw* - Exchange TON for exclusive items

*Select an option below:*
            """
            
            bot.send_message(
                user_id,
                welcome_text,
                parse_mode='Markdown',
                reply_markup=main_menu_keyboard()
            )
        else:
            join_text = f"""
👋 *Welcome {first_name}!*

📢 *Mandatory Join*

To access *Plush NFT Bot* features, you must join our official channel first:

{CHANNEL_USERNAME}

*Steps:*
1. Click *'Join Channel'* button below
2. Join the channel
3. Click *'I've Joined'* button

After verification, you'll get access to all features!
            """
            
            bot.send_message(
                user_id,
                join_text,
                parse_mode='Markdown',
                reply_markup=join_channel_keyboard()
            )
            
    except Exception as e:
        print(f"❌ Error in start handler: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "check_membership")
def check_membership_handler(call):
    try:
        user_id = call.from_user.id
        
        if check_channel_membership(user_id):
            update_channel_status(user_id, 1)
            
            user = get_user(user_id)
            first_name = user['first_name'] if user else "User"
            
            welcome_text = f"""
✅ *Channel Verified!*

Welcome *{first_name}* to Plush NFT Bot! 🎉

Now you can access all features:
• Claim daily bonus
• Earn from referrals  
• Withdraw exclusive items

*Select an option below:*
            """
            
            bot.edit_message_text(
                welcome_text,
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown',
                reply_markup=main_menu_keyboard()
            )
        else:
            bot.answer_callback_query(
                call.id,
                "❌ You haven't joined the channel yet! Please join first.",
                show_alert=True
            )
            
    except Exception as e:
        print(f"❌ Error in check_membership: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "back_to_main")
def back_to_main_handler(call):
    try:
        user_id = call.from_user.id
        
        if not check_channel_membership(user_id):
            bot.answer_callback_query(
                call.id,
                "❌ Please join the channel first!",
                show_alert=True
            )
            return
        
        update_channel_status(user_id, 1)
        
        welcome_text = """
✨ *Plush NFT Bot - Main Menu*

🎁 *Daily Bonus* - Claim 0.3 TON every 24h
👥 *Referral Program* - Earn 0.3 TON per referral
💰 *Withdraw* - Exchange TON for exclusive items

*Select an option:*
        """
        
        bot.edit_message_text(
            welcome_text,
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=main_menu_keyboard()
        )
        
    except Exception as e:
        print(f"❌ Error in back_to_main: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('menu_'))
def menu_handler(call):
    try:
        user_id = call.from_user.id
        
        if not check_channel_membership(user_id):
            bot.answer_callback_query(
                call.id,
                "❌ Please join the channel first!",
                show_alert=True
            )
            return
        
        update_channel_status(user_id, 1)
        
        user = get_user(user_id)
        if not user:
            bot.answer_callback_query(call.id, "❌ User not found!")
            return
        
        if call.data == "menu_profile":
            cursor = db.cursor()
            cursor.execute('SELECT COUNT(*) FROM referrals WHERE referrer_id = ?', (user['user_id'],))
            referral_count = cursor.fetchone()[0]
            
            referrer_id = user['invited_by']
            referrer_name = "No one"
            if referrer_id:
                cursor.execute('SELECT first_name FROM users WHERE user_id = ?', (referrer_id,))
                referrer = cursor.fetchone()
                if referrer:
                    referrer_name = referrer[0]
            
            profile_text = f"""
📊 *Your Profile*

👤 *Name:* {user['first_name']}
🆔 *User ID:* `{user['user_id']}`
📅 *Join Date:* {user['join_date']}
👥 *Your Referrals:* {referral_count} users
💰 *Balance:* {user['balance']:.2f} TON
🔗 *Your Referral Code:* `{user['referral_code']}`
👤 *Referred by:* {referrer_name}
            """
            
            bot.edit_message_text(
                profile_text,
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown',
                reply_markup=back_to_main_keyboard()
            )
            
        elif call.data == "menu_balance":
            balance_text = f"""
💰 *Your Balance*

*Current Balance:* `{user['balance']:.2f} TON`

💡 *Increase your balance by:*
1. Claiming daily bonus (0.3 TON every 24h)
2. Referring friends (0.3 TON per referral - one time only)

🔗 *Your referral link:*
`https://t.me/PlushNFTbot?start={user['referral_code']}`
            """
            
            bot.edit_message_text(
                balance_text,
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown',
                reply_markup=back_to_main_keyboard()
            )
            
        elif call.data == "menu_bonus":
            now = datetime.now()
            
            if user['last_bonus_date']:
                last_bonus = datetime.strptime(user['last_bonus_date'], "%Y-%m-%d %H:%M:%S")
                time_diff = now - last_bonus
                
                if time_diff < timedelta(hours=24):
                    next_bonus = last_bonus + timedelta(hours=24)
                    time_left = next_bonus - now
                    hours = time_left.seconds // 3600
                    minutes = (time_left.seconds % 3600) // 60
                    
                    bonus_text = f"""
⏳ *Daily Bonus*

*Status:* Not available yet
*Next bonus in:* {hours}h {minutes}m

Come back later to claim your 0.3 TON!
                    """
                    
                    bot.edit_message_text(
                        bonus_text,
                        call.message.chat.id,
                        call.message.message_id,
                        parse_mode='Markdown',
                        reply_markup=back_to_main_keyboard()
                    )
                    return
            
            cursor = db.cursor()
            cursor.execute('''
                UPDATE users 
                SET balance = balance + 0.3, last_bonus_date = ?
                WHERE user_id = ?
            ''', (now.strftime("%Y-%m-%d %H:%M:%S"), user['user_id']))
            db.commit()
            
            user = get_user(user_id)
            
            bonus_text = f"""
🎉 *Daily Bonus Claimed!*

✅ +0.3 TON added to your balance!
💰 *New Balance:* {user['balance']:.2f} TON

⏰ Come back in 24 hours for your next bonus.
            """
            
            bot.edit_message_text(
                bonus_text,
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown',
                reply_markup=back_to_main_keyboard()
            )
            
        elif call.data == "menu_referral":
            cursor = db.cursor()
            cursor.execute('SELECT COUNT(*) FROM referrals WHERE referrer_id = ?', (user['user_id'],))
            referral_count = cursor.fetchone()[0]
            
            was_referred = user['invited_by'] != 0
            
            referral_text = f"""
📤 *Referral Program*

*Your Stats:*
👥 Your Referrals: {referral_count} users
💰 Earned from referrals: {referral_count * 0.3:.2f} TON
{'✅ You were referred by someone' if was_referred else '❌ You were not referred by anyone'}

Earn *0.3 TON* for each NEW friend who joins using your link!
⚠️ *Note:* Each user can only be referred once.

*Your referral link:*
`https://t.me/PlushNFTbot?start={user['referral_code']}`

*Share this link:*
https://t.me/PlushNFTbot?start={user['referral_code']}
            """
            
            bot.edit_message_text(
                referral_text,
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown',
                reply_markup=back_to_main_keyboard()
            )
            
        elif call.data == "menu_withdraw":
            items_text = "🎁 *Available Items for Withdrawal*\n\n"
            for item in WITHDRAWAL_ITEMS:
                items_text += f"{item['name']} - {item['price']} TON\nWithdrawal: /{item['order_code']}\n――――――――――――――\n"
            
            items_text += f"\n💰 *Your Balance:* {user['balance']:.2f} TON\n\n*Select an item to withdraw:*"
            
            bot.edit_message_text(
                items_text,
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown',
                reply_markup=withdrawal_keyboard()
            )
            
        elif call.data == "menu_help":
            help_text = """
🆘 *Help Center*

*How to earn TON:*
1. Claim daily bonus every 24h (0.3 TON)
2. Invite NEW friends using referral link (0.3 TON each - one time only)

*Withdrawal Process:*
1. Go to Withdraw section
2. Select an item
3. If enough balance, it will be processed
4. Delivery within 48 hours

*Important Notes:*
• Each user can be referred only ONCE
• Daily bonus resets every 24 hours
• Minimum withdrawal varies per item

*Need help?*
Contact: @PlushNFTbot
            """
            
            bot.edit_message_text(
                help_text,
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown',
                reply_markup=back_to_main_keyboard()
            )
            
    except Exception as e:
        print(f"❌ Error in menu_handler: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('withdraw_'))
def withdraw_handler(call):
    try:
        user_id = call.from_user.id
        
        if not check_channel_membership(user_id):
            bot.answer_callback_query(
                call.id,
                "❌ Please join the channel first!",
                show_alert=True
            )
            return
        
        user = get_user(user_id)
        if not user:
            bot.answer_callback_query(call.id, "❌ User not found!")
            return
        
        order_code = call.data.replace('withdraw_', '')
        item = next((i for i in WITHDRAWAL_ITEMS if i['order_code'] == order_code), None)
        
        if not item:
            bot.answer_callback_query(call.id, "❌ Item not found!")
            return
        
        if user['balance'] < item['price']:
            bot.answer_callback_query(call.id, "❌ Insufficient balance!")
            
            error_text = f"""
❌ *Insufficient Balance*

*Item:* {item['name']}
*Price:* {item['price']} TON
*Your Balance:* {user['balance']:.2f} TON
*Required:* {item['price'] - user['balance']:.2f} TON more
            """
            
            bot.edit_message_text(
                error_text,
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown',
                reply_markup=back_to_main_keyboard()
            )
            return
        
        cursor = db.cursor()
        cursor.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (item['price'], user_id))
        
        cursor.execute('''
            INSERT INTO withdrawals (user_id, order_code, item_name, amount, request_date)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, order_code, item['name'], item['price'], datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        
        db.commit()
        
        user = get_user(user_id)
        
        confirmation_text = f"""
✅ *Withdrawal Successful!*

📦 *Item:* {item['name']}
💰 *Amount:* {item['price']} TON
📋 *Order Code:* `{order_code}`
📊 *Remaining Balance:* {user['balance']:.2f} TON
🔄 *Status:* Processing
⏰ *Estimated Time:* Up to 48 hours

Your withdrawal will be processed within 48 hours.
        """
        
        bot.edit_message_text(
            confirmation_text,
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=back_to_main_keyboard()
        )
        
    except Exception as e:
        print(f"❌ Error in withdraw_handler: {e}")

# ==================== ADMIN HANDLERS ====================
@bot.message_handler(commands=['padmin'])
def admin_panel_handler(message):
    try:
        user_id = message.from_user.id
        
        if user_id != ADMIN_ID:
            bot.send_message(
                user_id,
                "❌ *Access Denied!*\nYou are not authorized to access admin panel.",
                parse_mode='Markdown'
            )
            return
        
        admin_text = """
👑 *Admin Panel*

*Available Commands:*
📊 /stats - Bot statistics
💰 /addbalance [user_id] [amount] - Add balance to user
👥 /addall [amount] - Add balance to all users
📢 /broadcast - Send message to all users
📋 /users - List all users

*Or use buttons below:*
        """
        
        bot.send_message(
            user_id,
            admin_text,
            parse_mode='Markdown',
            reply_markup=admin_keyboard()
        )
        
    except Exception as e:
        print(f"❌ Error in admin_panel: {e}")

@bot.message_handler(commands=['stats'])
def stats_command(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        cursor = db.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM users')
        total_users = cursor.fetchone()[0]
        
        cursor.execute('SELECT SUM(balance) FROM users')
        total_balance = cursor.fetchone()[0] or 0
        
        cursor.execute('SELECT COUNT(*) FROM withdrawals WHERE status = "pending"')
        pending_withdrawals = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM referrals')
        total_referrals = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM users WHERE channel_joined = 1')
        channel_members = cursor.fetchone()[0]
        
        stats_text = f"""
📊 *Bot Statistics*

👥 *Total Users:* {total_users}
✅ *In Channel:* {channel_members}
💰 *Total Balance:* {total_balance:.2f} TON
📤 *Pending Withdrawals:* {pending_withdrawals}
🔗 *Total Referrals:* {total_referrals}
        """
        
        bot.send_message(
            message.chat.id,
            stats_text,
            parse_mode='Markdown',
            reply_markup=admin_keyboard()
        )
        
    except Exception as e:
        print(f"❌ Error in stats: {e}")

@bot.message_handler(commands=['addbalance'])
def add_balance_command(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        parts = message.text.split()
        if len(parts) != 3:
            bot.send_message(
                message.chat.id,
                "❌ Usage: /addbalance [user_id] [amount]\nExample: /addbalance 123456789 10.5",
                reply_markup=admin_keyboard()
            )
            return
        
        user_id = int(parts[1])
        amount = float(parts[2])
        
        cursor = db.cursor()
        cursor.execute('SELECT first_name FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        
        if not user:
            bot.send_message(message.chat.id, "❌ User not found!")
            return
        
        cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
        db.commit()
        
        try:
            bot.send_message(
                user_id,
                f"🎉 *Admin Bonus!*\n\n+{amount} TON added to your balance!\nNew balance available for withdrawal.",
                parse_mode='Markdown'
            )
        except:
            pass
        
        bot.send_message(
            message.chat.id,
            f"✅ Added {amount} TON to user {user_id} ({user[0]})",
            reply_markup=admin_keyboard()
        )
        
    except Exception as e:
        print(f"❌ Error in add_balance: {e}")
        bot.send_message(
            message.chat.id,
            "❌ Invalid format! Use: /addbalance [user_id] [amount]",
            reply_markup=admin_keyboard()
        )

@bot.message_handler(commands=['addall'])
def add_all_command(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        parts = message.text.split()
        if len(parts) != 2:
            bot.send_message(
                message.chat.id,
                "❌ Usage: /addall [amount]\nExample: /addall 5",
                reply_markup=admin_keyboard()
            )
            return
        
        amount = float(parts[1])
        
        cursor = db.cursor()
        cursor.execute('UPDATE users SET balance = balance + ?', (amount,))
        db.commit()
        
        cursor.execute('SELECT COUNT(*) FROM users')
        total_users = cursor.fetchone()[0]
        
        bot.send_message(
            message.chat.id,
            f"✅ Added {amount} TON to all {total_users} users!",
            reply_markup=admin_keyboard()
        )
        
    except Exception as e:
        print(f"❌ Error in add_all: {e}")
        bot.send_message(
            message.chat.id,
            "❌ Invalid amount! Please enter a number.",
            reply_markup=admin_keyboard()
        )

@bot.message_handler(commands=['broadcast'])
def broadcast_command(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    msg = bot.send_message(
        message.chat.id,
        "📢 *Send your broadcast message:*\n\n(Text, photo, or document)",
        parse_mode='Markdown'
    )
    bot.register_next_step_handler(msg, process_broadcast)

def process_broadcast(message):
    try:
        cursor = db.cursor()
        cursor.execute('SELECT user_id FROM users')
        users = cursor.fetchall()
        
        sent = 0
        failed = 0
        
        progress_msg = bot.send_message(message.chat.id, f"📤 Broadcasting to {len(users)} users...")
        
        for user_row in users:
            user_id = user_row[0]
            try:
                if message.content_type == 'text':
                    bot.send_message(user_id, message.text, parse_mode='Markdown')
                elif message.content_type == 'photo':
                    bot.send_photo(user_id, message.photo[-1].file_id, caption=message.caption, parse_mode='Markdown')
                elif message.content_type == 'document':
                    bot.send_document(user_id, message.document.file_id, caption=message.caption, parse_mode='Markdown')
                
                sent += 1
            except:
                failed += 1
        
        bot.send_message(
            message.chat.id,
            f"✅ *Broadcast Complete!*\n\nTotal: {len(users)} users\n✅ Sent: {sent}\n❌ Failed: {failed}",
            parse_mode='Markdown',
            reply_markup=admin_keyboard()
        )
        
    except Exception as e:
        print(f"❌ Error in broadcast: {e}")

@bot.message_handler(commands=['users'])
def users_command(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        cursor = db.cursor()
        cursor.execute('SELECT user_id, first_name, balance FROM users ORDER BY user_id DESC LIMIT 50')
        users = cursor.fetchall()
        
        if not users:
            bot.send_message(message.chat.id, "📭 No users found!")
            return
        
        users_text = "👥 *Latest 50 Users*\n\n"
        for user in users:
            users_text += f"🆔 `{user[0]}` - {user[1]} - {user[2]:.2f} TON\n"
        
        users_text += f"\n*Total users:* {len(users)}"
        
        bot.send_message(
            message.chat.id,
            users_text,
            parse_mode='Markdown',
            reply_markup=admin_keyboard()
        )
        
    except Exception as e:
        print(f"❌ Error in users: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_'))
def admin_callback_handler(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ Access denied!")
        return
    
    try:
        if call.data == "admin_stats":
            cursor = db.cursor()
            
            cursor.execute('SELECT COUNT(*) FROM users')
            total_users = cursor.fetchone()[0]
            
            cursor.execute('SELECT SUM(balance) FROM users')
            total_balance = cursor.fetchone()[0] or 0
            
            cursor.execute('SELECT COUNT(*) FROM referrals')
            total_referrals = cursor.fetchone()[0]
            
            stats_text = f"""
📊 *Bot Statistics*

👥 Total Users: {total_users}
💰 Total Balance: {total_balance:.2f} TON
🔗 Total Referrals: {total_referrals}
            """
            
            bot.edit_message_text(
                stats_text,
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown',
                reply_markup=admin_keyboard()
            )
        
        elif call.data == "admin_add_all":
            msg = bot.send_message(
                call.message.chat.id,
                "💰 *Enter amount to add to ALL users:*\n\nExample: 10.5",
                parse_mode='Markdown'
            )
            bot.register_next_step_handler(msg, admin_add_all_step)
        
        elif call.data == "admin_add_user":
            msg = bot.send_message(
                call.message.chat.id,
                "👤 *Enter user ID and amount:*\n\nExample: 123456789 10.5",
                parse_mode='Markdown'
            )
            bot.register_next_step_handler(msg, admin_add_user_step)
        
        elif call.data == "admin_broadcast":
            msg = bot.send_message(
                call.message.chat.id,
                "📢 *Send your broadcast message:*\n\n(Text, photo, or document)",
                parse_mode='Markdown'
            )
            bot.register_next_step_handler(msg, process_broadcast_callback)
        
        elif call.data == "admin_user_list":
            cursor = db.cursor()
            cursor.execute('SELECT COUNT(*) FROM users')
            total_users = cursor.fetchone()[0]
            
            cursor.execute('SELECT user_id, first_name, balance FROM users ORDER BY balance DESC LIMIT 20')
            top_users = cursor.fetchall()
            
            users_text = f"👥 *Top 20 Users by Balance*\n\n*Total Users:* {total_users}\n\n"
            
            for i, user in enumerate(top_users, 1):
                users_text += f"{i}. `{user[0]}` - {user[1]} - *{user[2]:.2f} TON*\n"
            
            bot.edit_message_text(
                users_text,
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown',
                reply_markup=admin_keyboard()
            )
            
    except Exception as e:
        print(f"❌ Error in admin_callback: {e}")

def admin_add_all_step(message):
    try:
        amount = float(message.text)
        
        cursor = db.cursor()
        cursor.execute('UPDATE users SET balance = balance + ?', (amount,))
        db.commit()
        
        cursor.execute('SELECT COUNT(*) FROM users')
        total_users = cursor.fetchone()[0]
        
        bot.send_message(
            message.chat.id,
            f"✅ Added {amount} TON to all {total_users} users!",
            reply_markup=admin_keyboard()
        )
    except:
        bot.send_message(message.chat.id, "❌ Invalid amount! Please enter a number.")

def admin_add_user_step(message):
    try:
        parts = message.text.split()
        if len(parts) != 2:
            raise ValueError
        
        user_id = int(parts[0])
        amount = float(parts[1])
        
        cursor = db.cursor()
        cursor.execute('SELECT first_name FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        
        if not user:
            bot.send_message(message.chat.id, "❌ User not found!")
            return
        
        cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
        db.commit()
        
        try:
            bot.send_message(
                user_id,
                f"🎉 *Admin Bonus!*\n\n+{amount} TON added to your balance!\nNew balance available for withdrawal.",
                parse_mode='Markdown'
            )
        except:
            pass
        
        bot.send_message(
            message.chat.id,
            f"✅ Added {amount} TON to user {user_id} ({user[0]})",
            reply_markup=admin_keyboard()
        )
        
    except:
        bot.send_message(
            message.chat.id,
            "❌ Invalid format! Use: [user_id] [amount]\nExample: 123456789 10.5"
        )

def process_broadcast_callback(message):
    try:
        cursor = db.cursor()
        cursor.execute('SELECT user_id FROM users')
        users = cursor.fetchall()
        
        sent = 0
        failed = 0
        
        progress_msg = bot.send_message(message.chat.id, f"📤 Broadcasting to {len(users)} users...")
        
        for user_row in users:
            user_id = user_row[0]
            try:
                if message.content_type == 'text':
                    bot.send_message(user_id, message.text, parse_mode='Markdown')
                elif message.content_type == 'photo':
                    bot.send_photo(user_id, message.photo[-1].file_id, caption=message.caption, parse_mode='Markdown')
                elif message.content_type == 'document':
                    bot.send_document(user_id, message.document.file_id, caption=message.caption, parse_mode='Markdown')
                
                sent += 1
            except:
                failed += 1
        
        bot.send_message(
            message.chat.id,
            f"✅ *Broadcast Complete!*\n\nTotal: {len(users)} users\n✅ Sent: {sent}\n❌ Failed: {failed}",
            parse_mode='Markdown',
            reply_markup=admin_keyboard()
        )
        
    except Exception as e:
        print(f"❌ Error in broadcast_callback: {e}")

# ==================== POLLING THREAD ====================
def start_polling():
    print("🤖 Starting bot polling...")
    while True:
        try:
            bot.polling(none_stop=True, interval=2, timeout=30)
        except Exception as e:
            print(f"⚠️ Polling error: {e}")
            time.sleep(5)
            print("🔄 Restarting polling...")

# ==================== FLASK ROUTES ====================
@app.route('/')
def home():
    return "🤖 Plush NFT Bot is running with polling!"

@app.route('/health')
def health():
    return "✅ Bot is healthy!"

# ==================== MAIN ====================
if __name__ == '__main__':
    print("=" * 50)
    print("🤖 PLUSH NFT BOT")
    print("=" * 50)
    print(f"Bot Token: {BOT_TOKEN[:10]}...")
    print(f"Admin ID: {ADMIN_ID}")
    print(f"Channel: {CHANNEL_USERNAME}")
    print("=" * 50)
    
    polling_thread = threading.Thread(target=start_polling, daemon=True)
    polling_thread.start()
    print("✅ Bot polling started in background thread")
    
    port = int(os.environ.get('PORT', 5000))
    print(f"🌐 Flask server starting on port {port}")
    app.run(host='0.0.0.0', port=port)
