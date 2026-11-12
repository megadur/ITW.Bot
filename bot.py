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

async def process_scammer_message(sender: User, message):
    """Verarbeitet eine Scammer-Nachricht (egal ob neu eingetroffen oder bereits ungelesen im Postfach)."""
    message_text = message.raw_text.strip() if hasattr(message, 'raw_text') and message.raw_text else ""
    if not message_text:
        message_text = "[Bild/Sticker/Sprachnachricht empfangen]"

    logger.info(f"🚨 Scambait-Aktion für: {sender.first_name} (ID: {sender.id}) -> '{message_text}'")

    # In Datenbank erfassen / prüfen
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

    # Nachricht speichern
    database.save_message(sender.id, "scammer", message_text)

    # Menschliches Verhalten simulieren
    total_delay = random.randint(config.MIN_DELAY_SECONDS, config.MAX_DELAY_SECONDS)
    read_delay = min(8, max(2, total_delay // 5))
    
    logger.info(f"⏳ Lese Nachricht in {read_delay}s und denke nach...")
    await asyncio.sleep(read_delay)
    try:
        await message.mark_read()
    except Exception as e:
        logger.debug(f"mark_read fehlgeschlagen: {e}")

    # KI-Antwort generieren
    history = database.get_chat_history(sender.id, limit=12)
    reply_text = brain.generate_reply(history)

    # Tipp-Dauer realistisch an Textlänge anpassen (ca. 6-8 Zeichen pro Sekunde)
    typing_delay = min(15, max(3, len(reply_text) // 7))
    wait_before_typing = max(5, total_delay - read_delay - typing_delay)

    logger.info(f"⏳ Warte {wait_before_typing}s, tippe dann {typing_delay}s...")
    await asyncio.sleep(wait_before_typing)

    # "Tippt..." Status anzeigen
    try:
        async with client.action(sender.id, 'typing'):
            await asyncio.sleep(typing_delay)
    except Exception as e:
        logger.debug(f"Typing-Action fehlgeschlagen: {e}")

    # Antwort direkt senden (ohne Quote-Reply-Box, wie im normalen 1-on-1 Chat)
    try:
        await client.send_message(sender.id, reply_text)
        database.save_message(sender.id, "bot", reply_text)
        logger.info(f"📤 Antwort an {sender.first_name} ({sender.id}) gesendet: '{reply_text}'")

        # Optional: Info in deine eigenen "Gespeicherten Nachrichten"
        if config.NOTIFY_SAVED_MESSAGES:
            summary = (
                f"🎣 **Scambaiter Live-Update**\n"
                f"👤 **{sender.first_name}** (`{sender.id}`): {message_text}\n"
                f"🤖 **Antwort:** {reply_text}"
            )
            await client.send_message('me', summary)
    except Exception as e:
        logger.error(f"Fehler beim Senden der Antwort an {sender.id}: {e}")

@client.on(events.NewMessage(incoming=True))
async def handle_incoming_message(event):
    if not event.is_private:
        return

    sender = await event.get_sender()
    if not isinstance(sender, User):
        return

    if sender.is_self or sender.bot or sender.verified:
        return

    if sender.contact or sender.id in KNOWN_CONTACT_IDS:
        logger.debug(f"Ignoriere Nachricht von Kontakt: {sender.id} ({sender.first_name})")
        return

    await process_scammer_message(sender, event.message)

async def check_existing_unread_messages():
    """Scannt beim Start alle Dialoge nach bereits wartenden ungelesenen Nachrichten von Nicht-Kontakten."""
    logger.info("🔍 Scanne nach bereits wartenden Nachrichten von Unbekannten...")
    try:
        async for dialog in client.iter_dialogs(limit=50):
            if not dialog.is_user:
                continue
            entity = dialog.entity
            if not isinstance(entity, User):
                continue
            if entity.is_self or entity.bot or entity.verified:
                continue
            if entity.contact or entity.id in KNOWN_CONTACT_IDS:
                continue
            
            # Wenn ungelesen und letzte Nachricht nicht von uns
            if dialog.unread_count > 0 and dialog.message and not dialog.message.out:
                logger.info(f"🎯 Ungelesener Chat von Unbekannt gefunden: {entity.first_name} (ID: {entity.id})")
                asyncio.create_task(process_scammer_message(entity, dialog.message))
    except Exception as e:
        logger.warning(f"Fehler beim Prüfen bestehender Dialoge: {e}")

async def main():
    database.init_db()
    logger.info("Starte Scambaiter Telegram Client...")
    
    await client.start(phone=config.TELEGRAM_PHONE if config.TELEGRAM_PHONE else None)
    logger.info("✅ Erfolgreich bei Telegram eingeloggt!")

    await refresh_contacts()
    
    me = await client.get_me()
    logger.info(f"Eingeloggt als: {me.first_name} (@{me.username or 'kein username'}) [ID: {me.id}]")

    # Auch bereits vor dem Start eingegangene ungelesene Chats verarbeiten
    await check_existing_unread_messages()
    
    logger.info("👂 Bot lauscht auf eingehende Nachrichten von Nicht-Kontakten...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot gestoppt.")
