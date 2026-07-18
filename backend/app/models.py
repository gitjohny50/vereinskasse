"""Datenmodell.

Phase 1 lieferte Systemeinstellung, Geraet, AuditLog und Druckauftrag.
Phase 2 ergänzt die Stammdaten gemäß Lastenheft 6-12 und 27: Rollen, Benutzer,
Sitzungen, Vereine, Kassenprofile, Veranstaltungen, Kategorien, Pfandarten,
Artikel samt Pfandzuordnung und Zahlungsmethoden.

Geldbeträge werden ausschließlich als ganzzahlige Cent-Spalten geführt
(Lastenheft 5.3). Katalogdaten (Kategorie, Artikel, Pfandart, Zahlungsmethode)
gehören zu einem Kassenprofil (Lastenheft 7.1).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ===================================================================
# Phase 1: System, Diagnose, Protokoll
# ===================================================================
class Systemeinstellung(Base):
    __tablename__ = "systemeinstellung"

    schluessel: Mapped[str] = mapped_column(String(120), primary_key=True)
    wert: Mapped[str] = mapped_column(Text, nullable=False, default="")
    beschreibung: Mapped[str] = mapped_column(Text, nullable=False, default="")
    geaendert_am: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class Geraet(Base):
    __tablename__ = "geraet"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    seriennummer: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    erstellt_am: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    zeitpunkt: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    benutzer: Mapped[str] = mapped_column(String(120), nullable=False, default="system")
    aktion: Mapped[str] = mapped_column(String(120), nullable=False)
    datensatz: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    vorher: Mapped[str] = mapped_column(Text, nullable=False, default="")
    nachher: Mapped[str] = mapped_column(Text, nullable=False, default="")
    begruendung: Mapped[str] = mapped_column(Text, nullable=False, default="")


class Druckauftrag(Base):
    __tablename__ = "druckauftrag"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dokumenttyp: Mapped[str] = mapped_column(String(60), nullable=False)
    # Klartext-Bezeichnung für das Druckprotokoll (z. B. der Artikelname des Tickets).
    bezeichnung: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    erstellt_am: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    drucker: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="offen")
    versuche: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_versuche: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    letzte_fehlermeldung: Mapped[str] = mapped_column(Text, nullable=False, default="")
    nachdruck: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    aktualisiert_am: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
    verkauf_id: Mapped[int | None] = mapped_column(ForeignKey("verkauf.id"), nullable=True)
    # ESC/POS-Bytes des Auftrags (base64), damit Wiederholungen ohne Neuberechnung möglich sind.
    payload_b64: Mapped[str] = mapped_column(Text, nullable=False, default="")


# ===================================================================
# Phase 2: Benutzer und Rollen (Lastenheft 6)
# ===================================================================
class Rolle(Base):
    __tablename__ = "rolle"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(60), nullable=False, unique=True)
    # Rechtestufe: 10 Bediener, 20 Administrator, 30 Servicetechniker.
    stufe: Mapped[int] = mapped_column(Integer, nullable=False)
    beschreibung: Mapped[str] = mapped_column(Text, nullable=False, default="")


class Benutzer(Base):
    __tablename__ = "benutzer"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # PIN wird niemals im Klartext gespeichert (Lastenheft 6.4).
    pin_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    rolle_id: Mapped[int] = mapped_column(ForeignKey("rolle.id"), nullable=False)
    aktiv: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    fehlversuche: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    letzter_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    erstellt_am: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    rolle: Mapped[Rolle] = relationship()


class Sitzung(Base):
    """Anmeldesitzung mit Ablauf für die automatische Sperre (Lastenheft 6.4)."""

    __tablename__ = "sitzung"

    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    benutzer_id: Mapped[int] = mapped_column(ForeignKey("benutzer.id"), nullable=False)
    erstellt_am: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    letzte_aktivitaet: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    laeuft_ab_am: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    benutzer: Mapped[Benutzer] = relationship()


# ===================================================================
# Phase 2: Verein, Profil, Veranstaltung (Lastenheft 7)
# ===================================================================
class Verein(Base):
    __tablename__ = "verein"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    anschrift: Mapped[str] = mapped_column(Text, nullable=False, default="")
    kontakt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    logo_pfad: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    aktiv: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    erstellt_am: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Kassenprofil(Base):
    __tablename__ = "kassenprofil"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    verein_id: Mapped[int] = mapped_column(ForeignKey("verein.id"), nullable=False)
    bonkopf: Mapped[str] = mapped_column(Text, nullable=False, default="")
    bonfuss: Mapped[str] = mapped_column(Text, nullable=False, default="")
    waehrung: Mapped[str] = mapped_column(String(8), nullable=False, default="EUR")
    aktiv: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    erstellt_am: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    verein: Mapped[Verein] = relationship()


class Veranstaltung(Base):
    __tablename__ = "veranstaltung"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kassenprofil_id: Mapped[int] = mapped_column(ForeignKey("kassenprofil.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    beschreibung: Mapped[str] = mapped_column(Text, nullable=False, default="")
    beginn: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ende: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ort: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    pfand_aktiv: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    bonkopf: Mapped[str] = mapped_column(Text, nullable=False, default="")
    logo_pfad: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    # Status: geplant | aktiv | abgeschlossen | archiviert (Lastenheft 7.2).
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="geplant")
    erstellt_am: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    kassenprofil: Mapped[Kassenprofil] = relationship()


# ===================================================================
# Phase 2: Katalog (Lastenheft 8, 9, 10, 12)
# ===================================================================
class Kategorie(Base):
    __tablename__ = "kategorie"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kassenprofil_id: Mapped[int] = mapped_column(ForeignKey("kassenprofil.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    farbe: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    symbol: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    sortierung: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    aktiv: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Pfandart(Base):
    __tablename__ = "pfandart"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kassenprofil_id: Mapped[int] = mapped_column(ForeignKey("kassenprofil.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    kurzname: Mapped[str] = mapped_column(String(60), nullable=False, default="")
    betrag_cent: Mapped[int] = mapped_column(Integer, nullable=False)
    farbe: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    symbol: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    aktiv: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    rueckgabe_erlaubt: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    artikelticket_drucken: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    steuersatz: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # Promille, z.B. 190 = 19%
    sortierung: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    beschreibung: Mapped[str] = mapped_column(Text, nullable=False, default="")
    max_rueckgabe_menge: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Artikel(Base):
    __tablename__ = "artikel"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kassenprofil_id: Mapped[int] = mapped_column(ForeignKey("kassenprofil.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    kurzname: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    preis_cent: Mapped[int] = mapped_column(Integer, nullable=False)
    kategorie_id: Mapped[int | None] = mapped_column(ForeignKey("kategorie.id"), nullable=True)
    aktiv: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    archiviert: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sortierung: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Ticketmodus: pro_stueck | pro_position | kein (Lastenheft 14.3).
    artikelticket_modus: Mapped[str] = mapped_column(String(20), nullable=False, default="pro_stueck")
    steuersatz: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # Promille
    artikelnummer: Mapped[str] = mapped_column(String(60), nullable=False, default="")
    barcode: Mapped[str] = mapped_column(String(60), nullable=False, default="")
    farbe: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    symbol: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    beschreibung: Mapped[str] = mapped_column(Text, nullable=False, default="")
    ausgabeort: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    erstellt_am: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    kategorie: Mapped[Kategorie | None] = relationship()
    pfandzuordnungen: Mapped[list["ArtikelPfandZuordnung"]] = relationship(
        back_populates="artikel", cascade="all, delete-orphan"
    )


class ArtikelPfandZuordnung(Base):
    """Zuordnung Artikel -> Pfandart (Lastenheft 10.4). Ein Artikel kann keine,
    eine oder mehrere Pfandarten besitzen."""

    __tablename__ = "artikel_pfand_zuordnung"
    __table_args__ = (UniqueConstraint("artikel_id", "pfandart_id", name="uq_artikel_pfandart"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    artikel_id: Mapped[int] = mapped_column(ForeignKey("artikel.id"), nullable=False)
    pfandart_id: Mapped[int] = mapped_column(ForeignKey("pfandart.id"), nullable=False)
    menge_pro_einheit: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    automatisch: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    abweichender_betrag_cent: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gueltig_ab: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    gueltig_bis: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    artikel: Mapped[Artikel] = relationship(back_populates="pfandzuordnungen")
    pfandart: Mapped[Pfandart] = relationship()


class Zahlungsmethode(Base):
    __tablename__ = "zahlungsmethode"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kassenprofil_id: Mapped[int] = mapped_column(ForeignKey("kassenprofil.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    kurzname: Mapped[str] = mapped_column(String(60), nullable=False, default="")
    farbe: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    symbol: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    aktiv: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sortierung: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    schublade_oeffnen: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    rueckgeld_berechnen: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    negativ_erlaubt: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


# ===================================================================
# Phase 3: Verkauf (Lastenheft 11, 12, 27)
# ===================================================================
class Belegkreis(Base):
    """Fortlaufender Belegnummernzähler je Kassenprofil.

    Phase 3 vergibt lückenlos aufsteigende Nummern innerhalb einer Transaktion.
    Die revisionssichere, TSE-gestützte Nummerierung folgt in Phase 9.
    """

    __tablename__ = "belegkreis"

    kassenprofil_id: Mapped[int] = mapped_column(ForeignKey("kassenprofil.id"), primary_key=True)
    letzte_nummer: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Verkauf(Base):
    """Ein abgeschlossener Verkaufsvorgang. Nach dem Abschluss unveränderlich
    (Lastenheft 11.6): es gibt bewusst keine Änderungs-/Löschendpunkte."""

    __tablename__ = "verkauf"
    __table_args__ = (UniqueConstraint("kassenprofil_id", "belegnummer", name="uq_verkauf_beleg"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    belegnummer: Mapped[str] = mapped_column(String(40), nullable=False)
    kassenprofil_id: Mapped[int] = mapped_column(ForeignKey("kassenprofil.id"), nullable=False)
    veranstaltung_id: Mapped[int | None] = mapped_column(ForeignKey("veranstaltung.id"), nullable=True)
    benutzer_id: Mapped[int] = mapped_column(ForeignKey("benutzer.id"), nullable=False)
    zeitpunkt: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    waren_cent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pfand_cent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    gesamt_cent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="abgeschlossen")
    # Zuordnung zum Kassenabschluss (Z-Bericht). NULL = noch offen (nicht abgeschlossen).
    abschluss_id: Mapped[int | None] = mapped_column(ForeignKey("kassenabschluss.id"), nullable=True)

    positionen: Mapped[list["Verkaufsposition"]] = relationship(
        back_populates="verkauf", cascade="all, delete-orphan", order_by="Verkaufsposition.id"
    )
    zahlungen: Mapped[list["Zahlung"]] = relationship(
        back_populates="verkauf", cascade="all, delete-orphan"
    )


class Verkaufsposition(Base):
    """Einzelne Position eines Verkaufs. Alle Werte sind Momentaufnahmen zum
    Verkaufszeitpunkt (Name, Einzelpreis, Steuersatz), damit spätere Stammdaten-
    änderungen den Beleg nicht verändern (Unveränderlichkeit)."""

    __tablename__ = "verkaufsposition"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    verkauf_id: Mapped[int] = mapped_column(ForeignKey("verkauf.id"), nullable=False)
    # typ: artikel | pfand | pfand_rueckgabe
    typ: Mapped[str] = mapped_column(String(20), nullable=False)
    artikel_id: Mapped[int | None] = mapped_column(ForeignKey("artikel.id"), nullable=True)
    pfandart_id: Mapped[int | None] = mapped_column(ForeignKey("pfandart.id"), nullable=True)
    bezeichnung: Mapped[str] = mapped_column(String(200), nullable=False)
    einzelpreis_cent: Mapped[int] = mapped_column(Integer, nullable=False)
    menge: Mapped[int] = mapped_column(Integer, nullable=False)
    gesamt_cent: Mapped[int] = mapped_column(Integer, nullable=False)  # vorzeichenbehaftet
    artikelticket_modus: Mapped[str] = mapped_column(String(20), nullable=False, default="kein")
    steuersatz: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    verkauf: Mapped[Verkauf] = relationship(back_populates="positionen")


class Zahlung(Base):
    __tablename__ = "zahlung"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    verkauf_id: Mapped[int] = mapped_column(ForeignKey("verkauf.id"), nullable=False)
    zahlungsmethode_id: Mapped[int] = mapped_column(ForeignKey("zahlungsmethode.id"), nullable=False)
    bezeichnung: Mapped[str] = mapped_column(String(120), nullable=False)
    betrag_cent: Mapped[int] = mapped_column(Integer, nullable=False)   # dem Verkauf zugeordnet
    gegeben_cent: Mapped[int] = mapped_column(Integer, nullable=False)  # gegeben (bar)
    rueckgeld_cent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    verkauf: Mapped[Verkauf] = relationship(back_populates="zahlungen")


# ===================================================================
# Phase 5: Kassenabschluss / Berichte (X-/Z-Bericht)
# ===================================================================
class Kassenabschluss(Base):
    """Ein Z-Bericht (Tagesabschluss). Fasst alle bis dahin offenen Verkäufe eines
    Kassenprofils zusammen und schließt sie ab. Unveränderlich."""

    __tablename__ = "kassenabschluss"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kassenprofil_id: Mapped[int] = mapped_column(ForeignKey("kassenprofil.id"), nullable=False)
    nummer: Mapped[str] = mapped_column(String(40), nullable=False)
    benutzer_id: Mapped[int] = mapped_column(ForeignKey("benutzer.id"), nullable=False)
    erstellt_am: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    von_zeitpunkt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    bis_zeitpunkt: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    anzahl_verkaeufe: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    waren_cent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pfand_cent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    gesamt_cent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bar_cent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Bargeld-Kassensturz (optional)
    anfangsbestand_cent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    erwartet_cent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    gezaehlt_cent: Mapped[int | None] = mapped_column(Integer, nullable=True)
    differenz_cent: Mapped[int | None] = mapped_column(Integer, nullable=True)

    zahlarten: Mapped[list["KassenabschlussZahlart"]] = relationship(
        back_populates="abschluss", cascade="all, delete-orphan", order_by="KassenabschlussZahlart.id"
    )


class KassenabschlussZahlart(Base):
    """Umsatz je Zahlart innerhalb eines Abschlusses (Momentaufnahme)."""

    __tablename__ = "kassenabschluss_zahlart"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    abschluss_id: Mapped[int] = mapped_column(ForeignKey("kassenabschluss.id"), nullable=False)
    zahlungsmethode_id: Mapped[int | None] = mapped_column(ForeignKey("zahlungsmethode.id"), nullable=True)
    bezeichnung: Mapped[str] = mapped_column(String(120), nullable=False)
    anzahl: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    betrag_cent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bar: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    abschluss: Mapped[Kassenabschluss] = relationship(back_populates="zahlarten")
