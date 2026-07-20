"""Auswertungen für Admin und Service."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import require_admin
from ..database import get_session
from ..models import Artikel, Benutzer, Kategorie, Verkauf
from ..schemas import (
    AuswertungBucketOut,
    AuswertungItemOut,
    AuswertungVerkaufOut,
    VerkaufsAuswertungOut,
    ZeitreiheBucketOut,
    ZeitreiheOut,
    ZeitreiheSegmentOut,
    ZeitreiheSummeOut,
)
from ..timeutils import as_utc, local_tz, to_local

router = APIRouter(prefix="/api/auswertung", tags=["auswertung"], dependencies=[Depends(require_admin)])


def _item_out(values: dict[str, dict[str, int]]) -> list[AuswertungItemOut]:
    return [
        AuswertungItemOut(bezeichnung=name, menge=data["menge"], umsatz_cent=data["umsatz_cent"])
        for name, data in sorted(values.items(), key=lambda row: (-row[1]["umsatz_cent"], row[0]))
    ]


def _bucket_start(dt: datetime, modus: str) -> datetime:
    if modus == "stunde":
        return dt.replace(minute=0, second=0, microsecond=0)
    if modus == "woche":
        day = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        return day - timedelta(days=day.weekday())
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def _parse_local(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Ungültiger Zeitpunkt: {value}") from None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=local_tz())
    return parsed.astimezone(local_tz())


def _step(granularitaet: str) -> timedelta:
    if granularitaet == "stunde":
        return timedelta(hours=1)
    if granularitaet == "tag":
        return timedelta(days=1)
    if granularitaet == "woche":
        return timedelta(weeks=1)
    raise HTTPException(status_code=422, detail="granularitaet muss stunde, tag oder woche sein.")


def _bucket_label(start: datetime, granularitaet: str, offset: int, ausrichtung: str) -> str:
    if ausrichtung == "relativ":
        suffix = {"stunde": "Std", "tag": "Tag", "woche": "Wo"}[granularitaet]
        return f"+{offset} {suffix}"
    if granularitaet == "stunde":
        return start.strftime("%H Uhr")
    if granularitaet == "woche":
        return "KW " + start.strftime("%V")
    return start.strftime("%d.%m.")


def _sale_payment(v: Verkauf):
    return v.zahlungen[0] if v.zahlungen else None


@router.get("/zeitreihe", response_model=ZeitreiheOut)
def zeitreihe(
    kassenprofil_id: int,
    von: str,
    bis: str,
    granularitaet: str = "stunde",
    metrik: str = "umsatz",
    gruppierung: str = "artikel",
    artikel_id: int | None = None,
    veranstaltung_id: int | None = None,
    bediener_id: int | None = None,
    zahlart_id: int | None = None,
    pfand_einbeziehen: bool = True,
    ausrichtung: str = "absolut",
    session: Session = Depends(get_session),
) -> ZeitreiheOut:
    if metrik not in {"umsatz", "anzahl", "menge"}:
        raise HTTPException(status_code=422, detail="metrik muss umsatz, anzahl oder menge sein.")
    if gruppierung not in {"keine", "kategorie", "artikel", "zahlart", "bediener"}:
        raise HTTPException(status_code=422, detail="gruppierung muss keine, kategorie, artikel, zahlart oder bediener sein.")
    if ausrichtung not in {"absolut", "relativ"}:
        raise HTTPException(status_code=422, detail="ausrichtung muss absolut oder relativ sein.")

    von_lokal = _bucket_start(_parse_local(von), granularitaet)
    bis_lokal = _parse_local(bis)
    if bis_lokal <= von_lokal:
        raise HTTPException(status_code=422, detail="bis muss nach von liegen.")
    step = _step(granularitaet)
    von_utc = von_lokal.astimezone(timezone.utc)
    bis_utc = bis_lokal.astimezone(timezone.utc)

    query = session.query(Verkauf).filter(
        Verkauf.kassenprofil_id == kassenprofil_id,
        Verkauf.zeitpunkt >= von_utc.replace(tzinfo=None),
        Verkauf.zeitpunkt < bis_utc.replace(tzinfo=None),
    )
    if veranstaltung_id is not None:
        query = query.filter(Verkauf.veranstaltung_id == veranstaltung_id)
    if bediener_id is not None:
        query = query.filter(Verkauf.benutzer_id == bediener_id)
    rows = query.order_by(Verkauf.zeitpunkt.desc(), Verkauf.id.desc()).all()

    artikel_map = {a.id: a for a in session.query(Artikel).filter(Artikel.kassenprofil_id == kassenprofil_id).all()}
    kategorien = {k.id: k.name for k in session.query(Kategorie).filter(Kategorie.kassenprofil_id == kassenprofil_id).all()}
    bediener = {b.id: b.name for b in session.query(Benutzer).all()}
    buckets: dict[datetime, dict] = {}
    top: dict[str, dict[str, int]] = defaultdict(lambda: {"menge": 0, "umsatz_cent": 0})
    total_umsatz = total_anzahl = total_menge = 0
    pfand_aus = pfand_zurueck = bar_cent = unbar_cent = 0
    verkaeufe: list[AuswertungVerkaufOut] = []

    cursor = von_lokal
    while cursor < bis_lokal:
        buckets[cursor] = {
            "gesamt_cent": 0,
            "anzahl": 0,
            "menge": 0,
            "segmente": defaultdict(lambda: {"name": "", "wert_cent": 0, "anzahl": 0, "menge": 0}),
            "items": defaultdict(lambda: {"menge": 0, "umsatz_cent": 0}),
        }
        cursor += step

    def group_key(v: Verkauf, artikel: Artikel | None, bezeichnung: str, zahlung) -> tuple[str, str]:
        if gruppierung == "keine":
            return "gesamt", "Gesamt"
        if gruppierung == "artikel":
            return bezeichnung, bezeichnung
        if gruppierung == "kategorie":
            if artikel and artikel.kategorie_id:
                name = kategorien.get(artikel.kategorie_id, "Sonstiges")
                return name, name
            return "Sonstiges", "Sonstiges"
        if gruppierung == "zahlart":
            key = str(zahlung.zahlungsmethode_id) if zahlung else "ohne"
            return key, zahlung.bezeichnung if zahlung else "Ohne Zahlung"
        key = str(v.benutzer_id)
        return key, bediener.get(v.benutzer_id, f"Bediener {v.benutzer_id}")

    for v in rows:
        zahlung = _sale_payment(v)
        if zahlart_id is not None and (zahlung is None or zahlung.zahlungsmethode_id != zahlart_id):
            continue
        bucket_key = _bucket_start(to_local(v.zeitpunkt), granularitaet)
        bucket = buckets.get(bucket_key)
        if bucket is None:
            continue

        sale_items: dict[str, dict[str, int]] = defaultdict(lambda: {"menge": 0, "umsatz_cent": 0})
        sale_total = 0
        sale_menge = 0
        sale_has_match = artikel_id is None
        position_groups_seen: set[str] = set()

        for p in v.positionen:
            if artikel_id is not None and p.artikel_id != artikel_id:
                continue
            if p.typ != "artikel" and not pfand_einbeziehen:
                continue
            sale_has_match = True
            artikel = artikel_map.get(p.artikel_id) if p.artikel_id else None
            sale_total += p.gesamt_cent
            sale_menge += p.menge
            if p.typ == "pfand":
                pfand_aus += p.gesamt_cent
            elif p.typ == "pfand_rueckgabe":
                pfand_zurueck += abs(p.gesamt_cent)
            if p.typ == "artikel":
                top[p.bezeichnung]["menge"] += p.menge
                top[p.bezeichnung]["umsatz_cent"] += p.gesamt_cent
            sale_items[p.bezeichnung]["menge"] += p.menge
            sale_items[p.bezeichnung]["umsatz_cent"] += p.gesamt_cent
            bucket["items"][p.bezeichnung]["menge"] += p.menge
            bucket["items"][p.bezeichnung]["umsatz_cent"] += p.gesamt_cent

            schluessel, name = group_key(v, artikel, p.bezeichnung, zahlung)
            seg = bucket["segmente"][schluessel]
            seg["name"] = name
            seg["wert_cent"] += p.gesamt_cent
            seg["menge"] += p.menge
            position_groups_seen.add(schluessel)

        if not sale_has_match:
            continue
        if not pfand_einbeziehen and artikel_id is None:
            sale_total = v.waren_cent
        bucket["gesamt_cent"] += sale_total
        bucket["anzahl"] += 1
        bucket["menge"] += sale_menge
        for schluessel in position_groups_seen:
            bucket["segmente"][schluessel]["anzahl"] += 1

        total_umsatz += sale_total
        total_anzahl += 1
        total_menge += sale_menge
        if zahlung:
            if zahlung.bezeichnung.lower().startswith("bar"):
                bar_cent += sale_total
            else:
                unbar_cent += sale_total
        verkaeufe.append(AuswertungVerkaufOut(
            id=v.id,
            belegnummer=v.belegnummer,
            zeitpunkt=as_utc(v.zeitpunkt),
            gesamt_cent=sale_total,
            zahlung=zahlung.bezeichnung if zahlung else "-",
            items=_item_out(sale_items),
        ))

    bucket_rows: list[ZeitreiheBucketOut] = []
    for index, (start, data) in enumerate(sorted(buckets.items())):
        segment_rows = [
            ZeitreiheSegmentOut(schluessel=key, name=seg["name"], wert_cent=seg["wert_cent"], anzahl=seg["anzahl"], menge=seg["menge"])
            for key, seg in sorted(data["segmente"].items(), key=lambda item: (-item[1]["wert_cent"], item[1]["name"]))
            if seg["wert_cent"] or seg["anzahl"] or seg["menge"]
        ]
        bucket_rows.append(ZeitreiheBucketOut(
            start=start,
            label=_bucket_label(start, granularitaet, index, ausrichtung),
            offset=index,
            gesamt_cent=data["gesamt_cent"],
            anzahl=data["anzahl"],
            menge=data["menge"],
            segmente=segment_rows if gruppierung != "keine" else [],
        ))

    return ZeitreiheOut(
        von=von_lokal,
        bis=bis_lokal,
        granularitaet=granularitaet,
        metrik=metrik,
        gruppierung=gruppierung,
        summe=ZeitreiheSummeOut(
            umsatz_cent=total_umsatz,
            anzahl=total_anzahl,
            durchschnitt_cent=round(total_umsatz / total_anzahl) if total_anzahl else 0,
            pfand_ausgegeben_cent=pfand_aus,
            pfand_zurueck_cent=pfand_zurueck,
            bar_cent=bar_cent,
            unbar_cent=unbar_cent,
            menge=total_menge,
        ),
        buckets=bucket_rows,
        top_artikel=_item_out(top)[:10],
        verkaeufe=verkaeufe[:200],
    )


@router.get("/verkauf", response_model=VerkaufsAuswertungOut)
def verkaufs_auswertung(
    kassenprofil_id: int,
    tage: int = 1,
    pfand: bool = False,
    session: Session = Depends(get_session),
) -> VerkaufsAuswertungOut:
    tage = max(1, min(tage, 30))
    tz = local_tz()
    jetzt_lokal = datetime.now(timezone.utc).astimezone(tz)
    start_datum = jetzt_lokal.date() - timedelta(days=tage - 1)
    von_lokal = datetime.combine(start_datum, time.min, tzinfo=tz)
    bis_lokal = jetzt_lokal
    von_utc = von_lokal.astimezone(timezone.utc)
    bis_utc = bis_lokal.astimezone(timezone.utc)
    bucket_modus = "stunde" if tage <= 2 else "tag"

    rows = (
        session.query(Verkauf)
        .filter(
            Verkauf.kassenprofil_id == kassenprofil_id,
            Verkauf.zeitpunkt >= von_utc.replace(tzinfo=None),
            Verkauf.zeitpunkt <= bis_utc.replace(tzinfo=None),
        )
        .order_by(Verkauf.zeitpunkt.desc(), Verkauf.id.desc())
        .all()
    )

    top: dict[str, dict[str, int]] = defaultdict(lambda: {"menge": 0, "umsatz_cent": 0})
    buckets: dict[datetime, dict] = {}
    verkaeufe: list[AuswertungVerkaufOut] = []

    for v in rows:
        zeit_lokal = to_local(v.zeitpunkt)
        bucket_key = _bucket_start(zeit_lokal, bucket_modus)
        sale_total = v.gesamt_cent if pfand else v.waren_cent
        bucket = buckets.setdefault(bucket_key, {
            "anzahl": 0,
            "gesamt_cent": 0,
            "items": defaultdict(lambda: {"menge": 0, "umsatz_cent": 0}),
        })
        bucket["anzahl"] += 1
        bucket["gesamt_cent"] += sale_total

        sale_items: dict[str, dict[str, int]] = defaultdict(lambda: {"menge": 0, "umsatz_cent": 0})
        for p in v.positionen:
            if p.typ != "artikel" and not pfand:
                continue
            top[p.bezeichnung]["menge"] += p.menge
            top[p.bezeichnung]["umsatz_cent"] += p.gesamt_cent
            bucket["items"][p.bezeichnung]["menge"] += p.menge
            bucket["items"][p.bezeichnung]["umsatz_cent"] += p.gesamt_cent
            sale_items[p.bezeichnung]["menge"] += p.menge
            sale_items[p.bezeichnung]["umsatz_cent"] += p.gesamt_cent

        zahlung = v.zahlungen[0].bezeichnung if v.zahlungen else "-"
        verkaeufe.append(AuswertungVerkaufOut(
            id=v.id,
            belegnummer=v.belegnummer,
            zeitpunkt=as_utc(v.zeitpunkt),
            gesamt_cent=sale_total,
            zahlung=zahlung,
            items=_item_out(sale_items),
        ))

    step = timedelta(hours=1) if bucket_modus == "stunde" else timedelta(days=1)
    cursor = _bucket_start(von_lokal, bucket_modus)
    last = _bucket_start(bis_lokal, bucket_modus)
    while cursor <= last:
        buckets.setdefault(cursor, {
            "anzahl": 0,
            "gesamt_cent": 0,
            "items": defaultdict(lambda: {"menge": 0, "umsatz_cent": 0}),
        })
        cursor += step

    bucket_rows = [
        AuswertungBucketOut(
            start=start,
            label=start.strftime("%H:%M") if bucket_modus == "stunde" else start.strftime("%d.%m."),
            anzahl=data["anzahl"],
            gesamt_cent=data["gesamt_cent"],
            items=_item_out(data["items"]),
        )
        for start, data in sorted(buckets.items())
    ]

    return VerkaufsAuswertungOut(
        kassenprofil_id=kassenprofil_id,
        von=von_lokal,
        bis=bis_lokal,
        bucket_modus=bucket_modus,
        anzahl_verkaeufe=len(rows),
        gesamt_cent=sum((v.gesamt_cent if pfand else v.waren_cent) for v in rows),
        top_artikel=_item_out(top)[:8],
        buckets=bucket_rows,
        verkaeufe=verkaeufe[:200],
    )
