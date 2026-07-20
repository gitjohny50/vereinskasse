import { useEffect, useState, useCallback } from "react";
import { api, ApiError, type Kassenprofil, type Zahlungsmethode } from "../api";

export function Zahlungsmethoden({ profil }: { profil: Kassenprofil }) {
  const [liste, setListe] = useState<Zahlungsmethode[]>([]);
  const [fehler, setFehler] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [kurzname, setKurzname] = useState("");
  const [schublade, setSchublade] = useState(true);
  const [rueckgeld, setRueckgeld] = useState(true);
  const [negativ, setNegativ] = useState(false);

  const laden = useCallback(async () => { 
    setListe(await api.zahlungsmethoden(profil.id)); 
  }, [profil.id]);

  useEffect(() => {
    setFehler(null);
    laden().catch((e) => setFehler(e instanceof ApiError ? e.message : "Fehler beim Laden."));
  }, [laden]);

  function body(z: Zahlungsmethode) {
    return {
      kassenprofil_id: profil.id, name: z.name, kurzname: z.kurzname, farbe: z.farbe, symbol: z.symbol,
      sortierung: z.sortierung, schublade_oeffnen: z.schublade_oeffnen, rueckgeld_berechnen: z.rueckgeld_berechnen,
      negativ_erlaubt: z.negativ_erlaubt, aktiv: z.aktiv,
    };
  }

  async function anlegen() {
    if (!name.trim()) { setFehler("Name fehlt."); return; }
    try {
      await api.zahlungsmethodeAnlegen({
        kassenprofil_id: profil.id, name: name.trim(), kurzname: kurzname.trim(),
        schublade_oeffnen: schublade, rueckgeld_berechnen: rueckgeld, negativ_erlaubt: negativ,
      });
      setName(""); setKurzname(""); setSchublade(true); setRueckgeld(true); setNegativ(false); setFehler(null);
      await laden();
    } catch (e) { setFehler(e instanceof ApiError ? e.message : "Speichern fehlgeschlagen."); }
  }

  async function umschalten(z: Zahlungsmethode, feld: "schublade_oeffnen" | "rueckgeld_berechnen" | "negativ_erlaubt" | "aktiv") {
    await api.zahlungsmethodeAendern(z.id, { ...body(z), [feld]: !z[feld] });
    await laden();
  }

  return (
    <section>
      <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-end", marginBottom: 16 }}>
        <div><div className="eyebrow">Katalog</div><strong style={{ fontSize: 17 }}>Zahlungsmethoden</strong></div>
      </div>

      <div className="formular" style={{ marginBottom: 16 }}>
        <div className="feld-grid">
          <label>Name<input value={name} onChange={(e) => setName(e.target.value)} placeholder="z. B. Bar" /></label>
          <label>Kurzname<input value={kurzname} onChange={(e) => setKurzname(e.target.value)} placeholder="Bar" /></label>
        </div>
        <div className="row" style={{ gap: 16, marginTop: 12, flexWrap: "wrap" }}>
          <label className="row" style={{ gap: 8 }}><input type="checkbox" checked={schublade} onChange={(e) => setSchublade(e.target.checked)} />Schublade öffnen</label>
          <label className="row" style={{ gap: 8 }}><input type="checkbox" checked={rueckgeld} onChange={(e) => setRueckgeld(e.target.checked)} />Rückgeld berechnen</label>
          <label className="row" style={{ gap: 8 }}><input type="checkbox" checked={negativ} onChange={(e) => setNegativ(e.target.checked)} />Negativbeträge erlaubt</label>
        </div>
        {fehler && <p className="login-error" style={{ marginTop: 10 }}>{fehler}</p>}
        <div className="row" style={{ marginTop: 12 }}><button className="btn btn-primary" onClick={anlegen}>+ Zahlungsmethode anlegen</button></div>
      </div>

      <table className="tabelle">
        <thead><tr><th>Methode</th><th>Schublade</th><th>Rückgeld</th><th>Negativ</th><th>Aktiv</th></tr></thead>
        <tbody>
          {liste.map((z) => (
            <tr key={z.id} style={{ opacity: z.aktiv ? 1 : 0.55 }}>
              <td><strong>{z.name}</strong>{z.kurzname && <span style={{ color: "var(--muted)", marginLeft: 8 }}>{z.kurzname}</span>}</td>
              <td><MiniToggle on={z.schublade_oeffnen} onClick={() => umschalten(z, "schublade_oeffnen")} /></td>
              <td><MiniToggle on={z.rueckgeld_berechnen} onClick={() => umschalten(z, "rueckgeld_berechnen")} /></td>
              <td><MiniToggle on={z.negativ_erlaubt} onClick={() => umschalten(z, "negativ_erlaubt")} /></td>
              <td><MiniToggle on={z.aktiv} onClick={() => umschalten(z, "aktiv")} /></td>
            </tr>
          ))}
          {liste.length === 0 && <tr><td colSpan={5} style={{ color: "var(--muted)" }}>Noch keine Zahlungsmethoden.</td></tr>}
        </tbody>
      </table>
      <p style={{ color: "var(--muted)", fontSize: 13, marginTop: 12 }}>Schalter direkt umlegen zum Ändern.</p>
    </section>
  );
}

function MiniToggle({ on, onClick }: { on: boolean; onClick: () => void }) {
  return (
    <button className="toggle" role="switch" aria-checked={on} onClick={onClick}>
      <span className={`toggle-track ${on ? "on" : ""}`}><span className="toggle-knob" /></span>
    </button>
  );
}