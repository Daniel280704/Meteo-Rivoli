#!/usr/bin/env python3
import requests
import feedparser
import os
import re

ARPA_RSS_URL = "https://www.arpa.piemonte.it/rischi_naturali/rss/allerte.xml"
FILE_ID_ULTIMA_ALLERTA = "last_alert.txt"

def estrai_colore(titolo):
    for colore in ["Gialla", "Arancione", "Rossa"]:
        if colore.lower() in titolo.lower():
            return colore
    return "di colore non specificato"

def main():
    feed = feedparser.parse(ARPA_RSS_URL)
    if not feed.entries: return

    # Filtriamo ESCLUSIVAMENTE per la Zona L
    allerta_zona_l = None
    for entry in feed.entries:
        # \b garantisce che matchi solo "zona l" e non altre zone
        if re.search(r"\bzona\s+l\b", entry.title, re.IGNORECASE):
            allerta_zona_l = entry
            break
    
    if not allerta_zona_l:
        print("Nessuna allerta per la Zona L (Rivoli) al momento.")
        return

    id_allerta = allerta_zona_l.id
    titolo = allerta_zona_l.title
    colore = estrai_colore(titolo)
    
    # Controllo duplicati
    if os.path.exists(FILE_ID_ULTIMA_ALLERTA):
        with open(FILE_ID_ULTIMA_ALLERTA, "r") as f:
            if f.read().strip() == id_allerta:
                return

    # Invio su Telegram
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    messaggio = f"⚠️ **Allerta {colore} nel comune di Rivoli**\n\n{titolo}\n\n👉 [Leggi dettagli]({allerta_zona_l.link})"
    
    requests.post(f"https://api.telegram.org/bot{token}/sendMessage", 
                  data={"chat_id": chat_id, "text": messaggio, "parse_mode": "Markdown"})
    
    # Salviamo l'ID
    with open(FILE_ID_ULTIMA_ALLERTA, "w") as f:
        f.write(id_allerta)

if __name__ == "__main__":
    main()