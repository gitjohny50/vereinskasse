import { useEffect, useState, useCallback } from "react";
import { api, ApiError, euroToCents, formatCents, type Kassenprofil, type Pfandart } from "../api";

export function Pfandarten({ profil }: { profil: Kassenprofil }) {
  const [liste, setListe] = useState<Pfandart[]>([]);
  const [fehler, setFehler] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [kurzname, setKurzname] = useState("");
  const [betrag, setBetrag] = useState("");
  const [rueckgabe, setRueckgabe] = useState(true);
  const [ticket, setTicket] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);

  const laden = useCallback(async () => { 
    setListe(await api.pfandarten(profil.id)); 
  }, [profil.id]);

  useEffect(() => {
    setFehler(null);
    laden().catch((e) => setFehler(e instanceof ApiError ? e.message : "Fehler beim Laden."));
  }, [laden]);

  function body(p: Pfandart) {
    return {
      kassenprofil_id: profil.id, name: p.name, kurzname: p.kurzname, betrag_cent: p.betrag_cent,
      farbe: p.farbe, symbol: p.symbol, rueckgabe_erlaubt: p.rueckgabe_erlaubt,
      artikelticket_drucken: p.artikelticket_drucken, steuersatz: p.steuersatz, sortierung: p.sortierung,
      max_rueckgabe_menge: p.max_rueckgabe_menge, aktiv: p.aktiv,
    };
  }

  async function anlegen() {
    const cents = euroToCents(betrag);
    if (!name.trim()) { setFehler("Name fehlt."); return; }
    if (cents === null) { setFehler("Betrag ungültig (z. B. 1,00)."); return; }
    try {
      await api.pfandartAnlegen({
        kassenprofil_id: profil.id, name: name.trim(), kurzname: kurzname.trim(),
        betrag_cent: cents, rueckgabe_erlaubt: rueckgabe, artikelticket_drucken: ticket,
      });
      setName(""); setKurzname(""); setBetrag(""); setRueckgabe(true); setTicket(false); setFehler(null);
      await laden();
    } catch (e) { setFehler(e instanceof ApiError ? e.message : "Speichern fehlgeschlagen."); }
  }

  async function speichern(p: Pfandart) { await api.pfandartAendern(p.id, body(p)); setEditId(null); await laden(); }
  async function aktivUmschalten(p: Pfandart) { await api.pfandartAendern(p.id, { ...body(p), aktiv: !p.aktiv }); await laden(); }
  function feld(id: number, patch: Partial<Pfandart>) {
    setListe((xs) => xs.map((x) => (x.id === id ? { ...x, ...patch } : x)));
  }

  return (
    <section>
      <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-end", marginBottom: 16 }}>
        <div><div className="eyebrow">Katalog</div><strong style={{ fontSize: 17 }}>Pfandarten</strong></div>
      </div>

      <div className="formular" style={{ marginBottom: 16 }}>
        <div className="feld-grid">
          <label>Name<input value={name} onChange={(e) => setName(e.target.value)} placeholder="z. B. Flaschenpfand" /></label>
          <label>Kurzname<input value={kurzname} onChange={(e) => setKurzname(e.target.value)} placeholder="Flasche" /></label>
          <label>Betrag (€)<input value={betrag} onChange={(e) => setBetrag(e.target.value)} placeholder="1,00" inputMode="decimal" /></label>
        </div>
        <div className="row" style={{ gap: 16, marginTop: 12, flexWrap: "wrap" }}>
          <label className="row" style={{ gap: 8 }}><input type="checkbox" checked={rueckgabe} onChange={(e) => setRueckgabe(e.target.checked)} />Rückgabe erlaubt</label>
          <label className="row" style={{ gap: 8 }}><input type="checkbox" checked={ticket} onChange={(e) => setTicket(e.target.checked)} />Artikelticket drucken</label>
        </div>
        {fehler && <p className="login-error" style={{ marginTop: 10 }}>{fehler}</p>}
        <div className="row" style={{ marginTop: 12 }}><button className="btn btn-primary" onClick={anlegen}>+ Pfandart anlegen</button></div>
      </div>

      <table className="tabelle">
        <thead><tr><th>Pfandart</th><th className="num">Betrag</th><th>Rückgabe</th><th>Ticket</th><th>Aktiv</th><th className="num">Aktionen</th></tr></thead>
        <tbody>
          {liste.map((p) => (
            <tr key={p.id} style={{ opacity: p.aktiv ? 1 : 0.55 }}>
              <td><strong>{p.name}</strong>{p.kurzname && <span style={{ color: "var(--muted)", marginLeft: 8 }}>{p.kurzname}</span>}</td>
              <td className="num">
                {editId === p.id
                  ? <input value={(p.betrag_cent / 100).toFixed(2).replace(".", ",")} onChange={(e) => feld(p.id, { betrag_cent: euroToCents(e.target.value) ?? p.betrag_cent })} style={{ width: 90 }} />
                  : formatCents(p.betrag_cent)}
              </td>
              <td>{p.rueckgabe_erlaubt ? "ja" : "nein"}</td>
              <td>{p.artikelticket_drucken ? "ja" : "nein"}</td>
              <td>
                <button className="toggle" role="switch" aria-checked={p.aktiv} onClick={() => aktivUmschalten(p)}>
                  <span className={`toggle-track ${p.aktiv ? "on" : ""}`}><span className="toggle-knob" /></span>
                </button>
              </td>
              <td className="num">
                {editId === p.id
                  ? <button className="btn btn-sm btn-primary" onClick={() => speichern(p)}>Speichern</button>
                  : <button className="btn btn-sm" onClick={() => setEditId(p.id)}>Bearbeiten</button>}
              </td>
            </tr>
          ))}
          {liste.length === 0 && <tr><td colSpan={6} style={{ color: "var(--muted)" }}>Noch keine Pfandarten.</td></tr>}
        </tbody>
      </table>
    </section>
  );
}