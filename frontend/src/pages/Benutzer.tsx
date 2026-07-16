import { useEffect, useState } from "react";
import { api, ApiError, type Benutzer as B, type Rolle } from "../api";

export function Benutzer() {
  const [liste, setListe] = useState<B[]>([]);
  const [rollen, setRollen] = useState<Rolle[]>([]);
  const [fehler, setFehler] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [pin, setPin] = useState("");
  const [rolleId, setRolleId] = useState<number | "">("");
  const [pinReset, setPinReset] = useState<{ id: number; pin: string } | null>(null);

  async function laden() {
    const [bs, rs] = await Promise.all([api.benutzer(), api.rollen()]);
    setListe(bs); setRollen(rs);
    if (rolleId === "" && rs.length) setRolleId(rs[0].id);
  }
  useEffect(() => {
    laden().catch((e) => setFehler(e instanceof ApiError ? e.message : "Fehler beim Laden."));
  }, []);

  async function anlegen() {
    if (!name.trim()) { setFehler("Name fehlt."); return; }
    if (!/^\d{4,}$/.test(pin)) { setFehler("PIN muss mindestens 4 Ziffern haben."); return; }
    if (rolleId === "") { setFehler("Rolle wählen."); return; }
    try {
      await api.benutzerAnlegen({ name: name.trim(), pin, rolle_id: rolleId });
      setName(""); setPin(""); setFehler(null);
      await laden();
    } catch (e) { setFehler(e instanceof ApiError ? e.message : "Speichern fehlgeschlagen."); }
  }

  async function rolleAendern(b: B, neu: number) { await api.benutzerAendern(b.id, { rolle_id: neu }); await laden(); }
  async function aktivUmschalten(b: B) { await api.benutzerAendern(b.id, { aktiv: !b.aktiv }); await laden(); }
  async function pinSpeichern() {
    if (!pinReset) return;
    if (!/^\d{4,}$/.test(pinReset.pin)) { setFehler("Neue PIN muss mindestens 4 Ziffern haben."); return; }
    try {
      await api.benutzerAendern(pinReset.id, { pin: pinReset.pin });
      setPinReset(null); setFehler(null);
      await laden();
    } catch (e) { setFehler(e instanceof ApiError ? e.message : "PIN-Änderung fehlgeschlagen."); }
  }

  return (
    <section>
      <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-end", marginBottom: 16 }}>
        <div><div className="eyebrow">Verwaltung</div><strong style={{ fontSize: 17 }}>Benutzer</strong></div>
      </div>

      <div className="formular" style={{ marginBottom: 16 }}>
        <div className="feld-grid">
          <label>Name<input value={name} onChange={(e) => setName(e.target.value)} placeholder="z. B. Anna" /></label>
          <label>PIN<input value={pin} onChange={(e) => setPin(e.target.value.replace(/\D/g, ""))} placeholder="4–20 Ziffern" inputMode="numeric" type="password" /></label>
          <label>Rolle
            <select value={rolleId} onChange={(e) => setRolleId(e.target.value === "" ? "" : Number(e.target.value))}>
              {rollen.map((r) => <option key={r.id} value={r.id}>{beschriftung(r)}</option>)}
            </select>
          </label>
        </div>
        {fehler && <p className="login-error" style={{ marginTop: 10 }}>{fehler}</p>}
        <div className="row" style={{ marginTop: 12 }}><button className="btn btn-primary" onClick={anlegen}>+ Benutzer anlegen</button></div>
      </div>

      <table className="tabelle">
        <thead><tr><th>Name</th><th>Rolle</th><th>Aktiv</th><th className="num">Aktionen</th></tr></thead>
        <tbody>
          {liste.map((b) => (
            <tr key={b.id} style={{ opacity: b.aktiv ? 1 : 0.55 }}>
              <td><strong>{b.name}</strong></td>
              <td>
                <select value={b.rolle_id} onChange={(e) => rolleAendern(b, Number(e.target.value))}>
                  {rollen.map((r) => <option key={r.id} value={r.id}>{beschriftung(r)}</option>)}
                </select>
              </td>
              <td>
                <button className="toggle" role="switch" aria-checked={b.aktiv} onClick={() => aktivUmschalten(b)}>
                  <span className={`toggle-track ${b.aktiv ? "on" : ""}`}><span className="toggle-knob" /></span>
                </button>
              </td>
              <td className="num">
                {pinReset?.id === b.id ? (
                  <span className="row" style={{ gap: 8, justifyContent: "flex-end" }}>
                    <input value={pinReset.pin} onChange={(e) => setPinReset({ id: b.id, pin: e.target.value.replace(/\D/g, "") })}
                      placeholder="neue PIN" inputMode="numeric" type="password" style={{ width: 120 }} autoFocus />
                    <button className="btn btn-sm btn-primary" onClick={pinSpeichern}>OK</button>
                    <button className="btn btn-sm" onClick={() => setPinReset(null)}>Abbrechen</button>
                  </span>
                ) : (
                  <button className="btn btn-sm" onClick={() => { setFehler(null); setPinReset({ id: b.id, pin: "" }); }}>PIN zurücksetzen</button>
                )}
              </td>
            </tr>
          ))}
          {liste.length === 0 && <tr><td colSpan={4} style={{ color: "var(--muted)" }}>Noch keine Benutzer.</td></tr>}
        </tbody>
      </table>
      <p style={{ color: "var(--muted)", fontSize: 13, marginTop: 12 }}>
        PIN-Zurücksetzen hebt zugleich eine Sperre nach zu vielen Fehlversuchen auf.
      </p>
    </section>
  );
}

function beschriftung(r: Rolle): string {
  const namen: Record<string, string> = { bediener: "Bediener", administrator: "Administrator", servicetechniker: "Servicetechniker" };
  return namen[r.name] ?? r.name;
}
