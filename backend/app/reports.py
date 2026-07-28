"""Kassenabschluss und Berichte (Phase 5).

X-Bericht  = Zwischenstand über die noch offenen Verkäufe, ohne etwas zu ändern.
Z-Bericht  = Tagesabschluss: fasst die offenen Verkäufe zusammen, schließt sie ab
             (setzt `verkaufsposition.abschluss_id`), speichert den Abschluss unveränderlich
             und druckt ihn über die Warteschlange.

Alle Beträge sind ganzzahlige Cent.
"""
from __future__ import annotations

import csv
import io
import logging
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from . import models, print_queue
from .timeutils import to_local

log = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def offene_verkaeufe(session: Session, kassenprofil_id: int) -> list[models.Verkauf]:
    return (
        session.query(models.Verkauf)
        .join(models.Verkaufsposition)
        .filter(
            models.Verkauf.kassenprofil_id == kassenprofil_id,
            models.Verkaufsposition.abschluss_id.is_(None),
        )
        .distinct()
        .order_by(models.Verkauf.id)
        .all()
    )


def _offene_positionen_query(session: Session, kassenprofil_id: int):
    return (
        session.query(models.Verkaufsposition)
        .join(models.Verkauf)
        .filter(
            models.Verkauf.kassenprofil_id == kassenprofil_id,
            models.Verkaufsposition.abschluss_id.is_(None),
        )
    )


def _positionen_fuer_umfang(
    session: Session,
    kassenprofil_id: int,
    umfang_typ: str = "alle",
    kategorie_ids: list[int] | None = None,
    artikel_ids: list[int] | None = None,
) -> list[models.Verkaufsposition]:
    umfang_typ = umfang_typ or "alle"
    if umfang_typ not in {"alle", "rest", "kategorie", "artikel"}:
        raise HTTPException(status_code=422, detail="Ungültiger Abschluss-Umfang.")

    q = _offene_positionen_query(session, kassenprofil_id)
    if umfang_typ == "kategorie":
        ids = [int(i) for i in (kategorie_ids or [])]
        if not ids:
            raise HTTPException(status_code=422, detail="Bitte mindestens eine Kategorie auswählen.")
        q = q.join(models.Artikel, models.Verkaufsposition.artikel_id == models.Artikel.id).filter(
            models.Verkaufsposition.typ == "artikel",
            models.Artikel.kategorie_id.in_(ids),
        )
    elif umfang_typ == "artikel":
        ids = [int(i) for i in (artikel_ids or [])]
        if not ids:
            raise HTTPException(status_code=422, detail="Bitte mindestens einen Artikel auswählen.")
        q = q.filter(models.Verkaufsposition.typ == "artikel", models.Verkaufsposition.artikel_id.in_(ids))

    return q.order_by(models.Verkaufsposition.verkauf_id, models.Verkaufsposition.id).all()


def _umfang_beschreibung(
    session: Session,
    umfang_typ: str,
    kategorie_ids: list[int] | None,
    artikel_ids: list[int] | None,
) -> str:
    if umfang_typ == "rest":
        return "Alle übrigen Positionen"
    if umfang_typ == "artikel":
        rows = session.query(models.Artikel.name).filter(models.Artikel.id.in_(artikel_ids or [])).order_by(models.Artikel.name).all()
        return ", ".join(row.name for row in rows) or "Ausgewählte Artikel"
    if umfang_typ == "kategorie":
        rows = session.query(models.Kategorie.name).filter(models.Kategorie.id.in_(kategorie_ids or [])).order_by(models.Kategorie.name).all()
        return ", ".join(row.name for row in rows) or "Ausgewählte Kategorien"
    return "Alle offenen Positionen"


def _positionen_summary(positionen: list[models.Verkaufsposition]) -> dict:
    return {
        "positionen": len(positionen),
        "menge": sum(p.menge for p in positionen),
        "umsatz_cent": sum(p.gesamt_cent for p in positionen),
    }


def offene_uebersicht(session: Session, kassenprofil_id: int) -> dict:
    positionen = _offene_positionen_query(session, kassenprofil_id).order_by(models.Verkaufsposition.id).all()
    artikel_ids = {p.artikel_id for p in positionen if p.artikel_id is not None}
    artikel = {a.id: a for a in session.query(models.Artikel).filter(models.Artikel.id.in_(artikel_ids)).all()} if artikel_ids else {}
    kategorie_ids = {a.kategorie_id for a in artikel.values() if a.kategorie_id is not None}
    kategorien = {k.id: k for k in session.query(models.Kategorie).filter(models.Kategorie.id.in_(kategorie_ids)).all()} if kategorie_ids else {}

    nach_kategorie: dict[int | None, dict] = {}
    nach_artikel: dict[int, dict] = {}
    for p in positionen:
        if p.typ == "artikel" and p.artikel_id is not None:
            art = artikel.get(p.artikel_id)
            kid = art.kategorie_id if art else None
            kat = kategorien.get(kid) if kid is not None else None
            eintrag = nach_kategorie.setdefault(kid, {
                "kategorie_id": kid,
                "name": kat.name if kat else "Ohne Kategorie",
                "menge": 0,
                "umsatz_cent": 0,
                "positionen": 0,
            })
            art_eintrag = nach_artikel.setdefault(p.artikel_id, {
                "artikel_id": p.artikel_id,
                "bezeichnung": p.bezeichnung,
                "menge": 0,
                "umsatz_cent": 0,
                "positionen": 0,
            })
            art_eintrag["menge"] += p.menge
            art_eintrag["umsatz_cent"] += p.gesamt_cent
            art_eintrag["positionen"] += 1
        else:
            eintrag = nach_kategorie.setdefault(None, {
                "kategorie_id": None,
                "name": "Pfand",
                "menge": 0,
                "umsatz_cent": 0,
                "positionen": 0,
            })
        eintrag["menge"] += p.menge
        eintrag["umsatz_cent"] += p.gesamt_cent
        eintrag["positionen"] += 1

    return {
        "offen_gesamt": _positionen_summary(positionen),
        "nach_kategorie": sorted(nach_kategorie.values(), key=lambda x: (x["kategorie_id"] is None, x["name"])),
        "nach_artikel": sorted(nach_artikel.values(), key=lambda x: (-x["umsatz_cent"], x["bezeichnung"])),
    }


def _bar_methoden(session: Session, kassenprofil_id: int) -> dict[int, bool]:
    """Zahlarten, die Bargeld in die Schublade bringen (Näherung über
    schublade_oeffnen)."""
    rows = session.query(models.Zahlungsmethode).filter(
        models.Zahlungsmethode.kassenprofil_id == kassenprofil_id
    ).all()
    return {z.id: z.schublade_oeffnen for z in rows}


def _aggregiere_positionen(
    session: Session,
    kassenprofil_id: int,
    positionen: list[models.Verkaufsposition],
    *,
    anfangsbestand_cent: int,
    gezaehlt_cent: int | None,
    kassensturz: bool,
) -> dict:
    bar_map = _bar_methoden(session, kassenprofil_id)
    waren = pfand = gesamt = bar = 0
    zahlarten: dict[int | None, dict] = {}
    artikel: dict[str, dict] = {}
    zeitpunkte: list[datetime] = []
    verkaeufe = sorted({p.verkauf for p in positionen}, key=lambda v: v.id)
    selected_ids = {p.id for p in positionen}

    for p in positionen:
        if p.typ == "artikel":
            waren += p.gesamt_cent
        else:
            pfand += p.gesamt_cent
        gesamt += p.gesamt_cent
        a = artikel.setdefault(p.bezeichnung, {"bezeichnung": p.bezeichnung, "menge": 0, "betrag_cent": 0})
        a["menge"] += p.menge
        a["betrag_cent"] += p.gesamt_cent

    davon_teiloffen = 0
    for v in verkaeufe:
        zeitpunkte.append(v.zeitpunkt)
        if any(p.abschluss_id is None and p.id not in selected_ids for p in v.positionen):
            davon_teiloffen += 1
        if not kassensturz:
            continue
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
        "betroffene_belege": len(verkaeufe),
        "davon_teiloffen": davon_teiloffen,
    }


def x_bericht(session: Session, kassenprofil_id: int, anfangsbestand_cent: int = 0,
              gezaehlt_cent: int | None = None, umfang_typ: str = "alle",
              kategorie_ids: list[int] | None = None, artikel_ids: list[int] | None = None) -> dict:
    kassensturz = umfang_typ in {"alle", "rest"}
    daten = _aggregiere_positionen(
        session,
        kassenprofil_id,
        _positionen_fuer_umfang(session, kassenprofil_id, umfang_typ, kategorie_ids, artikel_ids),
        anfangsbestand_cent=anfangsbestand_cent if kassensturz else 0,
        gezaehlt_cent=gezaehlt_cent if kassensturz else None,
        kassensturz=kassensturz,
    )
    daten.update({
        "typ": "X", "nummer": None, "umfang_typ": umfang_typ,
        "umfang_beschreibung": _umfang_beschreibung(session, umfang_typ, kategorie_ids, artikel_ids),
    })
    return daten


def erstelle_z(session: Session, kassenprofil_id: int, benutzer: models.Benutzer,
               anfangsbestand_cent: int = 0, gezaehlt_cent: int | None = None,
               umfang_typ: str = "alle", kategorie_ids: list[int] | None = None,
               artikel_ids: list[int] | None = None) -> models.Kassenabschluss:
    positionen = _positionen_fuer_umfang(session, kassenprofil_id, umfang_typ, kategorie_ids, artikel_ids)
    if not positionen:
        raise HTTPException(status_code=422, detail="Keine offenen Positionen im gewählten Umfang.")
    kassensturz = umfang_typ in {"alle", "rest"}
    daten = _aggregiere_positionen(
        session,
        kassenprofil_id,
        positionen,
        anfangsbestand_cent=anfangsbestand_cent if kassensturz else 0,
        gezaehlt_cent=gezaehlt_cent if kassensturz else None,
        kassensturz=kassensturz,
    )

    anzahl_bisher = session.query(models.Kassenabschluss).filter(
        models.Kassenabschluss.kassenprofil_id == kassenprofil_id
    ).count()
    nummer = f"Z-{anzahl_bisher + 1:04d}"

    abschluss = models.Kassenabschluss(
        kassenprofil_id=kassenprofil_id, nummer=nummer, benutzer_id=benutzer.id,
        von_zeitpunkt=daten["von"], bis_zeitpunkt=daten["bis"],
        anzahl_verkaeufe=daten["anzahl_verkaeufe"], waren_cent=daten["waren_cent"],
        pfand_cent=daten["pfand_cent"], gesamt_cent=daten["gesamt_cent"], bar_cent=daten["bar_cent"],
        anfangsbestand_cent=daten["anfangsbestand_cent"], erwartet_cent=daten["erwartet_cent"],
        gezaehlt_cent=daten["gezaehlt_cent"], differenz_cent=daten["differenz_cent"],
        umfang_typ=umfang_typ, umfang_beschreibung=_umfang_beschreibung(session, umfang_typ, kategorie_ids, artikel_ids),
    )
    session.add(abschluss)
    session.flush()

    for z in daten["zahlarten"]:
        session.add(models.KassenabschlussZahlart(
            abschluss_id=abschluss.id, zahlungsmethode_id=z["zahlungsmethode_id"],
            bezeichnung=z["bezeichnung"], anzahl=z["anzahl"], betrag_cent=z["betrag_cent"], bar=z["bar"],
        ))

    for p in positionen:
        p.abschluss_id = abschluss.id

    verkauf_ids = {p.verkauf_id for p in positionen}
    for verkauf_id in verkauf_ids:
        offen = session.query(models.Verkaufsposition.id).filter(
            models.Verkaufsposition.verkauf_id == verkauf_id,
            models.Verkaufsposition.abschluss_id.is_(None),
        ).first()
        if offen is None:
            verkauf = session.get(models.Verkauf, verkauf_id)
            if verkauf is not None:
                verkauf.abschluss_id = abschluss.id

    session.add(models.AuditLog(
        benutzer=benutzer.name, aktion="kassenabschluss.z", datensatz=nummer,
        nachher=f"{daten['gesamt_cent']} Cent, {daten['anzahl_verkaeufe']} Belege, {abschluss.umfang_beschreibung}",
    ))
    session.commit()
    session.refresh(abschluss)

    # Druck über die Warteschlange (best effort - der Abschluss ist gespeichert).
    try:
        druck_bericht(session, abschluss.id)
    except Exception as exc:  # noqa: BLE001  # pragma: no cover
        log.warning("Report printing failed: %s", exc)
    session.refresh(abschluss)
    return abschluss


def abschluss_bericht(session: Session, abschluss: models.Kassenabschluss) -> dict:
    """Rekonstruiert die Berichtsdaten eines gespeicherten Z-Abschlusses.
    Kopfzahlen aus dem Abschluss, Artikelaufstellung aus den zugeordneten Verkäufen."""
    positionen = (
        session.query(models.Verkaufsposition)
        .join(models.Verkauf)
        .filter(models.Verkaufsposition.abschluss_id == abschluss.id)
        .order_by(models.Verkauf.id, models.Verkaufsposition.id)
        .all()
    )
    artikel: dict[str, dict] = {}
    for p in positionen:
        a = artikel.setdefault(p.bezeichnung, {"bezeichnung": p.bezeichnung, "menge": 0, "betrag_cent": 0})
        a["menge"] += p.menge
        a["betrag_cent"] += p.gesamt_cent

    return {
        "typ": "Z", "nummer": abschluss.nummer, "abschluss_id": abschluss.id,
        "kassenprofil_id": abschluss.kassenprofil_id,
        "umfang_typ": abschluss.umfang_typ, "umfang_beschreibung": abschluss.umfang_beschreibung,
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


CSV_SPALTEN = [
    "abschluss_nummer",
    "abschluss_datum",
    "abschluss_uhrzeit",
    "belegnummer",
    "verkauf_datum",
    "verkauf_uhrzeit",
    "verkauf_stunde",
    "wochentag",
    "position_typ",
    "artikel",
    "menge",
    "einzelpreis_eur",
    "umsatz_eur",
    "zahlungsart",
    "gegeben_eur",
    "rueckgeld_eur",
]


def _local(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return to_local(dt)


def _datum(dt: datetime | None) -> str:
    local = _local(dt)
    return local.strftime("%Y-%m-%d") if local else ""


def _uhrzeit(dt: datetime | None) -> str:
    local = _local(dt)
    return local.strftime("%H:%M:%S") if local else ""


def _stunde(dt: datetime | None) -> str:
    local = _local(dt)
    return local.strftime("%H:00") if local else ""


def _wochentag(dt: datetime | None) -> str:
    local = _local(dt)
    return ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"][local.weekday()] if local else ""


def _eur(cent: int | None) -> str:
    if cent is None:
        return ""
    vorzeichen = "-" if cent < 0 else ""
    abs_cent = abs(cent)
    return f"{vorzeichen}{abs_cent // 100},{abs_cent % 100:02d}"


def _position_typ(typ: str) -> str:
    return {
        "artikel": "Artikel",
        "pfand": "Pfand",
        "pfand_rueckgabe": "Pfand Rueckgabe",
    }.get(typ, typ)


def abschluss_detail_csv(session: Session, abschluss: models.Kassenabschluss) -> str:
    """Erstellt einen digitalen Detailabschluss als CSV.

    Jede Verkaufsposition wird als eigene Zeile exportiert. Dadurch lassen sich
    Artikel später nach Uhrzeit, Beleg, Zahlungsart oder Pfandposition sauber
    auswerten, während der gedruckte Z-Abschluss unverändert bleibt.
    """
    positionen = (
        session.query(models.Verkaufsposition)
        .join(models.Verkauf)
        .filter(models.Verkaufsposition.abschluss_id == abschluss.id)
        .order_by(models.Verkauf.zeitpunkt, models.Verkauf.id, models.Verkaufsposition.id)
        .all()
    )

    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.DictWriter(output, fieldnames=CSV_SPALTEN, delimiter=";", lineterminator="\n")
    writer.writeheader()

    for position in positionen:
        verkauf = position.verkauf
        zahlung = verkauf.zahlungen[0] if verkauf.zahlungen else None
        basis = {
            "abschluss_nummer": abschluss.nummer,
            "abschluss_datum": _datum(abschluss.bis_zeitpunkt),
            "abschluss_uhrzeit": _uhrzeit(abschluss.bis_zeitpunkt),
            "belegnummer": verkauf.belegnummer,
            "verkauf_datum": _datum(verkauf.zeitpunkt),
            "verkauf_uhrzeit": _uhrzeit(verkauf.zeitpunkt),
            "verkauf_stunde": _stunde(verkauf.zeitpunkt),
            "wochentag": _wochentag(verkauf.zeitpunkt),
            "zahlungsart": zahlung.bezeichnung if zahlung else "",
            "gegeben_eur": _eur(zahlung.gegeben_cent) if zahlung else "",
            "rueckgeld_eur": _eur(zahlung.rueckgeld_cent) if zahlung else "",
        }
        writer.writerow({
            **basis,
            "position_typ": _position_typ(position.typ),
            "artikel": position.bezeichnung,
            "menge": position.menge,
            "einzelpreis_eur": _eur(position.einzelpreis_cent),
            "umsatz_eur": _eur(position.gesamt_cent),
        })

    return output.getvalue()


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
