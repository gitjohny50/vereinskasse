import { useEffect, useRef, useState } from "react";
import { api, ApiError, type Druckauftrag, type QueueStatus } from "../api";

const STATUS_STIL: Record<string, { text: string; farbe: string }> = {
  offen: { text: "offen", farbe: "var(--warn, #b45309)" },
  fehlgeschlagen: { text: "fehlgeschlagen", farbe: "var(--danger, #b3261e)" },
  erfolgreich: { text: "erfolgreich", farbe: "var(--ok, #2563eb)" },
  abgebrochen: { text: "abgebrochen", farbe: "var(--muted, #566664)" },
};

export function Druckwarteschlange({ canAdmin }: { canAdmin: boolean }) {
  const [status, setStatus] = useState<QueueStatus | null>(null);
  const [jobs, setJobs] = useState<Druckauftrag[]>([]);
  const [alle, setAlle] = useState(false);
  const [fehler, setFehler] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const alleRef = useRef(alle);
  alleRef.current = alle;

  async function laden() {
    try {
      const [st, js] = await Promise.all([
        api.druckStatus(),
        api.druckauftraege(alleRef.current ? undefined : "offen,fehlgeschlagen"),
      ]);
      setStatus(st);
      setJobs(js);
      setFehler(null);
    } catch (e) {
      setFehler(e instanceof ApiError ? e.message : "Warteschlange nicht erreichbar.");
    }
  }

  // Automatische Wiederholung: offene Aufträge regelmäßig verarbeiten.
  useEffect(() => {
    laden();
    const iv = setInterval(async () => {
      try { await api.druckVerarbeiten(); } catch { /* Drucker evtl. weiterhin offline */ }
      await laden();
    }, 12000);
    return () => clearInterval(iv);
  }, []);

  useEffect(() => { laden(); }, [alle]);

  async function jetztVerarbeiten() {
    setBusy(true);
    try { await api.druckVerarbeiten(); await laden(); }
    catch (e) { setFehler(e instanceof ApiError ? e.message : "Verarbeiten fehlgeschlagen."); }
    finally { setBusy(false); }
  }
  async function wiederholen(id: number) {
    try { await api.druckWiederholen(id); await laden(); }
    catch (e) { setFehler(e instanceof ApiError ? e.message : "Wiederholung fehlgeschlagen."); }
  }
  async function abbrechen(id: number) {
    try { await api.druckAbbrechen(id); await laden(); }
    catch (e) { setFehler(e instanceof ApiError ? e.message : "Abbrechen fehlgeschlagen."); }
  }

  function zeit(iso: string) {
    return new Date(iso).toLocaleString("de-DE", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit" });
  }

  const offenFehler = (status?.offen ?? 0) + (status?.fehlgeschlagen ?? 0);

  return (
    <section>
      <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-end", marginBottom: 16 }}>
        <div><div className="eyebrow">Drucken</div><strong style={{ fontSize: 17 }}>Druckwarteschlange</strong></div>
        <div className="row" style={{ gap: 8 }}>
          <button className="btn btn-sm" onClick={() => setAlle((v) => !v)}>{alle ? "Nur offene & Fehler" : "Alle anzeigen"}</button>
          <button className="btn btn-sm btn-primary" disabled={busy} onClick={jetztVerarbeiten}>Jetzt verarbeiten</button>
        </div>
      </div>

      {status && (
        <div className="row" style={{ gap: 10, flexWrap: "wrap", marginBottom: 16 }}>
          <Kennzahl label="Offen" wert={status.offen} farbe="var(--warn, #b45309)" />
          <Kennzahl label="Fehlgeschlagen" wert={status.fehlgeschlagen} farbe="var(--danger, #b3261e)" />
          <Kennzahl label="Erfolgreich" wert={status.erfolgreich} farbe="var(--ok, #2563eb)" />
          <Kennzahl label="Abgebrochen" wert={status.abgebrochen} farbe="var(--muted, #566664)" />
        </div>
      )}

      {offenFehler === 0 && !alle && (
        <p className="note" style={{ marginBottom: 12 }}>Alle Druckaufträge sind erledigt. Offene Aufträge werden automatisch erneut versucht.</p>
      )}
      {fehler && <p className="login-error" style={{ marginBottom: 12 }}>{fehler}</p>}

      <table className="tabelle">
        <thead><tr><th>Auftrag</th><th>Status</th><th className="num">Versuche</th><th>Aktualisiert</th><th className="num">Aktionen</th></tr></thead>
        <tbody>
          {jobs.map((j) => {
            const stil = STATUS_STIL[j.status] ?? { text: j.status, farbe: "var(--ink)" };
            const erledigt = j.status === "erfolgreich" || j.status === "abgebrochen";
            return (
              <tr key={j.id}>
                <td>
                  <strong>{j.dokumenttyp}{j.nachdruck ? " (Kopie)" : ""}</strong>
                  {j.bezeichnung && <span style={{ marginLeft: 8 }}>· {j.bezeichnung}</span>}
                  {j.verkauf_id && <span style={{ color: "var(--muted)", marginLeft: 8 }}>zu Verkauf #{j.verkauf_id}</span>}
                  {j.letzte_fehlermeldung && <div style={{ color: "var(--danger, #b3261e)", fontSize: 12, marginTop: 2 }}>{j.letzte_fehlermeldung}</div>}
                </td>
                <td><span style={{ color: stil.farbe, fontWeight: 600 }}>{stil.text}</span></td>
                <td className="num">{j.versuche}/{j.max_versuche}</td>
                <td>{zeit(j.aktualisiert_am)}</td>
                <td className="num">
                  {!erledigt && <button className="btn btn-sm" onClick={() => wiederholen(j.id)}>Wiederholen</button>}
                  {!erledigt && canAdmin && <button className="btn btn-sm btn-danger" onClick={() => abbrechen(j.id)}>Abbrechen</button>}
                  {erledigt && <span style={{ color: "var(--muted)" }}>–</span>}
                </td>
              </tr>
            );
          })}
          {jobs.length === 0 && <tr><td colSpan={5} style={{ color: "var(--muted)" }}>Keine Druckaufträge.</td></tr>}
        </tbody>
      </table>
      <p style={{ color: "var(--muted)", fontSize: 13, marginTop: 12 }}>
        Ein Verkauf wird immer gebucht, auch wenn der Druck scheitert. Der Bon bleibt hier in der Warteschlange
        und wird automatisch wiederholt; „Wiederholen“ erzwingt einen weiteren Versuch von Hand.
      </p>
    </section>
  );
}

function Kennzahl({ label, wert, farbe }: { label: string; wert: number; farbe: string }) {
  return (
    <div className="card" style={{ padding: "10px 16px", minWidth: 120 }}>
      <div className="eyebrow">{label}</div>
      <div style={{ fontSize: 26, fontWeight: 700, color: wert > 0 ? farbe : "var(--ink)" }}>{wert}</div>
    </div>
  );
}
