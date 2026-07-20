"""Kassenabschluss- und Berichts-Endpunkte (Phase 5).

Der Kassenabschluss ist eine Leitungsfunktion (Kassensturz, Umsatzzahlen) und
daher Administratoren vorbehalten. Ein Z-Abschluss ist nach dem Erstellen
unveränderlich - es gibt nur Erstellen, Ansehen und Nachdruck.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from .. import reports
from ..auth import require_admin
from ..database import get_session
from ..models import (
    AuditLog,
    Artikel,
    ArtikelPfandZuordnung,
    Belegkreis,
    Benutzer,
    Druckauftrag,
    Kassenabschluss,
    KassenabschlussZahlart,
    Verkauf,
    Verkaufsposition,
    Zahlung,
)
from ..schemas import (
    AbschlussArtikelResetIn,
    AbschlussArtikelResetOut,
    ActionResult,
    BerichtOut,
    KassenabschlussKopfOut,
    ZAbschlussIn,
)

router = APIRouter(prefix="/api/abschluss", tags=["kassenabschluss"],
                   dependencies=[Depends(require_admin)])


@router.get("/x", response_model=BerichtOut)
def x_bericht(kassenprofil_id: int, anfangsbestand_cent: int = 0, gezaehlt_cent: int | None = None,
              session: Session = Depends(get_session)) -> BerichtOut:
    """Zwischenstand über die noch nicht abgeschlossenen Verkäufe - ohne zu buchen."""
    return BerichtOut(**reports.x_bericht(session, kassenprofil_id, anfangsbestand_cent, gezaehlt_cent))


@router.post("/z", response_model=BerichtOut, status_code=201)
def z_abschluss(payload: ZAbschlussIn, session: Session = Depends(get_session),
                benutzer: Benutzer = Depends(require_admin)) -> BerichtOut:
    """Tagesabschluss: schließt die offenen Verkäufe ab, speichert und druckt ihn."""
    abschluss = reports.erstelle_z(
        session, payload.kassenprofil_id, benutzer,
        anfangsbestand_cent=payload.anfangsbestand_cent, gezaehlt_cent=payload.gezaehlt_cent,
    )
    return BerichtOut(**reports.abschluss_bericht(session, abschluss))


@router.get("", response_model=list[KassenabschlussKopfOut])
def liste(kassenprofil_id: int, limit: int = 100, session: Session = Depends(get_session)) -> list[Kassenabschluss]:
    return (
        session.query(Kassenabschluss)
        .filter(Kassenabschluss.kassenprofil_id == kassenprofil_id)
        .order_by(Kassenabschluss.id.desc())
        .limit(min(limit, 300))
        .all()
    )


@router.post("/daten-zuruecksetzen", response_model=AbschlussArtikelResetOut)
def artikeldaten_zuruecksetzen(
    kassenprofil_id: int,
    payload: AbschlussArtikelResetIn,
    session: Session = Depends(get_session),
    benutzer: Benutzer = Depends(require_admin),
) -> AbschlussArtikelResetOut:
    """Loescht ausgewählte Abschluss-, Verkaufs- und Stammdaten nach Abschluss."""
    if payload.bestaetigung.strip().upper() not in {"DATEN LOESCHEN", "ARTIKEL LOESCHEN"}:
        raise HTTPException(status_code=422, detail='Bitte mit "DATEN LOESCHEN" bestätigen.')

    if not any([
        payload.belege_loeschen,
        payload.abschluesse_loeschen,
        payload.artikel_loeschen,
        payload.pfandzuordnungen_loeschen,
        payload.druckwarteschlange_loeschen,
        payload.belegkreis_zuruecksetzen,
    ]):
        raise HTTPException(status_code=422, detail="Bitte mindestens einen Datenbereich auswählen.")

    offene = (
        session.query(Verkauf.id)
        .filter(Verkauf.kassenprofil_id == kassenprofil_id, Verkauf.abschluss_id.is_(None))
        .first()
    )
    if offene is not None:
        raise HTTPException(status_code=409, detail="Es gibt noch offene Verkäufe. Bitte zuerst den Z-Abschluss durchführen.")

    artikel_ids = [row.id for row in session.query(Artikel.id).filter(Artikel.kassenprofil_id == kassenprofil_id).all()]
    verkauf_ids = [row.id for row in session.query(Verkauf.id).filter(Verkauf.kassenprofil_id == kassenprofil_id).all()]
    abschluss_rows = (
        session.query(Kassenabschluss.id, Kassenabschluss.nummer)
        .filter(Kassenabschluss.kassenprofil_id == kassenprofil_id)
        .all()
    )
    abschluss_ids = [row.id for row in abschluss_rows]
    abschluss_nummern = [row.nummer for row in abschluss_rows]
    if payload.abschluesse_loeschen and not payload.belege_loeschen and verkauf_ids:
        raise HTTPException(status_code=422, detail="Abschlüsse können nur zusammen mit Belegen gelöscht werden.")

    pfandzuordnungen = 0
    artikel_geloescht = 0
    if artikel_ids and (payload.pfandzuordnungen_loeschen or payload.artikel_loeschen):
        pfandzuordnungen = (
            session.query(ArtikelPfandZuordnung)
            .filter(ArtikelPfandZuordnung.artikel_id.in_(artikel_ids))
            .delete(synchronize_session=False)
        )

    druckauftraege = 0
    positionen = 0
    zahlungen = 0
    belege = 0
    if payload.druckwarteschlange_loeschen:
        druckauftraege += session.query(Druckauftrag).delete(synchronize_session=False)
    elif payload.belege_loeschen and verkauf_ids:
        druckauftraege += (
            session.query(Druckauftrag)
            .filter(Druckauftrag.verkauf_id.in_(verkauf_ids))
            .delete(synchronize_session=False)
        )

    if payload.belege_loeschen and verkauf_ids:
        positionen = (
            session.query(Verkaufsposition)
            .filter(Verkaufsposition.verkauf_id.in_(verkauf_ids))
            .delete(synchronize_session=False)
        )
        zahlungen = (
            session.query(Zahlung)
            .filter(Zahlung.verkauf_id.in_(verkauf_ids))
            .delete(synchronize_session=False)
        )
        belege = (
            session.query(Verkauf)
            .filter(Verkauf.id.in_(verkauf_ids))
            .delete(synchronize_session=False)
        )

    abschluesse = 0
    if payload.abschluesse_loeschen and abschluss_ids:
        session.query(KassenabschlussZahlart).filter(KassenabschlussZahlart.abschluss_id.in_(abschluss_ids)).delete(
            synchronize_session=False
        )
        abschluesse = (
            session.query(Kassenabschluss)
            .filter(Kassenabschluss.id.in_(abschluss_ids))
            .delete(synchronize_session=False)
        )
    if not payload.druckwarteschlange_loeschen and payload.abschluesse_loeschen and abschluss_nummern:
        druckauftraege += (
            session.query(Druckauftrag)
            .filter(Druckauftrag.dokumenttyp == "Kassenabschluss", Druckauftrag.bezeichnung.in_(abschluss_nummern))
            .delete(synchronize_session=False)
        )

    if payload.artikel_loeschen and artikel_ids:
        artikel_geloescht = (
            session.query(Artikel)
            .filter(Artikel.id.in_(artikel_ids))
            .delete(synchronize_session=False)
        )

    belegkreis = session.get(Belegkreis, kassenprofil_id)
    belegkreis_zurueckgesetzt = payload.belegkreis_zuruecksetzen and belegkreis is not None
    if belegkreis_zurueckgesetzt:
        belegkreis.letzte_nummer = 0

    session.add(AuditLog(
        benutzer=benutzer.name,
        aktion="abschluss.daten_zuruecksetzen",
        datensatz=str(kassenprofil_id),
        vorher=f"{len(verkauf_ids)} Belege, {len(abschluss_ids)} Abschlüsse, {len(artikel_ids)} Artikel",
        nachher=(
            f"{belege} Belege, {abschluesse} Abschlüsse, {artikel_geloescht} Artikel, "
            f"{pfandzuordnungen} Pfandzuordnungen, {druckauftraege} Druckaufträge gelöscht"
        ),
    ))
    session.commit()
    return AbschlussArtikelResetOut(
        artikel_geloescht=artikel_geloescht,
        pfandzuordnungen_geloescht=pfandzuordnungen,
        belege_geloescht=belege,
        verkaufspositionen_geloescht=positionen,
        zahlungen_geloescht=zahlungen,
        abschluesse_geloescht=abschluesse,
        druckauftraege_geloescht=druckauftraege,
        belegkreis_zurueckgesetzt=belegkreis_zurueckgesetzt,
    )


@router.get("/{abschluss_id}/csv")
def csv_export(abschluss_id: int, session: Session = Depends(get_session)) -> Response:
    abschluss = session.get(Kassenabschluss, abschluss_id)
    if abschluss is None:
        raise HTTPException(status_code=404, detail="Kassenabschluss nicht gefunden.")
    dateiname = f"abschluss-{abschluss.nummer}-detail.csv".replace("/", "-")
    return Response(
        content=reports.abschluss_detail_csv(session, abschluss),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{dateiname}"'},
    )


@router.get("/{abschluss_id}", response_model=BerichtOut)
def detail(abschluss_id: int, session: Session = Depends(get_session)) -> BerichtOut:
    abschluss = session.get(Kassenabschluss, abschluss_id)
    if abschluss is None:
        raise HTTPException(status_code=404, detail="Kassenabschluss nicht gefunden.")
    return BerichtOut(**reports.abschluss_bericht(session, abschluss))


@router.post("/{abschluss_id}/nachdruck", response_model=ActionResult)
def nachdruck(abschluss_id: int, session: Session = Depends(get_session)) -> ActionResult:
    abschluss = session.get(Kassenabschluss, abschluss_id)
    if abschluss is None:
        raise HTTPException(status_code=404, detail="Kassenabschluss nicht gefunden.")
    return ActionResult(**reports.druck_bericht(session, abschluss_id))
