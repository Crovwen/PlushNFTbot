import os
import sqlite3
from datetime import datetime, timedelta
from dotenv import load_dotenv
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# Load environment variables
load_dotenv()

# Initialize bot
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID'))
bot = telebot.TeleBot(BOT_TOKEN)

# Channel settings
CHANNEL_USERNAME = "@PllushNFt"  # کانال مورد نظر
CHANNEL_URL = "https://t.me/PllushNFt"

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
            invited_by INTEGER DEFAULT 0,
            has_joined_channel INTEGER DEFAULT 0
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
            'invited_by': user[7],
            'has_joined_channel': user[8] if len(user) > 8 else 0
        }
    return None

def update_user_channel_status(user_id, status):
    cursor = db_connection.cursor()
    cursor.execute('UPDATE users SET has_joined_channel = ? WHERE user_id = ?', (status, user_id))
    db_connection.commit()

def check_channel_membership(user_id):
    """بررسی می‌کند کاربر در کانال عضو هست یا نه"""
    try:
        chat_member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return chat_member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        print(f"Error checking channel membership: {e}")
        # اگر ارور داد، فرض می‌کنیم کاربر عضو نیست
        return False

def create_user(user_id, username, first_name, referral_code=None):
    cursor = db_connection.cursor()
    join_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user_referral_code = f"REF{user_id}"
    
    # ابتدا بررسی می‌کنیم کاربر در کانال عضو هست یا نه
    has_joined = check_channel_membership(user_id)
    
    cursor.execute('''
        INSERT OR IGNORE INTO users 
        (user_id, username, first_name, join_date, referral_code, has_joined_channel) 
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, username, first_name, join_date, user_referral_code, 1 if has_joined else 0))
    
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
            
            try:
                bot.send_message(referrer[0], 
                               f"🎉 *New Referral!*\n\n{first_name} joined using your link.\n+0.3 TON added to your balance!",
                               parse_mode='Markdown')
            except:
                pass
    
    db_connection.commit()
    return has_joined

# Keyboard templates
def join_channel_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("✅ Join Channel", url=CHANNEL_URL)
    )
    keyboard.add(
        InlineKeyboardButton("🔍 I've Joined", callback_data="check_membership")
    )
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
    
    # Create user and check channel membership
    has_joined = create_user(user_id, username, first_name, referral_code)
    
    if has_joined:
        show_main_menu(user_id, first_name)
    else:
        show_join_channel_message(user_id, first_name)

def show_join_channel_message(user_id, first_name):
    join_text = f"""
👋 *Welcome {first_name}!*

📢 *Join Requirement*

To access *Plush NFT Bot* features, you must join our official channel:

{CHANNEL_USERNAME}

*How to proceed:*
1. Click *'Join Channel'* button below
2. Join our channel
3. Click *'I've Joined'* button

Once verified, you'll get access to:
🎁 Daily Bonus (0.3 TON every 24h)
👥 Referral Program (0.3 TON per referral)
💰 Withdraw exclusive items
    """
    
    bot.send_message(
        user_id,
        join_text,
        parse_mode='Markdown',
        reply_markup=join_channel_keyboard()
    )

def show_main_menu(user_id, first_name):
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

@bot.callback_query_handler(func=lambda call: call.data == "check_membership")
def check_membership_handler(call):
    user_id = call.from_user.id
    user = get_user(user_id)
    first_name = user['first_name'] if user else "User"
    
    if check_channel_membership(user_id):
        update_user_channel_status(user_id, 1)
        
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
            "❌ You haven't joined the channel yet! Please join first and then click 'I've Joined'.",
            show_alert=True
        )

# Main menu handlers
@bot.callback_query_handler(func=lambda call: call.data.startswith('menu_'))
def menu_handler(call):
    user_id = call.from_user.id
    user = get_user(user_id)
    
    if not user:
        bot.answer_callback_query(call.id, "❌ User not found!")
        return
    
    # بررسی عضویت در کانال برای همه منوها
    if not check_channel_membership(user_id):
        bot.answer_callback_query(
            call.id,
            "❌ Please join the channel first! Click 'I've Joined' after joining.",
            show_alert=True
        )
        
        # Get user info for personalized message
        user = get_user(user_id)
        first_name = user['first_name'] if user else "User"
        show_join_channel_message(user_id, first_name)
        return
    
    # به روزرسانی وضعیت عضویت
    update_user_channel_status(user_id, 1)
    
    if call.data == "menu_profile":
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

💡 *Increase your balance by:*
1. Claiming daily bonus (0.3 TON every 24h)
2. Referring friends (0.3 TON per referral)

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
        
        # Grant bonus
        cursor = db_connection.cursor()
        cursor.execute('''
            UPDATE users 
            SET balance = balance + 0.3, last_bonus_date = ?
            WHERE user_id = ?
        ''', (now.strftime("%Y-%m-%d %H:%M:%S"), user['user_id']))
        db_connection.commit()
        
        # Get updated balance
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
        # Count referrals for this user
        cursor = db_connection.cursor()
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

*Share this link with your friends:*
https://t.me/PlushNFTbot?start={user['referral_code']}

💡 *How it works:*
1. Share your link with friends
2. They join the bot using your link
3. You receive 0.3 TON automatically
4. They also get to join and earn!
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
2. Invite friends using your referral link (0.3 TON each)
3. Join our channel for updates

*Withdrawal Process:*
1. Go to Withdraw section
2. Select an item you want
3. If you have enough balance, it will be processed
4. Delivery within 48 hours

*Important Notes:*
• Minimum balance required for withdrawal varies per item
• Referral bonus is credited instantly
• Daily bonus resets every 24 hours

*Need more help?*
Contact: @YourSupportChannel
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
    user_id = call.from_user.id
    
    # بررسی عضویت در کانال
    if not check_channel_membership(user_id):
        bot.answer_callback_query(
            call.id,
            "❌ Please join the channel first!",
            show_alert=True
        )
        user = get_user(user_id)
        first_name = user['first_name'] if user else "User"
        show_join_channel_message(user_id, first_name)
        return
    
    user = get_user(user_id)
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
        
        error_text = f"""
❌ *Insufficient Balance*

*Item:* {selected_item['name']}
*Price:* {selected_item['price']} TON
*Your Balance:* {user['balance']:.2f} TON
*Required:* {selected_item['price'] - user['balance']:.2f} TON more

💡 *Earn more TON by:*
1. Claiming daily bonus
2. Inviting friends (0.3 TON each)
        """
        
        bot.edit_message_text(
            error_text,
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=back_to_main_keyboard()
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
    
    # Get updated balance
    user = get_user(user_id)
    
    # Send confirmation
    confirmation_text = f"""
✅ *Withdrawal Successful!*

📦 *Item:* {selected_item['name']}
💰 *Amount:* {selected_item['price']} TON
📋 *Order Code:* `{order_code}`
📊 *Remaining Balance:* {user['balance']:.2f} TON
🔄 *Status:* Processing
⏰ *Estimated Time:* Up to 48 hours

Your withdrawal has been registered and will be processed within 48 hours.
You will be notified when it's shipped.

Thank you for using Plush NFT Bot! 🎉
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
    user_id = call.from_user.id
    
    # بررسی عضویت در کانال
    if not check_channel_membership(user_id):
        bot.answer_callback_query(
            call.id,
            "❌ Please join the channel first!",
            show_alert=True
        )
        user = get_user(user_id)
        first_name = user['first_name'] if user else "User"
        show_join_channel_message(user_id, first_name)
        return
    
    update_user_channel_status(user_id, 1)
    
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

# Admin commands - بدون تغییر باقی می‌مانند
@bot.message_handler(commands=['padmin'])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ *Access Denied!*\n\nYou are not authorized to access this panel.",
                        parse_mode='Markdown')
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

# بقیه کدهای ادمین بدون تغییر از اینجا به بعد...
# فقط مطمئن شوید که import خطا نمی‌دهد

@bot.message_handler(commands=['stats'])
def stats_command(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    cursor = db_connection.cursor()
    
    # Total users
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    
    # Total balance
    cursor.execute('SELECT SUM(balance) FROM users')
    total_balance = cursor.fetchone()[0] or 0
    
    # Pending withdrawals
    cursor.execute('SELECT COUNT(*) FROM withdrawals WHERE status = "pending"')
    pending_withdrawals = cursor.fetchone()[0]
    
    # Today's users
    today = datetime.now().strftime("%Y-%m-%d")
    cursor.execute('SELECT COUNT(*) FROM users WHERE join_date LIKE ?', (f"{today}%",))
    today_users = cursor.fetchone()[0]
    
    # Total referrals
    cursor.execute('SELECT COUNT(*) FROM referrals')
    total_referrals = cursor.fetchone()[0]
    
    # Users in channel
    cursor.execute('SELECT COUNT(*) FROM users WHERE has_joined_channel = 1')
    channel_users = cursor.fetchone()[0]
    
    stats_text = f"""
📊 *Bot Statistics*

👥 *Total Users:* {total_users}
✅ *In Channel:* {channel_users}
💰 *Total Balance:* {total_balance:.2f} TON
📤 *Pending Withdrawals:* {pending_withdrawals}
📈 *Today's New Users:* {today_users}
🔗 *Total Referrals:* {total_referrals}
    """
    
    bot.send_message(
        message.chat.id,
        stats_text,
        parse_mode='Markdown',
        reply_markup=admin_keyboard()
    )

@bot.message_handler(commands=['addbalance'])
def add_balance_command(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        _, user_id, amount = message.text.split()
        user_id = int(user_id)
        amount = float(amount)
        
        cursor = db_connection.cursor()
        cursor.execute('SELECT first_name FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        
        if not user:
            bot.send_message(message.chat.id, "❌ User not found!")
            return
        
        cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
        db_connection.commit()
        
        # Notify user
        try:
            bot.send_message(user_id, f"🎉 *Admin Bonus!*\n\n+{amount} TON added to your balance by admin!\nNew balance available for withdrawal.",
                           parse_mode='Markdown')
        except:
            pass
        
        bot.send_message(
            message.chat.id,
            f"✅ Added {amount} TON to user {user_id} ({user[0]})",
            reply_markup=admin_keyboard()
        )
        
    except ValueError:
        bot.send_message(message.chat.id, "❌ Usage: /addbalance [user_id] [amount]\nExample: /addbalance 123456789 10.5")

@bot.message_handler(commands=['addall'])
def add_all_command(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        _, amount = message.text.split()
        amount = float(amount)
        
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
        bot.send_message(message.chat.id, "❌ Usage: /addall [amount]\nExample: /addall 5")

@bot.message_handler(commands=['broadcast'])
def broadcast_command(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    msg = bot.send_message(message.chat.id, "📢 *Send the broadcast message:*\n\n(Text, photo, or document)",
                          parse_mode='Markdown')
    bot.register_next_step_handler(msg, process_broadcast)

def process_broadcast(message):
    cursor = db_connection.cursor()
    cursor.execute('SELECT user_id FROM users')
    users = cursor.fetchall()
    
    sent = 0
    failed = 0
    
    progress_msg = bot.send_message(message.chat.id, f"📤 Broadcasting to {len(users)} users...\nSent: 0 | Failed: 0")
    
    for user_row in users:
        user_id = user_row[0]
        try:
            # Forward the message
            if message.content_type == 'text':
                bot.send_message(user_id, message.text, parse_mode='Markdown')
            elif message.content_type == 'photo':
                bot.send_photo(user_id, message.photo[-1].file_id, caption=message.caption)
            elif message.content_type == 'document':
                bot.send_document(user_id, message.document.file_id, caption=message.caption)
            
            sent += 1
        except Exception as e:
            failed += 1
        
        # Update progress every 10 users
        if (sent + failed) % 10 == 0:
            bot.edit_message_text(
                f"📤 Broadcasting to {len(users)} users...\nSent: {sent} | Failed: {failed}",
                message.chat.id,
                progress_msg.message_id
            )
    
    bot.edit_message_text(
        f"✅ *Broadcast Complete!*\n\nTotal: {len(users)} users\n✅ Sent: {sent}\n❌ Failed: {failed}",
        message.chat.id,
        progress_msg.message_id,
        parse_mode='Markdown'
    )
    bot.send_message(message.chat.id, "👑 *Admin Panel*", parse_mode='Markdown', reply_markup=admin_keyboard())

@bot.message_handler(commands=['users'])
def users_command(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    cursor = db_connection.cursor()
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
        
        # Notify user
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
            # Forward the message
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
    bot.delete_message(message.chat.id, progress_msg.message_id)

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

# Keep the bot running
if __name__ == "__main__":
    print("🤖 Plush NFT Bot is starting...")
    print(f"📢 Channel: {CHANNEL_USERNAME}")
    print(f"👑 Admin ID: {ADMIN_ID}")
    bot.infinity_polling(timeout=30, long_polling_timeout=5) 
