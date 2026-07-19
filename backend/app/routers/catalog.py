"""Katalogverwaltung: Kategorien, Pfandarten, Artikel, Zahlungsmethoden.

Umgesetzte Geschäftsregeln:
  * Artikel werden nie physisch gelöscht, sondern archiviert (Lastenheft 8.2).
  * Artikel kopieren ohne ID/Artikelnummer/Barcode (8.3).
  * Reihenfolge per Positionsliste (8.4).
  * Sammelbearbeitung mehrerer Artikel (8.5).
  * Preise ausschließlich als Cent-Ganzzahlen (5.3).
Lesen ab Bediener, Schreiben nur Administrator.
"""
from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import require_admin, require_bediener
from ..database import get_session
from ..models import (
    Artikel,
    ArtikelPfandZuordnung,
    AuditLog,
    Kassenprofil,
    Kategorie,
    Pfandart,
    Verkauf,
    Zahlungsmethode,
)
from ..schemas import (
    ArtikelIn,
    ArtikelBulkActionOut,
    ArtikelCsvImportIn,
    ArtikelCsvImportOut,
    ArtikelOut,
    ArtikelUpdateIn,
    BulkArtikelIn,
    KategorieIn,
    KategorieOut,
    PfandartIn,
    PfandartOut,
    PfandZuordnungIn,
    PfandZuordnungOut,
    ReorderIn,
    ZahlungsmethodeIn,
    ZahlungsmethodeOut,
)

router = APIRouter(prefix="/api", tags=["katalog"])

TICKET_MODI = {"pro_stueck", "pro_position", "kein"}


def _profil_or_422(session: Session, profil_id: int) -> None:
    if session.get(Kassenprofil, profil_id) is None:
        raise HTTPException(status_code=422, detail="Unbekanntes Kassenprofil")


def _norm_name(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _kategorie_name_frei(session: Session, kassenprofil_id: int, name: str, *, exclude_id: int | None = None) -> bool:
    ziel = _norm_name(name)
    rows = session.query(Kategorie).filter(Kategorie.kassenprofil_id == kassenprofil_id).all()
    return all(k.id == exclude_id or _norm_name(k.name) != ziel for k in rows)


def _artikel_by_name(session: Session, kassenprofil_id: int) -> dict[str, Artikel]:
    rows = session.query(Artikel).filter(Artikel.kassenprofil_id == kassenprofil_id).all()
    return {_norm_name(a.name): a for a in rows}


def _pruefe_kategorie(session: Session, kassenprofil_id: int, kategorie_id: int | None) -> None:
    if kategorie_id is None:
        return
    k = session.get(Kategorie, kategorie_id)
    if k is None or k.kassenprofil_id != kassenprofil_id:
        raise HTTPException(status_code=422, detail="Kategorie passt nicht zum Kassenprofil")


def _parse_bool(value: str, default: bool = True) -> bool:
    text = value.strip().lower()
    if text == "":
        return default
    if text in {"1", "true", "wahr", "ja", "j", "yes", "y"}:
        return True
    if text in {"0", "false", "falsch", "nein", "n", "no"}:
        return False
    raise ValueError(f"Ungültiger Ja/Nein-Wert: {value}")


def _parse_cent(value: str) -> int:
    text = value.strip().replace("€", "").replace(" ", "")
    if not text:
        raise ValueError("Preis fehlt")
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    cent = round(float(text) * 100)
    if cent < 0:
        raise ValueError("Preis darf nicht negativ sein")
    return cent


def _lookup_by_name(rows, name: str):
    ziel = _norm_name(name)
    for row in rows:
        if _norm_name(row.name) == ziel or _norm_name(getattr(row, "kurzname", "")) == ziel:
            return row
    return None


def _get_or_create_kategorie(session: Session, kategorien: list[Kategorie], profil_id: int, name: str, allow_create: bool) -> tuple[Kategorie | None, bool]:
    if not name:
        return None, False
    kat = _lookup_by_name(kategorien, name)
    if kat is not None:
        return kat, False
    if not allow_create:
        raise ValueError(f"Kategorie nicht gefunden: {name}")
    kat = Kategorie(kassenprofil_id=profil_id, name=name, sortierung=len(kategorien) + 1, aktiv=True)
    session.add(kat)
    session.flush()
    kategorien.append(kat)
    return kat, True


def _parse_pfand_part(value: str) -> tuple[str, int, int | None]:
    parts = [p.strip() for p in value.split(":")]
    name = parts[0] if parts else ""
    if not name:
        raise ValueError("Pfandname fehlt")
    menge = int(parts[1]) if len(parts) >= 2 and parts[1] else 1
    betrag = _parse_cent(parts[2]) if len(parts) >= 3 and parts[2] else None
    return name, max(1, menge), betrag


def _get_or_create_pfandart(session: Session, pfandarten: list[Pfandart], profil_id: int, name: str, betrag_cent: int | None, allow_create: bool) -> tuple[Pfandart, bool]:
    pfand = _lookup_by_name(pfandarten, name)
    if pfand is not None:
        return pfand, False
    if not allow_create:
        raise ValueError(f"Pfandart nicht gefunden: {name}")
    if betrag_cent is None:
        raise ValueError(f"Pfandart nicht gefunden und kein Betrag angegeben: {name}")
    pfand = Pfandart(kassenprofil_id=profil_id, name=name, kurzname=name, betrag_cent=betrag_cent, aktiv=True, rueckgabe_erlaubt=True)
    session.add(pfand)
    session.flush()
    pfandarten.append(pfand)
    return pfand, True


# ===================================================================
# Kategorien (Lastenheft 9)
# ===================================================================
@router.get("/kategorien", response_model=list[KategorieOut], dependencies=[Depends(require_bediener)])
def kategorien(kassenprofil_id: int, session: Session = Depends(get_session)) -> list[KategorieOut]:
    rows = (
        session.query(Kategorie)
        .filter(Kategorie.kassenprofil_id == kassenprofil_id)
        .order_by(Kategorie.sortierung, Kategorie.name)
        .all()
    )
    return [_kat_out(k) for k in rows]


@router.post("/kategorien", response_model=KategorieOut, status_code=201, dependencies=[Depends(require_admin)])
def kategorie_anlegen(payload: KategorieIn, session: Session = Depends(get_session)) -> KategorieOut:
    _profil_or_422(session, payload.kassenprofil_id)
    if not _kategorie_name_frei(session, payload.kassenprofil_id, payload.name):
        raise HTTPException(status_code=409, detail="Kategorie existiert bereits.")
    k = Kategorie(**payload.model_dump())
    session.add(k)
    session.commit()
    session.refresh(k)
    return _kat_out(k)


@router.put("/kategorien/{kid}", response_model=KategorieOut, dependencies=[Depends(require_admin)])
def kategorie_aendern(kid: int, payload: KategorieIn, session: Session = Depends(get_session)) -> KategorieOut:
    k = session.get(Kategorie, kid)
    if k is None:
        raise HTTPException(status_code=404, detail="Kategorie nicht gefunden")
    if not _kategorie_name_frei(session, k.kassenprofil_id, payload.name, exclude_id=k.id):
        raise HTTPException(status_code=409, detail="Kategorie existiert bereits.")
    for field, value in payload.model_dump(exclude={"kassenprofil_id"}).items():
        setattr(k, field, value)
    session.commit()
    session.refresh(k)
    return _kat_out(k)


@router.delete("/kategorien/{kid}", response_model=KategorieOut, dependencies=[Depends(require_admin)])
def kategorie_loeschen(kid: int, session: Session = Depends(get_session)) -> KategorieOut:
    k = session.get(Kategorie, kid)
    if k is None:
        raise HTTPException(status_code=404, detail="Kategorie nicht gefunden")
    offene = (
        session.query(Verkauf.id)
        .filter(Verkauf.kassenprofil_id == k.kassenprofil_id, Verkauf.abschluss_id.is_(None))
        .first()
    )
    if offene is not None:
        raise HTTPException(status_code=409, detail="Es gibt noch offene Verkäufe. Bitte zuerst den Z-Abschluss durchführen.")
    artikel = session.query(Artikel).filter(Artikel.kategorie_id == k.id).all()
    vorher = f"{k.name}, {len(artikel)} Artikel"
    out = _kat_out(k)
    for a in artikel:
        a.kategorie_id = None
    session.delete(k)
    session.add(AuditLog(
        benutzer="administrator", aktion="kategorie.loeschen", datensatz=str(kid),
        vorher=vorher, nachher=f"{len(artikel)} Artikel ohne Kategorie",
    ))
    session.commit()
    return out


# ===================================================================
# Pfandarten (Lastenheft 10.3)
# ===================================================================
@router.get("/pfandarten", response_model=list[PfandartOut], dependencies=[Depends(require_bediener)])
def pfandarten(kassenprofil_id: int, session: Session = Depends(get_session)) -> list[PfandartOut]:
    rows = (
        session.query(Pfandart)
        .filter(Pfandart.kassenprofil_id == kassenprofil_id)
        .order_by(Pfandart.sortierung, Pfandart.name)
        .all()
    )
    return [_pfand_out(p) for p in rows]


@router.post("/pfandarten", response_model=PfandartOut, status_code=201, dependencies=[Depends(require_admin)])
def pfandart_anlegen(payload: PfandartIn, session: Session = Depends(get_session)) -> PfandartOut:
    _profil_or_422(session, payload.kassenprofil_id)
    p = Pfandart(**payload.model_dump())
    session.add(p)
    session.commit()
    session.refresh(p)
    return _pfand_out(p)


@router.put("/pfandarten/{pid}", response_model=PfandartOut, dependencies=[Depends(require_admin)])
def pfandart_aendern(pid: int, payload: PfandartIn, session: Session = Depends(get_session)) -> PfandartOut:
    p = session.get(Pfandart, pid)
    if p is None:
        raise HTTPException(status_code=404, detail="Pfandart nicht gefunden")
    for field, value in payload.model_dump(exclude={"kassenprofil_id"}).items():
        setattr(p, field, value)
    session.commit()
    session.refresh(p)
    return _pfand_out(p)


# ===================================================================
# Artikel (Lastenheft 8)
# ===================================================================
@router.get("/artikel", response_model=list[ArtikelOut], dependencies=[Depends(require_bediener)])
def artikel_liste(
    kassenprofil_id: int,
    mit_archiviert: bool = False,
    session: Session = Depends(get_session),
) -> list[ArtikelOut]:
    q = session.query(Artikel).filter(Artikel.kassenprofil_id == kassenprofil_id)
    if not mit_archiviert:
        q = q.filter(Artikel.archiviert.is_(False))
    rows = q.order_by(Artikel.sortierung, Artikel.name).all()
    return [_art_out(a) for a in rows]


@router.post("/artikel", response_model=ArtikelOut, status_code=201, dependencies=[Depends(require_admin)])
def artikel_anlegen(payload: ArtikelIn, session: Session = Depends(get_session)) -> ArtikelOut:
    _profil_or_422(session, payload.kassenprofil_id)
    _pruefe_ticketmodus(payload.artikelticket_modus)
    _pruefe_kategorie(session, payload.kassenprofil_id, payload.kategorie_id)
    daten = payload.model_dump(exclude={"pfandzuordnungen"})
    artikel = Artikel(**daten)
    session.add(artikel)
    session.flush()
    _setze_zuordnungen(session, artikel, payload.pfandzuordnungen)
    session.add(AuditLog(benutzer="administrator", aktion="artikel.anlegen", datensatz=payload.name,
                         nachher=f"{payload.preis_cent} Cent"))
    session.commit()
    session.refresh(artikel)
    return _art_out(artikel)


@router.post("/artikel/csv-import", response_model=ArtikelCsvImportOut, dependencies=[Depends(require_admin)])
def artikel_csv_import(payload: ArtikelCsvImportIn, session: Session = Depends(get_session)) -> ArtikelCsvImportOut:
    _profil_or_422(session, payload.kassenprofil_id)
    delimiter = payload.delimiter if payload.delimiter in {",", ";", "\t"} else ";"
    kategorien = session.query(Kategorie).filter(Kategorie.kassenprofil_id == payload.kassenprofil_id).all()
    pfandarten = session.query(Pfandart).filter(Pfandart.kassenprofil_id == payload.kassenprofil_id).all()
    bekannte_artikel = _artikel_by_name(session, payload.kassenprofil_id)
    csv_artikel: set[str] = set()
    reader = csv.DictReader(io.StringIO(payload.csv_text), delimiter=delimiter)
    if not reader.fieldnames:
        raise HTTPException(status_code=422, detail="CSV enthält keine Kopfzeile.")

    fehler: list[str] = []
    created: list[Artikel] = []
    updated: list[Artikel] = []
    kategorien_angelegt = 0
    pfandarten_angelegt = 0
    for line_no, row in enumerate(reader, start=2):
        try:
            name = (row.get("name") or row.get("artikel") or "").strip()
            if not name:
                raise ValueError("name fehlt")
            norm = _norm_name(name)
            if norm in csv_artikel:
                raise ValueError(f"Artikel doppelt in CSV: {name}")
            csv_artikel.add(norm)
            preis_cent = _parse_cent(row.get("preis") or row.get("preis_eur") or row.get("preis_cent") or "")
            if row.get("preis_cent") and not (row.get("preis") or row.get("preis_eur")):
                preis_cent = int(row["preis_cent"])
            kat_name = (row.get("kategorie") or "").strip()
            kat, kat_created = _get_or_create_kategorie(
                session, kategorien, payload.kassenprofil_id, kat_name, payload.fehlende_stammdaten_anlegen,
            )
            if kat_created:
                kategorien_angelegt += 1
            modus = (row.get("artikelticket_modus") or row.get("ticket") or "pro_stueck").strip() or "pro_stueck"
            _pruefe_ticketmodus(modus)
            artikel = bekannte_artikel.get(norm)
            is_new = artikel is None
            if artikel is None:
                artikel = Artikel(kassenprofil_id=payload.kassenprofil_id, name=name)
                session.add(artikel)
                created.append(artikel)
                bekannte_artikel[norm] = artikel
            else:
                updated.append(artikel)
            artikel.name = name
            artikel.kurzname = (row.get("kurzname") or "").strip()
            artikel.preis_cent = preis_cent
            artikel.kategorie_id = kat.id if kat else None
            artikel.sortierung = int((row.get("reihenfolge") or row.get("sortierung") or "0").strip() or "0")
            artikel.artikelticket_modus = modus
            artikel.artikelnummer = (row.get("artikelnummer") or "").strip()
            artikel.barcode = (row.get("barcode") or "").strip()
            artikel.aktiv = _parse_bool(row.get("aktiv") or "", default=True)
            artikel.archiviert = False
            session.flush()
            if not is_new:
                artikel.pfandzuordnungen.clear()
                session.flush()
            pfand_text = (row.get("pfand") or "").strip()
            if pfand_text:
                for part in pfand_text.split("|"):
                    if not part.strip():
                        continue
                    pf_name, menge, betrag_cent = _parse_pfand_part(part)
                    pfand, pf_created = _get_or_create_pfandart(
                        session, pfandarten, payload.kassenprofil_id, pf_name, betrag_cent,
                        payload.fehlende_stammdaten_anlegen,
                    )
                    if pf_created:
                        pfandarten_angelegt += 1
                    session.add(ArtikelPfandZuordnung(
                        artikel_id=artikel.id,
                        pfandart_id=pfand.id,
                        menge_pro_einheit=max(1, menge),
                        automatisch=True,
                    ))
        except Exception as exc:  # noqa: BLE001 - sammelt zeilenweise Importfehler
            fehler.append(f"Zeile {line_no}: {exc}")

    if fehler:
        session.rollback()
        return ArtikelCsvImportOut(angelegt=0, fehler=fehler)
    session.add(AuditLog(benutzer="administrator", aktion="artikel.csv_import", datensatz=str(payload.kassenprofil_id),
                         nachher=f"{len(created)} angelegt, {len(updated)} aktualisiert"))
    session.commit()
    return ArtikelCsvImportOut(
        angelegt=len(created),
        aktualisiert=len(updated),
        kategorien_angelegt=kategorien_angelegt,
        pfandarten_angelegt=pfandarten_angelegt,
        fehler=[],
    )


@router.post("/artikel/alle-archivieren", response_model=ArtikelBulkActionOut, dependencies=[Depends(require_admin)])
def artikel_alle_archivieren(kassenprofil_id: int, session: Session = Depends(get_session)) -> ArtikelBulkActionOut:
    rows = session.query(Artikel).filter(Artikel.kassenprofil_id == kassenprofil_id, Artikel.archiviert.is_(False)).all()
    for a in rows:
        a.archiviert = True
        a.aktiv = False
    session.add(AuditLog(benutzer="administrator", aktion="artikel.alle_archivieren", datensatz=str(kassenprofil_id),
                         nachher=f"{len(rows)} Artikel"))
    session.commit()
    return ArtikelBulkActionOut(anzahl=len(rows))


@router.post("/artikel/pfand-zuruecksetzen", response_model=ArtikelBulkActionOut, dependencies=[Depends(require_admin)])
def artikel_pfand_zuruecksetzen(kassenprofil_id: int, session: Session = Depends(get_session)) -> ArtikelBulkActionOut:
    artikel_ids = [a.id for a in session.query(Artikel.id).filter(Artikel.kassenprofil_id == kassenprofil_id).all()]
    if not artikel_ids:
        return ArtikelBulkActionOut(anzahl=0)
    rows = session.query(ArtikelPfandZuordnung).filter(ArtikelPfandZuordnung.artikel_id.in_(artikel_ids)).all()
    anzahl = len(rows)
    for row in rows:
        session.delete(row)
    session.add(AuditLog(benutzer="administrator", aktion="artikel.pfand_zuruecksetzen", datensatz=str(kassenprofil_id),
                         nachher=f"{anzahl} Zuordnungen"))
    session.commit()
    return ArtikelBulkActionOut(anzahl=anzahl)


@router.get("/artikel/{aid}", response_model=ArtikelOut, dependencies=[Depends(require_bediener)])
def artikel_holen(aid: int, session: Session = Depends(get_session)) -> ArtikelOut:
    a = session.get(Artikel, aid)
    if a is None:
        raise HTTPException(status_code=404, detail="Artikel nicht gefunden")
    return _art_out(a)


@router.put("/artikel/{aid}", response_model=ArtikelOut, dependencies=[Depends(require_admin)])
def artikel_aendern(aid: int, payload: ArtikelUpdateIn, session: Session = Depends(get_session)) -> ArtikelOut:
    a = session.get(Artikel, aid)
    if a is None:
        raise HTTPException(status_code=404, detail="Artikel nicht gefunden")
    daten = payload.model_dump(exclude_unset=True, exclude={"pfandzuordnungen"})
    if "artikelticket_modus" in daten:
        _pruefe_ticketmodus(daten["artikelticket_modus"])
    if "kategorie_id" in daten:
        _pruefe_kategorie(session, a.kassenprofil_id, daten["kategorie_id"])
    vorher_preis = a.preis_cent
    for field, value in daten.items():
        setattr(a, field, value)
    if payload.pfandzuordnungen is not None:
        a.pfandzuordnungen.clear()
        session.flush()
        _setze_zuordnungen(session, a, payload.pfandzuordnungen)
    session.add(AuditLog(benutzer="administrator", aktion="artikel.aendern", datensatz=str(aid),
                         vorher=f"{vorher_preis} Cent", nachher=f"{a.preis_cent} Cent"))
    session.commit()
    session.refresh(a)
    return _art_out(a)


@router.delete("/artikel/{aid}", response_model=ArtikelOut, dependencies=[Depends(require_admin)])
def artikel_archivieren(aid: int, session: Session = Depends(get_session)) -> ArtikelOut:
    """Kein physisches Löschen (Lastenheft 8.2): Artikel wird archiviert."""
    a = session.get(Artikel, aid)
    if a is None:
        raise HTTPException(status_code=404, detail="Artikel nicht gefunden")
    a.archiviert = True
    a.aktiv = False
    session.add(AuditLog(benutzer="administrator", aktion="artikel.archivieren", datensatz=str(aid)))
    session.commit()
    session.refresh(a)
    return _art_out(a)


@router.post("/artikel/{aid}/kopieren", response_model=ArtikelOut, status_code=201, dependencies=[Depends(require_admin)])
def artikel_kopieren(aid: int, session: Session = Depends(get_session)) -> ArtikelOut:
    """Kopie ohne interne ID, Artikelnummer und Barcode (Lastenheft 8.3)."""
    quelle = session.get(Artikel, aid)
    if quelle is None:
        raise HTTPException(status_code=404, detail="Artikel nicht gefunden")
    kopie = Artikel(
        kassenprofil_id=quelle.kassenprofil_id, name=f"{quelle.name} (Kopie)", kurzname=quelle.kurzname,
        preis_cent=quelle.preis_cent, kategorie_id=quelle.kategorie_id, sortierung=quelle.sortierung,
        artikelticket_modus=quelle.artikelticket_modus, steuersatz=quelle.steuersatz,
        artikelnummer="", barcode="", farbe=quelle.farbe, symbol=quelle.symbol,
        beschreibung=quelle.beschreibung, ausgabeort=quelle.ausgabeort,
    )
    session.add(kopie)
    session.flush()
    for z in quelle.pfandzuordnungen:
        session.add(ArtikelPfandZuordnung(
            artikel_id=kopie.id, pfandart_id=z.pfandart_id, menge_pro_einheit=z.menge_pro_einheit,
            automatisch=z.automatisch, abweichender_betrag_cent=z.abweichender_betrag_cent,
        ))
    session.commit()
    session.refresh(kopie)
    return _art_out(kopie)


@router.post("/artikel/reihenfolge", dependencies=[Depends(require_admin)])
def artikel_reihenfolge(payload: ReorderIn, session: Session = Depends(get_session)) -> dict:
    """Setzt die Sortierung anhand der übergebenen ID-Reihenfolge (Lastenheft 8.4)."""
    for position, aid in enumerate(payload.reihenfolge, start=1):
        a = session.get(Artikel, aid)
        if a is not None:
            a.sortierung = position
    session.commit()
    return {"ok": True, "anzahl": len(payload.reihenfolge)}


@router.post("/artikel/sammelbearbeitung", response_model=list[ArtikelOut], dependencies=[Depends(require_admin)])
def artikel_sammelbearbeitung(payload: BulkArtikelIn, session: Session = Depends(get_session)) -> list[ArtikelOut]:
    """Mehrere Artikel gemeinsam bearbeiten (Lastenheft 8.5)."""
    if payload.artikelticket_modus is not None:
        _pruefe_ticketmodus(payload.artikelticket_modus)
    geaendert: list[Artikel] = []
    for aid in payload.artikel_ids:
        a = session.get(Artikel, aid)
        if a is None:
            continue
        if payload.preis_delta_cent is not None:
            a.preis_cent = max(0, a.preis_cent + payload.preis_delta_cent)
        if payload.kategorie_id is not None:
            a.kategorie_id = payload.kategorie_id
        if payload.aktiv is not None:
            a.aktiv = payload.aktiv
        if payload.artikelticket_modus is not None:
            a.artikelticket_modus = payload.artikelticket_modus
        geaendert.append(a)
    session.add(AuditLog(benutzer="administrator", aktion="artikel.sammelbearbeitung",
                         datensatz=",".join(map(str, payload.artikel_ids))))
    session.commit()
    for a in geaendert:
        session.refresh(a)
    return [_art_out(a) for a in geaendert]


# ===================================================================
# Zahlungsmethoden (Lastenheft 12.1)
# ===================================================================
@router.get("/zahlungsmethoden", response_model=list[ZahlungsmethodeOut], dependencies=[Depends(require_bediener)])
def zahlungsmethoden(kassenprofil_id: int, session: Session = Depends(get_session)) -> list[ZahlungsmethodeOut]:
    rows = (
        session.query(Zahlungsmethode)
        .filter(Zahlungsmethode.kassenprofil_id == kassenprofil_id)
        .order_by(Zahlungsmethode.sortierung, Zahlungsmethode.name)
        .all()
    )
    return [_zm_out(z) for z in rows]


@router.post("/zahlungsmethoden", response_model=ZahlungsmethodeOut, status_code=201, dependencies=[Depends(require_admin)])
def zahlungsmethode_anlegen(payload: ZahlungsmethodeIn, session: Session = Depends(get_session)) -> ZahlungsmethodeOut:
    _profil_or_422(session, payload.kassenprofil_id)
    z = Zahlungsmethode(**payload.model_dump())
    session.add(z)
    session.commit()
    session.refresh(z)
    return _zm_out(z)


@router.put("/zahlungsmethoden/{zid}", response_model=ZahlungsmethodeOut, dependencies=[Depends(require_admin)])
def zahlungsmethode_aendern(zid: int, payload: ZahlungsmethodeIn, session: Session = Depends(get_session)) -> ZahlungsmethodeOut:
    z = session.get(Zahlungsmethode, zid)
    if z is None:
        raise HTTPException(status_code=404, detail="Zahlungsmethode nicht gefunden")
    for field, value in payload.model_dump(exclude={"kassenprofil_id"}).items():
        setattr(z, field, value)
    session.commit()
    session.refresh(z)
    return _zm_out(z)


# ===================================================================
# Hilfsfunktionen
# ===================================================================
def _pruefe_ticketmodus(modus: str) -> None:
    if modus not in TICKET_MODI:
        raise HTTPException(status_code=422, detail=f"Ungültiger Ticketmodus: {modus}")


def _setze_zuordnungen(session: Session, artikel: Artikel, zuordnungen: list[PfandZuordnungIn]) -> None:
    for z in zuordnungen:
        pfand = session.get(Pfandart, z.pfandart_id)
        if pfand is None:
            raise HTTPException(status_code=422, detail=f"Unbekannte Pfandart {z.pfandart_id}")
        if pfand.kassenprofil_id != artikel.kassenprofil_id:
            raise HTTPException(status_code=422, detail=f"Pfandart {z.pfandart_id} passt nicht zum Kassenprofil")
        session.add(ArtikelPfandZuordnung(
            artikel_id=artikel.id, pfandart_id=z.pfandart_id, menge_pro_einheit=z.menge_pro_einheit,
            automatisch=z.automatisch, abweichender_betrag_cent=z.abweichender_betrag_cent,
        ))


def _kat_out(k: Kategorie) -> KategorieOut:
    return KategorieOut(id=k.id, kassenprofil_id=k.kassenprofil_id, name=k.name, farbe=k.farbe,
                        symbol=k.symbol, sortierung=k.sortierung, aktiv=k.aktiv)


def _pfand_out(p: Pfandart) -> PfandartOut:
    return PfandartOut(id=p.id, kassenprofil_id=p.kassenprofil_id, name=p.name, kurzname=p.kurzname,
                       betrag_cent=p.betrag_cent, farbe=p.farbe, symbol=p.symbol, aktiv=p.aktiv,
                       rueckgabe_erlaubt=p.rueckgabe_erlaubt, artikelticket_drucken=p.artikelticket_drucken,
                       steuersatz=p.steuersatz, sortierung=p.sortierung, max_rueckgabe_menge=p.max_rueckgabe_menge)


def _art_out(a: Artikel) -> ArtikelOut:
    return ArtikelOut(
        id=a.id, kassenprofil_id=a.kassenprofil_id, name=a.name, kurzname=a.kurzname, preis_cent=a.preis_cent,
        kategorie_id=a.kategorie_id, aktiv=a.aktiv, archiviert=a.archiviert, sortierung=a.sortierung,
        artikelticket_modus=a.artikelticket_modus, steuersatz=a.steuersatz, artikelnummer=a.artikelnummer,
        barcode=a.barcode, ausgabeort=a.ausgabeort,
        pfandzuordnungen=[
            PfandZuordnungOut(id=z.id, pfandart_id=z.pfandart_id, menge_pro_einheit=z.menge_pro_einheit,
                              automatisch=z.automatisch, abweichender_betrag_cent=z.abweichender_betrag_cent)
            for z in a.pfandzuordnungen
        ],
    )


def _zm_out(z: Zahlungsmethode) -> ZahlungsmethodeOut:
    return ZahlungsmethodeOut(id=z.id, kassenprofil_id=z.kassenprofil_id, name=z.name, kurzname=z.kurzname,
                             farbe=z.farbe, symbol=z.symbol, aktiv=z.aktiv, sortierung=z.sortierung,
                             schublade_oeffnen=z.schublade_oeffnen, rueckgeld_berechnen=z.rueckgeld_berechnen,
                             negativ_erlaubt=z.negativ_erlaubt)
