"""
Telegram Forward Userbot - Web Panel
Flask + Telethon
"""

from flask import Flask, render_template, request, jsonify, session
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError
import asyncio
import threading
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)

API_ID   = 39228801
API_HASH = "b0db9039f5f899b6493b8f5efa3771b9"

client       = None
bot_running  = False
phone_hash   = None
bot_thread   = None

def get_loop():
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/send_phone", methods=["POST"])
def send_phone():
    global client, phone_hash
    data  = request.json
    phone = data.get("phone", "").strip()
    loop   = get_loop()
    client = TelegramClient("userbot_session", API_ID, API_HASH, loop=loop)
    async def _send():
        global phone_hash
        await client.connect()
        result     = await client.send_code_request(phone)
        phone_hash = result.phone_code_hash
    try:
        loop.run_until_complete(_send())
        session["phone"] = phone
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

@app.route("/verify_code", methods=["POST"])
def verify_code():
    global client, phone_hash
    data     = request.json
    code     = data.get("code", "").strip()
    password = data.get("password", "").strip()
    phone    = session.get("phone")
    loop = get_loop()
    async def _verify():
        try:
            await client.sign_in(phone, code, phone_code_hash=phone_hash)
        except SessionPasswordNeededError:
            if password:
                await client.sign_in(password=password)
            else:
                raise Exception("2FA parol kerak")
    try:
        loop.run_until_complete(_verify())
        return jsonify({"ok": True})
    except PhoneCodeInvalidError:
        return jsonify({"ok": False, "error": "Kod noto'g'ri"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

@app.route("/start_bot", methods=["POST"])
def start_bot():
    global client, bot_running, bot_thread
    data     = request.json
    source   = data.get("source", "").strip().lstrip("@")
    target   = data.get("target", "").strip().lstrip("@")
    keywords = [k.strip().lower() for k in data.get("keywords", "").split(",") if k.strip()]
    if not source or not target or not keywords:
        return jsonify({"ok": False, "error": "Barcha maydonlarni to'ldiring"})
    def run_bot():
        global bot_running
        bot_running = True
        loop = get_loop()
        @client.on(events.NewMessage(chats=source))
        async def handler(event):
            text = event.message.text or event.message.caption or ""
            text_lower = text.lower()
            if any(kw in text_lower for kw in keywords):
                try:
                    await client.forward_messages(target, event.message)
                    print(f"✅ Forward: {text[:60]}")
                except Exception as e:
                    print(f"❌ Xato: {e}")
        async def _run():
            print(f"🤖 Bot ishlamoqda | {source} → {target}")
            await client.run_until_disconnected()
        loop.run_until_complete(_run())
        bot_running = False
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    return jsonify({"ok": True})

@app.route("/status")
def status():
    return jsonify({"running": bot_running})

@app.route("/stop_bot", methods=["POST"])
def stop_bot():
    global client, bot_running
    loop = get_loop()
    if client:
        loop.run_until_complete(client.disconnect())
    bot_running = False
    return jsonify({"ok": True})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
