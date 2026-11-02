import asyncio
import json
import logging
import os
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

# --- PYTHON 3.14+ EVENT LOOP FIX ---
try:
    loop = asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

from pyrogram import Client, filters
from pyrogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- BOSH LANG'ICH SOZLAMALAR ---
API_ID = 37881267
API_HASH = "fd1edeb73b34fa0955df2a06f31620fd"
BOT_TOKEN = "9214605810:AAEqIRIy93JA0qk4k792iRnTpq9ItO8quk4"
STRING_SESSION = "SIZNING_STRING_SESSION_KODINGIZ"

MAIN_ADMIN_ID = 8660278027 # Telegram ID'ingiz

BOT_CONFIG = {
    "channel_username": "siznin_kanaliniz",
    "keywords": ["Nukus", "Kungrad", "Kegeyli", "Shimbay"],
    "auto_boost": True,
    "check_interval_minutes": 15,
    "smm_url": "https://smm-panel-provider.com/api/v2",  # SMM API URL
    "smm_key": "YOUR_SMM_API_KEY",                        # SMM API KEY
    "smm_service_id": "123",                             # SERVICE ID
    "smm_amount": 1000                                   # Avto-boost standart soni
}

PREVIOUS_POSITIONS = {}
USERS_FILE = "users.json"

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_users(users_data):
    with open(USERS_FILE, "w") as f:
        json.dump(users_data, f, indent=4)

users_db = load_users()
user_states = {}

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK - Search Booster Bot Active")

def run_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

bot = Client("search_bot_app", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
userbot = Client("userbot_app", api_id=API_ID, api_hash=API_HASH, session_string=STRING_SESSION) if STRING_SESSION != "SIZNING_STRING_SESSION_KODINGIZ" else None

def send_smm_boost(custom_amount=None):
    try:
        amount = custom_amount if custom_amount else BOT_CONFIG["smm_amount"]
        payload = {
            "key": BOT_CONFIG["smm_key"],
            "action": "add",
            "service": BOT_CONFIG["smm_service_id"],
            "link": f"https://t.me/{BOT_CONFIG['channel_username']}",
            "quantity": amount
        }
        res = requests.post(BOT_CONFIG["smm_url"], data=payload, timeout=10)
        return res.json()
    except Exception as e:
        logger.error(f"SMM API Error: {e}")
        return None

async def check_search_position(keyword):
    if not userbot:
        return None
    pos = 1
    async for dialog in userbot.search_global(keyword, limit=20):
        chat = dialog.chat if hasattr(dialog, 'chat') else dialog
        if chat.username and chat.username.lower() == BOT_CONFIG["channel_username"].lower():
            return pos
        pos += 1
    return 0

async def run_full_check(notify_user=False, target_chat_id=None):
    report = "<b>📊 QIDIRUV NATIJALARI:</b>\n\n"
    boost_needed = False
    
    for kw in BOT_CONFIG["keywords"]:
        pos = await check_search_position(kw)
        prev_pos = PREVIOUS_POSITIONS.get(kw, None)
        
        if pos and pos > 0:
            report += f"• <b>{kw}</b>: {pos}-o'rinda\n"
            if pos == 1 and prev_pos != 1 and target_chat_id:
                try:
                    await bot.send_message(
                        target_chat_id, 
                        f"🎉 <b>Tabriklaymiz!</b> Kanalingiz '<code>{kw}</code>' kalit so'zi bo'yicha <b>1-O'RINGA</b> ko'tarildi! 🚀"
                    )
                except Exception as e:
                    logger.error(f"Xabar yuborishda xato: {e}")
                    
            if pos > 3:
                boost_needed = True
        else:
            report += f"• <b>{kw}</b>: Top-20 talikda yo'q!\n"
            boost_needed = True
            
        PREVIOUS_POSITIONS[kw] = pos

    if boost_needed:
        if BOT_CONFIG["auto_boost"]:
            send_smm_boost()
            report += f"\n🚀 <b>Avto-boost Ishladi:</b> SMM zakaz ({BOT_CONFIG['smm_amount']} ta) yuborildi!"
            if notify_user and target_chat_id:
                try:
                    await bot.send_message(
                        target_chat_id,
                        f"⚠️ <b>OGOHLANTIRISH!</b>\n\n"
                        f"Kanalingiz pozitsiyasi top-3 dan tushib ketdi. Hozir avto-boost ({BOT_CONFIG['smm_amount']} ta) yuborildi! 🛠🚀"
                    )
                except Exception as e:
                    logger.error(f"Xabar yuborishda xato: {e}")
        else:
            report += "\n⚠️ <b>Ogohlantirish:</b> Pozitsiya tushgan, lekin Auto 24/7 rejimi O'CHIRILGAN!"
    else:
        report += "\n✅ Kanal barcha kalit so'zlar bo'yicha TOP-3 talikda!"

    return report

async def auto_monitor_loop():
    while True:
        await asyncio.sleep(BOT_CONFIG["check_interval_minutes"] * 60)
        if userbot:
            for u, data in users_db.items():
                tg_id = data.get("telegram_id")
                if tg_id:
                    await run_full_check(notify_user=True, target_chat_id=tg_id)

def is_logged_in(user_id):
    if user_id == MAIN_ADMIN_ID:
        return True
    for u, data in users_db.items():
        if data.get("telegram_id") == user_id:
            return True
    return False

def main_keyboard(user_id):
    kb = [
        [KeyboardButton("🔍 Qidiruvni tekshirish"), KeyboardButton("🚀 Boost qilish")],
        [KeyboardButton("⚙️ Sozlamalar"), KeyboardButton("📊 Status")]
    ]
    if user_id == MAIN_ADMIN_ID:
        kb.append([KeyboardButton("👤 Login yaratish")])
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

@bot.on_message(filters.command("start"))
async def start_cmd(client: Client, message: Message):
    user_id = message.from_user.id
    if not is_logged_in(user_id):
        await message.reply_text(
            "<b>Assalomu alaykum!</b>\n\n"
            "Botdan foydalanish uchun tizimga kirishingiz kerak.\n"
            "Loginingiz bo'lsa /login buyrug'ini bosing.\n"
            "<i>(Login va parol yo'q bo'lsa, Bosh Adminga murojaat qiling).</i>"
        )
        return

    await message.reply_text(
        f"<b>Telegram Search Booster Bot Faol!</b>\n\n"
        f"📢 Kanal: @{BOT_CONFIG['channel_username']}\n"
        f"🔑 Kalitlar: {', '.join(BOT_CONFIG['keywords'])}\n"
        f"🔢 Avto-boost miqdori: {BOT_CONFIG['smm_amount']} ta\n"
        f"🔄 Auto 24/7: {'✅ Yoqilgan' if BOT_CONFIG['auto_boost'] else '❌ O_chirilgan'}\n"
        f"⏱ Interval: Har {BOT_CONFIG['check_interval_minutes']} daqiqada",
        reply_markup=main_keyboard(user_id)
    )

@bot.on_message(filters.command("login"))
async def login_cmd(client: Client, message: Message):
    user_id = message.from_user.id
    if is_logged_in(user_id):
        await message.reply_text("Siz allaqachon tizimga kirgansiz!")
        return
    user_states[user_id] = {"step": "awaiting_login"}
    await message.reply_text("🔑 Loginingizni kiriting:")

@bot.on_message(filters.regex("👤 Login yaratish") | filters.command("create_user"))
async def create_user_start(client: Client, message: Message):
    if message.from_user.id != MAIN_ADMIN_ID:
        await message.reply_text("⚠️ Bu buyruq faqat Bosh Admin uchun!")
        return
    user_states[MAIN_ADMIN_ID] = {"step": "admin_new_username"}
    await message.reply_text("👤 Yangi foydalanuvchi uchun **Login** kiriting:")

@bot.on_message(filters.text & ~filters.command(["start", "login", "create_user"]))
async def text_handler(client: Client, message: Message):
    user_id = message.from_user.id
    text = message.text.strip()

    if user_id == MAIN_ADMIN_ID and user_id in user_states:
        state = user_states[user_id].get("step")
        if state == "admin_new_username":
            user_states[user_id]["new_user"] = text
            user_states[user_id]["step"] = "admin_new_password"
            await message.reply_text(f"Login: <b>{text}</b> saqlandi.\nEndi **Parol** kiriting:")
            return
        elif state == "admin_new_password":
            new_user = user_states[user_id]["new_user"]
            users_db[new_user] = {"password": text, "telegram_id": None}
            save_users(users_db)
            del user_states[user_id]
            await message.reply_text(f"✅ Muvaffaqiyatli yaratildi!\n\n👤 Login: <code>{new_user}</code>\n🔑 Parol: <code>{text}</code>")
            return

    if user_id in user_states:
        state = user_states[user_id].get("step")
        if state == "awaiting_login":
            if text in users_db:
                user_states[user_id]["try_login"] = text
                user_states[user_id]["step"] = "awaiting_password"
                await message.reply_text("🔑 Endi Parolni kiriting:")
            else:
                await message.reply_text("❌ Bunday login topilmadi. Qaytadan urining.")
            return
        elif state == "awaiting_password":
            try_login = user_states[user_id]["try_login"]
            if users_db[try_login]["password"] == text:
                users_db[try_login]["telegram_id"] = user_id
                save_users(users_db)
                del user_states[user_id]
                await message.reply_text("🎉 Tizimga muvaffaqiyatli kirdingiz!", reply_markup=main_keyboard(user_id))
            else:
                await message.reply_text("❌ Parol noto'g'ri! Qaytadan kiriting:")
            return
        elif state == "set_channel":
            BOT_CONFIG["channel_username"] = text.replace("@", "")
            del user_states[user_id]
            await message.reply_text(f"✅ Kanal kiritildi: @{BOT_CONFIG['channel_username']}")
            return
        elif state == "set_keywords":
            keywords_list = [kw.strip() for kw in text.split(",")]
            BOT_CONFIG["keywords"] = keywords_list
            del user_states[user_id]
            await message.reply_text(f"✅ Kalit so'zlar yangilandi: {', '.join(keywords_list)}")
            return
        elif state == "manual_boost_amount":
            if text.isdigit():
                amount = int(text)
                del user_states[user_id]
                send_smm_boost(custom_amount=amount)
                await message.reply_text(f"🚀 **SMM Panel'ga {amount} ta boost buyurtmasi yuborildi!**")
            else:
                await message.reply_text("❌ Iltimos, faqat raqam kiriting (masalan: `500` yoki `1000`):")
            return
        elif state == "set_smm_api":
            try:
                parts = [p.strip() for p in text.split("\n")]
                if len(parts) >= 3:
                    BOT_CONFIG["smm_url"] = parts[0]
                    BOT_CONFIG["smm_key"] = parts[1]
                    BOT_CONFIG["smm_service_id"] = parts[2]
                    del user_states[user_id]
                    await message.reply_text("✅ SMM API ma'lumotlari saqlandi!")
                else:
                    await message.reply_text("❌ Format noto'g'ri. 3 qatorda yuboring!")
            except Exception as e:
                await message.reply_text(f"Xatolik: {e}")
            return

    if not is_logged_in(user_id):
        await message.reply_text("⚠️ Avval /login buyrug'i orqali tizimga kiring.")
        return

    if text == "🔍 Qidiruvni tekshirish":
        if not userbot:
            await message.reply_text("⚠️ Userbot ulanmagan! (STRING_SESSION kiriting).")
            return
        msg = await message.reply_text("🔎 Qidiruv tahlil qilinmoqda...")
        report = await run_full_check(notify_user=False)
        await msg.edit_text(report)

    elif text == "🚀 Boost qilish":
        auto_status_btn = "🟢 Auto 24/7 (FAOL)" if BOT_CONFIG["auto_boost"] else "🔴 Auto 24/7 (O'CHIK)"
        inline_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(auto_status_btn, callback_data="toggle_auto_247")],
            [InlineKeyboardButton("✋ Qo'lda berish", callback_data="start_manual_boost")]
        ])
        await message.reply_text("<b>🚀 Boost Rejimini Tanlang:</b>", reply_markup=inline_kb)

    elif text == "📊 Status":
        auto_status = "YOQILGAN (24/7 Nazoratda)" if BOT_CONFIG["auto_boost"] else "O_CHIRILGAN"
        await message.reply_text(
            f"<b>Tizim Holati:</b>\n\n"
            f"• Kanal: @{BOT_CONFIG['channel_username']}\n"
            f"• Kalitlar: {', '.join(BOT_CONFIG['keywords'])}\n"
            f"• Auto 24/7: {auto_status}\n"
            f"• Auto-boost miqdori: {BOT_CONFIG['smm_amount']} ta\n"
            f"• Tekshiruv vaqti: Har {BOT_CONFIG['check_interval_minutes']} daqiqada"
        )

    elif text == "⚙️ Sozlamalar":
        inline_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔑 SMM API va Service ID sozlash", callback_data="change_smm_api")],
            [InlineKeyboardButton("⏱ Tekshirish oralig'i (15m/30m/60m)", callback_data="change_time")],
            [InlineKeyboardButton("📢 Kanal usernamesini o'zgartirish", callback_data="change_channel")],
            [InlineKeyboardButton("🔑 Kalit so'zlarni o'zgartirish", callback_data="change_keywords")]
        ])
        await message.reply_text("<b>⚙️ Sozlamalar Paneli:</b>", reply_markup=inline_kb)

@bot.on_callback_query()
async def callback_handler(client: Client, query: CallbackQuery):
    user_id = query.from_user.id
    if not is_logged_in(user_id):
        await query.answer("Ruxsat berilmagan!", show_alert=True)
        return

    data = query.data
    if data == "toggle_auto_247":
        BOT_CONFIG["auto_boost"] = not BOT_CONFIG["auto_boost"]
        status = "Yoqildi! Bot endi 24/7 qidiruvni nazorat qiladi." if BOT_CONFIG["auto_boost"] else "O'chirildi!"
        await query.answer(f"Auto 24/7: {status}", show_alert=True)
        
        # Tugmani yangilash
        auto_status_btn = "🟢 Auto 24/7 (FAOL)" if BOT_CONFIG["auto_boost"] else "🔴 Auto 24/7 (O'CHIK)"
        inline_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(auto_status_btn, callback_data="toggle_auto_247")],
            [InlineKeyboardButton("✋ Qo'lda berish", callback_data="start_manual_boost")]
        ])
        await query.message.edit_reply_markup(reply_markup=inline_kb)

    elif data == "start_manual_boost":
        user_states[user_id] = {"step": "manual_boost_amount"}
        await query.message.reply_text("🔢 Nechta boost (nakrutka) urmoqchisiz? Sonini kiriting (masalan: `500` yoki `1000`):")
        await query.answer()

    elif data == "change_smm_api":
        user_states[user_id] = {"step": "set_smm_api"}
        await query.message.reply_text(
            "🔑 <b>SMM API sozlamasini kiritish uchun 3 ta qatorda yuboring:</b>\n\n"
            "1-qator: SMM API URL\n"
            "2-qator: SMM API KEY\n"
            "3-qator: SERVICE ID\n\n"
            "<i>Masalan:</i>\n"
            "<code>https://smm-provider.com/api/v2\nmy_api_key_12345\n789</code>"
        )
        await query.answer()

    elif data == "change_time":
        if BOT_CONFIG["check_interval_minutes"] == 15:
            BOT_CONFIG["check_interval_minutes"] = 30
        elif BOT_CONFIG["check_interval_minutes"] == 30:
            BOT_CONFIG["check_interval_minutes"] = 60
        else:
            BOT_CONFIG["check_interval_minutes"] = 15
        await query.answer(f"Vaqt har {BOT_CONFIG['check_interval_minutes']} daqiqaga o'zgartirildi!")

    elif data == "change_channel":
        user_states[user_id] = {"step": "set_channel"}
        await query.message.reply_text("📢 Yangi kanal username'ini kiriting (masalan: `my_channel`):")
        await query.answer()

    elif data == "change_keywords":
        user_states[user_id] = {"step": "set_keywords"}
        await query.message.reply_text("🔑 Kalit so'zlarni vergul bilan ajratib yozing (masalan: `Nukus, Shimbay`):")
        await query.answer()

async def main():
    server_thread = threading.Thread(target=run_dummy_server, daemon=True)
    server_thread.start()

    await bot.start()
    if userbot:
        await userbot.start()

    asyncio.create_task(auto_monitor_loop())
    logger.info(">>> Telegram Search Booster Bot 24/7 rejimida ishlamoqda! <<<")
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        loop.run_until_complete(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot to'xtatildi.")
