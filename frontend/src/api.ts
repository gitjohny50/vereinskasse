// API-Client mit Token-Verwaltung. Das Token wird im localStorage gehalten,
// damit ein Kiosk-Neustart angemeldet bleibt (bis zum Ablauf/Logout).

const TOKEN_KEY = "vk_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}
export function setToken(t: string | null) {
  if (t) localStorage.setItem(TOKEN_KEY, t);
  else localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json", ...(init?.headers as Record<string, string>) };
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`/api${path}`, { ...init, headers });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    let detail = text;
    try { detail = JSON.parse(text).detail ?? text; } catch { /* keep text */ }
    throw new ApiError(res.status, typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

// -- Typen --------------------------------------------------------------
export interface Health { status: string; version: string; db_integrity: string; }
export interface PrinterStatus { reachable: boolean; known: boolean; paper_ok: boolean | null; cover_closed: boolean | null; detail: string; }
export interface ActionResult { ok: boolean; detail: string; auftrag_id: number | null; drucker: string | null; }
export interface UsbGeraet { vendor_id: string; product_id: string; hersteller: string; produkt: string; beschreibung: string; }
export interface UsbListe { pyusb_installiert: boolean; geraete: UsbGeraet[]; hinweis: string; }
export interface Setting { schluessel: string; wert: string; beschreibung: string; }
export interface LoginUser { id: number; name: string; }
export interface Session { token: string; benutzer_id: number; name: string; rolle: string; stufe: number; }

export interface Rolle { id: number; name: string; stufe: number; beschreibung: string; }
export interface Benutzer { id: number; name: string; rolle_id: number; rolle: string; stufe: number; aktiv: boolean; }
export interface Verein { id: number; name: string; anschrift: string; kontakt: string; aktiv: boolean; }
export interface Kassenprofil { id: number; name: string; verein_id: number; bonkopf?: string; bonfuss?: string; waehrung: string; aktiv: boolean; }
export interface Veranstaltung { id: number; kassenprofil_id: number; name: string; beschreibung: string; ort: string; pfand_aktiv: boolean; status: string; }
export interface Kategorie { id: number; kassenprofil_id: number; name: string; farbe: string; symbol: string; sortierung: number; aktiv: boolean; }
export interface Pfandart { id: number; kassenprofil_id: number; name: string; kurzname: string; betrag_cent: number; farbe: string; symbol: string; aktiv: boolean; rueckgabe_erlaubt: boolean; artikelticket_drucken: boolean; steuersatz: number; sortierung: number; max_rueckgabe_menge: number | null; }
export interface Zahlungsmethode { id: number; kassenprofil_id: number; name: string; kurzname: string; farbe: string; symbol: string; aktiv: boolean; sortierung: number; schublade_oeffnen: boolean; rueckgeld_berechnen: boolean; negativ_erlaubt: boolean; }
export interface PfandZuordnung { id?: number; pfandart_id: number; menge_pro_einheit: number; automatisch: boolean; abweichender_betrag_cent: number | null; }
export interface Artikel {
  id: number; kassenprofil_id: number; name: string; kurzname: string; preis_cent: number;
  kategorie_id: number | null; aktiv: boolean; archiviert: boolean; sortierung: number;
  artikelticket_modus: string; steuersatz: number; artikelnummer: string; barcode: string;
  ausgabeort: string; pfandzuordnungen: PfandZuordnung[];
}

export interface BerechnungPosition { typ: string; bezeichnung: string; einzelpreis_cent: number; menge: number; gesamt_cent: number; artikelticket_modus: string; steuersatz: number; }
export interface Berechnung { positionen: BerechnungPosition[]; waren_cent: number; pfand_cent: number; gesamt_cent: number; }
export interface ZahlungInfo { zahlungsmethode_id: number; bezeichnung: string; betrag_cent: number; gegeben_cent: number; rueckgeld_cent: number; }
export interface Verkauf {
  id: number; belegnummer: string; kassenprofil_id: number; veranstaltung_id: number | null;
  benutzer_id: number; zeitpunkt: string; waren_cent: number; pfand_cent: number; gesamt_cent: number;
  status: string; positionen: BerechnungPosition[]; zahlung: ZahlungInfo | null;
}
export interface Druckauftrag {
  id: number; dokumenttyp: string; drucker: string; status: string; versuche: number; max_versuche: number;
  letzte_fehlermeldung: string; nachdruck: boolean; verkauf_id: number | null; erstellt_am: string; aktualisiert_am: string;
}
export interface QueueStatus { offen: number; fehlgeschlagen: number; erfolgreich: number; abgebrochen: number; }

export interface BerichtZahlart { zahlungsmethode_id: number | null; bezeichnung: string; anzahl: number; betrag_cent: number; bar: boolean; }
export interface BerichtArtikel { bezeichnung: string; menge: number; betrag_cent: number; }
export interface Bericht {
  typ: string; nummer: string | null; abschluss_id: number | null; kassenprofil_id: number;
  von: string | null; bis: string; anzahl_verkaeufe: number;
  waren_cent: number; pfand_cent: number; gesamt_cent: number; bar_cent: number;
  anfangsbestand_cent: number; erwartet_cent: number; gezaehlt_cent: number | null; differenz_cent: number | null;
  zahlarten: BerichtZahlart[]; artikel: BerichtArtikel[];
}
export interface KassenabschlussKopf {
  id: number; nummer: string; kassenprofil_id: number; erstellt_am: string;
  anzahl_verkaeufe: number; waren_cent: number; pfand_cent: number; gesamt_cent: number; bar_cent: number;
  gezaehlt_cent: number | null; differenz_cent: number | null;
}

type Body = Record<string, unknown>;
const j = (b: Body) => JSON.stringify(b);

// -- Endpunkte ----------------------------------------------------------
export const api = {
  // Auth
  loginUsers: () => req<LoginUser[]>("/auth/benutzerliste"),
  login: (benutzer_id: number, pin: string) => req<Session>("/auth/login", { method: "POST", body: j({ benutzer_id, pin }) }),
  me: () => req<Session>("/auth/me"),
  logout: () => req<{ ok: boolean }>("/auth/logout", { method: "POST" }),

  // System / Diagnose
  health: () => req<Health>("/health"),
  printerStatus: () => req<PrinterStatus>("/diagnose/drucker/status"),
  usbGeraete: () => req<UsbListe>("/diagnose/drucker/usb-geraete"),
  testPage: () => req<ActionResult>("/diagnose/drucker/testseite", { method: "POST" }),
  cutTest: (anzahl: number) => req<ActionResult>("/diagnose/drucker/schnitt-test", { method: "POST", body: j({ anzahl }) }),
  openDrawer: (grund: string) => req<ActionResult>("/diagnose/schublade/oeffnen", { method: "POST", body: j({ grund }) }),
  settings: () => req<Setting[]>("/einstellungen"),
  updateSetting: (schluessel: string, wert: string) => req<Setting>(`/einstellungen/${schluessel}`, { method: "PUT", body: j({ wert }) }),

  // Benutzer & Rollen
  rollen: () => req<Rolle[]>("/rollen"),
  benutzer: () => req<Benutzer[]>("/benutzer"),
  benutzerAnlegen: (b: Body) => req<Benutzer>("/benutzer", { method: "POST", body: j(b) }),
  benutzerAendern: (id: number, b: Body) => req<Benutzer>(`/benutzer/${id}`, { method: "PUT", body: j(b) }),

  // Vereine & Profile & Veranstaltungen
  vereine: () => req<Verein[]>("/vereine"),
  vereinAnlegen: (b: Body) => req<Verein>("/vereine", { method: "POST", body: j(b) }),
  profile: () => req<Kassenprofil[]>("/kassenprofile"),
  profilAnlegen: (b: Body) => req<Kassenprofil>("/kassenprofile", { method: "POST", body: j(b) }),
  veranstaltungen: (pid?: number) => req<Veranstaltung[]>(`/veranstaltungen${pid ? `?kassenprofil_id=${pid}` : ""}`),
  veranstaltungAnlegen: (b: Body) => req<Veranstaltung>("/veranstaltungen", { method: "POST", body: j(b) }),
  veranstaltungStatus: (id: number, status: string) => req<Veranstaltung>(`/veranstaltungen/${id}/status?status=${encodeURIComponent(status)}`, { method: "PUT" }),

  // Kategorien
  kategorien: (pid: number) => req<Kategorie[]>(`/kategorien?kassenprofil_id=${pid}`),
  kategorieAnlegen: (b: Body) => req<Kategorie>("/kategorien", { method: "POST", body: j(b) }),
  kategorieAendern: (id: number, b: Body) => req<Kategorie>(`/kategorien/${id}`, { method: "PUT", body: j(b) }),

  // Pfandarten
  pfandarten: (pid: number) => req<Pfandart[]>(`/pfandarten?kassenprofil_id=${pid}`),
  pfandartAnlegen: (b: Body) => req<Pfandart>("/pfandarten", { method: "POST", body: j(b) }),
  pfandartAendern: (id: number, b: Body) => req<Pfandart>(`/pfandarten/${id}`, { method: "PUT", body: j(b) }),

  // Zahlungsmethoden
  zahlungsmethoden: (pid: number) => req<Zahlungsmethode[]>(`/zahlungsmethoden?kassenprofil_id=${pid}`),
  zahlungsmethodeAnlegen: (b: Body) => req<Zahlungsmethode>("/zahlungsmethoden", { method: "POST", body: j(b) }),
  zahlungsmethodeAendern: (id: number, b: Body) => req<Zahlungsmethode>(`/zahlungsmethoden/${id}`, { method: "PUT", body: j(b) }),

  // Artikel
  artikel: (pid: number, mitArchiviert = false) => req<Artikel[]>(`/artikel?kassenprofil_id=${pid}&mit_archiviert=${mitArchiviert}`),
  artikelAnlegen: (b: Body) => req<Artikel>("/artikel", { method: "POST", body: j(b) }),
  artikelAendern: (id: number, b: Body) => req<Artikel>(`/artikel/${id}`, { method: "PUT", body: j(b) }),
  artikelArchivieren: (id: number) => req<Artikel>(`/artikel/${id}`, { method: "DELETE" }),
  artikelKopieren: (id: number) => req<Artikel>(`/artikel/${id}/kopieren`, { method: "POST" }),

  // Verkauf
  berechnung: (b: Body) => req<Berechnung>("/verkauf/berechnung", { method: "POST", body: j(b) }),
  verkaufAbschluss: (b: Body) => req<Verkauf>("/verkauf", { method: "POST", body: j(b) }),
  verkaeufe: (pid: number) => req<Verkauf[]>(`/verkauf?kassenprofil_id=${pid}`),
  verkaufDetail: (id: number) => req<Verkauf>(`/verkauf/${id}`),
  nachdruck: (id: number) => req<ActionResult>(`/verkauf/${id}/nachdruck`, { method: "POST" }),
  belegDrucken: (id: number) => req<ActionResult>(`/verkauf/${id}/beleg`, { method: "POST" }),

  // Druckwarteschlange
  druckauftraege: (status?: string) => req<Druckauftrag[]>(`/druckwarteschlange${status ? `?status=${encodeURIComponent(status)}` : ""}`),
  druckStatus: () => req<QueueStatus>("/druckwarteschlange/status"),
  druckVerarbeiten: () => req<{ verarbeitet: number; erfolg: number; fehler: number }>("/druckwarteschlange/verarbeiten", { method: "POST" }),
  druckWiederholen: (id: number) => req<Druckauftrag>(`/druckwarteschlange/${id}/wiederholen`, { method: "POST" }),
  druckAbbrechen: (id: number) => req<Druckauftrag>(`/druckwarteschlange/${id}/abbrechen`, { method: "POST" }),

  // Kassenabschluss (Phase 5)
  xBericht: (pid: number, anfangsbestand_cent = 0, gezaehlt_cent?: number | null) =>
    req<Bericht>(`/abschluss/x?kassenprofil_id=${pid}&anfangsbestand_cent=${anfangsbestand_cent}${gezaehlt_cent != null ? `&gezaehlt_cent=${gezaehlt_cent}` : ""}`),
  zAbschluss: (b: Body) => req<Bericht>("/abschluss/z", { method: "POST", body: j(b) }),
  abschluesse: (pid: number) => req<KassenabschlussKopf[]>(`/abschluss?kassenprofil_id=${pid}`),
  abschlussDetail: (id: number) => req<Bericht>(`/abschluss/${id}`),
  abschlussNachdruck: (id: number) => req<ActionResult>(`/abschluss/${id}/nachdruck`, { method: "POST" }),
};

// -- Geld-Helfer (Cent <-> deutsche Anzeige) ----------------------------
export function formatCents(cents: number): string {
  const sign = cents < 0 ? "-" : "";
  const abs = Math.abs(cents);
  const euro = Math.floor(abs / 100).toLocaleString("de-DE");
  const rest = String(abs % 100).padStart(2, "0");
  return `${sign}${euro},${rest}\u00a0\u20ac`;
}
export function euroToCents(text: string): number | null {
  const cleaned = text.trim().replace(/\s|€/g, "").replace(/\./g, "").replace(",", ".");
  if (cleaned === "" || isNaN(Number(cleaned))) return null;
  return Math.round(Number(cleaned) * 100);
}
