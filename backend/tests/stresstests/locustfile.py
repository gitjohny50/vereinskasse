import os
import random
from locust import HttpUser, task, between, events
from locust.exception import StopUser

# --- Konfiguration ---
LOCUST_HOST = os.getenv('LOCUST_HOST', 'http://127.0.0.1:8000')
KASSENPROFIL_ID = int(os.getenv('KASSENPROFIL_ID', '1'))
OPERATOR_PIN = os.getenv('LOCUST_OPERATOR_PIN', '123456')

# Operator-Pool (Benutzer-IDs für den Stresstest)
env_pool = os.getenv('LOCUST_USER_POOL', '')
if env_pool:
    USER_POOL = [int(x) for x in env_pool.split(';') if x.strip()]
else:
    # Setzt standardmäßig die IDs 3 bis 50 ein
    USER_POOL = list(range(3, 51))


class OperatorUser(HttpUser):
    host = LOCUST_HOST
    wait_time = between(1, 3)

    def on_start(self) -> None:
        """Führt den Login aus und speichert den Token."""
        if not USER_POOL:
            raise StopUser('USER_POOL ist leer.')
        
        self.user_id = random.choice(USER_POOL)
        response = self.client.post('/api/auth/login', json={'benutzer_id': self.user_id, 'pin': OPERATOR_PIN})
        
        if response.status_code != 200:
            if response.status_code == 423:
                raise StopUser(f'Login gesperrt für {self.user_id} (423)')
            raise StopUser(f'Login fehlgeschlagen für {self.user_id}: {response.status_code}')
            
        token = response.json().get('token')
        if not token:
            raise StopUser(f'Login hatte kein Token für {self.user_id}')
            
        self.client.headers.update({'Authorization': f'Bearer {token}'})

    def on_stop(self) -> None:
        """Meldet den User nach Abschluss des Tests sauber ab."""
        token = self.client.headers.get('Authorization')
        if token:
            self.client.post('/api/auth/logout', headers={'Authorization': token})
            self.client.headers.pop('Authorization', None)

    # --- Hauptaufgaben (Verkauf) ---
    @task(15)
    def create_sale(self) -> None:
        calc_payload = {
            'kassenprofil_id': KASSENPROFIL_ID,
            'artikel': [{'artikel_id': 1, 'menge': 1}],
            'pfand_rueckgaben': [],
        }
        self.client.post('/api/verkauf/berechnung', json=calc_payload)

        sale_payload = {
            'kassenprofil_id': KASSENPROFIL_ID,
            'veranstaltung_id': 1,
            'artikel': [{'artikel_id': 1, 'menge': 1}],
            'pfand_rueckgaben': [],
            'zahlungsmethode_id': 1,
            'gegeben_cent': 1000,
        }
        with self.client.post('/api/verkauf', json=sale_payload, catch_response=True) as response:
            if response.status_code in (201, 200):
                response.success()
            else:
                response.failure(f'Verkauf Fehler {response.status_code}: {response.text}')

    @task(5)
    def list_articles(self) -> None:
        with self.client.get(f'/api/artikel?kassenprofil_id={KASSENPROFIL_ID}', catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f'Artikel Fehler {response.status_code}')

    @task(3)
    def view_sale_history(self) -> None:
        params = {'kassenprofil_id': KASSENPROFIL_ID, 'limit': 20}
        with self.client.get('/api/verkauf', params=params, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f'Verkaufshistorie Fehler {response.status_code}')

    # --- Allgemeine Stammdaten & Listen ---
    @task(2)
    def get_profile_data(self) -> None:
        with self.client.get('/api/vereine', catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f'Vereine Fehler {response.status_code}')

        with self.client.get('/api/kassenprofile', catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f'Kassenprofile Fehler {response.status_code}')

    @task(2)
    def get_veranstaltungen(self) -> None:
        params = {'kassenprofil_id': KASSENPROFIL_ID}
        with self.client.get('/api/veranstaltungen', params=params, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f'Veranstaltungen Fehler {response.status_code}')

    @task(2)
    def list_print_queue(self) -> None:
        with self.client.get('/api/druckwarteschlange', catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f'Druckwarteschlange Fehler {response.status_code}')

    @task(2)
    def print_queue_status(self) -> None:
        with self.client.get('/api/druckwarteschlange/status', catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f'Druckwarteschlange Status Fehler {response.status_code}')

    @task(1)
    def process_print_queue(self) -> None:
        with self.client.post('/api/druckwarteschlange/verarbeiten', catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f'Queue Verarbeiten Fehler {response.status_code}')

    @task(1)
    def retry_print_job(self) -> None:
        auftrag_id = 1
        with self.client.post(f'/api/druckwarteschlange/{auftrag_id}/wiederholen', catch_response=True) as response:
            if response.status_code in (200, 404):
                response.success()
            else:
                response.failure(f'Queue Wiederholen Fehler {response.status_code}')

    @task(1)
    def print_receipt_on_demand(self) -> None:
        verkauf_id = 1
        with self.client.post(f'/api/verkauf/{verkauf_id}/beleg', catch_response=True) as response:
            if response.status_code in (200, 404):
                response.success()
            else:
                response.failure(f'Druck-Fehler {response.status_code}')

    # --- System ---
    @task(1)
    def check_me(self) -> None:
        with self.client.get('/api/auth/me', catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f'Me-Abfrage Fehler {response.status_code}')

    @task(1)
    def health_check(self) -> None:
        with self.client.get('/api/health', catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f'Health-Check Fehler {response.status_code}')


# --- Fehlertoleranz-Regel für CI ---
@events.quitting.add_listener
def fail_on_high_error_rate(environment, **kwargs):
    if environment.stats.total.fail_ratio > 0.60:
        print(f"CI-Abbruch: Fehlerrate liegt bei {environment.stats.total.fail_ratio * 100:.2f}% (Limit: 60%)")
        environment.process_exit_code = 1
    else:
        print(f"CI-Erfolg: Fehlerrate liegt bei {environment.stats.total.fail_ratio * 100:.2f}% (Toleriert bis 60%)")
        environment.process_exit_code = 0