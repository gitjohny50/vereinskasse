#!/usr/bin/env python3
"""API-Testlauf fuer Kasse, Drucker und Kassenschublade.

Das Skript nutzt nur die Standardbibliothek, damit es auf dem Raspberry Pi ohne
zusaetzliche Python-Pakete laufen kann.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from datetime import datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class ApiError(RuntimeError):
    pass


class Client:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = ""

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        data = None
        headers = {"Accept": "application/json"}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        req = Request(f"{self.base_url}{path}", data=data, headers=headers, method=method)
        try:
            with urlopen(req, timeout=30) as res:
                payload = res.read()
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")
            raise ApiError(f"{method} {path} -> HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise ApiError(f"{method} {path} fehlgeschlagen: {exc.reason}") from exc

        if not payload:
            return {}
        return json.loads(payload.decode("utf-8"))

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        suffix = f"?{urlencode(params)}" if params else ""
        return self.request("GET", f"{path}{suffix}")

    def post(self, path: str, body: dict[str, Any] | None = None) -> Any:
        return self.request("POST", path, body or {})


def log(message: str) -> None:
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}", flush=True)


def cents(value: int) -> str:
    return f"{value / 100:.2f} EUR".replace(".", ",")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Dauer- und Abnahmetest fuer Vereinskasse, Drucker und Kassenschublade."
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Backend-URL")
    parser.add_argument("--user-id", type=int, required=True, help="Benutzer-ID fuer den Login")
    parser.add_argument("--pin", required=True, help="PIN fuer den Login")
    parser.add_argument("--profil-id", type=int, help="Kassenprofil-ID; sonst erstes aktives Profil")
    parser.add_argument("--veranstaltung-id", type=int, help="Optionale Veranstaltung fuer die Testverkaeufe")
    parser.add_argument("--modus", choices=("abnahme", "dauer"), default="abnahme")
    parser.add_argument("--dauer-minuten", type=float, default=60.0, help="Laufzeit im Modus dauer")
    parser.add_argument("--intervall-sekunden", type=float, default=30.0, help="Pause zwischen Buchungen")
    parser.add_argument("--intervall-min-sekunden", type=float, default=5.0, help="Kleinste Pause im Dauertest")
    parser.add_argument("--intervall-max-sekunden", type=float, default=45.0, help="Groesste Pause im Dauertest")
    parser.add_argument("--max-verkaeufe", type=int, default=0, help="Optionales Limit im Modus dauer")
    parser.add_argument("--schnitt-anzahl", type=int, default=3, help="Anzahl Schnitte im Abnahmetest")
    parser.add_argument("--beleg-jeder-n", type=int, default=7, help="Jeder n-te Verkauf bekommt zusaetzlich einen Belegbon")
    parser.add_argument("--beleg-wahrscheinlichkeit", type=float, default=0.20, help="Zusatzchance pro Verkauf fuer Belegbon (0.0 bis 1.0)")
    parser.add_argument("--seed", type=int, help="Optionaler Zufalls-Seed fuer reproduzierbare Testlaeufe")
    parser.add_argument(
        "--ich-weiss-dass-gebucht-wird",
        action="store_true",
        help="Pflicht-Flag: bestaetigt echte Buchungen, Drucke und Schubladenimpulse.",
    )
    return parser.parse_args()


def require_real_run(args: argparse.Namespace) -> None:
    if args.ich_weiss_dass_gebucht_wird:
        return
    raise ApiError(
        "Abbruch: Der Test erzeugt echte Buchungen und Hardware-Aktionen. "
        "Starte erneut mit --ich-weiss-dass-gebucht-wird."
    )


def login(client: Client, args: argparse.Namespace) -> dict[str, Any]:
    token = client.post("/api/auth/login", {"benutzer_id": args.user_id, "pin": args.pin})
    client.token = token["token"]
    log(f"Angemeldet als {token['name']} ({token['rolle']}, Stufe {token['stufe']})")
    if token["stufe"] < 30:
        raise ApiError("Fuer Drucker- und Schubladendiagnose wird Service- oder Admin-Recht benoetigt.")
    return token


def pick_profile(client: Client, profil_id: int | None) -> dict[str, Any]:
    profiles = client.get("/api/kassenprofile")
    active = [p for p in profiles if p.get("aktiv", True)]
    if not active:
        raise ApiError("Kein aktives Kassenprofil gefunden.")
    if profil_id is None:
        profile = active[0]
    else:
        profile = next((p for p in profiles if p["id"] == profil_id), None)
        if profile is None:
            raise ApiError(f"Kassenprofil {profil_id} nicht gefunden.")
    log(f"Kassenprofil: {profile['name']} (ID {profile['id']})")
    return profile


def load_catalog(client: Client, profile_id: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    articles = client.get("/api/artikel", {"kassenprofil_id": profile_id})
    payments = client.get("/api/zahlungsmethoden", {"kassenprofil_id": profile_id})
    articles = [a for a in articles if a.get("aktiv", True) and not a.get("archiviert", False)]
    payments = [p for p in payments if p.get("aktiv", True)]
    if not articles:
        raise ApiError("Keine aktiven Artikel im Kassenprofil gefunden.")
    if not payments:
        raise ApiError("Keine aktive Zahlungsmethode im Kassenprofil gefunden.")
    log(f"Katalog geladen: {len(articles)} aktive Artikel, {len(payments)} aktive Zahlungsarten")
    return articles, payments


def pick_payment(payments: list[dict[str, Any]], prefer_drawer: bool) -> dict[str, Any]:
    matching = [p for p in payments if bool(p.get("schublade_oeffnen")) is prefer_drawer]
    if matching:
        return matching[0]
    return payments[0]


def build_cart(articles: list[dict[str, Any]], count: int | None = None) -> list[dict[str, int]]:
    size = count if count is not None else random.randint(1, min(3, len(articles)))
    sample = random.sample(articles, min(size, len(articles)))
    return [{"artikel_id": a["id"], "menge": random.randint(1, 3)} for a in sample]


def book_sale(
    client: Client,
    profile_id: int,
    event_id: int | None,
    articles: list[dict[str, Any]],
    payment: dict[str, Any],
    fixed_count: int | None = None,
) -> dict[str, Any]:
    cart = build_cart(articles, fixed_count)
    calc = client.post(
        "/api/verkauf/berechnung",
        {"kassenprofil_id": profile_id, "veranstaltung_id": event_id, "artikel": cart, "pfand_rueckgaben": []},
    )
    given = calc["gesamt_cent"]
    if payment.get("rueckgeld_berechnen"):
        given = ((calc["gesamt_cent"] + 99) // 100) * 100
    sale = client.post(
        "/api/verkauf",
        {
            "kassenprofil_id": profile_id,
            "veranstaltung_id": event_id,
            "artikel": cart,
            "pfand_rueckgaben": [],
            "zahlungsmethode_id": payment["id"],
            "gegeben_cent": given,
        },
    )
    return sale


def sale_summary(sale: dict[str, Any]) -> str:
    parts = []
    for pos in sale.get("positionen", []):
        if pos.get("typ") != "artikel":
            continue
        parts.append(f"{pos.get('menge', 0)}x {pos.get('bezeichnung', '?')}")
    return ", ".join(parts[:4]) + (" ..." if len(parts) > 4 else "")


def should_print_receipt(count: int, every_n: int, probability: float) -> bool:
    if every_n > 0 and count % every_n == 0:
        return True
    probability = max(0.0, min(1.0, probability))
    return random.random() < probability


def next_interval(min_seconds: float, max_seconds: float, fallback: float) -> float:
    if min_seconds <= 0 or max_seconds <= 0:
        return fallback
    lower = min(min_seconds, max_seconds)
    upper = max(min_seconds, max_seconds)
    return random.uniform(lower, upper)


def process_queue(client: Client) -> dict[str, Any]:
    result = client.post("/api/druckwarteschlange/verarbeiten")
    status = client.get("/api/druckwarteschlange/status")
    log(
        "Druckwarteschlange: "
        f"verarbeitet={result.get('verarbeitet', 0)}, "
        f"fehlgeschlagen={status.get('fehlgeschlagen', 0)}, offen={status.get('offen', 0)}"
    )
    return status


def run_acceptance(client: Client, profile_id: int, event_id: int | None, articles: list[dict[str, Any]], payments: list[dict[str, Any]], cut_count: int) -> None:
    log("Abnahmetest startet")
    printer = client.get("/api/diagnose/drucker/status")
    log(f"Druckerstatus: verfuegbar={printer.get('available')}, detail={printer.get('detail')}")
    client.post("/api/diagnose/drucker/testseite")
    log("Testseite gesendet")
    client.post("/api/diagnose/drucker/schnitt-test", {"anzahl": cut_count})
    log(f"Schnitt-Test gesendet ({cut_count} Schnitte)")
    client.post("/api/diagnose/schublade/oeffnen", {"grund": "API-Abnahmetest"})
    log("Schubladenimpuls gesendet")

    sale = book_sale(client, profile_id, event_id, articles, pick_payment(payments, True), fixed_count=1)
    log(f"Testverkauf gebucht: Beleg {sale['belegnummer']} / {cents(sale['gesamt_cent'])}")
    client.post(f"/api/verkauf/{sale['id']}/beleg")
    log("Original-Beleg erneut angefordert")
    client.post(f"/api/verkauf/{sale['id']}/nachdruck")
    log("Nachdruck angefordert")
    process_queue(client)
    log("Abnahmetest fertig")


def run_endurance(
    client: Client,
    profile_id: int,
    event_id: int | None,
    articles: list[dict[str, Any]],
    payments: list[dict[str, Any]],
    minutes: float,
    interval: float,
    interval_min: float,
    interval_max: float,
    max_sales: int,
    receipt_every_n: int,
    receipt_probability: float,
) -> None:
    log(
        f"Dauertest startet: {minutes:g} Minuten, variable Intervalle "
        f"{interval_min:g}-{interval_max:g} Sekunden"
    )
    deadline = time.monotonic() + minutes * 60
    count = 0
    receipt_count = 0
    drawer_payment = pick_payment(payments, True)
    quiet_payment = pick_payment(payments, False)

    while time.monotonic() < deadline:
        if max_sales and count >= max_sales:
            break
        count += 1
        payment = drawer_payment if count % 2 else quiet_payment
        sale = book_sale(client, profile_id, event_id, articles, payment)
        log(
            f"#{count:04d}: Beleg {sale['belegnummer']} / {cents(sale['gesamt_cent'])} "
            f"/ Zahlung {payment['name']} / {sale_summary(sale)}"
        )
        if should_print_receipt(count, receipt_every_n, receipt_probability):
            client.post(f"/api/verkauf/{sale['id']}/beleg")
            receipt_count += 1
            log(f"#{count:04d}: Belegbon zusaetzlich angefordert")
        process_queue(client)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        pause = next_interval(interval_min, interval_max, interval)
        log(f"Pause {pause:.1f} Sekunden")
        time.sleep(min(pause, remaining))

    status = client.get("/api/druckwarteschlange/status")
    log(
        f"Dauertest fertig: {count} Verkaeufe, {receipt_count} zusaetzliche Belegbons, "
        f"offen={status.get('offen', 0)}, fehlgeschlagen={status.get('fehlgeschlagen', 0)}"
    )


def main() -> int:
    args = parse_args()
    try:
        if args.seed is not None:
            random.seed(args.seed)
        require_real_run(args)
        client = Client(args.base_url)
        login(client, args)
        profile = pick_profile(client, args.profil_id)
        articles, payments = load_catalog(client, profile["id"])
        if args.modus == "abnahme":
            run_acceptance(client, profile["id"], args.veranstaltung_id, articles, payments, args.schnitt_anzahl)
        else:
            run_endurance(
                client,
                profile["id"],
                args.veranstaltung_id,
                articles,
                payments,
                args.dauer_minuten,
                args.intervall_sekunden,
                args.intervall_min_sekunden,
                args.intervall_max_sekunden,
                args.max_verkaeufe,
                args.beleg_jeder_n,
                args.beleg_wahrscheinlichkeit,
            )
    except KeyboardInterrupt:
        log("Abbruch durch Benutzer")
        return 130
    except ApiError as exc:
        print(f"FEHLER: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
