import os
import json
import sqlite3
import threading
from datetime import datetime, timedelta
from dotenv import load_dotenv
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from flask import Flask

# Load environment variables
load_dotenv()

# Initialize bot
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID'))
bot = telebot.TeleBot(BOT_TOKEN)

# Flask app for Render web service
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

# Run Flask in a separate thread
def run_flask():
    app.run(host='0.0.0.0', port=5000)

flask_thread = threading.Thread(target=run_flask)
flask_thread.start()

# Database setup
def init_db():
    conn = sqlite3.connect('bot_database.db', check_same_thread=False)
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            join_date TEXT,
            balance REAL DEFAULT 0.0,
            last_bonus_date TEXT,
            referral_code TEXT UNIQUE,
            invited_by INTEGER DEFAULT 0
        )
    ''')
    
    # Withdrawals table
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
    
    # Referral tracking
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER,
            referred_id INTEGER,
            date TEXT,
            FOREIGN KEY (referrer_id) REFERENCES users (user_id),
            FOREIGN KEY (referred_id) REFERENCES users (user_id)
        )
    ''')
    
    conn.commit()
    return conn

db_connection = init_db()

# Helper functions
def get_user(user_id):
    cursor = db_connection.cursor()
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
            'invited_by': user[7]
        }
    return None

def create_user(user_id, username, first_name, referral_code=None):
    cursor = db_connection.cursor()
    join_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user_referral_code = f"REF{user_id}"
    
    cursor.execute('''
        INSERT OR IGNORE INTO users 
        (user_id, username, first_name, join_date, referral_code) 
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, username, first_name, join_date, user_referral_code))
    
    if referral_code:
        cursor.execute('SELECT user_id FROM users WHERE referral_code = ?', (referral_code,))
        referrer = cursor.fetchone()
        if referrer and referrer[0] != user_id:
            cursor.execute('UPDATE users SET invited_by = ? WHERE user_id = ?', (referrer[0], user_id))
            
            # Add referral bonus
            cursor.execute('UPDATE users SET balance = balance + 0.3 WHERE user_id = ?', (referrer[0],))
            
            # Log referral
            cursor.execute('''
                INSERT INTO referrals (referrer_id, referred_id, date)
                VALUES (?, ?, ?)
            ''', (referrer[0], user_id, join_date))
            
            bot.send_message(referrer[0], 
                           f"🎉 New referral!\n{first_name} joined using your link.\n+0.3 TON added to your balance!")
    
    db_connection.commit()

def update_balance(user_id, amount):
    cursor = db_connection.cursor()
    cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
    db_connection.commit()

# Keyboard templates
def main_menu_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = [
        KeyboardButton("👤 Profile"),
        KeyboardButton("💰 Balance"),
        KeyboardButton("🎁 Daily Bonus"),
        KeyboardButton("📤 Withdraw"),
        KeyboardButton("🔗 Referral"),
    ]
    keyboard.add(*buttons)
    return keyboard

def back_to_main_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton("🔙 Back to Main"))
    return keyboard

# Withdrawal items
WITHDRAWAL_ITEMS = [
    {"name": "Vintage Cigar", "price": 20, "order_code": "/order_2348"},
    {"name": "Snoop Cigar", "price": 7, "order_code": "/order_2349"},
    {"name": "Snoop Dogg", "price": 3, "order_code": "/order_2350"},
    {"name": "Evil Eye", "price": 5, "order_code": "/order_2351"},
    {"name": "Star Notepad", "price": 2.5, "order_code": "/order_2352"},
    {"name": "Jester Hat", "price": 2, "order_code": "/order_2353"},
    {"name": "Pet Snake", "price": 2, "order_code": "/order_2354"},
    {"name": "Lunar Snake", "price": 1.5, "order_code": "/order_2355"}
]

def withdrawal_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)
    for item in WITHDRAWAL_ITEMS:
        keyboard.add(InlineKeyboardButton(
            f"{item['name']} - {item['price']} TON",
            callback_data=f"withdraw_{item['order_code']}"
        ))
    keyboard.add(InlineKeyboardButton("🔙 Back", callback_data="back_to_main"))
    return keyboard

# Bot handlers
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    
    # Check for referral parameter
    referral_code = None
    if len(message.text.split()) > 1:
        referral_code = message.text.split()[1]
    
    create_user(user_id, username, first_name, referral_code)
    
    welcome_text = f"""
✨ *Welcome to Plush NFT Bot* ✨

🎁 *Daily Bonus* - Claim 0.3 TON every 24h
👥 *Referral Program* - Earn 0.3 TON per referral
💰 *Withdraw* - Exchange TON for exclusive items

Select an option below:
    """
    
    bot.send_message(
        user_id,
        welcome_text,
        parse_mode='Markdown',
        reply_markup=main_menu_keyboard()
    )

@bot.message_handler(func=lambda message: message.text == "🔙 Back to Main")
def back_to_main(message):
    bot.send_message(
        message.chat.id,
        "🏠 *Main Menu*",
        parse_mode='Markdown',
        reply_markup=main_menu_keyboard()
    )

@bot.message_handler(func=lambda message: message.text == "👤 Profile")
def show_profile(message):
    user = get_user(message.from_user.id)
    if not user:
        return
    
    # Count referrals
    cursor = db_connection.cursor()
    cursor.execute('SELECT COUNT(*) FROM referrals WHERE referrer_id = ?', (user['user_id'],))
    referral_count = cursor.fetchone()[0]
    
    profile_text = f"""
📊 *Your Profile*

👤 *Name:* {user['first_name']}
🆔 *User ID:* `{user['user_id']}`
📅 *Join Date:* {user['join_date']}
👥 *Referrals:* {referral_count} users
🔗 *Your Referral Code:* `{user['referral_code']}`
    """
    
    bot.send_message(
        message.chat.id,
        profile_text,
        parse_mode='Markdown',
        reply_markup=back_to_main_keyboard()
    )

@bot.message_handler(func=lambda message: message.text == "💰 Balance")
def show_balance(message):
    user = get_user(message.from_user.id)
    if not user:
        return
    
    balance_text = f"""
💰 *Your Balance*

*Current Balance:* `{user['balance']:.2f} TON`

💡 *Increase your balance by inviting friends!*
Each referral earns you *0.3 TON*
    """
    
    bot.send_message(
        message.chat.id,
        balance_text,
        parse_mode='Markdown',
        reply_markup=back_to_main_keyboard()
    )

@bot.message_handler(func=lambda message: message.text == "🎁 Daily Bonus")
def daily_bonus(message):
    user = get_user(message.from_user.id)
    if not user:
        return
    
    now = datetime.now()
    
    if user['last_bonus_date']:
        last_bonus = datetime.strptime(user['last_bonus_date'], "%Y-%m-%d %H:%M:%S")
        time_diff = now - last_bonus
        
        if time_diff < timedelta(hours=24):
            next_bonus = last_bonus + timedelta(hours=24)
            time_left = next_bonus - now
            hours = time_left.seconds // 3600
            minutes = (time_left.seconds % 3600) // 60
            
            bot.send_message(
                message.chat.id,
                f"⏳ *Bonus Not Available*\n\nPlease wait {hours}h {minutes}m to claim your next bonus.",
                parse_mode='Markdown',
                reply_markup=back_to_main_keyboard()
            )
            return
    
    # Grant bonus
    cursor = db_connection.cursor()
    cursor.execute('''
        UPDATE users 
        SET balance = balance + 0.3, last_bonus_date = ?
        WHERE user_id = ?
    ''', (now.strftime("%Y-%m-%d %H:%M:%S"), user['user_id']))
    db_connection.commit()
    
    bot.send_message(
        message.chat.id,
        "🎉 *Daily Bonus Claimed!*\n\n+0.3 TON added to your balance!",
        parse_mode='Markdown',
        reply_markup=back_to_main_keyboard()
    )

@bot.message_handler(func=lambda message: message.text == "🔗 Referral")
def referral_link(message):
    user = get_user(message.from_user.id)
    if not user:
        return
    
    referral_text = f"""
📤 *Referral Program*

Earn *0.3 TON* for each friend who joins using your link!

*Your referral link:*
`https://t.me/PlushNFTbot?start={user['referral_code']}`

*Share this link with your friends:*
https://t.me/PlushNFTbot?start={user['referral_code']}

💡 *How it works:*
1. Share your link with friends
2. They join the bot using your link
3. You receive 0.3 TON automatically
    """
    
    bot.send_message(
        message.chat.id,
        referral_text,
        parse_mode='Markdown',
        reply_markup=back_to_main_keyboard()
    )

@bot.message_handler(func=lambda message: message.text == "📤 Withdraw")
def withdraw_menu(message):
    user = get_user(message.from_user.id)
    if not user:
        return
    
    items_text = "🎁 *Available Items for Withdrawal*\n\n"
    for item in WITHDRAWAL_ITEMS:
        items_text += f"{item['name']} - {item['price']} TON\nWithdrawal: {item['order_code']}\n――――――――――――――\n"
    
    items_text += f"\n💰 *Your Balance:* {user['balance']:.2f} TON\n\n*Select an item:*"
    
    bot.send_message(
        message.chat.id,
        items_text,
        parse_mode='Markdown',
        reply_markup=withdrawal_keyboard()
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('withdraw_'))
def process_withdrawal(call):
    user = get_user(call.from_user.id)
    if not user:
        return
    
    order_code = call.data.replace('withdraw_', '')
    selected_item = next((item for item in WITHDRAWAL_ITEMS if item['order_code'] == order_code), None)
    
    if not selected_item:
        bot.answer_callback_query(call.id, "❌ Item not found!")
        return
    
    if user['balance'] < selected_item['price']:
        bot.answer_callback_query(call.id, "❌ Insufficient balance!")
        bot.send_message(
            call.message.chat.id,
            f"❌ *Insufficient Balance*\n\nYou need {selected_item['price']} TON, but you have {user['balance']:.2f} TON.",
            parse_mode='Markdown'
        )
        return
    
    # Process withdrawal
    cursor = db_connection.cursor()
    cursor.execute('''
        UPDATE users SET balance = balance - ? WHERE user_id = ?
    ''', (selected_item['price'], user['user_id']))
    
    cursor.execute('''
        INSERT INTO withdrawals (user_id, order_code, item_name, amount, request_date)
        VALUES (?, ?, ?, ?, ?)
    ''', (user['user_id'], order_code, selected_item['name'], selected_item['price'], 
          datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    
    db_connection.commit()
    
    # Send confirmation
    confirmation_text = f"""
✅ *Withdrawal Successful!*

*Item:* {selected_item['name']}
*Amount:* {selected_item['price']} TON
*Order Code:* {order_code}
*Status:* Processing
*Estimated Time:* Up to 48 hours

Your withdrawal has been registered and will be processed within 48 hours.
    """
    
    bot.edit_message_text(
        confirmation_text,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown'
    )
    
    # Send main menu
    bot.send_message(
        call.message.chat.id,
        "🏠 *Main Menu*",
        parse_mode='Markdown',
        reply_markup=main_menu_keyboard()
    )

@bot.callback_query_handler(func=lambda call: call.data == "back_to_main")
def back_to_main_callback(call):
    bot.edit_message_text(
        "🏠 Returning to main menu...",
        call.message.chat.id,
        call.message.message_id
    )
    bot.send_message(
        call.message.chat.id,
        "🏠 *Main Menu*",
        parse_mode='Markdown',
        reply_markup=main_menu_keyboard()
    )

# Admin commands
@bot.message_handler(commands=['padmin'])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ Access denied!")
        return
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("📊 Stats", callback_data="admin_stats"),
        InlineKeyboardButton("💰 Add Balance to All", callback_data="admin_add_all"),
        InlineKeyboardButton("👤 Add Balance to User", callback_data="admin_add_user"),
        InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
        InlineKeyboardButton("🔙 Back", callback_data="back_to_main")
    )
    
    bot.send_message(
        message.chat.id,
        "👑 *Admin Panel*\n\nSelect an option:",
        parse_mode='Markdown',
        reply_markup=keyboard
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_'))
def admin_actions(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ Access denied!")
        return
    
    if call.data == "admin_stats":
        cursor = db_connection.cursor()
        cursor.execute('SELECT COUNT(*) FROM users')
        total_users = cursor.fetchone()[0]
        
        cursor.execute('SELECT SUM(balance) FROM users')
        total_balance = cursor.fetchone()[0] or 0
        
        cursor.execute('SELECT COUNT(*) FROM withdrawals WHERE status = "pending"')
        pending_withdrawals = cursor.fetchone()[0]
        
        stats_text = f"""
📊 *Bot Statistics*

👥 Total Users: {total_users}
💰 Total Balance: {total_balance:.2f} TON
📤 Pending Withdrawals: {pending_withdrawals}
        """
        
        bot.edit_message_text(
            stats_text,
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown'
        )
    
    elif call.data == "admin_add_all":
        msg = bot.send_message(
            call.message.chat.id,
            "Enter amount to add to ALL users (e.g., 10):"
        )
        bot.register_next_step_handler(msg, process_add_to_all)

def process_add_to_all(message):
    try:
        amount = float(message.text)
        cursor = db_connection.cursor()
        cursor.execute('UPDATE users SET balance = balance + ?', (amount,))
        db_connection.commit()
        
        bot.send_message(
            message.chat.id,
            f"✅ Added {amount} TON to all users!",
            reply_markup=main_menu_keyboard()
        )
    except ValueError:
        bot.send_message(message.chat.id, "❌ Invalid amount!")

# Keep alive for Render
def keep_alive():
    while True:
        try:
            bot.infinity_polling(timeout=30, long_polling_timeout=5)
        except Exception as e:
            print(f"Error: {e}")
            import time
            time.sleep(5)

if __name__ == "__main__":
    print("Bot is starting...")
    keep_alive()
