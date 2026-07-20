"""API-Schemata (Ein-/Ausgabe). Serverseitige Validierung, Lastenheft 28.1."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class HealthOut(BaseModel):
    status: str
    version: str
    db_integrity: str


class PrinterStatusOut(BaseModel):
    reachable: bool
    known: bool
    paper_ok: bool | None = None
    cover_closed: bool | None = None
    detail: str = ""


class ActionResult(BaseModel):
    ok: bool
    detail: str = ""
    auftrag_id: int | None = None
    drucker: str | None = None


class CutTestIn(BaseModel):
    anzahl: int = Field(default=3, ge=1, le=50)


class DrawerOpenIn(BaseModel):
    grund: str = Field(default="manueller Test", max_length=255)


class SettingOut(BaseModel):
    schluessel: str
    wert: str
    beschreibung: str = ""


class SettingUpdateIn(BaseModel):
    wert: str = Field(max_length=500)


class BonLogoIn(BaseModel):
    raster_b64: str = Field(max_length=200_000)
    breite_px: int = Field(ge=8, le=576)
    hoehe_px: int = Field(ge=1, le=384)


class BonLogoOut(BaseModel):
    aktiv: bool
    breite_px: int = 0
    hoehe_px: int = 0
    bytes: int = 0


# ===================================================================
# Phase 2: Authentifizierung
# ===================================================================
class LoginIn(BaseModel):
    benutzer_id: int
    pin: str = Field(min_length=4, max_length=20)


class TokenOut(BaseModel):
    token: str
    benutzer_id: int
    name: str
    rolle: str
    stufe: int


class BenutzerOut(BaseModel):
    id: int
    name: str
    rolle_id: int
    rolle: str
    stufe: int
    aktiv: bool


class BenutzerCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    pin: str = Field(min_length=4, max_length=20)
    rolle_id: int


class BenutzerUpdateIn(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    rolle_id: int | None = None
    aktiv: bool | None = None
    pin: str | None = Field(default=None, min_length=4, max_length=20)


class RolleOut(BaseModel):
    id: int
    name: str
    stufe: int
    beschreibung: str


# ===================================================================
# Phase 2: Verein / Profil / Veranstaltung
# ===================================================================
class VereinIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    anschrift: str = ""
    kontakt: str = ""


class VereinOut(VereinIn):
    id: int
    aktiv: bool


class KassenprofilIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    verein_id: int
    bonkopf: str = ""
    bonfuss: str = ""
    waehrung: str = "EUR"
    pfand_aktiv: bool = True


class KassenprofilOut(KassenprofilIn):
    id: int
    aktiv: bool


class VeranstaltungIn(BaseModel):
    kassenprofil_id: int
    name: str = Field(min_length=1, max_length=200)
    beschreibung: str = ""
    beginn: str | None = None
    ende: str | None = None
    ort: str = ""
    pfand_aktiv: bool = True
    bonkopf: str = ""
    status: str = "geplant"


class VeranstaltungOut(BaseModel):
    id: int
    kassenprofil_id: int
    name: str
    beschreibung: str
    ort: str
    pfand_aktiv: bool
    status: str


# ===================================================================
# Phase 2: Katalog
# ===================================================================
class KategorieIn(BaseModel):
    kassenprofil_id: int
    name: str = Field(min_length=1, max_length=120)
    farbe: str = ""
    symbol: str = ""
    sortierung: int = 0
    aktiv: bool = True


class KategorieOut(BaseModel):
    id: int
    kassenprofil_id: int
    name: str
    farbe: str
    symbol: str
    sortierung: int
    aktiv: bool


class PfandartIn(BaseModel):
    kassenprofil_id: int
    name: str = Field(min_length=1, max_length=120)
    kurzname: str = ""
    betrag_cent: int = Field(ge=0)
    farbe: str = ""
    symbol: str = ""
    rueckgabe_erlaubt: bool = True
    artikelticket_drucken: bool = False
    steuersatz: int = 0
    sortierung: int = 0
    beschreibung: str = ""
    max_rueckgabe_menge: int | None = None
    aktiv: bool = True


class PfandartOut(BaseModel):
    id: int
    kassenprofil_id: int
    name: str
    kurzname: str
    betrag_cent: int
    farbe: str
    symbol: str
    aktiv: bool
    rueckgabe_erlaubt: bool
    artikelticket_drucken: bool
    steuersatz: int
    sortierung: int
    max_rueckgabe_menge: int | None


class PfandZuordnungIn(BaseModel):
    pfandart_id: int
    menge_pro_einheit: int = Field(default=1, ge=1)
    automatisch: bool = True
    abweichender_betrag_cent: int | None = None


class PfandZuordnungOut(BaseModel):
    id: int
    pfandart_id: int
    menge_pro_einheit: int
    automatisch: bool
    abweichender_betrag_cent: int | None


class ArtikelIn(BaseModel):
    kassenprofil_id: int
    name: str = Field(min_length=1, max_length=200)
    kurzname: str = ""
    preis_cent: int = Field(ge=0)
    kategorie_id: int | None = None
    sortierung: int = 0
    artikelticket_modus: str = "pro_stueck"
    steuersatz: int = 0
    artikelnummer: str = ""
    barcode: str = ""
    farbe: str = ""
    symbol: str = ""
    beschreibung: str = ""
    ausgabeort: str = ""
    pfandzuordnungen: list[PfandZuordnungIn] = []


class ArtikelUpdateIn(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    kurzname: str | None = None
    preis_cent: int | None = Field(default=None, ge=0)
    kategorie_id: int | None = None
    sortierung: int | None = None
    artikelticket_modus: str | None = None
    steuersatz: int | None = None
    artikelnummer: str | None = None
    barcode: str | None = None
    aktiv: bool | None = None
    ausgabeort: str | None = None
    pfandzuordnungen: list[PfandZuordnungIn] | None = None


class ArtikelOut(BaseModel):
    id: int
    kassenprofil_id: int
    name: str
    kurzname: str
    preis_cent: int
    kategorie_id: int | None
    aktiv: bool
    archiviert: bool
    sortierung: int
    artikelticket_modus: str
    steuersatz: int
    artikelnummer: str
    barcode: str
    ausgabeort: str
    pfandzuordnungen: list[PfandZuordnungOut]


class ReorderIn(BaseModel):
    """Reihenfolge per Liste von IDs (Lastenheft 8.4)."""
    reihenfolge: list[int]


class BulkArtikelIn(BaseModel):
    """Sammelbearbeitung (Lastenheft 8.5)."""
    artikel_ids: list[int]
    preis_delta_cent: int | None = None
    kategorie_id: int | None = None
    aktiv: bool | None = None
    artikelticket_modus: str | None = None


class ArtikelCsvImportIn(BaseModel):
    kassenprofil_id: int
    csv_text: str = Field(min_length=1, max_length=500_000)
    delimiter: str = ";"
    fehlende_stammdaten_anlegen: bool = True


class ArtikelCsvImportOut(BaseModel):
    angelegt: int
    aktualisiert: int = 0
    kategorien_angelegt: int = 0
    pfandarten_angelegt: int = 0
    fehler: list[str] = []


class ArtikelBulkActionOut(BaseModel):
    anzahl: int


class AbschlussArtikelResetIn(BaseModel):
    bestaetigung: str = Field(min_length=1, max_length=80)
    belege_loeschen: bool = True
    abschluesse_loeschen: bool = True
    artikel_loeschen: bool = True
    pfandzuordnungen_loeschen: bool = True
    druckwarteschlange_loeschen: bool = True
    belegkreis_zuruecksetzen: bool = True


class AbschlussArtikelResetOut(BaseModel):
    artikel_geloescht: int
    pfandzuordnungen_geloescht: int
    belege_geloescht: int
    verkaufspositionen_geloescht: int
    zahlungen_geloescht: int
    abschluesse_geloescht: int
    druckauftraege_geloescht: int
    belegkreis_zurueckgesetzt: bool


class ZahlungsmethodeIn(BaseModel):
    kassenprofil_id: int
    name: str = Field(min_length=1, max_length=120)
    kurzname: str = ""
    farbe: str = ""
    symbol: str = ""
    sortierung: int = 0
    schublade_oeffnen: bool = True
    rueckgeld_berechnen: bool = True
    negativ_erlaubt: bool = False
    aktiv: bool = True


class ZahlungsmethodeOut(BaseModel):
    id: int
    kassenprofil_id: int
    name: str
    kurzname: str
    farbe: str
    symbol: str
    aktiv: bool
    sortierung: int
    schublade_oeffnen: bool
    rueckgeld_berechnen: bool
    negativ_erlaubt: bool


# ===================================================================
# Phase 3: Verkauf
# ===================================================================
class VerkaufItemIn(BaseModel):
    artikel_id: int
    menge: int = Field(ge=1)


class PfandRueckgabeIn(BaseModel):
    pfandart_id: int
    menge: int = Field(ge=1)


class BerechnungIn(BaseModel):
    kassenprofil_id: int
    veranstaltung_id: int | None = None
    artikel: list[VerkaufItemIn] = []
    pfand_rueckgaben: list[PfandRueckgabeIn] = []


class PositionOut(BaseModel):
    typ: str
    bezeichnung: str
    einzelpreis_cent: int
    menge: int
    gesamt_cent: int
    artikelticket_modus: str
    steuersatz: int = 0


class BerechnungOut(BaseModel):
    positionen: list[PositionOut]
    waren_cent: int
    pfand_cent: int
    gesamt_cent: int


class VerkaufIn(BaseModel):
    kassenprofil_id: int
    veranstaltung_id: int | None = None
    artikel: list[VerkaufItemIn] = []
    pfand_rueckgaben: list[PfandRueckgabeIn] = []
    zahlungsmethode_id: int
    gegeben_cent: int | None = None


class ZahlungOut(BaseModel):
    zahlungsmethode_id: int
    bezeichnung: str
    betrag_cent: int
    gegeben_cent: int
    rueckgeld_cent: int


class VerkaufOut(BaseModel):
    id: int
    belegnummer: str
    kassenprofil_id: int
    veranstaltung_id: int | None
    benutzer_id: int
    zeitpunkt: datetime
    waren_cent: int
    pfand_cent: int
    gesamt_cent: int
    status: str
    positionen: list[PositionOut]
    zahlung: ZahlungOut | None


class AuswertungItemOut(BaseModel):
    bezeichnung: str
    menge: int
    umsatz_cent: int


class AuswertungBucketOut(BaseModel):
    start: datetime
    label: str
    anzahl: int
    gesamt_cent: int
    items: list[AuswertungItemOut]


class AuswertungVerkaufOut(BaseModel):
    id: int
    belegnummer: str
    zeitpunkt: datetime
    gesamt_cent: int
    zahlung: str
    items: list[AuswertungItemOut]


class VerkaufsAuswertungOut(BaseModel):
    kassenprofil_id: int
    von: datetime
    bis: datetime
    bucket_modus: str
    anzahl_verkaeufe: int
    gesamt_cent: int
    top_artikel: list[AuswertungItemOut]
    buckets: list[AuswertungBucketOut]
    verkaeufe: list[AuswertungVerkaufOut]


class ZeitreiheSegmentOut(BaseModel):
    schluessel: str
    name: str
    wert_cent: int = 0
    anzahl: int = 0
    menge: int = 0


class ZeitreiheSummeOut(BaseModel):
    umsatz_cent: int
    anzahl: int
    durchschnitt_cent: int
    pfand_ausgegeben_cent: int
    pfand_zurueck_cent: int
    bar_cent: int
    unbar_cent: int
    menge: int


class ZeitreiheBucketOut(BaseModel):
    start: datetime
    label: str
    offset: int
    gesamt_cent: int
    anzahl: int
    menge: int
    segmente: list[ZeitreiheSegmentOut] = []


class ZeitreiheOut(BaseModel):
    von: datetime
    bis: datetime
    granularitaet: str
    metrik: str
    gruppierung: str
    summe: ZeitreiheSummeOut
    buckets: list[ZeitreiheBucketOut]
    top_artikel: list[AuswertungItemOut]
    verkaeufe: list[AuswertungVerkaufOut] = []


# ===================================================================
# Phase 4: Druckwarteschlange
# ===================================================================
class DruckauftragOut(BaseModel):
    id: int
    dokumenttyp: str
    bezeichnung: str = ""
    drucker: str
    status: str
    versuche: int
    max_versuche: int
    letzte_fehlermeldung: str
    nachdruck: bool
    verkauf_id: int | None
    erstellt_am: datetime
    aktualisiert_am: datetime


class QueueStatusOut(BaseModel):
    offen: int
    fehlgeschlagen: int
    erfolgreich: int
    abgebrochen: int


class QueueVerarbeitenOut(BaseModel):
    verarbeitet: int
    erfolg: int
    fehler: int


# ===================================================================
# Phase 5: Kassenabschluss / Berichte
# ===================================================================
class BerichtZahlartOut(BaseModel):
    zahlungsmethode_id: int | None
    bezeichnung: str
    anzahl: int
    betrag_cent: int
    bar: bool


class BerichtArtikelOut(BaseModel):
    bezeichnung: str
    menge: int
    betrag_cent: int


class BerichtOut(BaseModel):
    typ: str
    nummer: str | None = None
    abschluss_id: int | None = None
    kassenprofil_id: int
    von: datetime | None
    bis: datetime
    anzahl_verkaeufe: int
    waren_cent: int
    pfand_cent: int
    gesamt_cent: int
    bar_cent: int
    anfangsbestand_cent: int
    erwartet_cent: int
    gezaehlt_cent: int | None
    differenz_cent: int | None
    zahlarten: list[BerichtZahlartOut]
    artikel: list[BerichtArtikelOut]


class ZAbschlussIn(BaseModel):
    kassenprofil_id: int
    anfangsbestand_cent: int = 0
    gezaehlt_cent: int | None = None


class KassenabschlussKopfOut(BaseModel):
    id: int
    nummer: str
    kassenprofil_id: int
    erstellt_am: datetime
    anzahl_verkaeufe: int
    waren_cent: int
    pfand_cent: int
    gesamt_cent: int
    bar_cent: int
    gezaehlt_cent: int | None
    differenz_cent: int | None


# ===================================================================
# USB-Geräteliste (Drucker-Einrichtung)
# ===================================================================
class UsbGeraetOut(BaseModel):
    vendor_id: str
    product_id: str
    hersteller: str
    produkt: str
    beschreibung: str


class UsbListeOut(BaseModel):
    pyusb_installiert: bool
    geraete: list[UsbGeraetOut] = []
    hinweis: str = ""