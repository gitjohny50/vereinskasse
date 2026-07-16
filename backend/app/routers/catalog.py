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
    Zahlungsmethode,
)
from ..schemas import (
    ArtikelIn,
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
    for field, value in payload.model_dump(exclude={"kassenprofil_id"}).items():
        setattr(k, field, value)
    session.commit()
    session.refresh(k)
    return _kat_out(k)


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
        if session.get(Pfandart, z.pfandart_id) is None:
            raise HTTPException(status_code=422, detail=f"Unbekannte Pfandart {z.pfandart_id}")
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
