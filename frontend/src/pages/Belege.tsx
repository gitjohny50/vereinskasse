import { Fragment, useEffect, useState } from "react";
import { api, ApiError, formatCents, type Kassenprofil, type Verkauf } from "../api";

export function Belege({ profil }: { profil: Kassenprofil }) {
  const [liste, setListe] = useState<Verkauf[]>([]);
  const [fehler, setFehler] = useState<string | null>(null);
  const [offen, setOffen] = useState<number | null>(null);
  const [hinweis, setHinweis] = useState<string | null>(null);

  async function laden() { setListe(await api.verkaeufe(profil.id)); }
  useEffect(() => {
    setFehler(null);
    laden().catch((e) => setFehler(e instanceof ApiError ? e.message : "Fehler beim Laden."));
  }, [profil.id]);

  async function nachdruck(id: number, beleg: string) {
    setHinweis(null);
    try { await api.nachdruck(id); setHinweis(`Beleg ${beleg} als Nachdruck gesendet.`); }
    catch (e) { setFehler(e instanceof ApiError ? e.message : "Nachdruck fehlgeschlagen."); }
  }

  function zeit(iso: string) {
    const d = new Date(iso);
    return d.toLocaleString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
  }

  if (fehler) return <p className="login-error">{fehler}</p>;

  return (
    <section>
      <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-end", marginBottom: 16 }}>
        <div><div className="eyebrow">Verkauf</div><strong style={{ fontSize: 17 }}>Belege</strong></div>
        <button className="btn btn-sm" onClick={() => laden()}>Aktualisieren</button>
      </div>
      {hinweis && <p className="note" style={{ marginBottom: 12 }}>{hinweis}</p>}

      <table className="tabelle">
        <thead><tr><th>Beleg</th><th>Zeitpunkt</th><th className="num">Gesamt</th><th>Zahlung</th><th className="num">Aktionen</th></tr></thead>
        <tbody>
          {liste.map((v) => (
            <Fragment key={v.id}>
              <tr>
                <td><strong>{v.belegnummer}</strong></td>
                <td>{zeit(v.zeitpunkt)}</td>
                <td className="num">{formatCents(v.gesamt_cent)}</td>
                <td>{v.zahlung?.bezeichnung ?? "–"}</td>
                <td className="num">
                  <button className="btn btn-sm" onClick={() => setOffen(offen === v.id ? null : v.id)}>{offen === v.id ? "Zu" : "Details"}</button>
                  <button className="btn btn-sm" onClick={() => nachdruck(v.id, v.belegnummer)}>Nachdruck</button>
                </td>
              </tr>
              {offen === v.id && (
                <tr>
                  <td colSpan={5} style={{ background: "var(--surface, #f6f7f7)" }}>
                    <div style={{ padding: "4px 0" }}>
                      {v.positionen.map((p, i) => (
                        <div key={i} className="row" style={{ justifyContent: "space-between", maxWidth: 380 }}>
                          <span>{p.menge} × {p.bezeichnung}</span><span>{formatCents(p.gesamt_cent)}</span>
                        </div>
                      ))}
                      {v.zahlung && (
                        <div className="row" style={{ justifyContent: "space-between", maxWidth: 380, marginTop: 6, color: "var(--muted)" }}>
                          <span>Gegeben {formatCents(v.zahlung.gegeben_cent)} · Rückgeld {formatCents(v.zahlung.rueckgeld_cent)}</span>
                        </div>
                      )}
                    </div>
                  </td>
                </tr>
              )}
            </Fragment>
          ))}
          {liste.length === 0 && <tr><td colSpan={5} style={{ color: "var(--muted)" }}>Noch keine Belege.</td></tr>}
        </tbody>
      </table>
      <p style={{ color: "var(--muted)", fontSize: 13, marginTop: 12 }}>
        Belege sind unveränderlich. Der Nachdruck erzeugt eine Kopie ohne erneute Schubladenöffnung.
      </p>
    </section>
  );
}
