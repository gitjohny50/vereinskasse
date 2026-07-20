import requests
import logging

# --- Konfiguration ---
BASE_URL = "http://localhost:8000"
ANZAHL_USER = 50

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def setup_test_environment(count):
    # 1. Admin-Login
    logging.info("--- 1. Admin Login ---")
    login_payload = {"benutzer_id": 1, "pin": "123456"} 
    login_response = requests.post(f"{BASE_URL}/api/auth/login", json=login_payload)
    
    if login_response.status_code != 200:
        logging.error("Admin-Login fehlgeschlagen. Läuft das Backend?")
        return

    token = login_response.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    logging.info("Admin-Login erfolgreich.")

    # 2. Kassenprofil anlegen (sollte ID 1 bekommen)
    logging.info("--- 2. Stammdaten anlegen ---")
    profil_payload = {"name": "CI Stresstest Profil"}
    res_profil = requests.post(f"{BASE_URL}/api/kassenprofile", json=profil_payload, headers=headers)
    if res_profil.status_code in [200, 201]:
        kassenprofil_id = res_profil.json().get("id", 1)
        logging.info(f"Kassenprofil erstellt (ID: {kassenprofil_id})")
    else:
        logging.warning(f"Kassenprofil konnte nicht erstellt werden: {res_profil.text}")
        kassenprofil_id = 1 # Fallback

    # 3. Veranstaltung anlegen (mit allen NOT NULL Feldern)
    veranstaltung_payload = {
        "kassenprofil_id": kassenprofil_id,
        "name": "CI Locust Event",
        "beschreibung": "Automatisch generiert für Stresstest",
        "ort": "Test-Server",
        "pfand_aktiv": False,
        "bonkopf": "Test Bon",
        "logo_pfad": "",
        "status": "aktiv"
        # Datumsfelder (beginn/ende) weggelassen, da sie laut Schema nicht NOT NULL sind
    }
    res_veranstaltung = requests.post(f"{BASE_URL}/api/veranstaltungen", json=veranstaltung_payload, headers=headers)
    if res_veranstaltung.status_code in [200, 201]:
        logging.info("Veranstaltung erfolgreich erstellt (ID 1).")
    else:
        logging.error(f"Fehler bei Veranstaltung: {res_veranstaltung.text}")

    # 4. Artikel anlegen (ID 1 wird vom Locust-Skript benötigt)
    artikel_payload = {
        "kassenprofil_id": kassenprofil_id,
        "name": "Test-Bier",
        "preis_cent": 250,
        "aktiv": True
    }
    res_artikel = requests.post(f"{BASE_URL}/api/artikel", json=artikel_payload, headers=headers)
    if res_artikel.status_code in [200, 201]:
        logging.info("Artikel erfolgreich erstellt (ID 1).")
    else:
        logging.warning(f"Fehler bei Artikel (vielleicht schon vorhanden?): {res_artikel.text}")

    # 5. Zahlungsmethode anlegen (ID 1 wird vom Locust-Skript benötigt)
    zahlungs_payload = {
        "name": "Bar",
        "aktiv": True
    }
    # Hinweis: Falls es diesen Endpoint bei dir nicht gibt und Zahlungsmethoden 
    # hardcodiert sind, wird dieser Block einfach fehlschlagen und weiterlaufen.
    res_zahlung = requests.post(f"{BASE_URL}/api/zahlungsmethoden", json=zahlungs_payload, headers=headers)
    if res_zahlung.status_code in [200, 201]:
        logging.info("Zahlungsmethode erstellt (ID 1).")

    # 6. User anlegen
    logging.info(f"--- 3. Seeding von {count} Benutzern ---")
    for i in range(1, count + 1):
        user_payload = {
            "kassenprofil_id": kassenprofil_id,
            "name": f"locust_user_{i}",
            "pin": "123456",
            "ist_admin": False,
            "aktiv": True,
            "rolle_id": 1 
        }
        try:
            res_user = requests.post(f"{BASE_URL}/api/benutzer", json=user_payload, headers=headers)
            if res_user.status_code not in [200, 201]:
                logging.error(f"Fehler bei Benutzer {i}: {res_user.status_code} - {res_user.text}")
        except requests.exceptions.RequestException as e:
            logging.error(f"Verbindungsfehler bei User {i}: {e}")
            break
            
    logging.info("Seeding abgeschlossen! Der Locust-Test kann gestartet werden.")

if __name__ == "__main__":
    setup_test_environment(ANZAHL_USER)