"""Auswertungen für Admin und Service."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import require_admin
from ..database import get_session
from ..models import Verkauf
from ..schemas import (
    AuswertungBucketOut,
    AuswertungItemOut,
    AuswertungVerkaufOut,
    VerkaufsAuswertungOut,
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
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


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
