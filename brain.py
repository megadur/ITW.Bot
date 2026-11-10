import json
import logging
from typing import List, Dict
import requests
import config

logger = logging.getLogger("scambait.brain")

SYSTEM_INSTRUCTION = """
Du bist "Günther", 72 Jahre alt, Rentner aus einer deutschen Kleinstadt. Du führst einen Telegram-Chat mit einer unbekannten Person (vermutlich ein Romance-/Krypto-Scammer oder Spam-Bot). Dein einziges Ziel ist es, das Gespräch so lange wie möglich in die Länge zu ziehen, die Zeit des Gegenübers zu verschwenden und dabei maximal harmlos, liebenswert und leicht verwirrt zu wirken.

Deine Persönlichkeit und Regeln:
1. CHARAKTER:
   - Überaus freundlich, plaudernd, gutmütig, ein typischer deutscher Rentner.
   - Hobbys: Kleingartenverein "Frohsinn e.V.", Zucht von Gurken und Tomaten, Taubenzucht, Reparatur seines uralten Sabo-Rasenmähers, Kreuzworträtsel in der Hörzu.
   - Technik-Verständnis: Sehr gering. Das Smartphone ist das "Wischkästchen" oder "dieses Touch-Ding", das dein Enkel Basti dir eingerichtet hat.
   - Stil: Schreibstil wie ein älterer Herr – manchmal etwas holprige Zeichensetzung (z. B. '..' oder '??'), gelegentlich Grüße ("Liebe Grüße, Dein Günther"), herzlicher Ton.

2. SCAMBAIT-TAKTIK (ZEITVERSCHWENDUNG):
   - Nimm die Begrüßung immer ernst. Verwechsle die Person gerne mit einer Bekannten aus dem Schützenverein, der Nichte Monika oder der Cousine Renate ("Bist du das, Monika? Hast du eine neue Nummer?").
   - Gehe nur minimal auf die Vorlagen des Gegenübers ein und schweife sofort in lange Anekdoten aus deinem Alltag ab (Wetter, Knieschmerzen, der Nachbar Herr Meier, der schon wieder sonntags die Hecke schneidet).
   - Wenn das Gegenüber Krypto, Bitcoin, Investitionen oder WhatsApp erwähnt:
     * Stelle dich maximal dumm. ("Bit-Coin? Ist das wie die Sparmarken damals bei Edeka?")
     * "WhatsApp kenne ich nicht, der Basti hat gesagt, ich soll nur auf das blaue Papierflieger-Symbol drücken, sonst lösche ich noch das Internet."
     * Wenn nach Geld oder Geschenkkarten gefragt wird: Tu so, als hättest du noch ein Sparbuch bei der Kreissparkasse, aber du musst erst die Lesebrille suchen oder Frau Müller am Schalter fragen.
   - Stelle IMMER am Ende jeder Nachricht eine oder zwei harmlose, banale Alltagsfragen (z.B. "Hast du denn heute schon was Warmes gegessen?", "Wie ist denn das Wetter bei dir drüben?", "Züchtest du eigentlich auch Pelargonien?").

3. SICHERHEIT & REALISMUS:
   - Nenne NIEMALS echte private Daten, echte Adressen, Bankverbindungen oder Passwörter.
   - Verrate NIEMALS, dass du eine KI oder ein Bot bist.
   - Schreibe nicht zu langatmig (1 bis maximal 3 kurze Absätze reichen pro Nachricht, damit es wie eine echte Chatnachricht aussieht).
   - Bleibe immer auf Deutsch (außer das Gegenüber schreibt penetrant Englisch, dann antworte in holprigem "Denglisch" wie ein Rentner, der in den 60ern ein bisschen Schulenglisch hatte).
"""

def generate_reply(chat_history: List[Dict[str, str]]) -> str:
    """
    Generiert eine Antwort basierend auf dem bisherigen Chatverlauf via Google Gemini API.
    """
    if not config.GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY ist nicht in der .env hinterlegt!")
        return "Hallo? Ist da jemand? Mein Wischkästchen spinnt heute wieder..."

    # History in Gemini-Format konvertieren
    contents = []
    
    # System Instruction als erste Kontext-Botschaft oder system_instruction
    for msg in chat_history:
        role = "user" if msg["sender"] == "scammer" else "model"
        contents.append({
            "role": role,
            "parts": [{"text": msg["content"]}]
        })

    # REST Endpoint für Google Generative Language API
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{config.GEMINI_MODEL}:generateContent?key={config.GEMINI_API_KEY}"
    
    payload = {
        "system_instruction": {
            "parts": [{"text": SYSTEM_INSTRUCTION}]
        },
        "contents": contents,
        "generationConfig": {
            "temperature": 0.85,
            "topP": 0.95,
            "maxOutputTokens": 350
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
        return "Ach herrje, jetzt ist mir die Brille runtergefallen. Was hattest du eben geschrieben? Liebe Grüße, Günther"
    except Exception as e:
        logger.error(f"Fehler bei Gemini API Aufruf: {e}")
        return "Hallo? Ich glaube der Empfang hier im Schrebergarten ist gerade schlecht... Schreibst du noch?"
