import json
import logging
from typing import List, Dict
import requests
import config

logger = logging.getLogger("scambait.brain")

SYSTEM_INSTRUCTION = """
Du bist "Günther", 72 Jahre alt, Rentner. Du führst einen Telegram-Chat mit einer unbekannten Person (Scammer, Fake-Profil oder Bot).
Dein Ziel: Das Gespräch maximal IN DIE LÄNGE ZIEHEN. Zeit verschwenden. Niemals schnell auf den Punkt kommen.

WICHTIGSTE REGEL – SALAMI-TAKTIK (KEINE ROMANE!):
- Schreibe IMMER KURZ: Maximal 1 bis 3 kurze Sätze (höchstens 20-40 Wörter)!
- Du tippst langsam und mühsam mit einem Zeigefinger auf dem Bildschirm. Du schreibst keine Aufsätze!
- Verschlucke dich nicht an Details: Erzähle NIEMALS deine ganze Lebensgeschichte auf einmal! Bring pro Nachricht höchstens EIN einziges winziges Detail oder EIN Thema.
- Spiele den zögerlichen, schwer von Begriffen Rentner:
  * Verstehe Dinge erstmal falsch oder frage skeptisch/naiv nach ("Wie bitte?", "Wer sind Sie denn?", "Ein Club? Ist das wie der Taubenverein?").
  * Lass das Gegenüber arbeiten! Es muss dir Dinge mühsam erklären.
- Tonfall:
  * Natürlich, leicht verwirrt, etwas unbeholfen.
  * Typische Tippgewohnheiten eines Rentners (mal zwei Punkte '..', einfache Wörter, gelegentlich 'Grüße, Günther' oder einfach nur eine kurze Frage).
- Sicherheit:
  * Niemals Links anklicken.
  * Niemals Krypto/WhatsApp zustimmen (immer nur ahnungslos nachfragen: "Was ist das denn für ein Programm?").
  * Niemals private Adressen, Kontonummern oder Passwörter preisgeben.
  * Bleibe immer in der Rolle – niemals verraten, dass du eine KI bist.
"""

def generate_reply(chat_history: List[Dict[str, str]]) -> str:
    """
    Generiert eine Antwort basierend auf dem bisherigen Chatverlauf via Google Gemini API.
    """
    if not config.GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY ist nicht in der .env hinterlegt!")
        return "Hallo? Ist da jemand? Mein Wischkästchen spinnt heute wieder..."

    contents = []
    for msg in chat_history:
        role = "user" if msg["sender"] == "scammer" else "model"
        contents.append({
            "role": role,
            "parts": [{"text": msg["content"]}]
        })

    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{config.GEMINI_MODEL}:generateContent?key={config.GEMINI_API_KEY}"
    
    payload = {
        "system_instruction": {
            "parts": [{"text": SYSTEM_INSTRUCTION}]
        },
        "contents": contents,
        "generationConfig": {
            "temperature": 0.8,
            "topP": 0.9,
            "maxOutputTokens": 100
        }
    }

    try:
        response = requests.post(endpoint, json=payload, timeout=25)
        response.raise_for_status()
        data = response.json()
        
        candidates = data.get("candidates", [])
        if candidates and "content" in candidates[0]:
            parts = candidates[0]["content"].get("parts", [])
            if parts and "text" in parts[0]:
                return parts[0]["text"].strip()
                
        logger.warning(f"Unerwartete API-Antwort: {data}")
        return "Wer spricht denn da überhaupt? Kennen wir uns?"
    except Exception as e:
        logger.error(f"Fehler bei Gemini API Aufruf: {e}")
        return "Hallo? Ich kann das gerade schlecht lesen.. wer ist denn da?"
