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
  const [editArtikel, setEditArtikel] = useState<Art | null>(null);
  const [importBusy, setImportBusy] = useState(false);
  const [importInfo, setImportInfo] = useState<string | null>(null);
  const [importFehler, setImportFehler] = useState<string[]>([]);

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

  async function csvImportieren(file: File | null) {
    if (!file) return;
    setImportBusy(true);
    setImportInfo(null);
    setImportFehler([]);
    try {
      const text = await file.text();
      const firstLine = text.split(/\r?\n/, 1)[0] ?? "";
      const delimiter = firstLine.includes(";") ? ";" : ",";
      const result = await api.artikelCsvImport(profil.id, text, delimiter);
      if (result.fehler.length > 0) {
        setImportFehler(result.fehler);
        setImportInfo("Import abgebrochen. Es wurde nichts angelegt.");
      } else {
        setImportInfo(
          `${result.angelegt} Artikel angelegt, ${result.aktualisiert} aktualisiert. ` +
          `${result.kategorien_angelegt} Kategorien und ${result.pfandarten_angelegt} Pfandarten neu angelegt.`,
        );
        await neuLaden();
      }
    } catch (e) {
      setImportFehler([e instanceof ApiError ? e.message : "CSV-Import fehlgeschlagen."]);
    } finally {
      setImportBusy(false);
    }
  }

  async function alleArchivieren() {
    if (!window.confirm("Alle bestehenden Artikel dieses Kassenprofils archivieren und deaktivieren? Alte Belege bleiben erhalten.")) return;
    const result = await api.artikelAlleArchivieren(profil.id);
    setImportInfo(`${result.anzahl} Artikel archiviert.`);
    await neuLaden();
  }

  async function pfandZuruecksetzen() {
    if (!window.confirm("Alle Pfandzuordnungen der Artikel in diesem Kassenprofil entfernen? Pfandarten selbst bleiben erhalten.")) return;
    const result = await api.artikelPfandZuruecksetzen(profil.id);
    setImportInfo(`${result.anzahl} Pfandzuordnungen entfernt.`);
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

      <div className="import-card">
        <div>
          <div className="eyebrow">Schnellimport</div>
          <strong>Artikel per CSV einlesen</strong>
          <p>
            Die erste Zeile muss die Spaltennamen enthalten. Pflicht: <code>name</code> und <code>preis</code>.
            Optional: <code>kurzname</code>, <code>kategorie</code>, <code>pfand</code>, <code>ticket</code>,
            <code>reihenfolge</code>, <code>artikelnummer</code>, <code>barcode</code>, <code>aktiv</code>.
          </p>
          <p>
            Beispiel: <code>name;preis;kategorie;pfand;ticket</code><br />
            <code>Wasser;2,00;Getränke;Glaspfand:1;pro_stueck</code>
          </p>
          <p>
            Kategorien werden bei Bedarf automatisch angelegt. Pfandarten werden automatisch angelegt, wenn ein Betrag
            angegeben ist: <code>Glaspfand:1:2,00</code>. Mehrere Pfandarten mit <code>|</code> trennen,
            z. B. <code>Glaspfand:1:2,00|Kistenpfand:12:5,00</code>. Erlaubte Tickets: <code>pro_stueck</code>,
            <code>pro_position</code>, <code>kein</code>.
          </p>
          <p>
            Existiert ein Artikelname bereits, wird der Artikel aktualisiert und wieder aktiviert. Seine Pfandzuordnung
            wird dabei aus der CSV neu gesetzt.
          </p>
        </div>
        <label className={`btn btn-primary file-btn ${importBusy ? "disabled" : ""}`}>
          {importBusy ? "Importiere…" : "CSV auswählen"}
          <input
            type="file"
            accept=".csv,text/csv"
            disabled={importBusy}
            onChange={(e) => {
              csvImportieren(e.target.files?.[0] ?? null);
              e.currentTarget.value = "";
            }}
          />
        </label>
        {importInfo && <div className={`result ${importFehler.length ? "err" : "ok"}`}>{importInfo}</div>}
        {importFehler.length > 0 && (
          <div className="result err">
            {importFehler.map((msg) => <div key={msg}>{msg}</div>)}
          </div>
        )}
      </div>

      <div className="maintenance-card">
        <div>
          <div className="eyebrow">Admin-Wartung</div>
          <strong>Artikelbestand zurücksetzen</strong>
          <p>Für einen neuen Import kannst du Artikel archivieren oder nur die Pfandzuordnungen entfernen.</p>
        </div>
        <div className="row" style={{ flexWrap: "wrap", justifyContent: "flex-end" }}>
          <button className="btn btn-danger" onClick={alleArchivieren}>Alle Artikel archivieren</button>
          <button className="btn" onClick={pfandZuruecksetzen}>Pfand zurücksetzen</button>
        </div>
      </div>

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
              <td className="num">{formatCents(a.preis_cent)}</td>
              <td>
                {a.pfandzuordnungen.length === 0
                  ? <span style={{ color: "var(--muted)" }}>–</span>
                  : a.pfandzuordnungen.map((z) => {
                      const pf = pfandarten.find((p) => p.id === z.pfandart_id);
                      return pf ? <span key={z.pfandart_id} className="pill-mini">{pf.name} ×{z.menge_pro_einheit}</span> : null;
                    })}
              </td>
              <td>
                <button className="toggle" role="switch" aria-checked={a.aktiv} onClick={() => aktivUmschalten(a)}>
                  <span className={`toggle-track ${a.aktiv ? "on" : ""}`}><span className="toggle-knob" /></span>
                </button>
              </td>
              <td className="num">
                <button className="btn btn-sm btn-primary" onClick={() => setEditArtikel(a)}>Bearbeiten</button>
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
        Bearbeiten öffnet alle Stammdaten inklusive Kategorie und Pfand. Archivierte Artikel bleiben erhalten.
      </p>
      {editArtikel && (
        <ArtikelBearbeitenDialog
          artikel={editArtikel}
          kategorien={kategorien}
          pfandarten={pfandarten}
          onClose={() => setEditArtikel(null)}
          onSaved={async () => { setEditArtikel(null); await neuLaden(); }}
        />
      )}
    </section>
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

function ArtikelBearbeitenDialog({
  artikel, kategorien, pfandarten, onClose, onSaved,
}: {
  artikel: Art; kategorien: Kategorie[]; pfandarten: Pfandart[]; onClose: () => void; onSaved: () => void;
}) {
  const [name, setName] = useState(artikel.name);
  const [kurzname, setKurzname] = useState(artikel.kurzname);
  const [preis, setPreis] = useState((artikel.preis_cent / 100).toFixed(2).replace(".", ","));
  const [kategorieId, setKategorieId] = useState<number | "">(artikel.kategorie_id ?? "");
  const [ticketModus, setTicketModus] = useState(artikel.artikelticket_modus);
  const [reihenfolge, setReihenfolge] = useState(artikel.sortierung);
  const [aktiv, setAktiv] = useState(artikel.aktiv);
  const [pfand, setPfand] = useState<Record<number, number>>(() => {
    const init: Record<number, number> = {};
    artikel.pfandzuordnungen.forEach((z) => { init[z.pfandart_id] = z.menge_pro_einheit; });
    return init;
  });
  const [fehler, setFehler] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function togglePfand(id: number) {
    setPfand((s) => { const n = { ...s }; if (id in n) delete n[id]; else n[id] = 1; return n; });
  }

  async function speichern() {
    const cents = euroToCents(preis);
    if (!name.trim()) { setFehler("Name fehlt."); return; }
    if (cents === null) { setFehler("Preis ungültig."); return; }
    setBusy(true);
    setFehler(null);
    try {
      await api.artikelAendern(artikel.id, {
        name: name.trim(),
        kurzname: kurzname.trim(),
        preis_cent: cents,
        kategorie_id: kategorieId === "" ? null : kategorieId,
        sortierung: reihenfolge,
        artikelticket_modus: ticketModus,
        aktiv,
        pfandzuordnungen: Object.entries(pfand).map(([pid, menge]) => ({
          pfandart_id: Number(pid), menge_pro_einheit: menge, automatisch: true,
        })),
      });
      onSaved();
    } catch (e) {
      setFehler(e instanceof ApiError ? e.message : "Speichern fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-backdrop">
      <div className="modal-card">
        <div className="row" style={{ justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
          <div><div className="eyebrow">Artikel bearbeiten</div><strong>{artikel.name}</strong></div>
          <button className="btn btn-sm" onClick={onClose}>Schließen</button>
        </div>
        <div className="feld-grid">
          <label>Name<input value={name} onChange={(e) => setName(e.target.value)} /></label>
          <label>Kurzname<input value={kurzname} onChange={(e) => setKurzname(e.target.value)} /></label>
          <label>Preis (€)<input value={preis} onChange={(e) => setPreis(e.target.value)} inputMode="decimal" /></label>
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
          <label>Reihenfolge<input type="number" value={reihenfolge} onChange={(e) => setReihenfolge(Number(e.target.value))} /></label>
        </div>
        <label className="row" style={{ gap: 8, marginTop: 12 }}>
          <input type="checkbox" checked={aktiv} onChange={(e) => setAktiv(e.target.checked)} /> Aktiv
        </label>

        <div className="section-title">Pfand</div>
        <div className="row" style={{ flexWrap: "wrap", gap: 8 }}>
          {pfandarten.map((p) => (
            <label key={p.id} className={`pfand-chip ${p.id in pfand ? "on" : ""}`}>
              <input type="checkbox" checked={p.id in pfand} onChange={() => togglePfand(p.id)} style={{ display: "none" }} />
              {p.name} ({formatCents(p.betrag_cent)})
              {p.id in pfand && (
                <input
                  type="number" min={1} value={pfand[p.id]}
                  onClick={(e) => e.preventDefault()}
                  onChange={(e) => setPfand((s) => ({ ...s, [p.id]: Math.max(1, Number(e.target.value)) }))}
                  className="pfand-menge"
                />
              )}
            </label>
          ))}
          {pfandarten.length === 0 && <span style={{ color: "var(--muted)" }}>Keine Pfandarten angelegt.</span>}
        </div>
        {fehler && <p className="login-error" style={{ marginTop: 12 }}>{fehler}</p>}
        <div className="row" style={{ justifyContent: "flex-end", gap: 10, marginTop: 18 }}>
          <button className="btn" onClick={onClose}>Abbrechen</button>
          <button className="btn btn-primary" disabled={busy} onClick={speichern}>Speichern</button>
        </div>
      </div>
    </div>
  );
}
