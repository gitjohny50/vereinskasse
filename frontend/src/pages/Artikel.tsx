import { useEffect, useMemo, useState } from "react";
import {
  api, ApiError, euroToCents, formatCents,
  type Artikel as Art, type Kassenprofil, type Kategorie, type Pfandart,
} from "../api";

export function Artikel({ profil }: { profil: Kassenprofil }) {
  const [kategorien, setKategorien] = useState<Kategorie[]>([]);
  const [pfandarten, setPfandarten] = useState<Pfandart[]>([]);
  const [artikel, setArtikel] = useState<Art[]>([]);
  const [fehler, setFehler] = useState<string | null>(null);
  const [zeigeAnlegen, setZeigeAnlegen] = useState(false);

  const katName = useMemo(() => {
    const m = new Map<number, string>();
    kategorien.forEach((k) => m.set(k.id, k.name));
    return m;
  }, [kategorien]);
  async function ladeAlles(pid: number) {
    const [k, p, a] = await Promise.all([api.kategorien(pid), api.pfandarten(pid), api.artikel(pid)]);
    setKategorien(k);
    setPfandarten(p);
    setArtikel(a);
  }

  useEffect(() => {
    setFehler(null);
    ladeAlles(profil.id).catch((e) => setFehler(e instanceof ApiError ? e.message : "Fehler beim Laden."));
  }, [profil.id]);

  async function neuLaden() {
    await ladeAlles(profil.id);
  }

  async function preisAendern(a: Art, neuText: string) {
    const cents = euroToCents(neuText);
    if (cents === null || cents === a.preis_cent) return;
    await api.artikelAendern(a.id, { preis_cent: cents });
    await neuLaden();
  }

  async function aktivUmschalten(a: Art) {
    await api.artikelAendern(a.id, { aktiv: !a.aktiv });
    await neuLaden();
  }

  async function kopieren(a: Art) {
    await api.artikelKopieren(a.id);
    await neuLaden();
  }

  async function archivieren(a: Art) {
    await api.artikelArchivieren(a.id);
    await neuLaden();
  }

  if (fehler) return <p className="login-error">{fehler}</p>;

  return (
    <section>
      <div className="row" style={{ justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <div>
          <div className="eyebrow">Katalog</div>
          <strong style={{ fontSize: 17 }}>Artikel</strong>
        </div>
        <button className="btn btn-primary" onClick={() => setZeigeAnlegen((v) => !v)}>
          {zeigeAnlegen ? "Schließen" : "+ Artikel anlegen"}
        </button>
      </div>

      {zeigeAnlegen && (
        <AnlegenFormular
          profilId={profil.id}
          kategorien={kategorien}
          pfandarten={pfandarten}
          onFertig={async () => { setZeigeAnlegen(false); await neuLaden(); }}
        />
      )}

      <table className="tabelle">
        <thead>
          <tr>
            <th>Artikel</th><th>Kategorie</th><th className="num">Preis</th><th>Pfand</th><th>Aktiv</th><th className="num">Aktionen</th>
          </tr>
        </thead>
        <tbody>
          {artikel.map((a) => (
            <tr key={a.id} style={{ opacity: a.aktiv ? 1 : 0.55 }}>
              <td>
                <strong>{a.name}</strong>
                {a.kurzname && <span style={{ color: "var(--muted)", marginLeft: 8 }}>{a.kurzname}</span>}
              </td>
              <td>{a.kategorie_id ? katName.get(a.kategorie_id) ?? "–" : "–"}</td>
              <td className="num">
                <PreisFeld wert={a.preis_cent} onSpeichern={(t) => preisAendern(a, t)} />
              </td>
              <td>
                <PfandZelle
                  artikel={a}
                  pfandarten={pfandarten}
                  onSave={async (z) => { await api.artikelAendern(a.id, { pfandzuordnungen: z }); await neuLaden(); }}
                />
              </td>
              <td>
                <button className="toggle" role="switch" aria-checked={a.aktiv} onClick={() => aktivUmschalten(a)}>
                  <span className={`toggle-track ${a.aktiv ? "on" : ""}`}><span className="toggle-knob" /></span>
                </button>
              </td>
              <td className="num">
                <button className="btn btn-sm" onClick={() => kopieren(a)}>Kopieren</button>
                <button className="btn btn-sm btn-danger" onClick={() => archivieren(a)}>Archivieren</button>
              </td>
            </tr>
          ))}
          {artikel.length === 0 && (
            <tr><td colSpan={6} style={{ color: "var(--muted)" }}>Noch keine Artikel.</td></tr>
          )}
        </tbody>
      </table>
      <p style={{ color: "var(--muted)", fontSize: 13, marginTop: 12 }}>
        Preis anklicken zum Ändern. Archivierte Artikel bleiben erhalten (kein physisches Löschen).
      </p>
    </section>
  );
}

function PreisFeld({ wert, onSpeichern }: { wert: number; onSpeichern: (t: string) => void }) {
  const [editiere, setEditiere] = useState(false);
  const [text, setText] = useState("");
  if (!editiere) {
    return (
      <button className="preis-btn" onClick={() => { setText((wert / 100).toFixed(2).replace(".", ",")); setEditiere(true); }}>
        {formatCents(wert)}
      </button>
    );
  }
  return (
    <input
      className="preis-input"
      autoFocus
      value={text}
      onChange={(e) => setText(e.target.value)}
      onBlur={() => { onSpeichern(text); setEditiere(false); }}
      onKeyDown={(e) => { if (e.key === "Enter") { onSpeichern(text); setEditiere(false); } if (e.key === "Escape") setEditiere(false); }}
    />
  );
}

function AnlegenFormular({
  profilId, kategorien, pfandarten, onFertig,
}: {
  profilId: number; kategorien: Kategorie[]; pfandarten: Pfandart[]; onFertig: () => void;
}) {
  const [name, setName] = useState("");
  const [preis, setPreis] = useState("");
  const [kategorieId, setKategorieId] = useState<number | "">("");
  const [ticketModus, setTicketModus] = useState("pro_stueck");
  const [pfand, setPfand] = useState<Record<number, number>>({});
  const [fehler, setFehler] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function togglePfand(id: number) {
    setPfand((p) => {
      const n = { ...p };
      if (id in n) delete n[id];
      else n[id] = 1;
      return n;
    });
  }

  async function speichern() {
    const cents = euroToCents(preis);
    if (!name.trim()) { setFehler("Name fehlt."); return; }
    if (cents === null) { setFehler("Preis ungültig (z. B. 2,50)."); return; }
    setBusy(true);
    setFehler(null);
    try {
      await api.artikelAnlegen({
        kassenprofil_id: profilId,
        name: name.trim(),
        preis_cent: cents,
        kategorie_id: kategorieId === "" ? null : kategorieId,
        artikelticket_modus: ticketModus,
        pfandzuordnungen: Object.entries(pfand).map(([pid, menge]) => ({
          pfandart_id: Number(pid), menge_pro_einheit: menge, automatisch: true,
        })),
      });
      onFertig();
    } catch (e) {
      setFehler(e instanceof ApiError ? e.message : "Speichern fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="formular">
      <div className="feld-grid">
        <label>Name<input value={name} onChange={(e) => setName(e.target.value)} placeholder="z. B. Cola" /></label>
        <label>Preis (€)<input value={preis} onChange={(e) => setPreis(e.target.value)} placeholder="2,50" inputMode="decimal" /></label>
        <label>Kategorie
          <select value={kategorieId} onChange={(e) => setKategorieId(e.target.value === "" ? "" : Number(e.target.value))}>
            <option value="">– ohne –</option>
            {kategorien.map((k) => <option key={k.id} value={k.id}>{k.name}</option>)}
          </select>
        </label>
        <label>Artikelticket
          <select value={ticketModus} onChange={(e) => setTicketModus(e.target.value)}>
            <option value="pro_stueck">pro Stück</option>
            <option value="pro_position">pro Position</option>
            <option value="kein">kein Ticket</option>
          </select>
        </label>
      </div>
      {pfandarten.length > 0 && (
        <div style={{ marginTop: 12 }}>
          <div className="eyebrow" style={{ marginBottom: 8 }}>Pfand</div>
          <div className="row" style={{ flexWrap: "wrap", gap: 10 }}>
            {pfandarten.map((p) => (
              <label key={p.id} className={`pfand-chip ${p.id in pfand ? "on" : ""}`}>
                <input type="checkbox" checked={p.id in pfand} onChange={() => togglePfand(p.id)} style={{ display: "none" }} />
                {p.name} ({formatCents(p.betrag_cent)})
                {p.id in pfand && (
                  <input
                    type="number" min={1} value={pfand[p.id]}
                    onClick={(e) => e.preventDefault()}
                    onChange={(e) => setPfand((pf) => ({ ...pf, [p.id]: Math.max(1, Number(e.target.value)) }))}
                    className="pfand-menge"
                  />
                )}
              </label>
            ))}
          </div>
        </div>
      )}
      {fehler && <p className="login-error" style={{ marginTop: 12 }}>{fehler}</p>}
      <div className="row" style={{ marginTop: 16, gap: 10 }}>
        <button className="btn btn-primary" disabled={busy} onClick={speichern}>Speichern</button>
      </div>
    </div>
  );
}

function PfandZelle({
  artikel, pfandarten, onSave,
}: {
  artikel: Art;
  pfandarten: Pfandart[];
  onSave: (z: { pfandart_id: number; menge_pro_einheit: number; automatisch: boolean }[]) => Promise<void>;
}) {
  const [edit, setEdit] = useState(false);
  const [sel, setSel] = useState<Record<number, number>>({});
  const [busy, setBusy] = useState(false);

  function starten() {
    const init: Record<number, number> = {};
    artikel.pfandzuordnungen.forEach((z) => { init[z.pfandart_id] = z.menge_pro_einheit; });
    setSel(init);
    setEdit(true);
  }
  function toggle(id: number) {
    setSel((s) => { const n = { ...s }; if (id in n) delete n[id]; else n[id] = 1; return n; });
  }
  async function speichern() {
    setBusy(true);
    try {
      await onSave(Object.entries(sel).map(([pid, m]) => ({ pfandart_id: Number(pid), menge_pro_einheit: m, automatisch: true })));
      setEdit(false);
    } finally { setBusy(false); }
  }

  if (!edit) {
    return (
      <div>
        {artikel.pfandzuordnungen.length === 0
          ? <span style={{ color: "var(--muted)" }}>–</span>
          : artikel.pfandzuordnungen.map((z) => {
              const pf = pfandarten.find((p) => p.id === z.pfandart_id);
              return pf ? <span key={z.pfandart_id} className="pill-mini">{pf.name} ×{z.menge_pro_einheit}</span> : null;
            })}
        {pfandarten.length > 0 && <button className="btn btn-sm" style={{ marginLeft: 6 }} onClick={starten}>Pfand ändern</button>}
      </div>
    );
  }
  return (
    <div>
      <div className="row" style={{ flexWrap: "wrap", gap: 6 }}>
        {pfandarten.map((p) => (
          <label key={p.id} className={`pfand-chip ${p.id in sel ? "on" : ""}`}>
            <input type="checkbox" checked={p.id in sel} onChange={() => toggle(p.id)} style={{ display: "none" }} />
            {p.name} ({formatCents(p.betrag_cent)})
            {p.id in sel && (
              <input
                type="number" min={1} value={sel[p.id]}
                onClick={(e) => e.preventDefault()}
                onChange={(e) => setSel((s) => ({ ...s, [p.id]: Math.max(1, Number(e.target.value)) }))}
                className="pfand-menge"
              />
            )}
          </label>
        ))}
        {pfandarten.length === 0 && <span style={{ color: "var(--muted)" }}>Keine Pfandarten angelegt.</span>}
      </div>
      <div className="row" style={{ gap: 6, marginTop: 6 }}>
        <button className="btn btn-sm btn-primary" disabled={busy} onClick={speichern}>Speichern</button>
        <button className="btn btn-sm" onClick={() => setEdit(false)}>Abbrechen</button>
      </div>
    </div>
  );
}
