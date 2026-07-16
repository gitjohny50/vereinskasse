"""Erstbefüllung der Datenbank.

- Rollen werden immer sichergestellt.
- Ein Erst-Administrator wird nur angelegt, wenn noch kein Benutzer existiert.
  Die PIN kommt aus VK_INITIAL_ADMIN_PIN oder wird erzeugt und einmalig ins
  Log geschrieben. Sie MUSS im Produktivbetrieb geändert werden (Lastenheft 25.1
  - keine Standardpasswörter).
- Ein Demo-Kassenprofil mit Beispielsortiment erleichtert den Einstieg; es kann
  gelöscht oder ersetzt werden.
"""
from __future__ import annotations

import logging
import os
import secrets

from sqlalchemy.orm import Session

from . import models
from .auth import STUFE_ADMIN, STUFE_BEDIENER, STUFE_SERVICE
from .security import hash_pin

log = logging.getLogger("vereinskasse.seed")

ROLLEN = [
    ("bediener", STUFE_BEDIENER, "Verkauf und Pfandrückgabe"),
    ("administrator", STUFE_ADMIN, "Stammdaten, Stornos, Auswertungen"),
    ("servicetechniker", STUFE_SERVICE, "Hardware, Diagnose, Wiederherstellung"),
]


def ensure_roles(session: Session) -> dict[str, models.Rolle]:
    vorhanden = {r.name: r for r in session.query(models.Rolle).all()}
    for name, stufe, beschreibung in ROLLEN:
        if name not in vorhanden:
            rolle = models.Rolle(name=name, stufe=stufe, beschreibung=beschreibung)
            session.add(rolle)
            vorhanden[name] = rolle
    session.commit()
    return vorhanden


def ensure_initial_admin(session: Session, rollen: dict[str, models.Rolle]) -> None:
    if session.query(models.Benutzer).count() > 0:
        return
    pin = os.environ.get("VK_INITIAL_ADMIN_PIN") or "".join(secrets.choice("0123456789") for _ in range(6))
    admin = models.Benutzer(
        name="Administrator",
        pin_hash=hash_pin(pin),
        rolle_id=rollen["administrator"].id,
    )
    session.add(admin)
    session.commit()
    log.warning("Erst-Administrator angelegt (ID %s). Start-PIN: %s - bitte umgehend ändern!", admin.id, pin)


def ensure_demo_profile(session: Session) -> None:
    if session.query(models.Kassenprofil).count() > 0:
        return
    verein = models.Verein(name="Musterverein e.V.", anschrift="Musterstraße 1, 71522 Backnang")
    session.add(verein)
    session.flush()

    profil = models.Kassenprofil(
        name="Vereinsfest", verein_id=verein.id,
        bonkopf="Musterverein e.V.", bonfuss="Vielen Dank für Ihren Besuch!",
    )
    session.add(profil)
    session.flush()

    getraenke = models.Kategorie(kassenprofil_id=profil.id, name="Getränke", farbe="#0e7c6b", sortierung=1)
    essen = models.Kategorie(kassenprofil_id=profil.id, name="Essen", farbe="#b45309", sortierung=2)
    session.add_all([getraenke, essen])
    session.flush()

    # Genau eine Pfandart: Glaspfand. Wird automatisch auf jedes Getränk gebucht
    # und ist als einzige rückgabefähig - dadurch bietet die Pfandrücknahme nur "Glas".
    glaspfand = models.Pfandart(
        kassenprofil_id=profil.id, name="Glaspfand", kurzname="Glas",
        betrag_cent=200, rueckgabe_erlaubt=True, sortierung=1,
    )
    session.add(glaspfand)
    session.flush()

    cola = models.Artikel(kassenprofil_id=profil.id, name="Cola", preis_cent=250, kategorie_id=getraenke.id, sortierung=1)
    wasser = models.Artikel(kassenprofil_id=profil.id, name="Wasser", preis_cent=200, kategorie_id=getraenke.id, sortierung=2)
    pommes = models.Artikel(kassenprofil_id=profil.id, name="Pommes", preis_cent=400, kategorie_id=essen.id, sortierung=1)
    session.add_all([cola, wasser, pommes])
    session.flush()

    # Jedes Getränk bekommt automatisch Glaspfand (ein Glas je Stück).
    session.add_all([
        models.ArtikelPfandZuordnung(artikel_id=cola.id, pfandart_id=glaspfand.id, menge_pro_einheit=1, automatisch=True),
        models.ArtikelPfandZuordnung(artikel_id=wasser.id, pfandart_id=glaspfand.id, menge_pro_einheit=1, automatisch=True),
    ])

    session.add_all([
        models.Zahlungsmethode(kassenprofil_id=profil.id, name="Bar", kurzname="Bar", sortierung=1,
                               schublade_oeffnen=True, rueckgeld_berechnen=True),
        models.Zahlungsmethode(kassenprofil_id=profil.id, name="Karte", kurzname="Karte", sortierung=2,
                               schublade_oeffnen=False, rueckgeld_berechnen=False),
    ])
    session.commit()


def seed_all(session: Session) -> None:
    rollen = ensure_roles(session)
    ensure_initial_admin(session, rollen)
    ensure_demo_profile(session)
