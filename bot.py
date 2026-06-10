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
MAIN_CHANNEL = '@vexronnews'
DATA = "/tmp/konkurs_data.json"

if os.path.exists(DATA):
    with open(DATA) as f: data = json.load(f)
else:
    data = {"contests": {}, "participants": {}, "usernames": {}, "winners": {}, "messages": {}}

def save():
    with open(DATA, 'w') as f: json.dump(data, f, ensure_ascii=False)

async def check_sub(uid, context, channel=None):
    ch = channel or MAIN_CHANNEL
    try:
        member = await context.bot.get_chat_member(ch, uid)
        return member.status not in ['left', 'kicked']
    except:
        return False

async def check_bot_admin(context, channel):
    try:
        member = await context.bot.get_chat_member(channel, context.bot.id)
        return member.status in ['administrator', 'creator']
    except:
        return False

async def update_contest_message(context, contest_id):
    contest = data["contests"].get(contest_id)
    if not contest:
        return
    
    parts = data["participants"].get(contest_id, [])
    limit = contest.get("limit", 0)
    count = len(parts)
    
    bot_username = (await context.bot.get_me()).username
    button_text = f"{contest.get('button_text', 'Qatnashish')} ({count})"
    kb = [[InlineKeyboardButton(button_text, url=f"https://t.me/{bot_username}?start=join_{contest_id}")]]
    
    caption = f"""{contest['text']}

━━━━━━━━━━━━━━━━━
🏆 G'oliblar: {contest['winners']}
⏰ Tugash: {contest.get('end_time', '')}
👥 Ishtirokchilar: {count}/{limit if limit > 0 else '∞'}"""
    
    old_msg = data.get("messages", {}).get(contest_id)
    try:
        if old_msg:
            try:
                await context.bot.delete_message(old_msg["chat_id"], old_msg["message_id"])
            except:
                pass
    except:
        pass
    
    try:
        if contest.get('image'):
            msg = await context.bot.send_photo(contest['channel'], contest['image'], caption=caption, reply_markup=InlineKeyboardMarkup(kb))
        else:
            msg = await context.bot.send_message(contest['channel'], caption, reply_markup=InlineKeyboardMarkup(kb))
        
        data.setdefault("messages", {})[contest_id] = {"chat_id": msg.chat_id, "message_id": msg.message_id}
        save()
    except:
        pass

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
    args = context.args
    
    # Deep link - konkursga qatnashish
    if args and args[0].startswith("join_"):
        contest_id = args[0].replace("join_", "")
        contest = data.get("contests", {}).get(contest_id)
        
        if not contest:
            await update.message.reply_text("❌ Konkurs topilmadi!")
            return
        
        channels_to_check = [MAIN_CHANNEL]
        if contest.get("sub_channel"):
            channels_to_check.append(contest["sub_channel"])
        
        not_subscribed = []
        for ch in channels_to_check:
            if not await check_sub(uid, context, ch):
                not_subscribed.append(ch)
        
        if not_subscribed:
            kb = []
            for ch in not_subscribed:
                kb.append([InlineKeyboardButton(f"📢 {ch} ga obuna bo'lish", url=f"https://t.me/{ch[1:]}")])
            kb.append([InlineKeyboardButton("✅ Obuna bo'ldim", callback_data=f"checksub_{contest_id}")])
            
            channels_text = "\n".join(not_subscribed)
            await update.message.reply_text(
                f"⚠️ Konkursda qatnashish uchun obuna bo'ling:\n\n{channels_text}",
                reply_markup=InlineKeyboardMarkup(kb)
            )
            return
        
        parts = data.get("participants", {}).get(contest_id, [])
        limit = contest.get("limit", 0)
        
        if limit > 0 and len(parts) >= limit:
            await update.message.reply_text("❌ Ishtirokchilar limiti to'lgan!")
            return
        
        if str(uid) in parts:
            await update.message.reply_text("⚠️ Siz allaqachon qatnashgansiz!")
            return
        
        data.setdefault("participants", {}).setdefault(contest_id, []).append(str(uid))
        username = update.effective_user.username or update.effective_user.first_name
        data.setdefault("usernames", {}).setdefault(contest_id, {})[str(uid)] = username
        save()
        
        await update.message.reply_text(f"✅ Siz konkursga qo'shildingiz!\n👥 Jami: {len(parts) + 1}")
        await update_contest_message(context, contest_id)
        return
    
    # Oddiy start
    if not await check_sub(uid, context):
        kb = [[InlineKeyboardButton("📢 Kanalga obuna bo'lish", url=f"https://t.me/{MAIN_CHANNEL[1:]}")],
              [InlineKeyboardButton("✅ Obuna bo'ldim", callback_data="check_sub")]]
        await update.message.reply_text(
            f"⚠️ Botdan foydalanish uchun {MAIN_CHANNEL} kanaliga obuna bo'ling!",
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

# ==================== CALLBACK ====================
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d = q.data
    uid = q.from_user.id
    
    # === OBUNA TEKSHIRISH ===
    if d == "check_sub":
        if await check_sub(uid, context):
            await q.delete_message()
            active = len([c for c in data.get("contests", {}).values() if c.get("status") == "active"])
            await context.bot.send_message(
                uid,
                f"👋 Assalomu alaykum, {q.from_user.first_name}!\n\n"
                f"🏆 Konkurs Bot ga xush kelibsiz!\n\n"
                f"📊 Faol konkurslar: {active} ta\n\n"
                f"🎉 Konkurs yaratish tugmasini bosing!",
                reply_markup=main_menu()
            )
        else:
            await q.answer("❌ Hali obuna bo'lmadingiz!", show_alert=True)
        return
    
    if d.startswith("checksub_"):
        contest_id = d.replace("checksub_", "")
        contest = data.get("contests", {}).get(contest_id)
        
        if not contest:
            await q.answer("❌ Konkurs topilmadi!", show_alert=True)
            return
        
        channels_to_check = [MAIN_CHANNEL]
        if contest.get("sub_channel"):
            channels_to_check.append(contest["sub_channel"])
        
        not_subscribed = []
        for ch in channels_to_check:
            if not await check_sub(uid, context, ch):
                not_subscribed.append(ch)
        
        if not_subscribed:
            await q.answer("❌ Hali obuna bo'lmagansiz!", show_alert=True)
            return
        
        # Qatnashish
        parts = data.get("participants", {}).get(contest_id, [])
        limit = contest.get("limit", 0)
        
        if limit > 0 and len(parts) >= limit:
            await q.answer("❌ Limit to'lgan!", show_alert=True)
            return
        
        if str(uid) in parts:
            await q.answer("⚠️ Allaqachon qatnashgansiz!", show_alert=True)
            return
        
        data.setdefault("participants", {}).setdefault(contest_id, []).append(str(uid))
        username = q.from_user.username or q.from_user.first_name
        data.setdefault("usernames", {}).setdefault(contest_id, {})[str(uid)] = username
        save()
        
        await q.answer("✅ Muvaffaqiyatli qo'shildingiz!", show_alert=True)
        await update_contest_message(context, contest_id)
        return
    
    # === KONKURS YARATISH ===
    if d.startswith("btn_"):
        texts = {"btn_1": "Qatnashish ✅", "btn_2": "Qo'shilish ➕", "btn_3": "Ishtirok etish 🎯"}
        context.user_data['button_text'] = texts[d]
        context.user_data['step'] = 'winners'
        kb = [[InlineKeyboardButton(str(i), callback_data=f"win_{i}")] for i in range(1, 6)]
        await q.edit_message_text("🏆 Nechta g'olib bo'lsin?", reply_markup=InlineKeyboardMarkup(kb))
        return
    
    if d.startswith("win_"):
        context.user_data['winners'] = int(d.replace("win_", ""))
        context.user_data['step'] = 'hours'
        kb = [[InlineKeyboardButton(f"{h} soat", callback_data=f"hr_{h}")] for h in [1, 3, 6, 12, 24, 48, 72, 96]]
        await q.edit_message_text("⏰ Qancha vaqt davom etsin?", reply_markup=InlineKeyboardMarkup(kb))
        return
    
    if d.startswith("hr_"):
        context.user_data['hours'] = int(d.replace("hr_", ""))
        context.user_data['step'] = 'channel'
        await q.edit_message_text("📢 Konkurs qaysi kanalga?\n\nKanal username sini yozing:\nMasalan: @mychannel")
        return
    
    if d == "sub_yes":
        context.user_data['step'] = 'sub_channel_input'
        await q.edit_message_text("🔒 Qaysi kanalga obuna bo'lishi kerak?\n\nKanal username sini yozing:")
        return
    
    if d == "sub_no":
        context.user_data['sub_channel'] = None
        kb = [[InlineKeyboardButton("Cheksiz ♾️", callback_data="limit_0")],
              [InlineKeyboardButton("Cheklash 🔢", callback_data="limit_set")]]
        await q.edit_message_text("👥 Ishtirokchilar sonini cheklaymizmi?", reply_markup=InlineKeyboardMarkup(kb))
        return
    
    if d == "limit_0":
        context.user_data['limit'] = 0
        await publish_contest(update, context)
        return
    
    if d == "limit_set":
        context.user_data['step'] = 'limit'
        await q.edit_message_text("👥 Nechta ishtirokchi bo'lsin? Raqam kiriting:")
        return
    
    if d.startswith("manage_"):
        cid = d.replace("manage_", "")
        contest = data.get("contests", {}).get(cid)
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
    
    if d.startswith("draw_"):
        cid = d.replace("draw_", "")
        parts = data.get("participants", {}).get(cid, [])
        if not parts:
            await q.answer("❌ Ishtirokchilar yo'q!"); return
        
        winners_count = min(data["contests"][cid].get("winners", 1), len(parts))
        winner_ids = random.sample(parts, winners_count)
        
        winner_names = []
        for w in winner_ids:
            name = data.get("usernames", {}).get(cid, {}).get(w, w)
            winner_names.append(f"@{name}" if not name.startswith("@") else name)
        
        data.setdefault("winners", {})[cid] = winner_ids
        data["contests"][cid]["status"] = "finished"
        save()
        
        text = f"🎉 Konkurs #{cid} g'oliblari:\n\n"
        for i, name in enumerate(winner_names, 1):
            text += f"{i}. 👤 {name}\n"
        await q.edit_message_text(text)
        return
    
    if d.startswith("cancel_"):
        cid = d.replace("cancel_", "")
        if cid in data.get("contests", {}):
            data["contests"][cid]["status"] = "cancelled"
            save()
        await q.edit_message_text(f"❌ Konkurs #{cid} bekor qilindi!")
        return

# ==================== HANDLE TEXT ====================
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private':
        return
    
    uid = update.effective_user.id
    txt = update.message.text.strip()
    
    if not await check_sub(uid, context):
        await update.message.reply_text("❌ Avval kanalga obuna bo'ling! /start")
        return
    
    if txt == "🎉 Konkurs yaratish":
        context.user_data['creating'] = True
        context.user_data['step'] = 'text'
        await update.message.reply_text("📝 Konkurs matnini yuboring (yoki rasm yuboring):")
        return
    
    if context.user_data.get('step') == 'text':
        context.user_data['contest_text'] = txt
        context.user_data['contest_image'] = None
        context.user_data['step'] = 'button'
        kb = [[InlineKeyboardButton("Qatnashish ✅", callback_data="btn_1")],
              [InlineKeyboardButton("Qo'shilish ➕", callback_data="btn_2")],
              [InlineKeyboardButton("Ishtirok etish 🎯", callback_data="btn_3")]]
        await update.message.reply_text("🔘 Ishtirok tugmasi matnini tanlang:", reply_markup=InlineKeyboardMarkup(kb))
        return
    
    if context.user_data.get('step') == 'channel':
        channel = txt.strip()
        if not channel.startswith("@"):
            await update.message.reply_text("❌ @ bilan boshlanishi kerak!"); return
        
        if not await check_bot_admin(context, channel):
            await update.message.reply_text(f"❌ Bot {channel} da admin emas!\n\nAvval botni kanalga ADMIN qiling!")
            return
        
        context.user_data['channel'] = channel
        context.user_data['step'] = 'sub_channel'
        kb = [[InlineKeyboardButton("✅ Ha", callback_data="sub_yes")],
              [InlineKeyboardButton("❌ Yo'q", callback_data="sub_no")]]
        await update.message.reply_text("🔒 Majburiy obuna qo'shamizmi?", reply_markup=InlineKeyboardMarkup(kb))
        return
    
    if context.user_data.get('step') == 'sub_channel_input':
        sub_ch = txt.strip()
        if not sub_ch.startswith("@"):
            await update.message.reply_text("❌ @ bilan boshlanishi kerak!"); return
        context.user_data['sub_channel'] = sub_ch
        kb = [[InlineKeyboardButton("Cheksiz ♾️", callback_data="limit_0")],
              [InlineKeyboardButton("Cheklash 🔢", callback_data="limit_set")]]
        await update.message.reply_text("👥 Ishtirokchilar sonini cheklaymizmi?", reply_markup=InlineKeyboardMarkup(kb))
        return
    
    if context.user_data.get('step') == 'limit':
        try:
            limit = int(txt)
            if limit < 1:
                await update.message.reply_text("❌ 1 dan katta raqam kiriting!"); return
            context.user_data['limit'] = limit
            await publish_contest(update, context)
        except:
            await update.message.reply_text("❌ Raqam kiriting!")
        return
    
    if txt == "📊 Faol konkurslar":
        contests = data.get("contests", {})
        active = {k: v for k, v in contests.items() if v.get("status") == "active"}
        if not active:
            await update.message.reply_text("📭 Faol konkurslar yo'q!"); return
        
        bot_username = (await context.bot.get_me()).username
        for cid, c in active.items():
            parts = data.get("participants", {}).get(cid, [])
            limit = c.get("limit", 0)
            button_text = f"{c.get('button_text', 'Qatnashish')} ({len(parts)})"
            kb = [[InlineKeyboardButton(button_text, url=f"https://t.me/{bot_username}?start=join_{cid}")]]
            text = f"{c.get('text', '')}\n\n🏆 G'oliblar: {c.get('winners', 1)}\n👥 Ishtirokchilar: {len(parts)}/{limit if limit > 0 else '∞'}\n⏰ {c.get('end_time', '')}"
            
            try:
                if c.get('image'):
                    await update.message.reply_photo(c['image'], caption=text, reply_markup=InlineKeyboardMarkup(kb))
                else:
                    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb))
            except:
                pass
        return
    
    if txt == "📋 Mening konkurslarim":
        my = {k: v for k, v in data.get("contests", {}).items() if str(v.get("creator")) == str(uid)}
        if not my:
            await update.message.reply_text("📭 Sizda konkurslar yo'q!"); return
        kb = [[InlineKeyboardButton(f"⚙️ #{cid}", callback_data=f"manage_{cid}")] for cid in my]
        await update.message.reply_text("📋 Konkurslaringiz:", reply_markup=InlineKeyboardMarkup(kb))
        return
    
    if txt == "👤 Profilim":
        my = len({k: v for k, v in data.get("contests", {}).items() if str(v.get("creator")) == str(uid)})
        await update.message.reply_text(f"👤 Profil\n\n🎉 Yaratgan: {my} ta")
        return
    
    if txt == "📢 Kanalimiz":
        await update.message.reply_text(f"📢 {MAIN_CHANNEL} - bizning kanalimiz!")

# ==================== RASM ====================
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

async def publish_contest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id if update.effective_user else update.callback_query.from_user.id
    
    cid = str(len(data.get("contests", {})) + 1)
    end_time = datetime.now() + timedelta(hours=context.user_data.get('hours', 24))
    
    contest = {
        "creator": uid, "text": context.user_data.get('contest_text', ''),
        "image": context.user_data.get('contest_image'),
        "button_text": context.user_data.get('button_text', 'Qatnashish ✅'),
        "winners": context.user_data.get('winners', 1),
        "hours": context.user_data.get('hours', 24),
        "channel": context.user_data.get('channel', '@test'),
        "sub_channel": context.user_data.get('sub_channel'),
        "limit": context.user_data.get('limit', 0),
        "end_time": end_time.strftime("%Y-%m-%d %H:%M:%S"),
        "status": "active", "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    data.setdefault("contests", {})[cid] = contest
    data.setdefault("participants", {})[cid] = []
    save()
    
    bot_username = (await context.bot.get_me()).username
    button_text = f"{contest['button_text']} (0)"
    kb = [[InlineKeyboardButton(button_text, url=f"https://t.me/{bot_username}?start=join_{cid}")]]
    
    caption = f"""{contest['text']}

━━━━━━━━━━━━━━━━━
🏆 G'oliblar: {contest['winners']}
⏰ Tugash: {end_time.strftime('%d.%m.%Y %H:%M')}
👥 Ishtirokchilar: 0/{contest['limit'] if contest['limit'] > 0 else '∞'}"""
    
    try:
        if contest.get('image'):
            msg = await context.bot.send_photo(contest['channel'], contest['image'], caption=caption, reply_markup=InlineKeyboardMarkup(kb))
        else:
            msg = await context.bot.send_message(contest['channel'], caption, reply_markup=InlineKeyboardMarkup(kb))
        
        data.setdefault("messages", {})[cid] = {"chat_id": msg.chat_id, "message_id": msg.message_id}
        save()
        
        if update.callback_query:
            await update.callback_query.edit_message_text(f"✅ Konkurs #{cid} yaratildi!")
        else:
            await update.message.reply_text(f"✅ Konkurs #{cid} yaratildi!")
    except:
        if update.callback_query:
            await update.callback_query.edit_message_text("❌ Xatolik! Bot kanalda admin emas!")
        else:
            await update.message.reply_text("❌ Xatolik! Bot kanalda admin emas!")
    
    context.user_data.clear()

# ==================== MAIN ====================
def main():
    Thread(target=run_flask).start()
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(CallbackQueryHandler(callback_handler))
    
    print("✅ Konkurs Bot ishga tushdi!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
