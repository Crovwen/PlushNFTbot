import os
import sqlite3
from datetime import datetime, timedelta
from dotenv import load_dotenv
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask, request

# Load environment variables
load_dotenv()

# Initialize bot
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID'))
bot = telebot.TeleBot(BOT_TOKEN)

# Channel settings - CHANGE THIS TO YOUR CHANNEL
CHANNEL_USERNAME = "@PllushNFt"
CHANNEL_URL = "https://t.me/PllushNFt"

# Flask app
app = Flask(__name__)

# Database setup
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
            invited_by INTEGER DEFAULT 0
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
            cursor.execute('UPDATE users SET balance = balance + 0.3 WHERE user_id = ?', (referrer[0],))
            
            cursor.execute('''
                INSERT INTO referrals (referrer_id, referred_id, date)
                VALUES (?, ?, ?)
            ''', (referrer[0], user_id, join_date))
            
            try:
                bot.send_message(referrer[0], 
                               f"🎉 *New Referral!*\n\n{first_name} joined using your link.\n+0.3 TON added to your balance!",
                               parse_mode='Markdown')
            except:
                pass
    
    db_connection.commit()

# Keyboard templates
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

# Withdrawal items
WITHDRAWAL_ITEMS = [
    {"name": "🎩 Vintage Cigar", "price": 20, "order_code": "order_2348"},
    {"name": "🚬 Snoop Cigar", "price": 7, "order_code": "order_2349"},
    {"name": "🐶 Snoop Dogg", "price": 3, "order_code": "order_2350"},
    {"name": "👁️ Evil Eye", "price": 5, "order_code": "order_2351"},
    {"name": "📓 Star Notepad", "price": 2.5, "order_code": "order_2352"},
    {"name": "🎭 Jester Hat", "price": 2, "order_code": "order_2353"},
    {"name": "🐍 Pet Snake", "price": 2, "order_code": "order_2354"},
    {"name": "🌙 Lunar Snake", "price": 1.5, "order_code": "order_2355"}
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

# Admin keyboard
def admin_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("📊 Statistics", callback_data="admin_stats"),
        InlineKeyboardButton("💰 Add to All Users", callback_data="admin_add_all"),
        InlineKeyboardButton("👤 Add to Specific User", callback_data="admin_add_user"),
        InlineKeyboardButton("📢 Broadcast Message", callback_data="admin_broadcast"),
        InlineKeyboardButton("👥 User List", callback_data="admin_user_list"),
        InlineKeyboardButton("🔙 Back to Main", callback_data="back_to_main")
    )
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

*Select an option below:*
    """
    
    bot.send_message(
        user_id,
        welcome_text,
        parse_mode='Markdown',
        reply_markup=main_menu_keyboard()
    )

# Main menu handlers
@bot.callback_query_handler(func=lambda call: call.data.startswith('menu_'))
def menu_handler(call):
    user_id = call.from_user.id
    user = get_user(user_id)
    
    if not user:
        bot.answer_callback_query(call.id, "❌ User not found!")
        return
    
    if call.data == "menu_profile":
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

💡 *Increase your balance by inviting friends!*
Each referral earns you *0.3 TON*
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
                
                bot.edit_message_text(
                    f"⏳ *Bonus Not Available*\n\nPlease wait {hours}h {minutes}m to claim your next bonus.",
                    call.message.chat.id,
                    call.message.message_id,
                    parse_mode='Markdown',
                    reply_markup=back_to_main_keyboard()
                )
                return
        
        cursor = db_connection.cursor()
        cursor.execute('''
            UPDATE users 
            SET balance = balance + 0.3, last_bonus_date = ?
            WHERE user_id = ?
        ''', (now.strftime("%Y-%m-%d %H:%M:%S"), user['user_id']))
        db_connection.commit()
        
        bot.edit_message_text(
            "🎉 *Daily Bonus Claimed!*\n\n+0.3 TON added to your balance!",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=back_to_main_keyboard()
        )
        
    elif call.data == "menu_referral":
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
        
        items_text += f"\n💰 *Your Balance:* {user['balance']:.2f} TON\n\n*Select an item:*"
        
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
1. Claim daily bonus every 24h
2. Invite friends using your referral link
3. Each referral earns you 0.3 TON

*Withdrawal:*
1. Go to Withdraw section
2. Select an item
3. If you have enough balance, it will be processed
4. Delivery within 48 hours

*Need more help?*
Contact support: @YourSupportChannel
        """
        
        bot.edit_message_text(
            help_text,
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=back_to_main_keyboard()
        )

@bot.callback_query_handler(func=lambda call: call.data.startswith('withdraw_'))
def process_withdrawal(call):
    user = get_user(call.from_user.id)
    if not user:
        bot.answer_callback_query(call.id, "❌ User not found!")
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
    
    cursor = db_connection.cursor()
    cursor.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (selected_item['price'], user['user_id']))
    
    cursor.execute('''
        INSERT INTO withdrawals (user_id, order_code, item_name, amount, request_date)
        VALUES (?, ?, ?, ?, ?)
    ''', (user['user_id'], order_code, selected_item['name'], selected_item['price'], 
          datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    
    db_connection.commit()
    
    confirmation_text = f"""
✅ *Withdrawal Successful!*

*Item:* {selected_item['name']}
*Amount:* {selected_item['price']} TON
*Order Code:* /{order_code}
*Status:* Processing
*Estimated Time:* Up to 48 hours

Your withdrawal has been registered and will be processed within 48 hours.
    """
    
    bot.edit_message_text(
        confirmation_text,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
        reply_markup=back_to_main_keyboard()
    )

@bot.callback_query_handler(func=lambda call: call.data == "back_to_main")
def back_to_main_callback(call):
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

# Admin commands
@bot.message_handler(commands=['padmin'])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ *Access Denied!*\n\nYou are not authorized to access this panel.",
                        parse_mode='Markdown')
        return
    
    admin_text = """
👑 *Admin Panel*

*Select an option below:*
    """
    
    bot.send_message(
        message.chat.id,
        admin_text,
        parse_mode='Markdown',
        reply_markup=admin_keyboard()
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_'))
def admin_callback_handler(call):
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
            parse_mode='Markdown',
            reply_markup=admin_keyboard()
        )
    
    elif call.data == "admin_add_all":
        msg = bot.send_message(call.message.chat.id, "💰 *Enter amount to add to ALL users:*\n\nExample: 10.5",
                              parse_mode='Markdown')
        bot.register_next_step_handler(msg, admin_add_all_step)

def admin_add_all_step(message):
    try:
        amount = float(message.text)
        cursor = db_connection.cursor()
        cursor.execute('UPDATE users SET balance = balance + ?', (amount,))
        db_connection.commit()
        
        cursor.execute('SELECT COUNT(*) FROM users')
        total_users = cursor.fetchone()[0]
        
        bot.send_message(
            message.chat.id,
            f"✅ Added {amount} TON to all {total_users} users!",
            reply_markup=admin_keyboard()
        )
    except ValueError:
        bot.send_message(message.chat.id, "❌ Invalid amount! Please enter a number.")

@bot.callback_query_handler(func=lambda call: call.data == "admin_add_user")
def admin_add_user_callback(call):
    msg = bot.send_message(call.message.chat.id, "👤 *Enter user ID and amount:*\n\nExample: 123456789 10.5",
                          parse_mode='Markdown')
    bot.register_next_step_handler(msg, admin_add_user_step)

def admin_add_user_step(message):
    try:
        parts = message.text.split()
        if len(parts) != 2:
            raise ValueError
        
        user_id = int(parts[0])
        amount = float(parts[1])
        
        cursor = db_connection.cursor()
        cursor.execute('SELECT first_name FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        
        if not user:
            bot.send_message(message.chat.id, "❌ User not found!")
            return
        
        cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
        db_connection.commit()
        
        try:
            bot.send_message(user_id, f"🎉 *Admin Bonus!*\n\n+{amount} TON added to your balance!\nNew balance available for withdrawal.",
                           parse_mode='Markdown')
        except:
            pass
        
        bot.send_message(
            message.chat.id,
            f"✅ Added {amount} TON to user {user_id} ({user[0]})",
            reply_markup=admin_keyboard()
        )
        
    except ValueError:
        bot.send_message(message.chat.id, "❌ Invalid format! Use: [user_id] [amount]\nExample: 123456789 10.5")

@bot.callback_query_handler(func=lambda call: call.data == "admin_broadcast")
def admin_broadcast_callback(call):
    msg = bot.send_message(call.message.chat.id, "📢 *Send your broadcast message:*\n\n(Text, photo, or document)",
                          parse_mode='Markdown')
    bot.register_next_step_handler(msg, process_broadcast_callback)

def process_broadcast_callback(message):
    cursor = db_connection.cursor()
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

@bot.callback_query_handler(func=lambda call: call.data == "admin_user_list")
def admin_user_list_callback(call):
    cursor = db_connection.cursor()
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

# Flask routes
@app.route('/')
def home():
    return "🤖 Plush NFT Bot is running on Render!"

@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    else:
        return 'Invalid content type', 403

# Set webhook
def set_webhook():
    # Get Render URL from environment
    render_url = os.getenv('RENDER_EXTERNAL_URL', '')
    if render_url:
        webhook_url = f"{render_url}/{BOT_TOKEN}"
        bot.remove_webhook()
        bot.set_webhook(url=webhook_url)
        print(f"✅ Webhook set to: {webhook_url}")
    else:
        print("⚠️ Running without webhook (local development)")

if __name__ == '__main__':
    # Set webhook when starting
    set_webhook()
    
    # Run Flask app
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
