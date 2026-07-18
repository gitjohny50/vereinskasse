"""Kassenabschluss und Berichte (Phase 5).

X-Bericht  = Zwischenstand über die noch offenen Verkäufe, ohne etwas zu ändern.
Z-Bericht  = Tagesabschluss: fasst die offenen Verkäufe zusammen, schließt sie ab
             (setzt `verkauf.abschluss_id`), speichert den Abschluss unveränderlich
             und druckt ihn über die Warteschlange.

Alle Beträge sind ganzzahlige Cent.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from . import models
from . import print_queue


def _now() -> datetime:
    return datetime.now(timezone.utc)


def offene_verkaeufe(session: Session, kassenprofil_id: int) -> list[models.Verkauf]:
    return (
        session.query(models.Verkauf)
        .filter(models.Verkauf.kassenprofil_id == kassenprofil_id, models.Verkauf.abschluss_id.is_(None))
        .order_by(models.Verkauf.id)
        .all()
    )


def _bar_methoden(session: Session, kassenprofil_id: int) -> dict[int, bool]:
    """Zahlarten, die Bargeld in die Schublade bringen (Näherung über
    schublade_oeffnen)."""
    rows = session.query(models.Zahlungsmethode).filter(
        models.Zahlungsmethode.kassenprofil_id == kassenprofil_id
    ).all()
    return {z.id: z.schublade_oeffnen for z in rows}


def _aggregiere(session: Session, kassenprofil_id: int, verkaeufe: list[models.Verkauf],
                *, anfangsbestand_cent: int, gezaehlt_cent: int | None) -> dict:
    bar_map = _bar_methoden(session, kassenprofil_id)
    waren = pfand = gesamt = bar = 0
    zahlarten: dict[int | None, dict] = {}
    artikel: dict[str, dict] = {}
    zeitpunkte: list[datetime] = []

    for v in verkaeufe:
        waren += v.waren_cent
        pfand += v.pfand_cent
        gesamt += v.gesamt_cent
        zeitpunkte.append(v.zeitpunkt)
        for z in v.zahlungen:
            ist_bar = bar_map.get(z.zahlungsmethode_id, False)
            eintrag = zahlarten.setdefault(z.zahlungsmethode_id, {
                "zahlungsmethode_id": z.zahlungsmethode_id, "bezeichnung": z.bezeichnung,
                "anzahl": 0, "betrag_cent": 0, "bar": ist_bar,
            })
            eintrag["anzahl"] += 1
            eintrag["betrag_cent"] += z.betrag_cent
            if ist_bar:
                bar += z.betrag_cent
        for p in v.positionen:
            if p.typ != "artikel":
                continue
            a = artikel.setdefault(p.bezeichnung, {"bezeichnung": p.bezeichnung, "menge": 0, "betrag_cent": 0})
            a["menge"] += p.menge
            a["betrag_cent"] += p.gesamt_cent

    erwartet = anfangsbestand_cent + bar
    differenz = None if gezaehlt_cent is None else gezaehlt_cent - erwartet

    return {
        "kassenprofil_id": kassenprofil_id,
        "von": min(zeitpunkte) if zeitpunkte else None,
        "bis": _now(),
        "anzahl_verkaeufe": len(verkaeufe),
        "waren_cent": waren, "pfand_cent": pfand, "gesamt_cent": gesamt, "bar_cent": bar,
        "anfangsbestand_cent": anfangsbestand_cent, "erwartet_cent": erwartet,
        "gezaehlt_cent": gezaehlt_cent, "differenz_cent": differenz,
        "zahlarten": sorted(zahlarten.values(), key=lambda x: -x["betrag_cent"]),
        "artikel": sorted(artikel.values(), key=lambda x: -x["betrag_cent"]),
    }


def x_bericht(session: Session, kassenprofil_id: int, anfangsbestand_cent: int = 0,
              gezaehlt_cent: int | None = None) -> dict:
    daten = _aggregiere(session, kassenprofil_id, offene_verkaeufe(session, kassenprofil_id),
                        anfangsbestand_cent=anfangsbestand_cent, gezaehlt_cent=gezaehlt_cent)
    daten.update({"typ": "X", "nummer": None})
    return daten


def erstelle_z(session: Session, kassenprofil_id: int, benutzer: models.Benutzer,
               anfangsbestand_cent: int = 0, gezaehlt_cent: int | None = None) -> models.Kassenabschluss:
    verkaeufe = offene_verkaeufe(session, kassenprofil_id)
    daten = _aggregiere(session, kassenprofil_id, verkaeufe,
                        anfangsbestand_cent=anfangsbestand_cent, gezaehlt_cent=gezaehlt_cent)

    anzahl_bisher = session.query(models.Kassenabschluss).filter(
        models.Kassenabschluss.kassenprofil_id == kassenprofil_id
    ).count()
    nummer = f"Z-{anzahl_bisher + 1:04d}"

    abschluss = models.Kassenabschluss(
        kassenprofil_id=kassenprofil_id, nummer=nummer, benutzer_id=benutzer.id,
        von_zeitpunkt=daten["von"], bis_zeitpunkt=daten["bis"],
        anzahl_verkaeufe=daten["anzahl_verkaeufe"], waren_cent=daten["waren_cent"],
        pfand_cent=daten["pfand_cent"], gesamt_cent=daten["gesamt_cent"], bar_cent=daten["bar_cent"],
        anfangsbestand_cent=anfangsbestand_cent, erwartet_cent=daten["erwartet_cent"],
        gezaehlt_cent=gezaehlt_cent, differenz_cent=daten["differenz_cent"],
    )
    session.add(abschluss)
    session.flush()

    for z in daten["zahlarten"]:
        session.add(models.KassenabschlussZahlart(
            abschluss_id=abschluss.id, zahlungsmethode_id=z["zahlungsmethode_id"],
            bezeichnung=z["bezeichnung"], anzahl=z["anzahl"], betrag_cent=z["betrag_cent"], bar=z["bar"],
        ))

    # Offene Verkäufe abschließen (unveränderliche Zuordnung).
    for v in verkaeufe:
        v.abschluss_id = abschluss.id

    session.add(models.AuditLog(
        benutzer=benutzer.name, aktion="kassenabschluss.z", datensatz=nummer,
        nachher=f"{daten['gesamt_cent']} Cent, {daten['anzahl_verkaeufe']} Verkäufe",
    ))
    session.commit()
    session.refresh(abschluss)

    # Druck über die Warteschlange (best effort - der Abschluss ist gespeichert).
    try:
        druck_bericht(session, abschluss.id)
    except Exception:  # pragma: no cover
        pass
    session.refresh(abschluss)
    return abschluss


def abschluss_bericht(session: Session, abschluss: models.Kassenabschluss) -> dict:
    """Rekonstruiert die Berichtsdaten eines gespeicherten Z-Abschlusses.
    Kopfzahlen aus dem Abschluss, Artikelaufstellung aus den zugeordneten Verkäufen."""
    verkaeufe = (
        session.query(models.Verkauf)
        .filter(models.Verkauf.abschluss_id == abschluss.id)
        .order_by(models.Verkauf.id)
        .all()
    )
    artikel: dict[str, dict] = {}
    for v in verkaeufe:
        for p in v.positionen:
            if p.typ != "artikel":
                continue
            a = artikel.setdefault(p.bezeichnung, {"bezeichnung": p.bezeichnung, "menge": 0, "betrag_cent": 0})
            a["menge"] += p.menge
            a["betrag_cent"] += p.gesamt_cent

    return {
        "typ": "Z", "nummer": abschluss.nummer, "abschluss_id": abschluss.id,
        "kassenprofil_id": abschluss.kassenprofil_id,
        "von": abschluss.von_zeitpunkt, "bis": abschluss.bis_zeitpunkt,
        "anzahl_verkaeufe": abschluss.anzahl_verkaeufe, "waren_cent": abschluss.waren_cent,
        "pfand_cent": abschluss.pfand_cent, "gesamt_cent": abschluss.gesamt_cent, "bar_cent": abschluss.bar_cent,
        "anfangsbestand_cent": abschluss.anfangsbestand_cent, "erwartet_cent": abschluss.erwartet_cent,
        "gezaehlt_cent": abschluss.gezaehlt_cent, "differenz_cent": abschluss.differenz_cent,
        "zahlarten": [
            {"zahlungsmethode_id": z.zahlungsmethode_id, "bezeichnung": z.bezeichnung,
             "anzahl": z.anzahl, "betrag_cent": z.betrag_cent, "bar": z.bar}
            for z in abschluss.zahlarten
        ],
        "artikel": sorted(artikel.values(), key=lambda x: -x["betrag_cent"]),
    }


def druck_bericht(session: Session, abschluss_id: int, printer=None) -> dict:
    """Druckt einen gespeicherten Z-Abschluss über die Druckwarteschlange."""
    from .hardware import service as hw

    abschluss = session.get(models.Kassenabschluss, abschluss_id)
    profil = session.get(models.Kassenprofil, abschluss.kassenprofil_id)
    daten = abschluss_bericht(session, abschluss)
    cfg = hw.load_hw_settings(session)
    payload = hw.build_bericht_bytes(cfg, daten, profil.name if profil else "")
    job = print_queue.enqueue(session, dokumenttyp="Kassenabschluss", payload=payload, bezeichnung=abschluss.nummer)
    ok = print_queue._versuch(session, job, print_queue._printer(session, printer))
    return {"ok": ok, "detail": job.letzte_fehlermeldung, "auftrag_id": job.id, "drucker": job.drucker}
