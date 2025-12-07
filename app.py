import os
import sqlite3
from datetime import datetime, timedelta
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask
import threading
import time

# ==================== CONFIGURATION ====================
# مستقیم اینجا مقادیر را وارد کنید
BOT_TOKEN = "7593433447:AAF1XGZI3budBP3LN3NtY1ThVnIkssHbV9I" # توکن بات را اینجا قرار دهید
ADMIN_ID = 5095867558 # آیدی عددی ادمین را اینجا قرار دهید
CHANNEL_USERNAME = "@PllushNFt"  # آیدی کانال
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

def create_user(user_id, username, first_name, referral_code=None):
    cursor = db.cursor()
    join_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user_referral_code = f"REF{user_id}"
    
    # برای تست، فعلاً عضویت در کانال را چک نمی‌کنیم
    channel_member = True  # برای تست
    
    cursor.execute('''
        INSERT OR IGNORE INTO users 
        (user_id, username, first_name, join_date, referral_code, channel_joined) 
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, username, first_name, join_date, user_referral_code, 1))
    
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
                bot.send_message(
                    referrer[0], 
                    f"🎉 *New Referral!*\n\n{first_name} joined using your link.\n+0.3 TON added to your balance!",
                    parse_mode='Markdown'
                )
            except:
                pass
    
    db.commit()
    return True

def check_channel_membership(user_id):
    """بررسی عضویت کاربر در کانال"""
    try:
        chat_member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return chat_member.status in ['member', 'administrator', 'creator']
    except:
        # برای تست، همیشه True برمی‌گردانیم
        return True

# ==================== KEYBOARDS ====================
def join_channel_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("✅ Join Channel", url=CHANNEL_URL))
    keyboard.add(InlineKeyboardButton("🔍 Check Membership", callback_data="check_membership"))
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
        username = message.from_user.username
        first_name = message.from_user.first_name
        
        print(f"🚀 User {user_id} started the bot")
        
        referral_code = None
        if len(message.text.split()) > 1:
            referral_code = message.text.split()[1]
        
        create_user(user_id, username, first_name, referral_code)
        
        welcome_text = f"""
✨ *Welcome to Plush NFT Bot, {first_name}!* ✨

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
        
    except Exception as e:
        print(f"❌ Error in start handler: {e}")

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    try:
        user_id = call.from_user.id
        print(f"📱 Callback: {call.data} from user {user_id}")
        
        if call.data == "check_membership":
            if check_channel_membership(user_id):
                bot.answer_callback_query(call.id, "✅ You're a member!")
                welcome_text = """
✅ *Channel Verified!*

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
                    "❌ You haven't joined the channel yet!",
                    show_alert=True
                )
        
        elif call.data == "back_to_main":
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
        
        elif call.data.startswith('menu_'):
            user = get_user(user_id)
            if not user:
                bot.answer_callback_query(call.id, "❌ User not found!")
                return
            
            if call.data == "menu_profile":
                cursor = db.cursor()
                cursor.execute('SELECT COUNT(*) FROM referrals WHERE referrer_id = ?', (user['user_id'],))
                referral_count = cursor.fetchone()[0]
                
                profile_text = f"""
📊 *Your Profile*

👤 *Name:* {user['first_name']}
🆔 *User ID:* `{user['user_id']}`
📅 *Join Date:* {user['join_date']}
👥 *Referrals:* {referral_count} users
🔗 *Your Referral Code:* `{user['referral_code']}`
💰 *Balance:* {user['balance']:.2f} TON
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
                
                referral_text = f"""
📤 *Referral Program*

*Your Stats:*
👥 Referrals: {referral_count} users
💰 Earned: {referral_count * 0.3:.2f} TON

Earn *0.3 TON* for each friend who joins using your link!

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
2. Invite friends using referral link (0.3 TON each)

*Withdrawal Process:*
1. Go to Withdraw section
2. Select an item
3. If enough balance, it will be processed
4. Delivery within 48 hours

*Need help?*
Contact: @YourSupportChannel
                """
                
                bot.edit_message_text(
                    help_text,
                    call.message.chat.id,
                    call.message.message_id,
                    parse_mode='Markdown',
                    reply_markup=back_to_main_keyboard()
                )
        
        elif call.data.startswith('withdraw_'):
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
        
        elif call.data.startswith('admin_'):
            if user_id != ADMIN_ID:
                bot.answer_callback_query(call.id, "❌ Access denied!")
                return
            
            if call.data == "admin_stats":
                cursor = db.cursor()
                cursor.execute('SELECT COUNT(*) FROM users')
                total_users = cursor.fetchone()[0]
                
                cursor.execute('SELECT SUM(balance) FROM users')
                total_balance = cursor.fetchone()[0] or 0
                
                stats_text = f"""
📊 *Bot Statistics*

👥 Total Users: {total_users}
💰 Total Balance: {total_balance:.2f} TON
                """
                
                bot.edit_message_text(
                    stats_text,
                    call.message.chat.id,
                    call.message.message_id,
                    parse_mode='Markdown',
                    reply_markup=admin_keyboard()
                )
                
    except Exception as e:
        print(f"❌ Error in callback handler: {e}")

@bot.message_handler(commands=['padmin'])
def admin_panel_handler(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(
            message.chat.id,
            "❌ *Access Denied!*\nYou are not authorized.",
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
        message.chat.id,
        admin_text,
        parse_mode='Markdown',
        reply_markup=admin_keyboard()
    )

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
    
    # Start bot polling in a separate thread
    polling_thread = threading.Thread(target=start_polling, daemon=True)
    polling_thread.start()
    print("✅ Bot polling started in background thread")
    
    # Start Flask server
    port = int(os.environ.get('PORT', 5000))
    print(f"🌐 Flask server starting on port {port}")
    app.run(host='0.0.0.0', port=port)
