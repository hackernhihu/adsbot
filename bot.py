# bot.py - Advanced Ads Bot with Channel Join & Auto Posting
import asyncio
import sqlite3
import json
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

# ==================== CONFIGURATION ====================
BOT_TOKEN = "8602929076:AAGwLbiiceSMIsrWWSoBfC6GlF2_DxO7ZH8"
ADMIN_ID = 8574753078
UPI_ID = "theghost@ptyes"

# Channel links (Replace with your channels)
CHANNEL_1 = "https://t.me/+HNFMEGAiozRiMGU9"
CHANNEL_2 = "https://t.me/+u26_kBpHtCYxZjM1"
CHANNEL_1_ID = "-1003746369177"  # Bot must be admin here
CHANNEL_2_ID = "-1003562532116"  # Bot must be admin here

# Premium plans
PREMIUM_PLANS = {
    "weekly": {"price": "₹99", "days": 7, "id": "week"},
    "monthly": {"price": "₹199", "days": 30, "id": "month"},
    "yearly": {"price": "₹599", "days": 365, "id": "year"}
}

# ==================== DATABASE SETUP ====================
def init_db():
    conn = sqlite3.connect('ads_bot.db')
    c = conn.cursor()
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        join_date TEXT,
        premium_until TEXT,
        is_premium INTEGER DEFAULT 0,
        is_banned INTEGER DEFAULT 0,
        max_accounts INTEGER DEFAULT 1
    )''')
    
    # Accounts table (user's telegram accounts for posting)
    c.execute('''CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        phone_number TEXT,
        session_string TEXT,
        is_active INTEGER DEFAULT 1,
        added_date TEXT,
        FOREIGN KEY(user_id) REFERENCES users(user_id)
    )''')
    
    # Ads table
    c.execute('''CREATE TABLE IF NOT EXISTS ads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        account_id INTEGER,
        message_text TEXT,
        media_type TEXT,
        media_file_id TEXT,
        status TEXT DEFAULT 'active',
        created_date TEXT,
        last_posted TEXT,
        FOREIGN KEY(user_id) REFERENCES users(user_id)
    )''')
    
    # Groups table (where bot will post)
    c.execute('''CREATE TABLE IF NOT EXISTS groups (
        group_id INTEGER PRIMARY KEY,
        group_title TEXT,
        group_link TEXT,
        added_date TEXT
    )''')
    
    # Pending UTR requests
    c.execute('''CREATE TABLE IF NOT EXISTS pending_utr (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        plan_type TEXT,
        amount TEXT,
        utr_number TEXT,
        status TEXT DEFAULT 'pending',
        submitted_date TEXT
    )''')
    
    conn.commit()
    conn.close()

init_db()

# ==================== HELPER FUNCTIONS ====================

def get_main_keyboard(user_id):
    """Get main menu keyboard based on user status"""
    conn = sqlite3.connect('ads_bot.db')
    c = conn.cursor()
    c.execute("SELECT is_premium, premium_until, is_banned FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    conn.close()
    
    if user and user[2] == 1:
        return None  # Banned user
    
    keyboard = [
        [InlineKeyboardButton("📱 MY ACCOUNTS", callback_data="my_accounts")],
        [InlineKeyboardButton("📝 MY ADS", callback_data="my_ads")],
        [InlineKeyboardButton("➕ ADD ACCOUNT", callback_data="add_account")],
        [InlineKeyboardButton("✍️ CREATE NEW AD", callback_data="create_ad")],
        [InlineKeyboardButton("💰 BUY PREMIUM", callback_data="buy_premium")],
        [InlineKeyboardButton("💬 SUPPORT", callback_data="support")]
    ]
    
    if user_id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("👑 ADMIN PANEL", callback_data="admin_panel")])
    
    return InlineKeyboardMarkup(keyboard)

def check_premium(user_id):
    """Check if user has active premium"""
    conn = sqlite3.connect('ads_bot.db')
    c = conn.cursor()
    c.execute("SELECT premium_until, is_premium FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    
    if result and result[1] == 1:
        if result[0]:
            premium_until = datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S')
            if premium_until > datetime.now():
                return True
    return False

def get_user_accounts(user_id):
    """Get user's added accounts"""
    conn = sqlite3.connect('ads_bot.db')
    c = conn.cursor()
    c.execute("SELECT id, phone_number, is_active FROM accounts WHERE user_id = ?", (user_id,))
    accounts = c.fetchall()
    conn.close()
    return accounts

def can_add_account(user_id):
    """Check if user can add more accounts"""
    accounts = get_user_accounts(user_id)
    max_accounts = 5 if check_premium(user_id) else 1
    return len(accounts) < max_accounts

# ==================== COMMAND HANDLERS ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # Check if user needs to join channels
    keyboard = [
        [InlineKeyboardButton("📢 Join Channel 1", url=CHANNEL_1)],
        [InlineKeyboardButton("📢 Join Channel 2", url=CHANNEL_2)],
        [InlineKeyboardButton("✅ I've Joined", callback_data="check_join")]
    ]
    
    # Add user to database if not exists
    conn = sqlite3.connect('ads_bot.db')
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, username, first_name, join_date) VALUES (?, ?, ?, ?)",
              (user.id, user.username, user.first_name, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(
        f"🎯 **Welcome {user.first_name}!**\n\n"
        "To use this bot, you must join our channels first:\n\n"
        "📢 **Channel 1**\n"
        "📢 **Channel 2**\n\n"
        "After joining, click the button below.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def check_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    
    await query.answer("Checking...")
    
    try:
        # Check if user joined channels
        member1 = await context.bot.get_chat_member(CHANNEL_1_ID, user_id)
        member2 = await context.bot.get_chat_member(CHANNEL_2_ID, user_id)
        
        if member1.status in ['member', 'administrator', 'creator'] and member2.status in ['member', 'administrator', 'creator']:
            await query.edit_message_text(
                "✅ **Verification Successful!**\n\n"
                "Welcome to the Ads Bot!\n"
                "Use the buttons below to get started.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_main_keyboard(user_id)
            )
        else:
            keyboard = [
                [InlineKeyboardButton("📢 Join Channel 1", url=CHANNEL_1)],
                [InlineKeyboardButton("📢 Join Channel 2", url=CHANNEL_2)],
                [InlineKeyboardButton("✅ I've Joined", callback_data="check_join")]
            ]
            await query.edit_message_text(
                "❌ **You haven't joined both channels!**\n\n"
                "Please join both channels first.",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
    except Exception as e:
        await query.edit_message_text(
            "❌ Error checking membership. Please try again.",
            reply_markup=get_main_keyboard(user_id)
        )

async def my_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    
    accounts = get_user_accounts(user_id)
    
    if not accounts:
        await query.edit_message_text(
            "📱 **Your Accounts:**\n\n"
            "No accounts added yet!\n\n"
            "Use '➕ ADD ACCOUNT' to add your first account.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_main_keyboard(user_id)
        )
        return
    
    text = "📱 **Your Accounts:**\n\n"
    for acc in accounts:
        text += f"📞 `{acc[1]}` - {'✅ Active' if acc[2] else '❌ Inactive'}\n"
    
    text += f"\n📊 **Limit:** {len(accounts)}/{5 if check_premium(user_id) else 1} accounts\n"
    
    keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")]]
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def add_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    
    if not can_add_account(user_id):
        await query.answer("❌ You've reached your account limit! Upgrade to premium for 5 accounts.", show_alert=True)
        return
    
    await query.edit_message_text(
        "📱 **Add Account Instructions:**\n\n"
        "To add your Telegram account:\n\n"
        "1️⃣ Download [Telegram Desktop](https://desktop.telegram.org/)\n"
        "2️⃣ Login to your account\n"
        "3️⃣ Get your API ID & Hash from [my.telegram.org](https://my.telegram.org/apps)\n"
        "4️⃣ Send the string in format:\n\n"
        "`api_id|api_hash|phone_number`\n\n"
        "⚠️ This is secure and we don't store your password!",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")]])
    )
    
    context.user_data['awaiting_account'] = True

async def create_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    
    accounts = get_user_accounts(user_id)
    if not accounts:
        await query.answer("❌ Please add an account first!", show_alert=True)
        return
    
    await query.edit_message_text(
        "✍️ **Create New Ad**\n\n"
        "Send me the message you want to post as an ad.\n\n"
        "You can send:\n"
        "• Text message\n"
        "• Photo with caption\n"
        "• Video with caption\n\n"
        "Type /cancel to cancel.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="back_to_menu")]])
    )
    
    context.user_data['awaiting_ad'] = True

async def my_ads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    
    conn = sqlite3.connect('ads_bot.db')
    c = conn.cursor()
    c.execute("SELECT id, message_text, status, created_date FROM ads WHERE user_id = ? ORDER BY id DESC LIMIT 10", (user_id,))
    ads = c.fetchall()
    conn.close()
    
    if not ads:
        await query.edit_message_text(
            "📝 **Your Ads:**\n\n"
            "No ads created yet!\n\n"
            "Use '✍️ CREATE NEW AD' to create your first ad.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_main_keyboard(user_id)
        )
        return
    
    text = "📝 **Your Recent Ads:**\n\n"
    for ad in ads:
        text += f"🆔 Ad #{ad[0]}\n📝 `{ad[1][:50]}...`\n📊 Status: {ad[2]}\n📅 {ad[3]}\n\n"
    
    keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")]]
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def buy_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    text = (
        "💰 **Premium Plans**\n\n"
        "✨ **Benefits:**\n"
        "• Add 5 accounts (instead of 1)\n"
        "• Priority posting\n"
        "• 24/7 support\n"
        "• No ads on your posts\n\n"
        "**Plans:**\n"
        f"📅 Weekly - ₹99\n"
        f"📅 Monthly - ₹199\n"
        f"📅 Yearly - ₹599\n\n"
        f"**UPI ID:** `{UPI_ID}`\n\n"
        "After payment, send:\n"
        "`/utr YOUR_UTR_NUMBER PLAN`\n\n"
        "Example: `/utr HDFC123456789 weekly`"
    )
    
    keyboard = [
        [InlineKeyboardButton("💰 Weekly - ₹99", callback_data="select_weekly")],
        [InlineKeyboardButton("💰 Monthly - ₹199", callback_data="select_monthly")],
        [InlineKeyboardButton("💰 Yearly - ₹599", callback_data="select_yearly")],
        [InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")]
    ]
    
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_utr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text.strip()
    
    parts = text.split()
    if len(parts) < 3 or parts[0] != '/utr':
        await update.message.reply_text(
            "❌ Invalid format!\nUse: `/utr UTR_NUMBER PLAN`\n\nPlans: weekly, monthly, yearly",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    utr = parts[1]
    plan_type = parts[2].lower()
    
    if plan_type not in PREMIUM_PLANS:
        await update.message.reply_text("❌ Invalid plan! Choose: weekly, monthly, yearly")
        return
    
    plan = PREMIUM_PLANS[plan_type]
    
    conn = sqlite3.connect('ads_bot.db')
    c = conn.cursor()
    c.execute("INSERT INTO pending_utr (user_id, plan_type, amount, utr_number, submitted_date) VALUES (?, ?, ?, ?, ?)",
              (user.id, plan_type, plan['price'], utr, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    conn.close()
    
    # Notify admin
    admin_text = (
        f"💰 **New Premium Request**\n\n"
        f"👤 User: {user.first_name}\n"
        f"🆔 ID: `{user.id}`\n"
        f"📝 Username: @{user.username if user.username else 'N/A'}\n"
        f"💎 Plan: {plan['price']}\n"
        f"🔢 UTR: `{utr}`\n\n"
        f"Use:\n"
        f"/approve {user.id} - to approve\n"
        f"/reject {user.id} - to reject"
    )
    
    await context.bot.send_message(ADMIN_ID, admin_text, parse_mode=ParseMode.MARKDOWN)
    
    await update.message.reply_text(
        "✅ **UTR Received!**\n\n"
        "Your request has been sent to admin.\n"
        "You'll get premium access within 24 hours after verification.\n\n"
        "Thank you! 🎉",
        parse_mode=ParseMode.MARKDOWN
    )

async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    keyboard = [[InlineKeyboardButton("📩 Contact Support", url="https://t.me/RSCODERHUB")]]
    await query.edit_message_text(
        "💬 **Support Center**\n\n"
        "For any issues or queries:\n\n"
        "📧 Contact: @RSCODERHUB\n\n"
        "Response time: Usually within 12 hours\n\n"
        "**FAQs:**\n"
        "• How to add account?\n"
        "• Premium benefits?\n"
        "• Posting schedule?\n\n"
        "Click below to message support.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ==================== ADMIN COMMANDS ====================

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    if query.from_user.id != ADMIN_ID:
        await query.answer("❌ Admin only!", show_alert=True)
        return
    
    conn = sqlite3.connect('ads_bot.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE is_premium = 1")
    premium_users = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM pending_utr WHERE status = 'pending'")
    pending_requests = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM ads")
    total_ads = c.fetchone()[0]
    conn.close()
    
    text = (
        f"👑 **Admin Panel**\n\n"
        f"📊 **Statistics:**\n"
        f"• Total Users: `{total_users}`\n"
        f"• Premium Users: `{premium_users}`\n"
        f"• Total Ads: `{total_ads}`\n"
        f"• Pending Requests: `{pending_requests}`\n\n"
        f"**Commands:**\n"
        f"/broadcast - Send message to all\n"
        f"/stats - View stats\n"
        f"/ban <user_id> - Ban user\n"
        f"/unban <user_id> - Unban user\n"
        f"/approve <user_id> - Approve premium\n"
        f"/reject <user_id> - Reject premium"
    )
    
    keyboard = [
        [InlineKeyboardButton("📊 View Pending Requests", callback_data="view_pending")],
        [InlineKeyboardButton("👥 View Users", callback_data="view_users")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="broadcast")],
        [InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")]
    ]
    
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def approve_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Admin only!")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /approve <user_id>")
        return
    
    user_id = int(context.args[0])
    
    conn = sqlite3.connect('ads_bot.db')
    c = conn.cursor()
    c.execute("SELECT plan_type FROM pending_utr WHERE user_id = ? AND status = 'pending' ORDER BY id DESC LIMIT 1", (user_id,))
    result = c.fetchone()
    
    if result:
        plan_type = result[0]
        plan = PREMIUM_PLANS[plan_type]
        premium_until = (datetime.now() + timedelta(days=plan['days'])).strftime('%Y-%m-%d %H:%M:%S')
        
        c.execute("UPDATE users SET is_premium = 1, premium_until = ?, max_accounts = 5 WHERE user_id = ?", (premium_until, user_id))
        c.execute("UPDATE pending_utr SET status = 'approved' WHERE user_id = ? AND status = 'pending'", (user_id,))
        conn.commit()
        
        await context.bot.send_message(
            user_id,
            f"🎉 **Premium Activated!**\n\n"
            f"Plan: {plan['price']}\n"
            f"Valid until: {premium_until}\n\n"
            f"Now you can add up to 5 accounts!\n\n"
            f"Thank you for choosing us! 🚀",
            parse_mode=ParseMode.MARKDOWN
        )
        
        await update.message.reply_text(f"✅ Premium approved for user {user_id}")
    else:
        await update.message.reply_text("❌ No pending request found for this user")
    
    conn.close()

async def reject_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Admin only!")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /reject <user_id>")
        return
    
    user_id = int(context.args[0])
    
    conn = sqlite3.connect('ads_bot.db')
    c = conn.cursor()
    c.execute("UPDATE pending_utr SET status = 'rejected' WHERE user_id = ? AND status = 'pending'", (user_id,))
    conn.commit()
    
    await context.bot.send_message(
        user_id,
        "❌ **Premium Request Rejected**\n\n"
        "Your payment couldn't be verified.\n"
        "Please contact support: @RSCODERHUB",
        parse_mode=ParseMode.MARKDOWN
    )
    
    await update.message.reply_text(f"❌ Premium rejected for user {user_id}")
    conn.close()

async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Admin only!")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /ban <user_id>")
        return
    
    user_id = int(context.args[0])
    
    conn = sqlite3.connect('ads_bot.db')
    c = conn.cursor()
    c.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(f"✅ User {user_id} has been banned")

async def unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Admin only!")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /unban <user_id>")
        return
    
    user_id = int(context.args[0])
    
    conn = sqlite3.connect('ads_bot.db')
    c = conn.cursor()
    c.execute("UPDATE users SET is_banned = 0 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(f"✅ User {user_id} has been unbanned")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Admin only!")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /broadcast Your message here")
        return
    
    message = ' '.join(context.args)
    
    conn = sqlite3.connect('ads_bot.db')
    c = conn.cursor()
    c.execute("SELECT user_id FROM users")
    users = c.fetchall()
    conn.close()
    
    success = 0
    for user in users:
        try:
            await context.bot.send_message(user[0], f"📢 **Announcement:**\n\n{message}", parse_mode=ParseMode.MARKDOWN)
            success += 1
            await asyncio.sleep(0.1)
        except:
            pass
    
    await update.message.reply_text(f"✅ Broadcast sent to {success} users")

# ==================== MESSAGE HANDLER ====================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if context.user_data.get('awaiting_account'):
        # Handle account addition
        text = update.message.text
        try:
            parts = text.split('|')
            if len(parts) == 3:
                api_id, api_hash, phone = parts
                # Here you would use Telethon to create session
                # For now, just store placeholder
                
                conn = sqlite3.connect('ads_bot.db')
                c = conn.cursor()
                c.execute("INSERT INTO accounts (user_id, phone_number, session_string, added_date) VALUES (?, ?, ?, ?)",
                          (user_id, phone, "session_placeholder", datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                conn.commit()
                conn.close()
                
                await update.message.reply_text(
                    "✅ **Account Added Successfully!**\n\n"
                    f"📞 Phone: {phone}\n\n"
                    "You can now create ads with this account.",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=get_main_keyboard(user_id)
                )
                context.user_data['awaiting_account'] = False
            else:
                await update.message.reply_text("❌ Invalid format! Send: `api_id|api_hash|phone_number`", parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    elif context.user_data.get('awaiting_ad'):
        # Save ad
        conn = sqlite3.connect('ads_bot.db')
        c = conn.cursor()
        c.execute("INSERT INTO ads (user_id, account_id, message_text, created_date) VALUES (?, ?, ?, ?)",
                  (user_id, 1, update.message.text, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(
            "✅ **Ad Created Successfully!**\n\n"
            "Your ad will be posted every 5 minutes in all groups.\n\n"
            "Use /start to manage your ads.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_main_keyboard(user_id)
        )
        context.user_data['awaiting_ad'] = False

# ==================== AUTO POSTING FUNCTION ====================

async def auto_post(context: ContextTypes.DEFAULT_TYPE):
    """Automatically post ads every 5 minutes"""
    conn = sqlite3.connect('ads_bot.db')
    c = conn.cursor()
    c.execute("SELECT id, user_id, account_id, message_text, media_type, media_file_id FROM ads WHERE status = 'active'")
    ads = c.fetchall()
    
    c.execute("SELECT group_id, group_link FROM groups")
    groups = c.fetchall()
    conn.close()
    
    for ad in ads:
        for group in groups:
            try:
                await context.bot.send_message(group[0], f"📢 **Ad:**\n\n{ad[3]}")
                await asyncio.sleep(2)  # Delay to avoid flood
            except Exception as e:
                print(f"Error posting: {e}")

# ==================== MAIN ====================

async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.edit_message_text(
        "🎯 **Main Menu**\n\nUse the buttons below to manage your ads.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=get_main_keyboard(query.from_user.id)
    )

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("utr", handle_utr))
    app.add_handler(CommandHandler("approve", approve_premium))
    app.add_handler(CommandHandler("reject", reject_premium))
    app.add_handler(CommandHandler("ban", ban_user))
    app.add_handler(CommandHandler("unban", unban_user))
    app.add_handler(CommandHandler("broadcast", broadcast))
    
    # Callback handlers
    app.add_handler(CallbackQueryHandler(check_join, pattern='check_join'))
    app.add_handler(CallbackQueryHandler(my_accounts, pattern='my_accounts'))
    app.add_handler(CallbackQueryHandler(add_account, pattern='add_account'))
    app.add_handler(CallbackQueryHandler(create_ad, pattern='create_ad'))
    app.add_handler(CallbackQueryHandler(my_ads, pattern='my_ads'))
    app.add_handler(CallbackQueryHandler(buy_premium, pattern='buy_premium'))
    app.add_handler(CallbackQueryHandler(support, pattern='support'))
    app.add_handler(CallbackQueryHandler(admin_panel, pattern='admin_panel'))
    app.add_handler(CallbackQueryHandler(back_to_menu, pattern='back_to_menu'))
    
    # Message handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Auto post job (every 5 minutes)
    job_queue = app.job_queue
    job_queue.run_repeating(auto_post, interval=300, first=10)
    
    print("🤖 Ads Bot is running!")
    app.run_polling()

if __name__ == "__main__":
    main()
