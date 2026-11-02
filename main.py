import asyncio
import logging
import time
import requests
from pyrogram import Client, filters
from pyrogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

# --- KONFIGURACIYA ---
API_ID = 37881267
API_HASH = "fd1edeb73b34fa0955df2a06f31620fd"
BOT_TOKEN = "9214605810:AAEqIRIy93JA0qk4k792iRnTpq9ItO8quk4"

MAIN_ADMIN_ID = 0  # Telegram ID-ingizni kiriting

MY_CHANNEL_USERNAME = "siznin_kanaliniz"  # Kanaliziz ( @ belgisiz )
KEYWORDS = ["Nukus", "Kungrad", "Kegeyli", "Shimbay"]  # Gilt sózler

# SMM Panel API (Boshlang'ich qiymatlar - Bot menyusidan o'zgartirsa bo'ladi)
smm_config = {
    "url": "https://smm-panel-provider.com/api/v2",
    "key": "YOUR_SMM_API_KEY",
    "service_id": "123",
    "amount": 5000
}

# Standart taymerlar
cooldown_minutes = 15       # Nakrutka urıw pauzası (minutta)
search_interval_seconds = 60 # Izlewdi tekseriw aralıq waqtı (sekundta)

last_boost_time = {kw: 0 for kw in KEYWORDS}

# Rejimlar hám Ma'lumotlar
admin_database = {"admin": "secretpassword123"}
keyword_states = {kw: True for kw in KEYWORDS}
authenticated_users = set()
notifications_enabled = True
auto_mode_enabled = True  # True = Avto-mode, False = Manual
user_states = {}

# Clientlerdi jaratıw
user_app = Client("user_session", api_id=API_ID, api_hash=API_HASH)
bot_app = Client("bot_session", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)


# --- MENYU KNOPKALARI ---
def get_keyboard(user_id: int):
    auto_txt = "🤖 Avto-Mode: JAǴILǴAN ✅" if auto_mode_enabled else "🤖 Avto-Mode: ÓSHIRILGEN ❌"
    
    buttons = [
        [KeyboardButton("📊 Status hám Orınlar"), KeyboardButton("⚙️ Настройки")],
        [KeyboardButton(auto_txt), KeyboardButton("⏱️ Pauzany oʻzgertiw")],
        [KeyboardButton("🔍 Izlew waqtyn oʻzgertiw"), KeyboardButton("🔑 SMM API Sozlamalari")],
        [KeyboardButton("🔔 Eskertiwler: Jaǵıw/Óshiriw"), KeyboardButton("🚀 Házir Nakrutka Urıw")],
        [KeyboardButton("ℹ️ Yárdem")]
    ]
    if user_id == MAIN_ADMIN_ID or user_id in authenticated_users:
        buttons.append([KeyboardButton("➕ Jańa Admin Qosıw"), KeyboardButton("👥 Adminler Dizimi")])
        
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)


def send_smm_order(target_link: str, amount: int):
    """Básekelesiwshiǵa nakrutka urıw sorawı"""
    payload = {
        'key': smm_config["key"],
        'action': 'add',
        'service': smm_config["service_id"],
        'link': target_link,
        'quantity': amount
    }
    try:
        res = requests.post(smm_config["url"], data=payload, timeout=10)
        return res.json()
    except Exception as e:
        return {"error": str(e)}


# --- BOT BUYRIQLARI HÁM MENYU LOGIKASI ---

@bot_app.on_message(filters.command("start") & filters.private)
async def start_cmd(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id in authenticated_users or user_id == MAIN_ADMIN_ID:
        authenticated_users.add(user_id)
        await message.reply_text(
            "✅ **Siz sistemadasız!**\nMonitoring 24/7 rejiminde islep tur.",
            reply_markup=get_keyboard(user_id)
        )
    else:
        await message.reply_text("🔒 **Admin Panelge kiriw.**\n`login:parol` formatında jiberiń:")


@bot_app.on_message(filters.text & filters.private)
async def message_handler(client: Client, message: Message):
    global notifications_enabled, auto_mode_enabled, cooldown_minutes, search_interval_seconds
    user_id = message.from_user.id
    text = message.text.strip()

    # --- SMM API SOZLAMALARIN O'ZGARTIRISH LOGIKASI ---
    if user_states.get(user_id) == "WAITING_SMM_DATA":
        parts = text.split("\n")
        if len(parts) >= 3:
            smm_config["url"] = parts[0].strip()
            smm_config["key"] = parts[1].strip()
            smm_config["service_id"] = parts[2].strip()
            if len(parts) >= 4 and parts[3].strip().isdigit():
                smm_config["amount"] = int(parts[3].strip())
            
            user_states[user_id] = None
            await message.reply_text(
                "✅ **SMM API ma'lumotlari muvaffaqiyatli saqlandi!**\n\n"
                f"🌐 **URL:** `{smm_config['url']}`\n"
                f"🔑 **API Key:** `{smm_config['key']}`\n"
                f"🆔 **Service ID:** `{smm_config['service_id']}`\n"
                f"🔢 **Soni (Amount):** `{smm_config['amount']}`",
                reply_markup=get_keyboard(user_id)
            )
        else:
            await message.reply_text(
                "⚠️ **Format noto'g'ri!** Qatorma-qator 3 yoki 4 ta ma'lumot kiriting:\n\n"
                "`API_URL`\n`API_KEY`\n`SERVICE_ID`\n`AMOUNT (ixtiyoriy)`"
            )
        return

    # --- IZLEW WAQTYN OʻZGERTIW ---
    if user_states.get(user_id) == "WAITING_SEARCH_INTERVAL":
        if text.isdigit() and int(text) > 0:
            search_interval_seconds = int(text)
            user_states[user_id] = None
            await message.reply_text(
                f"✅ **Izlew tekseriw waqty oʻzgertildi!**\n\n"
                f"Endi bot hár **{search_interval_seconds} sekundta** Telegram izlewdi tekserip turadı.",
                reply_markup=get_keyboard(user_id)
            )
        else:
            await message.reply_text("⚠️ Faqat musbat san (sekundlarda) kiriting! Masalan: `10`, `30` yamasa `60`")
        return

    # --- PAUZANY OʻZGERTIW ---
    if user_states.get(user_id) == "WAITING_COOLDOWN_TIME":
        if text.isdigit() and int(text) > 0:
            cooldown_minutes = int(text)
            user_states[user_id] = None
            await message.reply_text(
                f"✅ **Pauza waqty oʻzgertildi!**\n\n"
                f"Endi bot hár bir gilt sóz boyınsha keminde **{cooldown_minutes} minut** kútip nakrutka uradı.",
                reply_markup=get_keyboard(user_id)
            )
        else:
            await message.reply_text("⚠️ Faqat musbat san kiriting! Masalan: `5` yamasa `15`")
        return

    # --- JAŃA ADMIN QOSIW ---
    if user_states.get(user_id) == "WAITING_NEW_ADMIN":
        if ":" in text:
            new_login, new_pass = text.split(":", 1)
            admin_database[new_login.strip()] = new_pass.strip()
            user_states[user_id] = None
            await message.reply_text(
                f"✅ **Jańa Admin qosıldı!**\n\n👤 **Login:** `{new_login.strip()}`\n🔑 **Parol:** `{new_pass.strip()}`",
                reply_markup=get_keyboard(user_id)
            )
        else:
            await message.reply_text("⚠️ Qáte format! Iltimos `login:parol` kórinisinde jiberiń.")
        return

    # Login tekseriw
    if user_id not in authenticated_users and user_id != MAIN_ADMIN_ID:
        if ":" in text:
            login, password = text.split(":", 1)
            if login.strip() in admin_database and admin_database[login.strip()] == password.strip():
                authenticated_users.add(user_id)
                await message.reply_text("🎉 **Xosh keldissiz!**", reply_markup=get_keyboard(user_id))
            else:
                await message.reply_text("❌ Login yamasa parol qáte!")
        return

    # --- KNOPKALAR ---

    if text == "🔑 SMM API Sozlamalari":
        user_states[user_id] = "WAITING_SMM_DATA"
        await message.reply_text(
            "🛠 **SMM API ma'lumotlarini kiriting:**\n\n"
            "Xabarni bir nechta qatorda, pastdagidek ko'rinishda yuboring:\n\n"
            "`https://smm-panel.com/api/v2`\n"
            "`SIZNING_API_KEYINGIZ`\n"
            "`123` (Service ID)\n"
            "`5000` (Soni - Amount)",
            disable_web_page_preview=True
        )

    elif text == "📊 Status hám Orınlar":
        status_msg = "🔎 **Házirgi qıdırıw poziciyaları:**\n\n"
        for kw, is_top1 in keyword_states.items():
            state = "✅ Top-1 (Sizniki)" if is_top1 else "⚠️ Básekelesiwshi 1-orında"
            status_msg += f"• **{kw}**: {state}\n"
        await message.reply_text(status_msg)

    elif text == "⚙️ Настройки":
        mode_str = "Автоматический" if auto_mode_enabled else "Ручной (Вы сами накручиваете)"
        settings_msg = (
            f"⚙️ **Настройки бота:**\n\n"
            f"📌 **Ваш канал:** @{MY_CHANNEL_USERNAME}\n"
            f"🤖 **Режим работы:** {mode_str}\n"
            f"🔑 **Ключевые слова:** {', '.join(KEYWORDS)}\n"
            f"🌐 **SMM API URL:** `{smm_config['url']}`\n"
            f"🆔 **SMM Service ID:** `{smm_config['service_id']}`\n"
            f"🚀 **Количество накрутки:** {smm_config['amount']} шт.\n"
            f"🔍 **Интервал поиска:** каждые {search_interval_seconds} сек.\n"
            f"⏳ **Пауза между накрутками:** {cooldown_minutes} мин."
        )
        await message.reply_text(settings_msg)

    elif text == "⏱️ Pauzany oʻzgertiw":
        user_states[user_id] = "WAITING_COOLDOWN_TIME"
        await message.reply_text(
            f"⏱️ **Nakrutka urıw pauza waqtyn oʻzgertiw:**\n\n"
            f"Házirgi pauza waqtı: **{cooldown_minutes} minut**.\n\n"
            f"Jańa pauza waqtın minutta kiritiń (Masalan: `5`, `10` yamasa `15`):"
        )

    elif text == "🔍 Izlew waqtyn oʻzgertiw":
        user_states[user_id] = "WAITING_SEARCH_INTERVAL"
        await message.reply_text(
            f"🔍 **Izlew tekseriw aralıǵyn oʻzgertiw:**\n\n"
            f"Házirgi tekseriw waqtı: **hár {search_interval_seconds} sekundta**.\n\n"
            f"Jańa tekseriw waqtın sekundlarda kiritiń (Masalan: `10`, `30` yamasa `60`):"
        )

    elif "🤖 Avto-Mode" in text:
        auto_mode_enabled = not auto_mode_enabled
        st_txt = "Jaǵıldı (Bot oʻzi avtomat uradi) ✅" if auto_mode_enabled else "Óshirildi (Oʻzingiz knopkadan urasiz) ❌"
        await message.reply_text(f"🤖 **Avto-Mode:** {st_txt}", reply_markup=get_keyboard(user_id))

    elif text == "🔔 Eskertiwler: Jaǵıw/Óshiriw":
        notifications_enabled = not notifications_enabled
        st_txt = "Jaǵıldı ✅" if notifications_enabled else "Óshirildi ❌"
        await message.reply_text(f"🔔 **Eskertiw xabarları:** {st_txt}")

    elif text == "🚀 Házir Nakrutka Urıw":
        await message.reply_text("🔎 Básekelesiwshiler tekserilmekte...")
        orders_sent = 0
        for kw in KEYWORDS:
            try:
                results = await user_app.search_global(kw, limit=3)
                if results and results[0].chat.username.lower() != MY_CHANNEL_USERNAME.lower():
                    comp_username = results[0].chat.username
                    smm_res = send_smm_order(f"https://t.me/{comp_username}", smm_config["amount"])
                    await message.reply_text(f"🚀 **[{kw}]** boyınsha @{comp_username} básekelesiwshige nakrutka urıldı!\nJuwap: `{smm_res}`")
                    orders_sent += 1
            except Exception as e:
                pass
        if orders_sent == 0:
            await message.reply_text("✅ Barlıq gilt sózler boyınsha kanalıńız Top-1 de tur!")

    elif text == "ℹ️ Yárdem":
        await message.reply_text("🤖 Bul bot Telegram Global Search baqlawshısı va básekelesiwshilerdi cheklevchi sistema.")

    elif text == "➕ Jańa Admin Qosıw":
        user_states[user_id] = "WAITING_NEW_ADMIN"
        await message.reply_text("👤 **Jańa Admin:** `login:parol` formatında jiberiń:")

    elif text == "👥 Adminler Dizimi":
        admin_list = "👥 **Bazadaǵı Adminler:**\n\n" + "\n".join([f"• `{l}` : `{p}`" for l, p in admin_database.items()])
        await message.reply_text(admin_list)


# --- MONITORING SIKLI ---

async def search_monitor():
    while True:
        for kw in KEYWORDS:
            try:
                results = await user_app.search_global(kw, limit=3)
                
                if results:
                    top_1_username = results[0].chat.username

                    # AGAR BÁSEKELESIWSHI TOP-1 GE SHIǴSA
                    if top_1_username and top_1_username.lower() != MY_CHANNEL_USERNAME.lower():
                        if keyword_states[kw] is True:
                            keyword_states[kw] = False
                            
                            if notifications_enabled:
                                alert_msg = (
                                    f"⚠️ **Eskertiw!**\n\n"
                                    f"**{kw}** gilt sózi boyınsha 1-orında shiǵa almayatırsańız!\n"
                                    f"👤 **Házirgi Top-1 básekelesiwshi:** @{top_1_username}"
                                )
                                for admin_uid in authenticated_users:
                                    try: await bot_app.send_message(admin_uid, alert_msg)
                                    except: pass

                        # AVTO-MODE JAǴIQLI BOLSA HÁM TAYMER ÓTKEN BOLSA NAKRUTKA URILADI
                        curr_time = time.time()
                        cooldown_seconds = cooldown_minutes * 60
                        
                        if auto_mode_enabled and (curr_time - last_boost_time[kw] > cooldown_seconds):
                            target_url = f"https://t.me/{top_1_username}"
                            smm_res = send_smm_order(target_url, smm_config["amount"])
                            last_boost_time[kw] = curr_time
                            
                            if notifications_enabled:
                                report_msg = f"🚀 **Avto-Nakrutka:** @{top_1_username} básekelesiwshige jiberildi.\nJuwap: `{smm_res}`"
                                for admin_uid in authenticated_users:
                                    try: await bot_app.send_message(admin_uid, report_msg)
                                    except: pass

                    # AGAR KANAL QAYTA TOP-1 GE SHIǴSA
                    else:
                        if keyword_states[kw] is False:
                            keyword_states[kw] = True
                            if notifications_enabled:
                                success_msg = f"✅ **Sizniki 1-orında!**\n\n**{kw}** boyınsha kanalıńız (@{MY_CHANNEL_USERNAME}) Top-1 ge qayttı."
                                for admin_uid in authenticated_users:
                                    try: await bot_app.send_message(admin_uid, success_msg)
                                    except: pass

            except Exception as e:
                logging.error(f"Error [{kw}]: {e}")

            await asyncio.sleep(3)

        await asyncio.sleep(search_interval_seconds)


async def main():
    await user_app.start()
    await bot_app.start()
    print("Bot iske túsirildi...")
    asyncio.create_task(search_monitor())
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
