import { useEffect, useState, useCallback } from "react";
import { api, ApiError, type Kassenprofil, type Kategorie } from "../api";

export function Kategorien({ profil }: { profil: Kassenprofil }) {
  const [liste, setListe] = useState<Kategorie[]>([]);
  const [fehler, setFehler] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [farbe, setFarbe] = useState("#6366f1");
  const [reihenfolge, setReihenfolge] = useState(0);
  const [editId, setEditId] = useState<number | null>(null);

  const laden = useCallback(async () => {
    setListe(await api.kategorien(profil.id));
  }, [profil.id]);

  useEffect(() => {
    setFehler(null);
    laden().catch((e) => setFehler(e instanceof ApiError ? e.message : "Fehler beim Laden."));
  }, [laden]);

  async function anlegen() {
    if (!name.trim()) { setFehler("Name fehlt."); return; }
    try {
      await api.kategorieAnlegen({ kassenprofil_id: profil.id, name: name.trim(), farbe, sortierung: reihenfolge });
      setName(""); setReihenfolge(0); setFehler(null);
      await laden();
    } catch (e) { setFehler(e instanceof ApiError ? e.message : "Speichern fehlgeschlagen."); }
  }

  async function speichern(k: Kategorie) {
    try {
      await api.kategorieAendern(k.id, {
        kassenprofil_id: profil.id, name: k.name, farbe: k.farbe, symbol: k.symbol, sortierung: k.sortierung, aktiv: k.aktiv,
      });
      setEditId(null);
      setFehler(null);
      await laden();
    } catch (e) { setFehler(e instanceof ApiError ? e.message : "Speichern fehlgeschlagen."); }
  }

  async function aktivUmschalten(k: Kategorie) {
    try {
      await api.kategorieAendern(k.id, {
        kassenprofil_id: profil.id, name: k.name, farbe: k.farbe, symbol: k.symbol, sortierung: k.sortierung, aktiv: !k.aktiv,
      });
      setFehler(null);
      await laden();
    } catch (e) { setFehler(e instanceof ApiError ? e.message : "Speichern fehlgeschlagen."); }
  }

  async function loeschen(k: Kategorie) {
    if (!window.confirm(`Kategorie "${k.name}" löschen? Das geht nur nach einem Z-Abschluss. Zugeordnete Artikel bleiben erhalten und sind danach ohne Kategorie.`)) return;
    try {
      await api.kategorieLoeschen(k.id);
      setFehler(null);
      await laden();
    } catch (e) { setFehler(e instanceof ApiError ? e.message : "Löschen fehlgeschlagen."); }
  }

  function feld(id: number, patch: Partial<Kategorie>) {
    setListe((xs) => xs.map((x) => (x.id === id ? { ...x, ...patch } : x)));
  }

  return (
    <section>
      <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-end", marginBottom: 16 }}>
        <div><div className="eyebrow">Katalog</div><strong style={{ fontSize: 17 }}>Kategorien</strong></div>
      </div>

      <div className="formular" style={{ marginBottom: 16 }}>
        <div className="feld-grid">
          <label>Name<input value={name} onChange={(e) => setName(e.target.value)} placeholder="z. B. Getränke" /></label>
          <label>Farbe<input type="color" value={farbe} onChange={(e) => setFarbe(e.target.value)} style={{ height: 44, padding: 4 }} /></label>
          <label>Reihenfolge<input type="number" value={reihenfolge} onChange={(e) => setReihenfolge(Number(e.target.value))} /></label>
        </div>
        {fehler && <p className="login-error" style={{ marginTop: 10 }}>{fehler}</p>}
        <div className="row" style={{ marginTop: 12 }}><button className="btn btn-primary" onClick={anlegen}>+ Kategorie anlegen</button></div>
      </div>

      <table className="tabelle">
        <thead><tr><th>Kategorie</th><th>Farbe</th><th className="num">Reihenfolge</th><th>Aktiv</th><th className="num">Aktionen</th></tr></thead>
        <tbody>
          {liste.map((k) => (
            <tr key={k.id} style={{ opacity: k.aktiv ? 1 : 0.55 }}>
              <td>
                <span className="dot" style={{ background: k.farbe || "var(--border)", marginRight: 8 }} />
                {editId === k.id
                  ? <input value={k.name} onChange={(e) => feld(k.id, { name: e.target.value })} style={{ maxWidth: 200 }} />
                  : <strong>{k.name}</strong>}
              </td>
              <td>
                {editId === k.id
                  ? <input type="color" value={k.farbe || "#6366f1"} onChange={(e) => feld(k.id, { farbe: e.target.value })} style={{ height: 38, width: 64, padding: 3 }} />
                  : <span className="mono">{k.farbe || "–"}</span>}
              </td>
              <td className="num">
                {editId === k.id
                  ? <input type="number" value={k.sortierung} onChange={(e) => feld(k.id, { sortierung: Number(e.target.value) })} style={{ width: 70 }} />
                  : k.sortierung}
              </td>
              <td>
                <button className="toggle" role="switch" aria-checked={k.aktiv} onClick={() => aktivUmschalten(k)}>
                  <span className={`toggle-track ${k.aktiv ? "on" : ""}`}><span className="toggle-knob" /></span>
                </button>
              </td>
              <td className="num">
                {editId === k.id
                  ? <button className="btn btn-sm btn-primary" onClick={() => speichern(k)}>Speichern</button>
                  : <>
                      <button className="btn btn-sm" onClick={() => setEditId(k.id)}>Bearbeiten</button>
                      <button className="btn btn-sm btn-danger" onClick={() => loeschen(k)}>Löschen</button>
                    </>}
              </td>
            </tr>
          ))}
          {liste.length === 0 && <tr><td colSpan={5} style={{ color: "var(--muted)" }}>Noch keine Kategorien.</td></tr>}
        </tbody>
      </table>
    </section>
  );
}