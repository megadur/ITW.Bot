import asyncio
import logging
import random
import sys
from datetime import datetime

from telethon import TelegramClient, events
from telethon.tl.functions.contacts import GetContactsRequest
from telethon.tl.types import User

import config
import database
import brain

# Logging konfigurieren
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(config.LOGS_DIR / "bot.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("scambait.bot")

# Telethon Client initialisieren
client = TelegramClient(config.SESSION_FILE, config.TELEGRAM_API_ID, config.TELEGRAM_API_HASH)

# Set für bekannte Kontakt-IDs (Whitelist)
KNOWN_CONTACT_IDS = set()

async def refresh_contacts():
    """Lädt die Kontaktliste vom Telegram-Account, um niemals Freunde/Familie anzuschreiben."""
    global KNOWN_CONTACT_IDS
    try:
        contacts_result = await client(GetContactsRequest(hash=0))
        for user in contacts_result.users:
            KNOWN_CONTACT_IDS.add(user.id)
        logger.info(f"✅ {len(KNOWN_CONTACT_IDS)} bestehende Kontakte als Whitelist geladen.")
    except Exception as e:
        logger.warning(f"Konnte Kontakte nicht direkt abrufen: {e}")

@client.on(events.NewMessage(incoming=True))
async def handle_incoming_message(event):
    # 1. Nur private Direktnachrichten (keine Gruppen, keine Kanäle)
    if not event.is_private:
        return

    sender = await event.get_sender()
    if not isinstance(sender, User):
        return

    # 2. Eigene Nachrichten, Bots und verifizierte Accounts ignorieren
    if sender.is_self or sender.bot or sender.verified:
        return

    # 3. Sicherheitsfilter: Ist der Absender in den Kontakten?
    if sender.contact or sender.id in KNOWN_CONTACT_IDS:
        logger.debug(f"Ignoriere Nachricht von Kontakt: {sender.id} ({sender.first_name})")
        return

    message_text = event.raw_text.strip()
    if not message_text:
        # Falls nur Sticker oder Bild ohne Text
        message_text = "[Bild/Sticker/Sprachnachricht empfangen]"

    logger.info(f"🚨 Neuer Scambait-Kandidat: {sender.first_name} (ID: {sender.id}) -> '{message_text}'")

    # 4. In Datenbank erfassen / prüfen
    chat_info = database.get_or_create_chat(
        user_id=sender.id,
        first_name=sender.first_name or "",
        last_name=sender.last_name or "",
        username=sender.username or "",
        phone=sender.phone or ""
    )

    if chat_info.get("status") == "ignored":
        logger.info(f"User {sender.id} ist auf 'ignored'. Breche ab.")
        return

    if chat_info.get("reply_count", 0) >= config.MAX_REPLIES_PER_CHAT:
        logger.info(f"User {sender.id} hat Limit von {config.MAX_REPLIES_PER_CHAT} erreicht.")
        return

    # Eingehende Nachricht speichern
    database.save_message(sender.id, "scammer", message_text)

    # 5. Menschliches Verhalten simulieren:
    # Erst nach kurzer Zeit als gelesen markieren, dann nachdenken, dann tippen
    total_delay = random.randint(config.MIN_DELAY_SECONDS, config.MAX_DELAY_SECONDS)
    read_delay = min(5, total_delay // 4)
    typing_delay = min(config.TYPING_DURATION_SECONDS, total_delay // 3)
    wait_before_typing = max(2, total_delay - read_delay - typing_delay)

    logger.info(f"⏳ Warte {total_delay}s bis zur Antwort (Read: {read_delay}s, Pause: {wait_before_typing}s, Tippen: {typing_delay}s)...")

    await asyncio.sleep(read_delay)
    await event.mark_read()

    await asyncio.sleep(wait_before_typing)

    # 6. KI-Antwort generieren
    history = database.get_chat_history(sender.id, limit=10)
    reply_text = brain.generate_reply(history)

    # 7. "Tippt..." Status anzeigen
    try:
        async with client.action(sender.id, 'typing'):
            await asyncio.sleep(typing_delay)
    except Exception as e:
        logger.debug(f"Typing-Action fehlgeschlagen: {e}")

    # 8. Antwort senden
    try:
        await event.reply(reply_text)
        database.save_message(sender.id, "bot", reply_text)
        logger.info(f"📤 Antwort an {sender.first_name} ({sender.id}) gesendet: '{reply_text}'")

        # 9. Optional: Info in deine eigenen "Gespeicherten Nachrichten"
        if config.NOTIFY_SAVED_MESSAGES:
            summary = (
                f"🎣 **Scambaiter Live-Update**\n"
                f"👤 **Scammer:** {sender.first_name} (`{sender.id}`)\n"
                f"💬 **Er/Sie:** {message_text}\n"
                f"👴 **Opa Günther:** {reply_text}"
            )
            await client.send_message('me', summary)
    except Exception as e:
        logger.error(f"Fehler beim Senden der Antwort an {sender.id}: {e}")

async def main():
    database.init_db()
    logger.info("Starte Scambaiter Telegram Client...")
    
    await client.start(phone=config.TELEGRAM_PHONE if config.TELEGRAM_PHONE else None)
    logger.info("✅ Erfolgreich bei Telegram eingeloggt!")

    await refresh_contacts()
    
    me = await client.get_me()
    logger.info(f"Eingeloggt als: {me.first_name} (@{me.username or 'kein username'}) [ID: {me.id}]")
    logger.info("👂 Bot lauscht auf eingehende Nachrichten von Nicht-Kontakten...")
    
    await client.run_until_disconnected()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot gestoppt.")
