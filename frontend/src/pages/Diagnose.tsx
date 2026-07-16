import { useEffect, useState } from "react";
import { api, type ActionResult, type Health, type PrinterStatus, type Setting } from "../api";

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
};

const SETTING_ORDER = [
  "drucker.transport",
  "drucker.netzwerk.host",
  "drucker.netzwerk.port",
  "drucker.codepage_id",
  "schnitt.modus",
  "schnitt.vorschub_zeilen",
  "schublade.aktiv",
  "schublade.pin",
  "schublade.puls_ms",
  "schublade.pause_ms",
];

export function Diagnose() {
  const [health, setHealth] = useState<Health | null>(null);
  const [printer, setPrinter] = useState<PrinterStatus | null>(null);
  const [settings, setSettings] = useState<Setting[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [cutCount, setCutCount] = useState(3);
  const [testResult, setTestResult] = useState<ActionResult | null>(null);
  const [cutResult, setCutResult] = useState<ActionResult | null>(null);
  const [drawerResult, setDrawerResult] = useState<ActionResult | null>(null);

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

  useEffect(() => {
    refreshStatus();
    refreshSettings();
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

  const orderedSettings = SETTING_ORDER.map((k) => settings.find((s) => s.schluessel === k)).filter(
    (s): s is Setting => Boolean(s)
  );

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
            <span className="key">{s.schluessel}</span>
            {SELECT_OPTIONS[s.schluessel] ? (
              <select value={s.wert} onChange={(e) => saveSetting(s.schluessel, e.target.value)}>
                {SELECT_OPTIONS[s.schluessel].map((opt) => (
                  <option key={opt} value={opt}>{opt}</option>
                ))}
              </select>
            ) : (
              <input
                defaultValue={s.wert}
                onBlur={(e) => e.target.value !== s.wert && saveSetting(s.schluessel, e.target.value)}
              />
            )}
          </div>
        ))}
      </div>

      <p className="note">
        Alle Schnitt-, Schubladen- und USB-Parameter sind Platzhalter, bis sie am echten NetumScan NS-8360L
        verifiziert wurden (Lastenheft 4.2). Bis dahin arbeitet der Transport „mock“, sodass der gesamte Ablauf
        ohne Hardware prüfbar bleibt.
      </p>
    </>
  );
}
