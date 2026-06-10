import json
import os
import asyncio
import random
from datetime import datetime, timedelta
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
CHANNEL = '@vexronnews'
ADMIN_ID = 8306639956
DATA = "/tmp/konkurs_data.json"

if os.path.exists(DATA):
    with open(DATA) as f: data = json.load(f)
else:
    data = {"contests": {}, "participants": {}, "winners": {}}

def save():
    with open(DATA, 'w') as f: json.dump(data, f, ensure_ascii=False)

async def check_sub(uid, context):
    try:
        member = await context.bot.get_chat_member(CHANNEL, uid)
        return member.status not in ['left', 'kicked']
    except:
        return False

def main_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🎉 Konkurs yaratish")],
        [KeyboardButton("📊 Faol konkurslar"), KeyboardButton("📋 Mening konkurslarim")],
        [KeyboardButton("👤 Profilim"), KeyboardButton("📢 Kanalimiz")],
    ], resize_keyboard=True)

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
    
    active = len([c for c in data.get("contests", {}).values() if c.get("status") == "active"])
    
    await update.message.reply_text(
        f"👋 Assalomu alaykum, {update.effective_user.first_name}!\n\n"
        f"🏆 Konkurs Bot ga xush kelibsiz!\n\n"
        f"📊 Faol konkurslar: {active} ta\n\n"
        f"🎉 Konkurs yaratish tugmasini bosing!",
        reply_markup=main_menu()
    )

async def check_sub_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if await check_sub(q.from_user.id, context):
        await q.delete_message()
        await start(update, context)
    else:
        await q.answer("❌ Hali obuna bo'lmadingiz!", show_alert=True)

# ==================== HANDLE TEXT ====================
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private':
        return
    
    uid = update.effective_user.id
    txt = update.message.text.strip()
    
    if not await check_sub(uid, context):
        await update.message.reply_text("❌ Avval kanalga obuna bo'ling! /start")
        return
    
    # KONKURS YARATISH
    if txt == "🎉 Konkurs yaratish":
        context.user_data['creating'] = True
        context.user_data['step'] = 'text'
        await update.message.reply_text("📝 Konkurs matnini yuboring (yoki rasm yuboring):")
        return
    
    # Konkurs matni
    if context.user_data.get('step') == 'text':
        context.user_data['contest_text'] = txt
        context.user_data['contest_image'] = None
        context.user_data['step'] = 'button'
        
        kb = [[InlineKeyboardButton("Qatnashish ✅", callback_data="btn_1")],
              [InlineKeyboardButton("Qo'shilish ➕", callback_data="btn_2")],
              [InlineKeyboardButton("Ishtirok etish 🎯", callback_data="btn_3")]]
        await update.message.reply_text("🔘 Ishtirok tugmasi matnini tanlang:", reply_markup=InlineKeyboardMarkup(kb))
        return
    
    # Kanal nomi
    if context.user_data.get('step') == 'channel':
        channel = txt.strip()
        if not channel.startswith("@"):
            await update.message.reply_text("❌ @ bilan boshlanishi kerak! Masalan: @mychannel")
            return
        
        context.user_data['channel'] = channel
        
        # Limit
        kb = [[InlineKeyboardButton("Cheksiz ♾️", callback_data="limit_0")],
              [InlineKeyboardButton("Cheklash 🔢", callback_data="limit_set")]]
        await update.message.reply_text("👥 Ishtirokchilar sonini cheklaymizmi?", reply_markup=InlineKeyboardMarkup(kb))
        return
    
    # Limit raqami
    if context.user_data.get('step') == 'limit':
        try:
            limit = int(txt)
            if limit < 1:
                await update.message.reply_text("❌ 1 dan katta raqam kiriting!")
                return
            context.user_data['limit'] = limit
            await publish_contest(update, context)
        except:
            await update.message.reply_text("❌ Raqam kiriting!")
        return
    
    # Faol konkurslar
    if txt == "📊 Faol konkurslar":
        contests = data.get("contests", {})
        active = {k: v for k, v in contests.items() if v.get("status") == "active"}
        if not active:
            await update.message.reply_text("📭 Faol konkurslar yo'q!")
            return
        
        for cid, c in active.items():
            parts = data.get("participants", {}).get(cid, [])
            limit = c.get("limit", 0)
            button_text = f"{c.get('button_text', 'Qatnashish')} ({len(parts)})"
            
            kb = [[InlineKeyboardButton(button_text, callback_data=f"join_{cid}")]]
            
            text = f"{c.get('text', '')}\n\n━━━━━━━━━━\n🏆 G'oliblar: {c.get('winners', 1)}\n👥 Ishtirokchilar: {len(parts)}/{limit if limit > 0 else '∞'}\n⏰ {c.get('end_time', '')}"
            
            try:
                if c.get('image'):
                    await update.message.reply_photo(c['image'], caption=text, reply_markup=InlineKeyboardMarkup(kb))
                else:
                    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb))
            except:
                pass
        return
    
    # Mening konkurslarim
    if txt == "📋 Mening konkurslarim":
        my = {k: v for k, v in data.get("contests", {}).items() if str(v.get("creator")) == str(uid)}
        if not my:
            await update.message.reply_text("📭 Sizda konkurslar yo'q!")
            return
        
        kb = [[InlineKeyboardButton(f"⚙️ #{cid}", callback_data=f"manage_{cid}")] for cid in my]
        await update.message.reply_text("📋 Konkurslaringiz:", reply_markup=InlineKeyboardMarkup(kb))
        return
    
    if txt == "👤 Profilim":
        my = len({k: v for k, v in data.get("contests", {}).items() if str(v.get("creator")) == str(uid)})
        await update.message.reply_text(f"👤 Profil\n\n🎉 Yaratgan: {my} ta")
        return
    
    if txt == "📢 Kanalimiz":
        await update.message.reply_text(f"📢 {CHANNEL} - bizning kanalimiz!")

# ==================== RASM QABUL ====================
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    
    if context.user_data.get('step') == 'text':
        photo = update.message.photo[-1]
        context.user_data['contest_image'] = photo.file_id
        context.user_data['contest_text'] = update.message.caption or "🏆 Konkurs!"
        context.user_data['step'] = 'button'
        
        kb = [[InlineKeyboardButton("Qatnashish ✅", callback_data="btn_1")],
              [InlineKeyboardButton("Qo'shilish ➕", callback_data="btn_2")],
              [InlineKeyboardButton("Ishtirok etish 🎯", callback_data="btn_3")]]
        await update.message.reply_text("🔘 Ishtirok tugmasi matnini tanlang:", reply_markup=InlineKeyboardMarkup(kb))

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
        texts = {"btn_1": "Qatnashish ✅", "btn_2": "Qo'shilish ➕", "btn_3": "Ishtirok etish 🎯"}
        context.user_data['button_text'] = texts[d]
        context.user_data['step'] = 'winners'
        
        kb = [[InlineKeyboardButton(str(i), callback_data=f"win_{i}")] for i in range(1, 6)]
        await q.edit_message_text("🏆 Nechta g'olib bo'lsin?", reply_markup=InlineKeyboardMarkup(kb))
        return
    
    # G'oliblar
    if d.startswith("win_"):
        context.user_data['winners'] = int(d.replace("win_", ""))
        context.user_data['step'] = 'hours'
        
        kb = [[InlineKeyboardButton(f"{h} soat", callback_data=f"hr_{h}")] for h in [1, 3, 6, 12, 24, 48]]
        await q.edit_message_text("⏰ Qancha vaqt davom etsin?", reply_markup=InlineKeyboardMarkup(kb))
        return
    
    # Vaqt
    if d.startswith("hr_"):
        context.user_data['hours'] = int(d.replace("hr_", ""))
        context.user_data['step'] = 'channel'
        await q.edit_message_text("📢 Konkurs qaysi kanalga?\n\nKanal username sini yozing:\nMasalan: @mychannel")
        return
    
    # Limit
    if d == "limit_0":
        context.user_data['limit'] = 0
        await publish_contest(update, context)
        return
    
    if d == "limit_set":
        context.user_data['step'] = 'limit'
        await q.edit_message_text("👥 Nechta ishtirokchi bo'lsin? Raqam kiriting:")
        return
    
    # Konkursga qo'shilish
    if d.startswith("join_"):
        cid = d.replace("join_", "")
        
        if not await check_sub(uid, context):
            await q.answer("❌ Avval kanalga obuna bo'ling!", show_alert=True)
            return
        
        contest = data.get("contests", {}).get(cid)
        if not contest:
            await q.answer("❌ Topilmadi!"); return
        
        parts = data.get("participants", {}).get(cid, [])
        limit = contest.get("limit", 0)
        
        if limit > 0 and len(parts) >= limit:
            await q.answer("❌ Limit to'lgan!", show_alert=True)
            return
        
        if str(uid) in parts:
            await q.answer("⚠️ Allaqachon qo'shilgansiz!", show_alert=True)
            return
        
        data.setdefault("participants", {}).setdefault(cid, []).append(str(uid))
        save()
        await q.answer("✅ Muvaffaqiyatli qo'shildingiz!", show_alert=True)
        return
    
    # Boshqarish
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
            f"⚙️ Konkurs #{cid}\n\n👥 Ishtirokchilar: {len(parts)}\n🏆 G'oliblar: {contest.get('winners', 1)}",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return
    
    # G'oliblarni tanlash
    if d.startswith("draw_"):
        cid = d.replace("draw_", "")
        parts = data.get("participants", {}).get(cid, [])
        
        if not parts:
            await q.answer("❌ Ishtirokchilar yo'q!"); return
        
        winners_count = min(data["contests"][cid].get("winners", 1), len(parts))
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

async def publish_contest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id if update.effective_user else update.callback_query.from_user.id
    
    cid = str(len(data.get("contests", {})) + 1)
    end_time = datetime.now() + timedelta(hours=context.user_data.get('hours', 24))
    
    contest = {
        "creator": uid,
        "text": context.user_data.get('contest_text', ''),
        "image": context.user_data.get('contest_image'),
        "button_text": context.user_data.get('button_text', 'Qatnashish ✅'),
        "winners": context.user_data.get('winners', 1),
        "hours": context.user_data.get('hours', 24),
        "channel": context.user_data.get('channel', '@test'),
        "limit": context.user_data.get('limit', 0),
        "end_time": end_time.strftime("%Y-%m-%d %H:%M:%S"),
        "status": "active",
        "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    data.setdefault("contests", {})[cid] = contest
    data.setdefault("participants", {})[cid] = []
    save()
    
    parts_count = 0
    button_text = f"{contest['button_text']} ({parts_count})"
    kb = [[InlineKeyboardButton(button_text, callback_data=f"join_{cid}")]]
    
    caption = f"""{contest['text']}

━━━━━━━━━━━━━━━━━
🏆 G'oliblar: {contest['winners']}
⏰ Tugash: {end_time.strftime('%d.%m.%Y %H:%M')}
👥 Ishtirokchilar: 0/{contest['limit'] if contest['limit'] > 0 else '∞'}"""
    
    try:
        if contest.get('image'):
            await context.bot.send_photo(contest['channel'], contest['image'], caption=caption, reply_markup=InlineKeyboardMarkup(kb))
        else:
            await context.bot.send_message(contest['channel'], caption, reply_markup=InlineKeyboardMarkup(kb))
        
        if update.callback_query:
            await update.callback_query.edit_message_text(f"✅ Konkurs #{cid} yaratildi va {contest['channel']} ga yuborildi!")
        else:
            await update.message.reply_text(f"✅ Konkurs #{cid} yaratildi va {contest['channel']} ga yuborildi!")
    except Exception as e:
        if update.callback_query:
            await update.callback_query.edit_message_text(f"❌ Xatolik! Bot {contest['channel']} da admin emas!")
        else:
            await update.message.reply_text(f"❌ Xatolik! Bot {contest['channel']} da admin emas!")
    
    context.user_data.clear()

# ==================== MAIN ====================
def main():
    Thread(target=run_flask).start()
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(CallbackQueryHandler(check_sub_callback, pattern="^check_sub$"))
    application.add_handler(CallbackQueryHandler(callback_handler, pattern="^btn_"))
    application.add_handler(CallbackQueryHandler(callback_handler, pattern="^win_"))
    application.add_handler(CallbackQueryHandler(callback_handler, pattern="^hr_"))
    application.add_handler(CallbackQueryHandler(callback_handler, pattern="^limit_"))
    application.add_handler(CallbackQueryHandler(callback_handler, pattern="^join_"))
    application.add_handler(CallbackQueryHandler(callback_handler, pattern="^manage_"))
    application.add_handler(CallbackQueryHandler(callback_handler, pattern="^draw_"))
    application.add_handler(CallbackQueryHandler(callback_handler, pattern="^cancel_"))
    
    print("✅ Konkurs Bot ishga tushdi!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
