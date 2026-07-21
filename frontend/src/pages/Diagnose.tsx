import { useEffect, useState } from "react";
import { api, type ActionResult, type BonLogoInfo, type Health, type PrinterStatus, type Setting, type UsbGeraet, type UsbListe } from "../api";

type DotKind = "ok" | "warn" | "danger" | "unknown";

function Pill({ kind, label, detail }: { kind: DotKind; label: string; detail?: string }) {
  return (
    <span className="pill">
      <span className={`dot ${kind}`} aria-hidden="true" />
      <span className="label">{label}</span>
      {detail && <span className="detail">{detail}</span>}
    </span>
  );
}

function ResultLine({ result }: { result: ActionResult | null }) {
  if (!result) return <div className="result">Noch keine Aktion ausgeführt.</div>;
  return (
    <div className={`result ${result.ok ? "ok" : "err"}`}>
      {result.ok ? "OK" : "FEHLER"} · {result.detail}
      {result.auftrag_id != null && ` · Auftrag #${result.auftrag_id}`}
      {result.drucker && ` · ${result.drucker}`}
    </div>
  );
}

// Nur diese Schlüssel werden im Panel als Auswahl angeboten; der Rest ist Text.
const SELECT_OPTIONS: Record<string, string[]> = {
  "drucker.transport": ["mock", "network", "usb"],
  "schnitt.modus": ["partial", "full", "none"],
  "schublade.aktiv": ["1", "0"],
  "schublade.pin": ["0", "1"],
  "verkauf.beleg_autodruck": ["1", "0"],
};

const SETTING_ORDER = [
  "drucker.transport",
  "drucker.netzwerk.host",
  "drucker.netzwerk.port",
  "drucker.usb.vendor_id",
  "drucker.usb.product_id",
  "drucker.usb.endpoint",
  "drucker.encoding",
  "drucker.codepage_id",
  "bon.breite_zeichen",
  "diagnose.testseite.qr_url",
  "schnitt.modus",
  "schnitt.vorschub_zeilen",
  "artikelticket.vorschub_zeilen",
  "schublade.aktiv",
  "schublade.pin",
  "schublade.puls_ms",
  "schublade.pause_ms",
  "verkauf.beleg_autodruck",
];

// Klartext-Beschriftungen (Fallback: der Schlüssel selbst).
const LABELS: Record<string, string> = {
  "drucker.transport": "Anschlussart",
  "drucker.netzwerk.host": "Netzwerk: IP-Adresse",
  "drucker.netzwerk.port": "Netzwerk: Port",
  "drucker.usb.vendor_id": "USB: Hersteller-ID",
  "drucker.usb.product_id": "USB: Produkt-ID",
  "drucker.usb.endpoint": "USB: Endpunkt",
  "drucker.encoding": "Zeichenkodierung",
  "drucker.codepage_id": "Codepage-ID",
  "bon.breite_zeichen": "Bonbreite (Zeichen)",
  "diagnose.testseite.qr_url": "Testseite: QR-Code-URL",
  "schnitt.modus": "Schnitt-Modus",
  "schnitt.vorschub_zeilen": "Schnitt: Vorschubzeilen",
  "artikelticket.vorschub_zeilen": "Artikelticket: Vorschubzeilen",
  "schublade.aktiv": "Schublade aktiv",
  "schublade.pin": "Schublade: Pin",
  "schublade.puls_ms": "Schublade: Puls (ms)",
  "schublade.pause_ms": "Schublade: Pause (ms)",
  "verkauf.beleg_autodruck": "Beleg automatisch drucken (1/0)",
};

interface RasterLogo {
  raster_b64: string;
  breite_px: number;
  hoehe_px: number;
}

function bytesToBase64(bytes: Uint8Array): string {
  let binary = "";
  for (let i = 0; i < bytes.length; i += 1) binary += String.fromCharCode(bytes[i]);
  return btoa(binary);
}

async function svgToRasterLogo(file: File): Promise<RasterLogo> {
  const svg = await file.text();
  const imageUrl = URL.createObjectURL(new Blob([svg], { type: "image/svg+xml" }));
  try {
    const image = await new Promise<HTMLImageElement>((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = () => reject(new Error("SVG konnte nicht gelesen werden."));
      img.src = imageUrl;
    });
    const sourceWidth = image.naturalWidth || 384;
    const sourceHeight = image.naturalHeight || 128;
    const width = 384;
    const height = Math.max(24, Math.min(240, Math.round((sourceHeight / sourceWidth) * width)));
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("Canvas ist nicht verfügbar.");
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, width, height);
    ctx.drawImage(image, 0, 0, width, height);
    const pixels = ctx.getImageData(0, 0, width, height).data;
    const rowBytes = width / 8;
    const raster = new Uint8Array(rowBytes * height);
    for (let y = 0; y < height; y += 1) {
      for (let x = 0; x < width; x += 1) {
        const offset = (y * width + x) * 4;
        const alpha = pixels[offset + 3] / 255;
        const luminance = 0.299 * pixels[offset] + 0.587 * pixels[offset + 1] + 0.114 * pixels[offset + 2];
        if (alpha > 0.2 && luminance < 180) {
          raster[y * rowBytes + Math.floor(x / 8)] |= 0x80 >> (x % 8);
        }
      }
    }
    return { raster_b64: bytesToBase64(raster), breite_px: width, hoehe_px: height };
  } finally {
    URL.revokeObjectURL(imageUrl);
  }
}

export function Diagnose() {
  const [health, setHealth] = useState<Health | null>(null);
  const [printer, setPrinter] = useState<PrinterStatus | null>(null);
  const [settings, setSettings] = useState<Setting[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [cutCount, setCutCount] = useState(3);
  const [testResult, setTestResult] = useState<ActionResult | null>(null);
  const [cutResult, setCutResult] = useState<ActionResult | null>(null);
  const [drawerResult, setDrawerResult] = useState<ActionResult | null>(null);
  const [usbList, setUsbList] = useState<UsbListe | null>(null);
  const [usbBusy, setUsbBusy] = useState(false);
  const [logo, setLogo] = useState<BonLogoInfo | null>(null);
  const [logoBusy, setLogoBusy] = useState(false);
  const [logoResult, setLogoResult] = useState<string>("Noch kein Logo geladen.");

  async function refreshStatus() {
    try {
      const [h, p] = await Promise.all([api.health(), api.printerStatus()]);
      setHealth(h);
      setPrinter(p);
    } catch {
      setPrinter(null);
    }
  }

  async function refreshSettings() {
    try {
      setSettings(await api.settings());
    } catch {
      /* Fehler still ignorieren; Statusleiste zeigt Systemzustand */
    }
  }

  async function refreshLogo() {
    try {
      setLogo(await api.bonLogo());
    } catch {
      setLogo(null);
    }
  }

  useEffect(() => {
    refreshStatus();
    refreshSettings();
    refreshLogo();
    const t = setInterval(refreshStatus, 8000);
    return () => clearInterval(t);
  }, []);

  const printerKind: DotKind = !printer
    ? "danger"
    : !printer.reachable
      ? "danger"
      : printer.known
        ? "ok"
        : "unknown";
  const printerLabel = !printer
    ? "Backend nicht erreichbar"
    : !printer.reachable
      ? "Drucker nicht erreichbar"
      : printer.known
        ? "Drucker bereit"
        : "Druckerstatus unbekannt";

  const dbKind: DotKind = health?.db_integrity === "ok" ? "ok" : health ? "warn" : "danger";
  const dbLabel = health
    ? health.db_integrity === "ok"
      ? "Datenbank ok"
      : "Datenbank prüfen"
    : "Datenbank unbekannt";

  async function run(name: string, fn: () => Promise<ActionResult>, set: (r: ActionResult) => void) {
    setBusy(name);
    try {
      set(await fn());
    } catch (e) {
      set({ ok: false, detail: e instanceof Error ? e.message : "Unbekannter Fehler", auftrag_id: null, drucker: null });
    } finally {
      setBusy(null);
      refreshStatus();
    }
  }

  async function saveSetting(key: string, value: string) {
    try {
      const updated = await api.updateSetting(key, value);
      setSettings((prev) => prev.map((s) => (s.schluessel === key ? updated : s)));
      refreshStatus();
    } catch {
      refreshSettings();
    }
  }

  async function sucheUsb() {
    setUsbBusy(true);
    try {
      setUsbList(await api.usbGeraete());
    } catch {
      setUsbList({ pyusb_installiert: false, geraete: [], hinweis: "Abruf fehlgeschlagen." });
    } finally {
      setUsbBusy(false);
    }
  }
  async function uebernehmeUsb(g: UsbGeraet) {
    await saveSetting("drucker.usb.vendor_id", g.vendor_id);
    await saveSetting("drucker.usb.product_id", g.product_id);
  }

  async function logoEinlesen(file: File | null) {
    if (!file) return;
    setLogoBusy(true);
    try {
      const raster = await svgToRasterLogo(file);
      const updated = await api.uploadBonLogo(raster.raster_b64, raster.breite_px, raster.hoehe_px);
      setLogo(updated);
      setLogoResult(`Logo gespeichert · ${updated.breite_px}×${updated.hoehe_px}px`);
    } catch (e) {
      setLogoResult(e instanceof Error ? e.message : "Logo konnte nicht gespeichert werden.");
    } finally {
      setLogoBusy(false);
    }
  }

  async function logoEntfernen() {
    setLogoBusy(true);
    try {
      const updated = await api.deleteBonLogo();
      setLogo(updated);
      setLogoResult("Logo entfernt.");
    } catch (e) {
      setLogoResult(e instanceof Error ? e.message : "Logo konnte nicht entfernt werden.");
    } finally {
      setLogoBusy(false);
    }
  }

  const transport = settings.find((s) => s.schluessel === "drucker.transport")?.wert ?? "mock";
  const orderedSettings = SETTING_ORDER
    .filter((k) => {
      if (k.startsWith("drucker.netzwerk.")) return transport === "network";
      if (k.startsWith("drucker.usb.")) return transport === "usb";
      return true;
    })
    .map((k) => settings.find((s) => s.schluessel === k))
    .filter((s): s is Setting => Boolean(s));

  return (
    <>

      <div className="statusbar">
        <Pill kind={printerKind} label={printerLabel} detail={printer?.detail} />
        <Pill kind={dbKind} label={dbLabel} detail={health?.db_integrity} />
        <Pill kind="unknown" label="Netzwerk" detail="Phase 2" />
      </div>

      <div className="grid">
        <section className="card">
          <div className="num">01 / TESTSEITE</div>
          <h2>Testseite drucken</h2>
          <p>Prüft Umlaute, Eurozeichen, Fett, doppelte Breite/Höhe, QR-Code und einen Teilschnitt. Erzeugt keinen Verkauf.</p>
          <div className="spacer" />
          <ResultLine result={testResult} />
          <button
            className="btn primary"
            disabled={busy !== null}
            onClick={() => run("test", api.testPage, setTestResult)}
          >
            {busy === "test" ? "Drucke…" : "Testseite drucken"}
          </button>
        </section>

        <section className="card">
          <div className="num">02 / SCHNITT</div>
          <h2>Schnitt-Test</h2>
          <p>Druckt mehrere kurze Tickets und schneidet nach jedem. Prüft die Schneideeinheit bei vielen Aufträgen.</p>
          <div className="spacer" />
          <div className="row">
            <div className="stepper" aria-label="Anzahl Tickets">
              <button onClick={() => setCutCount((n) => Math.max(1, n - 1))} disabled={busy !== null}>−</button>
              <span>{cutCount}</span>
              <button onClick={() => setCutCount((n) => Math.min(50, n + 1))} disabled={busy !== null}>+</button>
            </div>
            <span className="detail" style={{ fontFamily: "var(--mono)", color: "var(--muted)", fontSize: 13 }}>
              Tickets
            </span>
          </div>
          <ResultLine result={cutResult} />
          <button
            className="btn"
            disabled={busy !== null}
            onClick={() => run("cut", () => api.cutTest(cutCount), setCutResult)}
          >
            {busy === "cut" ? "Drucke…" : `${cutCount} Tickets schneiden`}
          </button>
        </section>

        <section className="card">
          <div className="num">03 / SCHUBLADE</div>
          <h2>Kassenschublade</h2>
          <p>Löst genau einen Öffnungsimpuls über den Bondrucker aus. Wird mit Benutzer, Zeit und Grund protokolliert.</p>
          <div className="spacer" />
          <ResultLine result={drawerResult} />
          <button
            className="btn danger"
            disabled={busy !== null}
            onClick={() => run("drawer", () => api.openDrawer("manueller Test (Servicebereich)"), setDrawerResult)}
          >
            {busy === "drawer" ? "Öffne…" : "Schublade öffnen"}
          </button>
        </section>
      </div>

      <div className="section-title">Hardware-Einstellungen</div>
      <div className="settings">
        {orderedSettings.length === 0 && <div className="setting"><span className="key">Lade Einstellungen…</span><span /></div>}
        {orderedSettings.map((s) => (
          <div className="setting" key={s.schluessel}>
            <span className="key">{LABELS[s.schluessel] ?? s.schluessel}</span>
            {SELECT_OPTIONS[s.schluessel] ? (
              <select value={s.wert} onChange={(e) => saveSetting(s.schluessel, e.target.value)}>
                {SELECT_OPTIONS[s.schluessel].map((opt) => (
                  <option key={opt} value={opt}>{opt}</option>
                ))}
              </select>
            ) : (
              <input
                key={s.wert}
                defaultValue={s.wert}
                onBlur={(e) => e.target.value !== s.wert && saveSetting(s.schluessel, e.target.value)}
              />
            )}
          </div>
        ))}
      </div>

      <div className="section-title">Bon-Logo</div>
      <section className="card">
        <div className="row" style={{ justifyContent: "space-between", alignItems: "center", flexWrap: "wrap" }}>
          <div>
            <h2>SVG-Logo auf Beleg</h2>
            <p>
              {logo?.aktiv
                ? `Aktiv · ${logo.breite_px}×${logo.hoehe_px}px`
                : "Kein Logo auf dem Beleg aktiv."}
            </p>
          </div>
          <div className="row" style={{ flexWrap: "wrap" }}>
            <label className={`btn btn-sm btn-primary file-btn ${logoBusy ? "disabled" : ""}`}>
              {logoBusy ? "Verarbeite…" : "SVG einlesen"}
              <input
                type="file"
                accept=".svg,image/svg+xml"
                disabled={logoBusy}
                onChange={(e) => {
                  logoEinlesen(e.target.files?.[0] ?? null);
                  e.currentTarget.value = "";
                }}
              />
            </label>
            <button className="btn btn-sm" disabled={logoBusy || !logo?.aktiv} onClick={logoEntfernen}>
              Entfernen
            </button>
          </div>
        </div>
        <div className={`result ${logo?.aktiv ? "ok" : ""}`}>{logoResult}</div>
      </section>

      {transport === "usb" && (
        <div className="card" style={{ marginTop: 12 }}>
          <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
            <strong>USB-Drucker einrichten</strong>
            <button className="btn btn-sm" disabled={usbBusy} onClick={sucheUsb}>
              {usbBusy ? "Suche…" : "USB-Geräte suchen"}
            </button>
          </div>
          {usbList && !usbList.pyusb_installiert && (
            <p className="note" style={{ marginTop: 8 }}>
              USB-Unterstützung nicht verfügbar (pyusb/libusb fehlt). Siehe deploy/USB-DRUCKER.md.
              {usbList.hinweis && ` – ${usbList.hinweis}`}
            </p>
          )}
          {usbList && usbList.pyusb_installiert && usbList.geraete.length === 0 && (
            <p className="note" style={{ marginTop: 8 }}>Keine USB-Geräte gefunden{usbList.hinweis ? ` – ${usbList.hinweis}` : ""}.</p>
          )}
          {usbList && usbList.geraete.length > 0 && (
            <table className="tabelle" style={{ marginTop: 8 }}>
              <thead><tr><th>Gerät</th><th>Hersteller-ID</th><th>Produkt-ID</th><th className="num"></th></tr></thead>
              <tbody>
                {usbList.geraete.map((g, i) => (
                  <tr key={`${g.vendor_id}:${g.product_id}:${i}`}>
                    <td>{g.beschreibung}</td>
                    <td className="mono">{g.vendor_id}</td>
                    <td className="mono">{g.product_id}</td>
                    <td className="num"><button className="btn btn-sm btn-primary" onClick={() => uebernehmeUsb(g)}>Übernehmen</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <p className="note" style={{ marginTop: 8 }}>
            Beim Drucker auf „Übernehmen“ tippen – Hersteller- und Produkt-ID werden gesetzt. Für den Zugriff
            ohne root ist einmalig die udev-Regel nötig (deploy/USB-DRUCKER.md).
          </p>
        </div>
      )}

      <p className="note">
        Alle Schnitt-, Schubladen- und USB-Parameter sind Platzhalter, bis sie am echten NetumScan NS-8360L
        verifiziert wurden (Lastenheft 4.2). Bis dahin arbeitet der Transport „mock“, sodass der gesamte Ablauf
        ohne Hardware prüfbar bleibt.
      </p>
    </>
  );
}
