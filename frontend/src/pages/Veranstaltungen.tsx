import { useEffect, useState } from "react";
import { api, ApiError, type Kassenprofil, type Veranstaltung, type Verein } from "../api";

const STATUS = ["geplant", "aktiv", "abgeschlossen", "archiviert"];

export function Veranstaltungen({ onProfilesChanged }: { onProfilesChanged?: () => void }) {
  const [vereine, setVereine] = useState<Verein[]>([]);
  const [profile, setProfile] = useState<Kassenprofil[]>([]);
  const [events, setEvents] = useState<Veranstaltung[]>([]);
  const [fehler, setFehler] = useState<string | null>(null);

  // Formularzustände
  const [vName, setVName] = useState("");
  const [pName, setPName] = useState("");
  const [pVerein, setPVerein] = useState<number | "">("");
  const [eName, setEName] = useState("");
  const [eProfil, setEProfil] = useState<number | "">("");
  const [eOrt, setEOrt] = useState("");
  const [ePfand, setEPfand] = useState(true);

  async function laden() {
    const [vs, ps, es] = await Promise.all([api.vereine(), api.profile(), api.veranstaltungen()]);
    setVereine(vs); setProfile(ps); setEvents(es);
    if (pVerein === "" && vs.length) setPVerein(vs[0].id);
    if (eProfil === "" && ps.length) setEProfil(ps[0].id);
  }
  useEffect(() => { laden().catch((e) => setFehler(e instanceof ApiError ? e.message : "Fehler beim Laden.")); }, []);

  function melde(e: unknown) { setFehler(e instanceof ApiError ? e.message : "Speichern fehlgeschlagen."); }

  async function vereinAnlegen() {
    if (!vName.trim()) { setFehler("Vereinsname fehlt."); return; }
    try { await api.vereinAnlegen({ name: vName.trim() }); setVName(""); setFehler(null); await laden(); } catch (e) { melde(e); }
  }
  async function profilAnlegen() {
    if (!pName.trim()) { setFehler("Profilname fehlt."); return; }
    if (pVerein === "") { setFehler("Verein wählen."); return; }
    try {
      await api.profilAnlegen({ name: pName.trim(), verein_id: pVerein });
      setPName(""); setFehler(null);
      await laden();
      onProfilesChanged?.();
    } catch (e) { melde(e); }
  }
  async function eventAnlegen() {
    if (!eName.trim()) { setFehler("Veranstaltungsname fehlt."); return; }
    if (eProfil === "") { setFehler("Kassenprofil wählen."); return; }
    try {
      await api.veranstaltungAnlegen({ kassenprofil_id: eProfil, name: eName.trim(), ort: eOrt.trim(), pfand_aktiv: ePfand });
      setEName(""); setEOrt(""); setFehler(null);
      await laden();
    } catch (e) { melde(e); }
  }
  async function statusAendern(ev: Veranstaltung, status: string) {
    try { await api.veranstaltungStatus(ev.id, status); await laden(); } catch (e) { melde(e); }
  }

  const profilName = (id: number) => profile.find((p) => p.id === id)?.name ?? "–";

  return (
    <section>
      {fehler && <p className="login-error" style={{ marginBottom: 12 }}>{fehler}</p>}

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="section-title">Vereine</div>
        <div className="row" style={{ gap: 10, marginTop: 10, flexWrap: "wrap" }}>
          <input value={vName} onChange={(e) => setVName(e.target.value)} placeholder="Vereinsname" style={{ flex: 1, minWidth: 200 }} />
          <button className="btn btn-primary" onClick={vereinAnlegen}>+ Verein</button>
        </div>
        <div className="row" style={{ gap: 8, marginTop: 12, flexWrap: "wrap" }}>
          {vereine.map((v) => <span key={v.id} className="pill">{v.name}</span>)}
          {vereine.length === 0 && <span style={{ color: "var(--muted)" }}>Noch keine Vereine.</span>}
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="section-title">Kassenprofile</div>
        <div className="row" style={{ gap: 10, marginTop: 10, flexWrap: "wrap" }}>
          <input value={pName} onChange={(e) => setPName(e.target.value)} placeholder="Profilname (z. B. Vereinsfest)" style={{ flex: 1, minWidth: 200 }} />
          <select value={pVerein} onChange={(e) => setPVerein(e.target.value === "" ? "" : Number(e.target.value))}>
            <option value="">– Verein –</option>
            {vereine.map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}
          </select>
          <button className="btn btn-primary" onClick={profilAnlegen}>+ Profil</button>
        </div>
        <div className="row" style={{ gap: 8, marginTop: 12, flexWrap: "wrap" }}>
          {profile.map((p) => <span key={p.id} className="pill">{p.name}</span>)}
          {profile.length === 0 && <span style={{ color: "var(--muted)" }}>Noch keine Profile.</span>}
        </div>
      </div>

      <div className="card">
        <div className="section-title">Veranstaltungen</div>
        <div className="feld-grid" style={{ marginTop: 10 }}>
          <label>Name<input value={eName} onChange={(e) => setEName(e.target.value)} placeholder="z. B. Sommerfest Tag 1" /></label>
          <label>Kassenprofil
            <select value={eProfil} onChange={(e) => setEProfil(e.target.value === "" ? "" : Number(e.target.value))}>
              <option value="">– Profil –</option>
              {profile.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </label>
          <label>Ort<input value={eOrt} onChange={(e) => setEOrt(e.target.value)} placeholder="Festplatz" /></label>
        </div>
        <div className="row" style={{ gap: 16, marginTop: 12 }}>
          <label className="row" style={{ gap: 8 }}><input type="checkbox" checked={ePfand} onChange={(e) => setEPfand(e.target.checked)} />Pfand aktiv</label>
          <button className="btn btn-primary" onClick={eventAnlegen}>+ Veranstaltung anlegen</button>
        </div>

        <table className="tabelle" style={{ marginTop: 16 }}>
          <thead><tr><th>Veranstaltung</th><th>Profil</th><th>Ort</th><th>Pfand</th><th>Status</th></tr></thead>
          <tbody>
            {events.map((ev) => (
              <tr key={ev.id}>
                <td><strong>{ev.name}</strong></td>
                <td>{profilName(ev.kassenprofil_id)}</td>
                <td>{ev.ort || "–"}</td>
                <td>{ev.pfand_aktiv ? "ja" : "nein"}</td>
                <td>
                  <select value={ev.status} onChange={(e) => statusAendern(ev, e.target.value)}>
                    {STATUS.map((s) => <option key={s} value={s}>{s}</option>)}
                  </select>
                </td>
              </tr>
            ))}
            {events.length === 0 && <tr><td colSpan={5} style={{ color: "var(--muted)" }}>Noch keine Veranstaltungen.</td></tr>}
          </tbody>
        </table>
      </div>
    </section>
  );
}
