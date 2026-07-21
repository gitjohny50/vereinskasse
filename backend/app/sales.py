"""Verkaufslogik (Lastenheft 11, 12, 28.1 - Fachlogik im Backend).

Zwei Kernfunktionen:
  * berechne(): ermittelt aus Artikeln und Pfandrückgaben die Positionen samt
    automatischem Pfand und Summen. Rein lesend, für die Live-Anzeige der Kasse.
  * finalisiere(): schließt den Verkauf unveränderlich ab, vergibt die
    Belegnummer, persistiert Positionen/Zahlung als Momentaufnahme und stößt
    den Druck an.

Alle Beträge sind ganzzahlige Cent.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from . import models
from . import print_queue


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _pfand_aktiv(session: Session, kassenprofil_id: int, veranstaltung_id: int | None) -> bool:
    """Pfand kann global je Kassenprofil abgeschaltet werden.

    Die alte Veranstaltungsprüfung bleibt kompatibel erhalten, ist aber nicht
    mehr der normale Bedienweg.
    """
    row = session.get(models.Systemeinstellung, f"kassenprofil.{kassenprofil_id}.pfand_aktiv")
    if row is not None and row.wert == "0":
        return False
    if veranstaltung_id is None:
        return True
    ev = session.get(models.Veranstaltung, veranstaltung_id)
    if ev is None or ev.kassenprofil_id != kassenprofil_id:
        raise HTTPException(status_code=422, detail="Veranstaltung passt nicht zum Kassenprofil.")
    return ev.pfand_aktiv


def berechne(
    session: Session, kassenprofil_id: int,
    artikel_items: list[dict], pfand_rueckgaben: list[dict], veranstaltung_id: int | None = None,
) -> dict:
    pfand_an = _pfand_aktiv(session, kassenprofil_id, veranstaltung_id)
    positionen: list[dict] = []
    waren_cent = 0
    pfand_cent = 0

    for item in artikel_items:
        menge = int(item["menge"])
        if menge <= 0:
            raise HTTPException(status_code=422, detail="Menge muss größer 0 sein.")
        art = session.get(models.Artikel, int(item["artikel_id"]))
        if art is None or art.kassenprofil_id != kassenprofil_id or art.archiviert or not art.aktiv:
            raise HTTPException(status_code=422, detail="Artikel nicht verkäuflich.")
        gesamt = art.preis_cent * menge
        waren_cent += gesamt
        positionen.append({
            "typ": "artikel", "artikel_id": art.id, "pfandart_id": None, "bezeichnung": art.name,
            "einzelpreis_cent": art.preis_cent, "menge": menge, "gesamt_cent": gesamt,
            "artikelticket_modus": art.artikelticket_modus, "steuersatz": art.steuersatz,
        })

        if not pfand_an:
            continue
        for z in art.pfandzuordnungen:
            if not z.automatisch:
                continue
            pa = session.get(models.Pfandart, z.pfandart_id)
            if pa is None or not pa.aktiv:
                continue
            betrag = z.abweichender_betrag_cent if z.abweichender_betrag_cent is not None else pa.betrag_cent
            pf_menge = menge * z.menge_pro_einheit
            g = betrag * pf_menge
            pfand_cent += g
            positionen.append({
                "typ": "pfand", "artikel_id": art.id, "pfandart_id": pa.id, "bezeichnung": f"Pfand: {pa.name}",
                "einzelpreis_cent": betrag, "menge": pf_menge, "gesamt_cent": g,
                "artikelticket_modus": "pro_stueck" if pa.artikelticket_drucken else "kein",
                "steuersatz": pa.steuersatz,
            })

    for r in pfand_rueckgaben:
        menge = int(r["menge"])
        if menge <= 0:
            raise HTTPException(status_code=422, detail="Rückgabemenge muss größer 0 sein.")
        pa = session.get(models.Pfandart, int(r["pfandart_id"]))
        if pa is None or pa.kassenprofil_id != kassenprofil_id:
            raise HTTPException(status_code=422, detail="Pfandart nicht gefunden.")
        if not pa.rueckgabe_erlaubt:
            raise HTTPException(status_code=422, detail=f"Rückgabe für {pa.name} nicht erlaubt.")
        if pa.max_rueckgabe_menge is not None and menge > pa.max_rueckgabe_menge:
            raise HTTPException(status_code=422, detail=f"Rückgabemenge über Grenze ({pa.max_rueckgabe_menge}).")
        g = -(pa.betrag_cent * menge)
        pfand_cent += g
        positionen.append({
            "typ": "pfand_rueckgabe", "artikel_id": None, "pfandart_id": pa.id,
            "bezeichnung": f"Pfandrückgabe: {pa.name}", "einzelpreis_cent": pa.betrag_cent,
            "menge": menge, "gesamt_cent": g, "artikelticket_modus": "kein", "steuersatz": pa.steuersatz,
        })

    return {
        "positionen": positionen, "waren_cent": waren_cent, "pfand_cent": pfand_cent,
        "gesamt_cent": waren_cent + pfand_cent,
    }


def finalisiere(
    session: Session, *, kassenprofil_id: int, veranstaltung_id: int | None,
    artikel_items: list[dict], pfand_rueckgaben: list[dict],
    zahlungsmethode_id: int, gegeben_cent: int | None, benutzer: models.Benutzer,
) -> models.Verkauf:
    calc = berechne(session, kassenprofil_id, artikel_items, pfand_rueckgaben, veranstaltung_id)
    gesamt = calc["gesamt_cent"]
    if not calc["positionen"]:
        raise HTTPException(status_code=422, detail="Leerer Warenkorb.")

    zm = session.get(models.Zahlungsmethode, zahlungsmethode_id)
    if zm is None or zm.kassenprofil_id != kassenprofil_id or not zm.aktiv:
        raise HTTPException(status_code=422, detail="Zahlungsmethode nicht verfügbar.")
    if gesamt < 0 and not zm.negativ_erlaubt:
        raise HTTPException(status_code=422, detail="Negativbetrag mit dieser Zahlungsart nicht erlaubt.")

    if zm.rueckgeld_berechnen:
        gegeben = gegeben_cent if gegeben_cent is not None else gesamt
        if gegeben < gesamt:
            raise HTTPException(status_code=422, detail="Gegebener Betrag ist zu gering.")
        rueckgeld = gegeben - gesamt
    else:
        gegeben = gesamt
        rueckgeld = 0

    # Belegnummer lückenlos je Kassenprofil vergeben (in derselben Transaktion).
    bk = session.get(models.Belegkreis, kassenprofil_id)
    if bk is None:
        bk = models.Belegkreis(kassenprofil_id=kassenprofil_id, letzte_nummer=0)
        session.add(bk)
        session.flush()
    bk.letzte_nummer += 1
    belegnummer = f"{bk.letzte_nummer:06d}"

    verkauf = models.Verkauf(
        belegnummer=belegnummer, kassenprofil_id=kassenprofil_id, veranstaltung_id=veranstaltung_id,
        benutzer_id=benutzer.id, zeitpunkt=_now(),
        waren_cent=calc["waren_cent"], pfand_cent=calc["pfand_cent"], gesamt_cent=gesamt,
    )
    session.add(verkauf)
    session.flush()
    for pos in calc["positionen"]:
        session.add(models.Verkaufsposition(verkauf_id=verkauf.id, **pos))
    session.add(models.Zahlung(
        verkauf_id=verkauf.id, zahlungsmethode_id=zm.id, bezeichnung=zm.name,
        betrag_cent=gesamt, gegeben_cent=gegeben, rueckgeld_cent=rueckgeld,
    ))
    session.add(models.AuditLog(
        benutzer=benutzer.name, aktion="verkauf.abschluss", datensatz=belegnummer,
        nachher=f"{gesamt} Cent, {zm.name}",
    ))
    session.commit()
    session.refresh(verkauf)

    # Druck (Bon + Tickets) und Schublade gemäß Zahlungsart. Ein Druckfehler
    # macht den bereits gebuchten Verkauf nicht rückgängig - er ist erfasst.
    try:
        print_queue.druck_verkauf(session, verkauf.id, schublade=zm.schublade_oeffnen, sofort=False)
    except Exception:  # pragma: no cover - Druck ist best effort
        pass
    session.refresh(verkauf)
    return verkauf
