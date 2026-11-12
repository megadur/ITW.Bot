import asyncio
import logging
import random
import sys
from collections import defaultdict
from typing import Dict, List

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

# Debounce & Concurrency-Schutz pro User (verhindert Mehrfach-Antworten bei Foto-Alben oder Nachrichten-Salven)
MESSAGE_BUFFERS: Dict[int, List[str]] = defaultdict(list)
DEBOUNCE_TASKS: Dict[int, asyncio.Task] = {}
USER_LOCKS: Dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)
LAST_MESSAGES: Dict[int, object] = {}
SEEN_GROUPS = set()

DEBOUNCE_SECONDS = 8  # Wartet 8s nach der letzten Nachricht, ob noch weitere Bilder/Texte nachkommen


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


async def process_buffered_messages(sender: User):
    """Wartet kurz ab (Debounce) und verarbeitet dann alle gesammelten Nachrichten eines Users auf einmal."""
    user_id = sender.id
    try:
        await asyncio.sleep(DEBOUNCE_SECONDS)
    except asyncio.CancelledError:
        # Es kam noch eine Nachricht/ein Bild nach -> Timer wurde neu gestartet
        return

    async with USER_LOCKS[user_id]:
        buffered = MESSAGE_BUFFERS.pop(user_id, [])
        last_msg = LAST_MESSAGES.pop(user_id, None)
        if not buffered:
            return

        combined_text = "\n".join(buffered).strip()
        logger.info(f"🚨 Scambait-Aktion für: {sender.first_name} (ID: {user_id}) -> '{combined_text}'")

        # In Datenbank erfassen / prüfen
        chat_info = database.get_or_create_chat(
            user_id=user_id,
            first_name=sender.first_name or "",
            last_name=sender.last_name or "",
            username=sender.username or "",
            phone=sender.phone or ""
        )

        if chat_info.get("status") == "ignored":
            logger.info(f"User {user_id} ist auf 'ignored'. Breche ab.")
            return

        if chat_info.get("reply_count", 0) >= config.MAX_REPLIES_PER_CHAT:
            logger.info(f"User {user_id} hat Limit von {config.MAX_REPLIES_PER_CHAT} erreicht.")
            return

        # Gesammelte Nachricht speichern
        database.save_message(user_id, "scammer", combined_text)

        # Menschliches Verhalten simulieren
        total_delay = random.randint(config.MIN_DELAY_SECONDS, config.MAX_DELAY_SECONDS)
        read_delay = min(8, max(2, total_delay // 5))

        logger.info(f"⏳ Lese Nachricht in {read_delay}s und denke nach...")
        await asyncio.sleep(read_delay)
        if last_msg:
            try:
                await last_msg.mark_read()
            except Exception as e:
                logger.debug(f"mark_read fehlgeschlagen: {e}")

        # KI-Antwort generieren
        history = database.get_chat_history(user_id, limit=12)
        reply_text = brain.generate_reply(history)

        # Tipp-Dauer realistisch an Textlänge anpassen
        typing_delay = min(15, max(3, len(reply_text) // 7))
        wait_before_typing = max(5, total_delay - read_delay - typing_delay)

        logger.info(f"⏳ Warte {wait_before_typing}s, tippe dann {typing_delay}s...")
        await asyncio.sleep(wait_before_typing)

        # Wenn während der Wartezeit schon wieder neue Nachrichten eingetrudelt sind,
        # bleiben wir ruhig – der neue Debounce-Task übernimmt gleich.
        if MESSAGE_BUFFERS[user_id]:
            logger.info(f"ℹ️ Während des Wartens kam noch etwas von {sender.first_name}. Passe Antwort an...")

        # "Tippt..." Status anzeigen
        try:
            async with client.action(user_id, 'typing'):
                await asyncio.sleep(typing_delay)
        except Exception as e:
            logger.debug(f"Typing-Action fehlgeschlagen: {e}")

        # Antwort direkt senden (eine einzige Nachricht!)
        try:
            await client.send_message(user_id, reply_text)
            database.save_message(user_id, "bot", reply_text)
            logger.info(f"📤 Antwort an {sender.first_name} ({user_id}) gesendet: '{reply_text}'")

            if config.NOTIFY_SAVED_MESSAGES:
                summary = (
                    f"🎣 **Scambaiter Live-Update**\n"
                    f"👤 **{sender.first_name}** (`{user_id}`): {combined_text}\n"
                    f"🤖 **Antwort:** {reply_text}"
                )
                await client.send_message('me', summary)
        except Exception as e:
            logger.error(f"Fehler beim Senden der Antwort an {user_id}: {e}")


def queue_message(sender: User, message):
    """Reiht eine eingehende Nachricht in den Debounce-Buffer für diesen User ein."""
    user_id = sender.id
    grouped_id = getattr(message, "grouped_id", None)
    raw_text = message.raw_text.strip() if hasattr(message, 'raw_text') and message.raw_text else ""

    if grouped_id:
        if grouped_id in SEEN_GROUPS and not raw_text:
            # Weiteres Bild aus demselben Foto-Album ohne eigenen Text -> nicht 10x loggen!
            LAST_MESSAGES[user_id] = message
            if user_id in DEBOUNCE_TASKS and not DEBOUNCE_TASKS[user_id].done():
                DEBOUNCE_TASKS[user_id].cancel()
            DEBOUNCE_TASKS[user_id] = asyncio.create_task(process_buffered_messages(sender))
            return
        SEEN_GROUPS.add(grouped_id)
        if len(SEEN_GROUPS) > 500:
            SEEN_GROUPS.clear()

    if not raw_text:
        text_entry = "[Mehrere Bilder/Medien empfangen]" if grouped_id else "[Bild/Sticker/Sprachnachricht empfangen]"
    else:
        text_entry = raw_text

    # Doppelte Platzhalter im selben Burst vermeiden
    if not (text_entry.startswith("[") and MESSAGE_BUFFERS[user_id] and MESSAGE_BUFFERS[user_id][-1] == text_entry):
        MESSAGE_BUFFERS[user_id].append(text_entry)

    LAST_MESSAGES[user_id] = message

    # Vorherigen Timer abbrechen und neu starten
    if user_id in DEBOUNCE_TASKS and not DEBOUNCE_TASKS[user_id].done():
        DEBOUNCE_TASKS[user_id].cancel()

    DEBOUNCE_TASKS[user_id] = asyncio.create_task(process_buffered_messages(sender))


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

    queue_message(sender, event.message)


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

            if dialog.unread_count > 0 and dialog.message and not dialog.message.out:
                logger.info(f"🎯 Ungelesener Chat von Unbekannt gefunden: {entity.first_name} (ID: {entity.id})")
                queue_message(entity, dialog.message)
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

    await check_existing_unread_messages()

    logger.info("👂 Bot lauscht auf eingehende Nachrichten von Nicht-Kontakten...")
    await client.run_until_disconnected()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot gestoppt.")
