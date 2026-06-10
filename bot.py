import json
import os
import asyncio
from datetime import datetime, timedelta
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.constants import ParseMode
from flask import Flask
from threading import Thread

app = Flask(__name__)
@app.route('/')
def home(): return "Konkurs Bot"
@app.route('/ping')
def ping(): return "PONG"
def run_flask(): app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

BOT_TOKEN = os.environ.get('BOT_TOKEN', '8902742471:AAG6SWWBESpslnAyaiSx0T-wLzrd35xsvUM')
ADMIN_ID = 8306639956
CHANNEL = '@vexronnews'
DATA = "/tmp/konkurs_data.json"

if os.path.exists(DATA):
    with open(DATA) as f: data = json.load(f)
else:
    data = {"contests": {}, "participants": {}, "winners": {}, "admins": [str(ADMIN_ID)]}

def save():
    with open(DATA, 'w') as f: json.dump(data, f, ensure_ascii=False)

def is_admin(uid):
    return str(uid) in data.get("admins", [])

async def check_sub(uid, context):
    try:
        member = await context.bot.get_chat_member(CHANNEL, uid)
        return member.status not in ['left', 'kicked']
    except:
        return False

def main_menu(uid):
    contests = data.get("contests", {})
    active = len([c for c in contests.values() if c.get("status") == "active"])
    finished = len([c for c in contests.values() if c.get("status") == "finished"])
    
    kb = [
        [KeyboardButton("🎉 Konkurs yaratish")],
        [KeyboardButton(f"📊 Konkurslar ({active} faol)")],
        [KeyboardButton("📋 Konkurslarni boshqarish")],
        [KeyboardButton("👤 Profilim")],
    ]
    if is_admin(uid):
        kb.append([KeyboardButton("⚙️ Admin Panel")])
    kb.append([KeyboardButton("📢 Kanalimiz")])
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

# ==================== START ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private':
        return
    
    uid = update.effective_user.id
    
    if not await check_sub(uid, context):
        kb = [[InlineKeyboardButton("📢 Kanalga obuna bo'lish", url=f"https://t.me/{CHANNEL[1:]}")],
              [InlineKeyboardButton("✅ Obuna bo'ldim", callback_data="check_sub")]]
        await update.message.reply_text(
            f"⚠️ Botdan foydalanish uchun {CHANNEL} kanaliga obuna bo'ling!",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return
    
    contests = data.get("contests", {})
    active = len([c for c in contests.values() if c.get("status") == "active"])
    finished = len([c for c in contests.values() if c.get("status") == "finished"])
    
    await update.message.reply_text(
        f"👋 Assalomu alaykum, {update.effective_user.first_name}!\n\n"
        f"🏆 Konkurs Bot ga xush kelibsiz!\n\n"
        f"📊 Faol: {active} | Yakunlangan: {finished}\n\n"
        f"🎉 Konkurs yaratish tugmasini bosing.",
        reply_markup=main_menu(uid)
    )

async def check_sub_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if await check_sub(q.from_user.id, context):
        await q.delete_message()
        await start(update, context)
    else:
        await q.answer("❌ Hali obuna bo'lmadingiz!", show_alert=True)

# ==================== KONKURS YARATISH ====================
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private':
        return
    
    uid = update.effective_user.id
    txt = update.message.text.strip()
    
    if not await check_sub(uid, context):
        await update.message.reply_text("❌ Avval kanalga obuna bo'ling!")
        return
    
    # Konkurs yaratish
    if txt == "🎉 Konkurs yaratish":
        context.user_data['creating_contest'] = True
        context.user_data['contest_step'] = 'text'
        await update.message.reply_text("📝 Konkurs matnini yuboring (yoki rasm bilan):")
        return
    
    # Konkurs matni
    if context.user_data.get('contest_step') == 'text':
        context.user_data['contest_text'] = txt
        context.user_data['contest_image'] = None
        context.user_data['contest_step'] = 'button'
        
        kb = [[InlineKeyboardButton("Qatnashish ✅", callback_data="btn_qatnashish")],
              [InlineKeyboardButton("Qo'shilish ➕", callback_data="btn_qoshilish")],
              [InlineKeyboardButton("Ishtirok etish 🎯", callback_data="btn_ishtirok")]]
        await update.message.reply_text("🔘 Ishtirok etish tugmasi uchun matn tanlang:", reply_markup=InlineKeyboardMarkup(kb))
        return
    
    # Konkurslar
    if txt == "📊 Konkurslar (0 faol)" or txt.startswith("📊 Konkurslar"):
        contests = data.get("contests", {})
        active = {k: v for k, v in contests.items() if v.get("status") == "active"}
        if not active:
            await update.message.reply_text("📭 Faol konkurslar yo'q!")
            return
        text = "📊 Faol konkurslar:\n\n"
        for cid, c in active.items():
            parts = data.get("participants", {}).get(cid, [])
            text += f"🏆 #{cid} - {c.get('text', '')[:50]}...\n👥 {len(parts)} ishtirokchi\n\n"
        await update.message.reply_text(text)
        return
    
    if txt == "📋 Konkurslarni boshqarish":
        contests = data.get("contests", {})
        my_contests = {k: v for k, v in contests.items() if str(v.get("creator")) == str(uid)}
        if not my_contests:
            await update.message.reply_text("📭 Sizda konkurslar yo'q!")
            return
        kb = [[InlineKeyboardButton(f"⚙️ #{cid} - {c.get('text', '')[:30]}", callback_data=f"manage_{cid}")] for cid, c in my_contests.items()]
        await update.message.reply_text("📋 Konkurslaringiz:", reply_markup=InlineKeyboardMarkup(kb))
        return
    
    if txt == "👤 Profilim":
        my = len({k: v for k, v in data.get("contests", {}).items() if str(v.get("creator")) == str(uid)})
        won = len([w for w in data.get("winners", {}).values() if str(w) == str(uid)])
        await update.message.reply_text(f"👤 Profil\n\n🎉 Yaratgan: {my}\n🏆 Yutgan: {won}")
        return
    
    if txt == "📢 Kanalimiz":
        await update.message.reply_text(f"📢 {CHANNEL} - bizning kanalimiz!")
        return
    
    # Admin panel
    if txt == "⚙️ Admin Panel" and is_admin(uid):
        contests = data.get("contests", {})
        active = len([c for c in contests.values() if c.get("status") == "active"])
        await update.message.reply_text(
            f"⚙️ Admin Panel\n\n📊 Jami: {len(contests)}\n🟢 Faol: {active}"
        )
        return

# ==================== KONKURS RASMI ====================
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    
    if context.user_data.get('contest_step') == 'text':
        photo = update.message.photo[-1]
        context.user_data['contest_image'] = photo.file_id
        context.user_data['contest_text'] = update.message.caption or "🏆 Konkurs!"
        context.user_data['contest_step'] = 'button'
        
        kb = [[InlineKeyboardButton("Qatnashish ✅", callback_data="btn_qatnashish")],
              [InlineKeyboardButton("Qo'shilish ➕", callback_data="btn_qoshilish")],
              [InlineKeyboardButton("Ishtirok etish 🎯", callback_data="btn_ishtirok")]]
        await update.message.reply_text("🔘 Ishtirok etish tugmasi uchun matn tanlang:", reply_markup=InlineKeyboardMarkup(kb))

# ==================== CALLBACK ====================
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d = q.data
    uid = q.from_user.id
    
    if d == "check_sub":
        await check_sub_callback(update, context)
        return
    
    # Tugma matni
    if d.startswith("btn_"):
        texts = {"btn_qatnashish": "Qatnashish ✅", "btn_qoshilish": "Qo'shilish ➕", "btn_ishtirok": "Ishtirok etish 🎯"}
        context.user_data['button_text'] = texts[d]
        context.user_data['contest_step'] = 'winners'
        
        kb = [[InlineKeyboardButton(str(i), callback_data=f"winners_{i}")] for i in range(1, 6)]
        await q.edit_message_text("🏆 Nechta g'olib bo'lsin? (1-5)", reply_markup=InlineKeyboardMarkup(kb))
        return
    
    # G'oliblar soni
    if d.startswith("winners_"):
        context.user_data['winners_count'] = int(d.replace("winners_", ""))
        context.user_data['contest_step'] = 'duration'
        
        kb = []
        for h in [1, 3, 6, 12, 24, 48, 72, 96]:
            kb.append([InlineKeyboardButton(f"{h} soat", callback_data=f"dur_{h}")])
        await q.edit_message_text("⏰ Konkurs qancha vaqt davom etsin?", reply_markup=InlineKeyboardMarkup(kb))
        return
    
    # Davomiylik
    if d.startswith("dur_"):
        hours = int(d.replace("dur_", ""))
        context.user_data['duration'] = hours
        context.user_data['contest_step'] = 'channel'
        await q.edit_message_text("📢 Konkurs qaysi kanalga tashlansin?\nMasalan: @mychannel")
        return
    
    # Kanal tanlash (keyingi xabar orqali)
    
    # Konkursga qatnashish
    if d.startswith("participate_"):
        cid = d.replace("participate_", "")
        
        if not await check_sub(uid, context):
            await q.answer("❌ Avval kanalga obuna bo'ling!", show_alert=True)
            return
        
        contest = data.get("contests", {}).get(cid)
        if not contest:
            await q.answer("❌ Konkurs topilmadi!", show_alert=True)
            return
        
        if contest.get("status") == "finished":
            await q.answer("❌ Konkurs yakunlangan!", show_alert=True)
            return
        
        parts = data.get("participants", {}).get(cid, [])
        limit = contest.get("limit", 0)
        
        if limit > 0 and len(parts) >= limit:
            await q.answer("❌ Ishtirokchilar limiti to'lgan!", show_alert=True)
            return
        
        if str(uid) in parts:
            await q.answer("⚠️ Allaqachon qo'shilgansiz!", show_alert=True)
            return
        
        data.setdefault("participants", {}).setdefault(cid, []).append(str(uid))
        save()
        await q.answer("✅ Muvaffaqiyatli qo'shildingiz!", show_alert=True)
        return
    
    # Konkursni boshqarish
    if d.startswith("manage_"):
        cid = d.replace("manage_", "")
        contest = data.get("contests", {}).get(cid)
        if not contest:
            await q.answer("❌ Topilmadi!"); return
        
        parts = data.get("participants", {}).get(cid, [])
        kb = [
            [InlineKeyboardButton("🎲 G'oliblarni tanlash", callback_data=f"draw_{cid}")],
            [InlineKeyboardButton("❌ Bekor qilish", callback_data=f"cancel_{cid}")],
        ]
        await q.edit_message_text(
            f"⚙️ Konkurs #{cid}\n\n📝 {contest.get('text', '')[:100]}...\n👥 {len(parts)} ishtirokchi\n🏆 {contest.get('winners', 1)} g'olib",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return
    
    # G'oliblarni tanlash
    if d.startswith("draw_"):
        cid = d.replace("draw_", "")
        contest = data.get("contests", {}).get(cid)
        parts = data.get("participants", {}).get(cid, [])
        
        if not parts:
            await q.answer("❌ Ishtirokchilar yo'q!"); return
        
        winners_count = min(contest.get("winners", 1), len(parts))
        winners = random.sample(parts, winners_count)
        
        data.setdefault("winners", {})[cid] = winners
        data["contests"][cid]["status"] = "finished"
        save()
        
        text = f"🎉 Konkurs #{cid} g'oliblari:\n\n"
        for i, w in enumerate(winners, 1):
            text += f"{i}. 👤 <code>{w}</code>\n"
        
        await q.edit_message_text(text, parse_mode='HTML')
        return
    
    # Bekor qilish
    if d.startswith("cancel_"):
        cid = d.replace("cancel_", "")
        if cid in data.get("contests", {}):
            data["contests"][cid]["status"] = "cancelled"
            save()
        await q.edit_message_text(f"❌ Konkurs #{cid} bekor qilindi!")
        return

# ==================== KANAL TANLASH (xabar orqali) ====================
async def handle_channel_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    
    if context.user_data.get('contest_step') == 'channel':
        channel = update.message.text.strip()
        
        if not channel.startswith("@"):
            await update.message.reply_text("❌ @ belgisi bilan yozing!")
            return
        
        context.user_data['channel'] = channel
        context.user_data['contest_step'] = 'limit'
        
        kb = [[InlineKeyboardButton("Cheksiz ♾️", callback_data="limit_no")],
              [InlineKeyboardButton("Cheklash 🔢", callback_data="limit_yes")]]
        await update.message.reply_text("👥 Ishtirokchilar sonini cheklaymizmi?", reply_markup=InlineKeyboardMarkup(kb))
        return
    
    if context.user_data.get('contest_step') == 'limit_number':
        try:
            limit = int(update.message.text.strip())
            if limit < 1:
                await update.message.reply_text("❌ 1 dan katta raqam kiriting!"); return
            
            context.user_data['limit'] = limit
            await create_contest_final(update, context)
        except:
            await update.message.reply_text("❌ Raqam kiriting!")

async def limit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    if q.data == "limit_no":
        context.user_data['limit'] = 0
        await create_contest_final(update, context)
    else:
        context.user_data['contest_step'] = 'limit_number'
        await q.edit_message_text("👥 Nechta ishtirokchi bo'lsin? Raqam kiriting:")

async def create_contest_final(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    cid = str(len(data.get("contests", {})) + 1)
    
    end_time = datetime.now() + timedelta(hours=context.user_data.get('duration', 24))
    
    contest = {
        "creator": uid,
        "text": context.user_data.get('contest_text', ''),
        "image": context.user_data.get('contest_image'),
        "button_text": context.user_data.get('button_text', 'Qatnashish ✅'),
        "winners": context.user_data.get('winners_count', 1),
        "duration": context.user_data.get('duration', 24),
        "channel": context.user_data.get('channel', '@test'),
        "limit": context.user_data.get('limit', 0),
        "end_time": end_time.strftime("%Y-%m-%d %H:%M:%S"),
        "status": "active",
        "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    data.setdefault("contests", {})[cid] = contest
    save()
    
    # Konkursni kanalga yuborish
    parts_count = len(data.get("participants", {}).get(cid, []))
    button_text = f"{contest['button_text']} ({parts_count})"
    
    kb = [[InlineKeyboardButton(button_text, callback_data=f"participate_{cid}")]]
    
    caption = f"""{contest['text']}

━━━━━━━━━━━━━━━━━
🏆 G'oliblar: {contest['winners']}
⏰ Tugash: {end_time.strftime('%d.%m.%Y %H:%M')}
👥 Ishtirokchilar: {parts_count}/{contest['limit'] if contest['limit'] > 0 else '∞'}"""
    
    try:
        if contest.get('image'):
            await context.bot.send_photo(contest['channel'], contest['image'], caption=caption, reply_markup=InlineKeyboardMarkup(kb))
        else:
            await context.bot.send_message(contest['channel'], caption, reply_markup=InlineKeyboardMarkup(kb))
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                f"✅ Konkurs yaratildi!\n\n📢 {contest['channel']}\n⏰ {end_time.strftime('%d.%m.%Y %H:%M')}\n🏆 {contest['winners']} g'olib\n🆔 #{cid}"
            )
        else:
            await update.message.reply_text(
                f"✅ Konkurs yaratildi!\n\n📢 {contest['channel']}\n⏰ {end_time.strftime('%d.%m.%Y %H:%M')}\n🆔 #{cid}"
            )
    except Exception as e:
        if update.callback_query:
            await update.callback_query.edit_message_text(f"❌ Xatolik! Bot kanalda admin emas!\n{e}")
        else:
            await update.message.reply_text(f"❌ Xatolik! Bot kanalda admin emas!")
    
    context.user_data.clear()

# ==================== MAIN ====================
def main():
    Thread(target=run_flask).start()
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_channel_input))
    application.add_handler(CallbackQueryHandler(check_sub_callback, pattern="^check_sub$"))
    application.add_handler(CallbackQueryHandler(callback_handler, pattern="^btn_"))
    application.add_handler(CallbackQueryHandler(callback_handler, pattern="^winners_"))
    application.add_handler(CallbackQueryHandler(callback_handler, pattern="^dur_"))
    application.add_handler(CallbackQueryHandler(callback_handler, pattern="^participate_"))
    application.add_handler(CallbackQueryHandler(callback_handler, pattern="^manage_"))
    application.add_handler(CallbackQueryHandler(callback_handler, pattern="^draw_"))
    application.add_handler(CallbackQueryHandler(callback_handler, pattern="^cancel_"))
    application.add_handler(CallbackQueryHandler(limit_callback, pattern="^limit_"))
    
    print("✅ Konkurs Bot ishga tushdi!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
