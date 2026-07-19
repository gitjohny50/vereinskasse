import { useEffect, useState } from "react";
import { api, ApiError, type Kassenprofil, type Verein } from "../api";

type EditVerein = { id: number; name: string; anschrift: string; kontakt: string };
type EditProfil = { id: number; name: string; verein_id: number; bonkopf: string; bonfuss: string; waehrung: string; pfand_aktiv: boolean };

export function Veranstaltungen({ onProfilesChanged }: { onProfilesChanged?: () => void }) {
  const [vereine, setVereine] = useState<Verein[]>([]);
  const [profile, setProfile] = useState<Kassenprofil[]>([]);
  const [fehler, setFehler] = useState<string | null>(null);
  const [vName, setVName] = useState("");
  const [pName, setPName] = useState("");
  const [pVerein, setPVerein] = useState<number | "">("");
  const [editVerein, setEditVerein] = useState<EditVerein | null>(null);
  const [editProfil, setEditProfil] = useState<EditProfil | null>(null);

  async function laden() {
    const [vs, ps] = await Promise.all([api.vereine(), api.profile()]);
    setVereine(vs); setProfile(ps);
    if (pVerein === "" && vs.length) setPVerein(vs[0].id);
  }
  useEffect(() => { laden().catch((e) => setFehler(e instanceof ApiError ? e.message : "Fehler beim Laden.")); }, []);

  function melde(e: unknown) { setFehler(e instanceof ApiError ? e.message : "Speichern fehlgeschlagen."); }

  async function vereinAnlegen() {
    if (!vName.trim()) { setFehler("Vereinsname fehlt."); return; }
    try { await api.vereinAnlegen({ name: vName.trim() }); setVName(""); setFehler(null); await laden(); } catch (e) { melde(e); }
  }
  async function vereinSpeichern() {
    if (!editVerein?.name.trim()) { setFehler("Vereinsname fehlt."); return; }
    try {
      await api.vereinAendern(editVerein.id, editVerein);
      setEditVerein(null); setFehler(null);
      await laden();
    } catch (e) { melde(e); }
  }
  async function profilAnlegen() {
    if (!pName.trim()) { setFehler("Profilname fehlt."); return; }
    if (pVerein === "") { setFehler("Verein wählen."); return; }
    try {
      await api.profilAnlegen({ name: pName.trim(), verein_id: pVerein, pfand_aktiv: true });
      setPName(""); setFehler(null);
      await laden();
      onProfilesChanged?.();
    } catch (e) { melde(e); }
  }
  async function profilSpeichern(next = editProfil) {
    if (!next?.name.trim()) { setFehler("Profilname fehlt."); return; }
    try {
      await api.profilAendern(next.id, next);
      setEditProfil(null); setFehler(null);
      await laden();
      onProfilesChanged?.();
    } catch (e) { melde(e); }
  }
  async function pfandUmschalten(p: Kassenprofil) {
    await profilSpeichern({
      id: p.id,
      name: p.name,
      verein_id: p.verein_id,
      bonkopf: p.bonkopf ?? "",
      bonfuss: p.bonfuss ?? "",
      waehrung: p.waehrung,
      pfand_aktiv: !p.pfand_aktiv,
    });
  }
  async function profilLoeschen(p: Kassenprofil) {
    if (!window.confirm(`Kassenprofil "${p.name}" ausblenden? Alte Belege bleiben erhalten, das Profil wird nur deaktiviert.`)) return;
    try {
      await api.profilLoeschen(p.id);
      setFehler(null);
      await laden();
      onProfilesChanged?.();
    } catch (e) { melde(e); }
  }

  const vereinName = (id: number) => vereine.find((v) => v.id === id)?.name ?? "–";

  return (
    <section>
      {fehler && <p className="login-error" style={{ marginBottom: 12 }}>{fehler}</p>}

      <div className="info-panel">
        <div>
          <div className="eyebrow">Struktur</div>
          <strong>Verein und Kassenprofile</strong>
        </div>
        <p>
          Für euren Betrieb reicht diese Ebene: Der Verein ist der feste Betreiber, ein Kassenprofil enthält Sortiment,
          Preise, Bontexte und die globale Pfand-Einstellung. Eine eigene Veranstaltungsebene würde aktuell nur Klicks
          erzeugen, ohne im Verkauf einen echten Vorteil zu bringen.
        </p>
      </div>

      <div className="event-summary">
        <div><span>Vereine</span><strong>{vereine.length}</strong></div>
        <div><span>Kassenprofile</span><strong>{profile.length}</strong></div>
        <div><span>Pfand aktiv</span><strong>{profile.filter((p) => p.pfand_aktiv).length}</strong></div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="section-title">Verein</div>
        <div className="row" style={{ gap: 10, marginTop: 10, flexWrap: "wrap" }}>
          <input value={vName} onChange={(e) => setVName(e.target.value)} placeholder="Vereinsname" style={{ flex: 1, minWidth: 220 }} />
          <button className="btn btn-primary" onClick={vereinAnlegen}>+ Verein</button>
        </div>
        <div className="profile-grid">
          {vereine.map((v) => (
            <div key={v.id} className="profile-tile">
              <strong>{v.name}</strong>
              {v.kontakt && <span>{v.kontakt}</span>}
              <button className="btn btn-sm" onClick={() => setEditVerein({ id: v.id, name: v.name, anschrift: v.anschrift, kontakt: v.kontakt })}>Verändern</button>
            </div>
          ))}
          {vereine.length === 0 && <span style={{ color: "var(--muted)" }}>Noch kein Verein angelegt.</span>}
        </div>
      </div>

      <div className="card">
        <div className="section-title">Kassenprofile</div>
        <div className="row" style={{ gap: 10, marginTop: 10, flexWrap: "wrap" }}>
          <input value={pName} onChange={(e) => setPName(e.target.value)} placeholder="Profilname (z. B. Hauptkasse)" style={{ flex: 1, minWidth: 220 }} />
          <select value={pVerein} onChange={(e) => setPVerein(e.target.value === "" ? "" : Number(e.target.value))}>
            <option value="">– Verein –</option>
            {vereine.map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}
          </select>
          <button className="btn btn-primary" onClick={profilAnlegen}>+ Profil</button>
        </div>

        <div className="profile-grid">
          {profile.map((p) => (
            <div key={p.id} className="profile-tile profile-tile-wide">
              <strong>{p.name}</strong>
              <span>{vereinName(p.verein_id)}</span>
              <div className="row" style={{ justifyContent: "space-between", marginTop: 6 }}>
                <span className="pill-mini">Pfand {p.pfand_aktiv ? "aktiv" : "inaktiv"}</span>
                <button className="toggle" onClick={() => pfandUmschalten(p)} aria-label="Pfand umschalten">
                  <span className={`toggle-track ${p.pfand_aktiv ? "on" : ""}`}><span className="toggle-knob" /></span>
                </button>
              </div>
              <div className="row" style={{ marginTop: 8 }}>
                <button className="btn btn-sm" onClick={() => setEditProfil({
                  id: p.id, name: p.name, verein_id: p.verein_id, bonkopf: p.bonkopf ?? "", bonfuss: p.bonfuss ?? "",
                  waehrung: p.waehrung, pfand_aktiv: p.pfand_aktiv,
                })}>Verändern</button>
                <button className="btn btn-sm btn-danger" onClick={() => profilLoeschen(p)}>Löschen</button>
              </div>
            </div>
          ))}
          {profile.length === 0 && <span style={{ color: "var(--muted)" }}>Noch kein Kassenprofil angelegt.</span>}
        </div>
      </div>

      {editVerein && (
        <div className="modal-backdrop">
          <div className="modal-card">
            <div className="section-title">Verein verändern</div>
            <div className="feld-grid">
              <label>Name<input value={editVerein.name} onChange={(e) => setEditVerein({ ...editVerein, name: e.target.value })} /></label>
              <label>Kontakt<input value={editVerein.kontakt} onChange={(e) => setEditVerein({ ...editVerein, kontakt: e.target.value })} /></label>
              <label>Anschrift<textarea value={editVerein.anschrift} onChange={(e) => setEditVerein({ ...editVerein, anschrift: e.target.value })} /></label>
            </div>
            <div className="row" style={{ marginTop: 14 }}>
              <button className="btn btn-primary" onClick={vereinSpeichern}>Speichern</button>
              <button className="btn" onClick={() => setEditVerein(null)}>Abbrechen</button>
            </div>
          </div>
        </div>
      )}

      {editProfil && (
        <div className="modal-backdrop">
          <div className="modal-card">
            <div className="section-title">Kassenprofil verändern</div>
            <div className="feld-grid">
              <label>Name<input value={editProfil.name} onChange={(e) => setEditProfil({ ...editProfil, name: e.target.value })} /></label>
              <label>Verein
                <select value={editProfil.verein_id} onChange={(e) => setEditProfil({ ...editProfil, verein_id: Number(e.target.value) })}>
                  {vereine.map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}
                </select>
              </label>
              <label>Währung<input value={editProfil.waehrung} onChange={(e) => setEditProfil({ ...editProfil, waehrung: e.target.value })} /></label>
              <label className="row" style={{ gap: 8, alignItems: "center" }}>
                <input type="checkbox" checked={editProfil.pfand_aktiv} onChange={(e) => setEditProfil({ ...editProfil, pfand_aktiv: e.target.checked })} />
                Pfand im Verkauf aktiv
              </label>
              <label>Bonkopf<textarea value={editProfil.bonkopf} onChange={(e) => setEditProfil({ ...editProfil, bonkopf: e.target.value })} /></label>
              <label>Bonfuß<textarea value={editProfil.bonfuss} onChange={(e) => setEditProfil({ ...editProfil, bonfuss: e.target.value })} /></label>
            </div>
            <div className="row" style={{ marginTop: 14 }}>
              <button className="btn btn-primary" onClick={() => profilSpeichern()}>Speichern</button>
              <button className="btn" onClick={() => setEditProfil(null)}>Abbrechen</button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
