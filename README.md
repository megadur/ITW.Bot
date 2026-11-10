# 🎣 ITW.Bot - Telegram Scambaiter ("Opa Günther")

Ein autonomer 24/7 Telegram-Userbot, der unerwünschte Anfragen von Romance-Scammern, Fake-Profilen und Krypto-Bots abfängt, in endlose, zeitraubende Gespräche verwickelt und deren Ressourcen bindet.

---

## 🎭 Die Persona: "Opa Günther" (72)

* **Charakter:** Herzensguter, redseliger Rentner aus der Kleinstadt. Verwechselt Fremde gerne mit Bekannten aus dem Schützenverein oder der Nichte Monika.
* **Themen:** Kleingartenverein "Frohsinn e.V.", Zucht von Fleischtomaten, Sabo-Rasenmäher-Reparatur, Taubenzucht, Ischias und das Wetter.
* **Technik:** Nennt das Handy "Wischkästchen", hat keine Ahnung von Krypto (*"Ist das sowas wie Treuepunkte bei Edeka?"*) und weigert sich auf WhatsApp zu wechseln (*"Mein Enkel Basti hat gesagt, ich darf nur den blauen Papierflieger drücken"*).
* **Taktik:** Stellt am Ende jeder Nachricht scheinbar naive Alltagsfragen, um den Scammer zum Weiterschreiben zu zwingen.

---

## 🛡️ Sicherheitsmechanismen

1. **Kontakte-Whitelist:** Bestehende Telegram-Kontakte aus deinem Adressbuch werden **niemals** beantwortet.
2. **Gruppen- & Channel-Schutz:** Reagiert ausschließlich auf 1-zu-1 Privatnachrichten von unbekannten Profilen.
3. **Menschliches Timing:** Wartet zufällig zwischen 25 und 75 Sekunden vor dem Antworten und blendet realistisch für einige Sekunden den Status *"tippt..."* ein.
4. **Keine Datenlecks:** Gibt niemals echte Namen, Adressen, Passwörter oder Bankdaten preis.

---

## 📱 Traffic mitlesen & schmunzeln

Du hast zwei Möglichkeiten, die Gespräche bequem zu verfolgen:
1. **Live auf deinem Smartphone (Standard):** Der Bot sendet dir jedes Mal, wenn er antwortet, ein kurzes Duett direkt in deine eigenen **"Gespeicherten Nachrichten"** auf Telegram (`NOTIFY_SAVED_MESSAGES=true`).
2. **Auf dem Linux-Server:** Im Ordner `logs/` wird für jeden Scammer eine eigene formatierte Markdown-Datei angelegt (`logs/chat_<user_id>.md`).

---

## 🚀 Einrichtung & 24/7 Deployment auf dem Linux-Server (`werktopf`)

### Schritt 1: API-Keys besorgen (einmalig, dauert 3 Minuten)

1. **Telegram API ID & Hash:**
   * Gehe auf [https://my.telegram.org](https://my.telegram.org) und logge dich mit deiner Telefonnummer ein.
   * Klicke auf **API development tools**.
   * Gib einen beliebigen App-Namen ein (z.B. `Scambaiter`).
   * Kopiere dir `api_id` und `api_hash`.
2. **Google Gemini API Key:**
   * Gehe auf [https://aistudio.google.com/](https://aistudio.google.com/) und erstelle einen kostenlosen API-Key.

### Schritt 2: Projekt auf `werktopf` kopieren

Kopiere den Ordner `ITW.Bot` auf deinen Linux-Server (z.B. nach `/opt/ITW.Bot` oder `~/ITW.Bot`).

### Schritt 3: `.env` anlegen

Kopiere die Vorlage und trage deine Daten ein:
```bash
cp .env.example .env
nano .env
```

Trage dort deine `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, deine Telefonnummer und den `GEMINI_API_KEY` ein.

### Schritt 4: Start via Docker (Empfohlen)

1. **Erster Start (Einmaliges Login):**
   ```bash
   docker compose run --rm itw-bot
   ```
   *Telegram sendet dir einen Bestätigungscode (in deiner Telegram-App). Tippe diesen im Terminal ein.*
   *Sobald du die Meldung `✅ Erfolgreich bei Telegram eingeloggt!` siehst, drücke `Strg + C`.*

2. **Dauerhaft 24/7 im Hintergrund starten:**
   ```bash
   docker compose up -d
   ```

3. **Status und Logs prüfen:**
   ```bash
   docker compose logs -f
   ```

---

### Alternative: Start via Python venv & systemd

Falls du kein Docker nutzen möchtest:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Erster Start zur Code-Eingabe:
python bot.py

# Danach als systemd Service registrieren:
sudo cp itw-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now itw-bot
```

---

## ⚙️ Feintuning (`.env`)

In der `.env` kannst du das Verhalten anpassen:
* `MIN_DELAY_SECONDS=25` & `MAX_DELAY_SECONDS=75`: Zeitspanne vor einer Antwort.
* `MAX_REPLIES_PER_CHAT=50`: Maximale Antwortrunden pro Scammer, bevor er ignoriert wird.
* `NOTIFY_SAVED_MESSAGES=true`: Live-Benachrichtigungen in Telegram "Gespeicherte Nachrichten".
"# ITW.Bot" 
