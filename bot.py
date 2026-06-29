"""
Telegram Forward Userbot - Bot Panel
Aiogram + Telethon | StringSession
"""

import asyncio
import os
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import CommandStart, Command
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
API_ID    = int(os.environ.get("API_ID", "39228801"))
API_HASH  = os.environ.get("API_HASH", "b0db9039f5f899b6493b8f5efa3771b9")

class Setup(StatesGroup):
    phone    = State()
    code     = State()
    password = State()
    source   = State()
    target   = State()
    keywords = State()

user_clients: dict = {}
user_bots:    dict = {}
user_config:  dict = {}
phone_hashes: dict = {}
user_phones:  dict = {}

bot = Bot(token=BOT_TOKEN)
dp  = Dispatcher(storage=MemoryStorage())

def stop_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="⏹ Botni to'xtatish")]],
        resize_keyboard=True
    )

def cancel_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Bekor qilish")]],
        resize_keyboard=True
    )

async def cleanup_client(uid):
    """Foydalanuvchi clientini to'liq tozalash"""
    if uid in user_clients:
        try:
            await user_clients[uid].disconnect()
        except:
            pass
        del user_clients[uid]
    phone_hashes.pop(uid, None)
    user_phones.pop(uid, None)

@dp.message(CommandStart())
async def cmd_start(msg: Message, state: FSMContext):
    uid = msg.from_user.id

    if uid in user_bots and not user_bots[uid].done():
        cfg = user_config.get(uid, {})
        await msg.answer(
            f"✅ <b>Botingiz ishlayapti!</b>\n\n"
            f"📥 Manba: <code>@{cfg.get('source','?')}</code>\n"
            f"📤 Maqsad: <code>@{cfg.get('target','?')}</code>\n"
            f"🔑 Kalit so'zlar: <code>{cfg.get('keywords','?')}</code>",
            parse_mode="HTML",
            reply_markup=stop_kb()
        )
        return

    await cleanup_client(uid)
    await state.clear()

    await msg.answer(
        "👋 <b>Forward Bot ga xush kelibsiz!</b>\n\n"
        "Bu bot sizning Telegram akkauntingiz nomidan "
        "bir guruhdan ikkinchisiga kalit so'zli xabarlarni yuboradi.\n\n"
        "📱 <b>Telefon raqamingizni</b> yuboring:\n"
        "<i>Misol: +998901234567</i>",
        parse_mode="HTML",
        reply_markup=cancel_kb()
    )
    await state.set_state(Setup.phone)

@dp.message(F.text == "❌ Bekor qilish")
async def cancel(msg: Message, state: FSMContext):
    uid = msg.from_user.id
    await cleanup_client(uid)
    await state.clear()
    await msg.answer("❌ Bekor qilindi.", reply_markup=ReplyKeyboardRemove())

@dp.message(Setup.phone)
async def get_phone(msg: Message, state: FSMContext):
    uid   = msg.from_user.id
    phone = msg.text.strip()

    if not phone.startswith("+") or len(phone) < 10:
        await msg.answer("❗ To'g'ri format: <code>+998901234567</code>", parse_mode="HTML")
        return

    # Avvalgi clientni to'liq tozalash
    await cleanup_client(uid)

    await msg.answer("⏳ Kod yuborilmoqda...")

    # iPhone sifatida ko'rinadi — Telegram kam bloklaydi
    client = TelegramClient(
        StringSession(),
        API_ID,
        API_HASH,
        device_model="iPhone 13",
        system_version="iOS 16.0",
        app_version="9.0.0"
    )

    try:
        await client.connect()
        result = await client.send_code_request(phone, force_sms=True)
        phone_hashes[uid] = result.phone_code_hash
        user_phones[uid]  = phone
        user_clients[uid] = client

        await msg.answer(
            "📩 <b>SMS kod yuborildi!</b>\n\n"
            "Telefoningizga kelgan <b>5 xonali kodni</b> yuboring:\n"
            "<i>(Kod 2 daqiqa ichida kiritilsin)</i>",
            parse_mode="HTML"
        )
        await state.set_state(Setup.code)

    except Exception as e:
        await client.disconnect()
        logger.error(f"[{uid}] send_code_request xato: {e}")
        await msg.answer(f"❌ Xato: <code>{e}</code>\n\nQaytadan /start bosing.", parse_mode="HTML")

@dp.message(Setup.code)
async def get_code(msg: Message, state: FSMContext):
    uid  = msg.from_user.id
    code = msg.text.strip().replace(" ", "").replace("-", "")

    client = user_clients.get(uid)
    if not client:
        await msg.answer("❗ Sessiya topilmadi. /start bosing.")
        return

    try:
        await client.sign_in(
            user_phones[uid],
            code,
            phone_code_hash=phone_hashes[uid]
        )
        await msg.answer(
            "✅ <b>Muvaffaqiyatli kirildi!</b>\n\n"
            "📥 <b>Manba guruh</b> username ini yuboring:\n"
            "<i>Misol: testguruh (@ belgisisiz)</i>",
            parse_mode="HTML"
        )
        await state.set_state(Setup.source)

    except SessionPasswordNeededError:
        await msg.answer(
            "🔐 <b>2FA parol</b> kerak.\nParolingizni yuboring:",
            parse_mode="HTML"
        )
        await state.set_state(Setup.password)

    except PhoneCodeInvalidError:
        await msg.answer(
            "❌ Kod noto'g'ri yoki eskirgan.\n\n"
            "Qaytadan /start bosib, yangi kod oling."
        )
        await cleanup_client(uid)
        await state.clear()

    except Exception as e:
        logger.error(f"[{uid}] sign_in xato: {e}")
        await msg.answer(f"❌ Xato: <code>{e}</code>\n\nQaytadan /start bosing.", parse_mode="HTML")
        await cleanup_client(uid)
        await state.clear()

@dp.message(Setup.password)
async def get_password(msg: Message, state: FSMContext):
    uid      = msg.from_user.id
    password = msg.text.strip()
    client   = user_clients.get(uid)

    if not client:
        await msg.answer("❗ Sessiya topilmadi. /start bosing.")
        await state.clear()
        return

    try:
        await client.sign_in(password=password)
        await msg.answer(
            "✅ <b>Kirildi!</b>\n\n"
            "📥 <b>Manba guruh</b> username ini yuboring:\n"
            "<i>Misol: testguruh (@ belgisisiz)</i>",
            parse_mode="HTML"
        )
        await state.set_state(Setup.source)
    except Exception as e:
        await msg.answer(f"❌ Parol xato: <code>{e}</code>", parse_mode="HTML")

@dp.message(Setup.source)
async def get_source(msg: Message, state: FSMContext):
    source = msg.text.strip().lstrip("@")
    await state.update_data(source=source)
    await msg.answer(
        f"✅ Manba: <code>@{source}</code>\n\n"
        "📤 <b>Maqsad guruh</b> username ini yuboring:",
        parse_mode="HTML"
    )
    await state.set_state(Setup.target)

@dp.message(Setup.target)
async def get_target(msg: Message, state: FSMContext):
    target = msg.text.strip().lstrip("@")
    await state.update_data(target=target)
    await msg.answer(
        f"✅ Maqsad: <code>@{target}</code>\n\n"
        "🔑 <b>Kalit so'zlarni</b> vergul bilan yuboring:\n"
        "<i>Misol: yuk bor, tonna, toshkent</i>",
        parse_mode="HTML"
    )
    await state.set_state(Setup.keywords)

@dp.message(Setup.keywords)
async def get_keywords(msg: Message, state: FSMContext):
    uid      = msg.from_user.id
    data     = await state.get_data()
    source   = data["source"]
    target   = data["target"]
    keywords = [k.strip().lower() for k in msg.text.split(",") if k.strip()]

    if not keywords:
        await msg.answer("❗ Kamida bitta kalit so'z kiriting.")
        return

    client = user_clients.get(uid)
    if not client:
        await msg.answer("❗ Sessiya topilmadi. /start dan boshlang.")
        await state.clear()
        return

    user_config[uid] = {
        "source": source,
        "target": target,
        "keywords": ", ".join(keywords)
    }

    await state.clear()

    @client.on(events.NewMessage(chats=source))
    async def handler(event):
        text = (event.message.text or event.message.caption or "").lower()
        if any(kw in text for kw in keywords):
            try:
                await client.forward_messages(target, event.message)
                logger.info(f"[{uid}] ✅ Forward: {text[:60]}")
            except Exception as e:
                logger.error(f"[{uid}] ❌ Forward xato: {e}")

    async def run_client():
        try:
            await client.run_until_disconnected()
        except Exception as e:
            logger.error(f"[{uid}] Client uzildi: {e}")

    task = asyncio.create_task(run_client())
    user_bots[uid] = task

    await msg.answer(
        f"🚀 <b>Bot ishga tushdi!</b>\n\n"
        f"📥 Manba: <code>@{source}</code>\n"
        f"📤 Maqsad: <code>@{target}</code>\n"
        f"🔑 Kalit so'zlar: <code>{', '.join(keywords)}</code>\n\n"
        f"✅ 24/7 ishlaydi!",
        parse_mode="HTML",
        reply_markup=stop_kb()
    )

@dp.message(F.text == "⏹ Botni to'xtatish")
async def stop_bot_handler(msg: Message, state: FSMContext):
    uid = msg.from_user.id

    if uid in user_bots:
        user_bots[uid].cancel()
        del user_bots[uid]

    await cleanup_client(uid)
    user_config.pop(uid, None)
    await state.clear()

    await msg.answer(
        "⏹ <b>Bot to'xtatildi.</b>\n\nQayta ishga tushirish uchun /start",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove()
    )

@dp.message(Command("stop"))
async def cmd_stop(msg: Message, state: FSMContext):
    await stop_bot_handler(msg, state)

@dp.message(Command("status"))
async def cmd_status(msg: Message, state: FSMContext):
    uid = msg.from_user.id
    if uid in user_bots and not user_bots[uid].done():
        cfg = user_config.get(uid, {})
        await msg.answer(
            f"✅ <b>Bot ishlayapti</b>\n\n"
            f"📥 Manba: <code>@{cfg.get('source','?')}</code>\n"
            f"📤 Maqsad: <code>@{cfg.get('target','?')}</code>\n"
            f"🔑 Kalit so'zlar: <code>{cfg.get('keywords','?')}</code>",
            parse_mode="HTML"
        )
    else:
        await msg.answer("❌ Bot hozir ishlamayapti.\n/start bilan boshlang.")

async def main():
    logger.info("Bot ishga tushmoqda...")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

if __name__ == "__main__":
    asyncio.run(main())
