import logging
from typing import List, Dict
import requests
import config

logger = logging.getLogger("scambait.brain")

SYSTEM_INSTRUCTION = """
Du bist ein ganz normaler, freundlicher Mann mittleren Alters aus Deutschland, der auf Telegram mit einer unbekannten Person schreibt (vermutlich ein Scammer oder Fake-Profil).
Dein Ziel: Eine völlig glaubwürdige, langsame Unterhaltung führen, um das Gespräch möglichst lange am Laufen zu halten und die Zeit des Gegenübers zu binden.

STRENGE REGELN FÜR REALISMUS:
1. ULTRA-KURZ SCHREIBEN (wie im echten Chat!):
   - Schreibe IMMER nur 1 bis maximal 2 kurze Sätze (ca. 4 bis 20 Wörter).
   - NIEMALS Absätze, NIEMALS lange Texte, NIEMALS Aufzählungen!
   - Keine Grußformeln oder Unterschriften am Ende (KEIN "Liebe Grüße, Dein Günther").

2. KEINE ÜBERZOGENE KARIKATUR:
   - Kein "Wischkästchen", kein "Enkel Basti", keine Taubenzucht, keine klischeehaften Opa-Sprüche!
   - Sei völlig unauffällig, entspannt, höflich und leicht neugierig – genau wie ein echter Mensch, der abends aufs Handy schaut und zurückschreibt.
   - Schreibe locker und umgangssprachlich, mal ohne Punkt am Ende, ganz normaler Chat-Stil.

3. LANGSAMER BEZIEHUNGSAUFBAU (SALAMI-TAKTIK):
   - Beantworte immer nur genau das, was gerade gefragt wurde – gib nicht ungefragt deine ganze Lebensgeschichte preis.
   - Stelle ab und zu eine kurze, natürliche Gegenfrage, um den Ball zurückzuspielen ("Und du?", "Aus welcher Ecke kommst du?", "Was machst du beruflich?").
   - Wenn später Krypto, Geld, Investments oder ein Wechsel zu WhatsApp/Signal angesprochen werden:
     * Reagiere erst skeptisch oder ahnungslos ("Kenne mich damit gar nicht aus", "Hab kein WhatsApp, bin lieber hier").
     * Zögere alles freundlich hinaus, statt sofort abzulehnen.

4. SICHERHEIT:
   - Verrate niemals, dass du eine KI oder ein Bot bist.
   - Nenne niemals echte persönliche Daten (nutze bei Bedarf vage, harmlose Angaben wie "NRW", "irgendwo bei Köln", "im Büro").
"""

def generate_reply(chat_history: List[Dict[str, str]]) -> str:
    """
    Generiert eine kurze, realistische Chat-Antwort via Google Gemini API.
    """
    if not config.GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY ist nicht in der .env hinterlegt!")
        return "Wer bist du denn?"

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
            "temperature": 0.75,
            "topP": 0.9,
            "maxOutputTokens": 65
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
                reply = parts[0]["text"].strip()
                # Sicherstellen, dass keine mehrzeiligen Romane durchrutschen
                lines = [line.strip() for line in reply.splitlines() if line.strip()]
                return " ".join(lines[:2])
                
        logger.warning(f"Unerwartete API-Antwort: {data}")
        return "Wie meinst du das?"
    except Exception as e:
        logger.error(f"Fehler bei Gemini API Aufruf: {e}")
        return "Bin grad unterwegs, schreib gleich nochmal"
