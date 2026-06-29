"""
Telegram Forward Userbot - Bot Panel
Aiogram + Telethon | Har bir foydalanuvchi uchun alohida sessiya
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
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Sozlamalar ──────────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN")
API_ID    = int(os.environ.get("API_ID", "39228801"))
API_HASH  = os.environ.get("API_HASH", "b0db9039f5f899b6493b8f5efa3771b9")
SESSIONS_DIR = "/app/sessions"  # Railway volume yoki oddiy papka

os.makedirs(SESSIONS_DIR, exist_ok=True)

# ── FSM holatlari ─────────────────────────────────────────
class Setup(StatesGroup):
    phone    = State()
    code     = State()
    password = State()
    source   = State()
    target   = State()
    keywords = State()

# ── Foydalanuvchi ma'lumotlari ────────────────────────────
user_clients: dict[int, TelegramClient] = {}
user_bots:    dict[int, asyncio.Task]   = {}
user_config:  dict[int, dict]           = {}
phone_hashes: dict[int, str]            = {}
user_phones:  dict[int, str]            = {}

bot = Bot(token=BOT_TOKEN)
dp  = Dispatcher(storage=MemoryStorage())

# ── Yordamchi tugmalar ─────────────────────────────────────
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

# ── /start ─────────────────────────────────────────────────
@dp.message(CommandStart())
async def cmd_start(msg: Message, state: FSMContext):
    uid = msg.from_user.id

    # Agar allaqachon bot ishlayotgan bo'lsa
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

    await state.clear()
    await msg.answer(
        "👋 <b>Forward Bot ga xush kelibsiz!</b>\n\n"
        "Bu bot sizning Telegram akkauntingiz nomidan "
        "bir guruhdan ikkinchisiga kalit so'zli xabarlarni yuboradi.\n\n"
        "📱 Boshlash uchun <b>telefon raqamingizni</b> yuboring:\n"
        "<i>Misol: +998901234567</i>",
        parse_mode="HTML",
        reply_markup=cancel_kb()
    )
    await state.set_state(Setup.phone)

# ── Bekor qilish ───────────────────────────────────────────
@dp.message(F.text == "❌ Bekor qilish")
async def cancel(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer("❌ Bekor qilindi.", reply_markup=ReplyKeyboardRemove())

# ── Telefon raqam ──────────────────────────────────────────
@dp.message(Setup.phone)
async def get_phone(msg: Message, state: FSMContext):
    uid   = msg.from_user.id
    phone = msg.text.strip()

    if not phone.startswith("+") or len(phone) < 10:
        await msg.answer("❗ Telefon raqam to'g'ri formatda kiriting.\nMisol: <code>+998901234567</code>", parse_mode="HTML")
        return

    await msg.answer("⏳ Kod yuborilmoqda...")

    session_path = os.path.join(SESSIONS_DIR, f"user_{uid}")
    client = TelegramClient(session_path, API_ID, API_HASH)

    try:
        await client.connect()
        result = await client.send_code_request(phone)
        phone_hashes[uid] = result.phone_code_hash
        user_phones[uid]  = phone
        user_clients[uid] = client

        await msg.answer(
            "📩 <b>SMS kod yuborildi!</b>\n\n"
            "Telegram dan kelgan <b>5 xonali kodni</b> yuboring:",
            parse_mode="HTML"
        )
        await state.set_state(Setup.code)

    except Exception as e:
        await client.disconnect()
        await msg.answer(f"❌ Xato: <code>{e}</code>", parse_mode="HTML")

# ── Tasdiqlash kodi ────────────────────────────────────────
@dp.message(Setup.code)
async def get_code(msg: Message, state: FSMContext):
    uid  = msg.from_user.id
    code = msg.text.strip().replace(" ", "")

    client = user_clients.get(uid)
    if not client:
        await msg.answer("❗ Avval /start ni bosing.")
        return

    try:
        await client.sign_in(
            user_phones[uid],
            code,
            phone_code_hash=phone_hashes[uid]
        )
        await msg.answer(
            "✅ <b>Muvaffaqiyatli kirildi!</b>\n\n"
            "📥 Endi <b>manba guruh</b> username ini yuboring:\n"
            "<i>Misol: testguruh (@ belgisisiz)</i>",
            parse_mode="HTML"
        )
        await state.set_state(Setup.source)

    except SessionPasswordNeededError:
        await msg.answer(
            "🔐 <b>2FA parol</b> o'rnatilgan.\n"
            "Parolingizni yuboring:",
            parse_mode="HTML"
        )
        await state.set_state(Setup.password)

    except PhoneCodeInvalidError:
        await msg.answer("❌ Kod noto'g'ri. Qaytadan kiriting:")

    except Exception as e:
        await msg.answer(f"❌ Xato: <code>{e}</code>", parse_mode="HTML")

# ── 2FA parol ──────────────────────────────────────────────
@dp.message(Setup.password)
async def get_password(msg: Message, state: FSMContext):
    uid      = msg.from_user.id
    password = msg.text.strip()
    client   = user_clients.get(uid)

    try:
        await client.sign_in(password=password)
        await msg.answer(
            "✅ <b>Kirildi!</b>\n\n"
            "📥 <b>Manba guruh</b> username ini yuboring:\n"
            "<i>Misol: testguruh</i>",
            parse_mode="HTML"
        )
        await state.set_state(Setup.source)
    except Exception as e:
        await msg.answer(f"❌ Parol xato: <code>{e}</code>", parse_mode="HTML")

# ── Manba guruh ────────────────────────────────────────────
@dp.message(Setup.source)
async def get_source(msg: Message, state: FSMContext):
    source = msg.text.strip().lstrip("@")
    await state.update_data(source=source)
    await msg.answer(
        f"✅ Manba: <code>@{source}</code>\n\n"
        "📤 Endi <b>maqsad guruh</b> username ini yuboring:",
        parse_mode="HTML"
    )
    await state.set_state(Setup.target)

# ── Maqsad guruh ───────────────────────────────────────────
@dp.message(Setup.target)
async def get_target(msg: Message, state: FSMContext):
    target = msg.text.strip().lstrip("@")
    await state.update_data(target=target)
    await msg.answer(
        f"✅ Maqsad: <code>@{target}</code>\n\n"
        "🔑 <b>Kalit so'zlarni</b> vergul bilan yuboring:\n"
        "<i>Misol: yuk bor, tonna, toshkent, andijon</i>",
        parse_mode="HTML"
    )
    await state.set_state(Setup.keywords)

# ── Kalit so'zlar va botni ishga tushirish ─────────────────
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
        return

    user_config[uid] = {
        "source": source,
        "target": target,
        "keywords": ", ".join(keywords)
    }

    await state.clear()

    # Forward handler
    @client.on(events.NewMessage(chats=source))
    async def handler(event):
        text = (event.message.text or event.message.caption or "").lower()
        if any(kw in text for kw in keywords):
            try:
                await client.forward_messages(target, event.message)
                logger.info(f"[{uid}] ✅ Forward: {text[:60]}")
            except Exception as e:
                logger.error(f"[{uid}] ❌ Xato: {e}")

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
        f"24/7 ishlaydi. To'xtatish uchun tugmani bosing.",
        parse_mode="HTML",
        reply_markup=stop_kb()
    )

# ── Botni to'xtatish ───────────────────────────────────────
@dp.message(F.text == "⏹ Botni to'xtatish")
async def stop_bot(msg: Message, state: FSMContext):
    uid = msg.from_user.id

    if uid in user_bots:
        user_bots[uid].cancel()
        del user_bots[uid]

    if uid in user_clients:
        try:
            await user_clients[uid].disconnect()
        except:
            pass
        del user_clients[uid]

    user_config.pop(uid, None)
    await state.clear()

    await msg.answer(
        "⏹ <b>Bot to'xtatildi.</b>\n\nQayta ishga tushirish uchun /start",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove()
    )

# ── /stop command ──────────────────────────────────────────
@dp.message(Command("stop"))
async def cmd_stop(msg: Message, state: FSMContext):
    await stop_bot(msg, state)

# ── /status command ────────────────────────────────────────
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

# ── Main ───────────────────────────────────────────────────
async def main():
    logger.info("Bot ishga tushmoqda...")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

if __name__ == "__main__":
    asyncio.run(main())
