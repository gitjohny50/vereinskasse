import { useEffect, useState } from "react";
import {
  api, ApiError, euroToCents, formatCents,
  type Bericht, type KassenabschlussKopf as Kopf, type Kassenprofil,
} from "../api";

export function Kassenabschluss({ profil }: { profil: Kassenprofil }) {
  const [x, setX] = useState<Bericht | null>(null);
  const [liste, setListe] = useState<Kopf[]>([]);
  const [anfang, setAnfang] = useState("");
  const [gezaehlt, setGezaehlt] = useState("");
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [fehler, setFehler] = useState<string | null>(null);
  const [erfolg, setErfolg] = useState<Bericht | null>(null);
  const [detail, setDetail] = useState<Bericht | null>(null);

  async function laden() {
    const [xb, l] = await Promise.all([api.xBericht(profil.id), api.abschluesse(profil.id)]);
    setX(xb); setListe(l);
  }
  useEffect(() => {
    setFehler(null); setErfolg(null); setDetail(null); setConfirm(false);
    laden().catch((e) => setFehler(e instanceof ApiError ? e.message : "Fehler beim Laden."));
  }, [profil.id]);

  const anfangCent = euroToCents(anfang) ?? 0;
  const gezaehltCent = gezaehlt.trim() === "" ? null : euroToCents(gezaehlt);
  const erwartet = (x?.bar_cent ?? 0) + anfangCent;
  const differenz = gezaehltCent == null ? null : gezaehltCent - erwartet;

  async function zAbschluss() {
    setBusy(true); setFehler(null);
    try {
      const z = await api.zAbschluss({ kassenprofil_id: profil.id, anfangsbestand_cent: anfangCent, gezaehlt_cent: gezaehltCent });
      setErfolg(z); setConfirm(false); setAnfang(""); setGezaehlt("");
      await laden();
    } catch (e) { setFehler(e instanceof ApiError ? e.message : "Abschluss fehlgeschlagen."); }
    finally { setBusy(false); }
  }

  async function zeigeDetail(id: number) {
    try { setDetail(await api.abschlussDetail(id)); } catch (e) { setFehler(e instanceof ApiError ? e.message : "Detail nicht ladbar."); }
  }

  function zeit(iso: string | null) {
    return iso ? new Date(iso).toLocaleString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "–";
  }

  if (fehler && !x) return <p className="login-error">{fehler}</p>;

  return (
    <section>
      <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-end", marginBottom: 16 }}>
        <div><div className="eyebrow">Kasse</div><strong style={{ fontSize: 17 }}>Kassenabschluss</strong></div>
        <button className="btn btn-sm" onClick={() => laden().catch(() => {})}>Aktualisieren</button>
      </div>

      {x && (
        <div className="card" style={{ marginBottom: 18 }}>
          <div className="row" style={{ justifyContent: "space-between", alignItems: "baseline" }}>
            <div className="section-title">Aktueller Stand (X-Bericht)</div>
            <span style={{ color: "var(--muted)", fontSize: 13 }}>{x.anzahl_verkaeufe} offene Verkäufe</span>
          </div>

          <div className="korb-summen" style={{ marginTop: 8 }}>
            <Zeile label="Waren" wert={x.waren_cent} />
            {x.pfand_cent !== 0 && <Zeile label="Pfand" wert={x.pfand_cent} />}
            <Zeile label="Gesamt" wert={x.gesamt_cent} gross />
          </div>

          {x.zahlarten.length > 0 && (
            <div style={{ marginTop: 12 }}>
              <div className="eyebrow" style={{ marginBottom: 6 }}>Nach Zahlart</div>
              {x.zahlarten.map((z) => (
                <div key={z.zahlungsmethode_id ?? z.bezeichnung} className="row" style={{ justifyContent: "space-between", maxWidth: 360 }}>
                  <span>{z.bezeichnung} <span style={{ color: "var(--muted)" }}>({z.anzahl})</span>{z.bar ? " · bar" : ""}</span>
                  <span>{formatCents(z.betrag_cent)}</span>
                </div>
              ))}
            </div>
          )}

          <div className="feld-grid" style={{ marginTop: 16 }}>
            <label>Anfangsbestand (Wechselgeld) €<input value={anfang} onChange={(e) => setAnfang(e.target.value)} inputMode="decimal" placeholder="z. B. 50,00" /></label>
            <label>Gezählt (Kassensturz) €<input value={gezaehlt} onChange={(e) => setGezaehlt(e.target.value)} inputMode="decimal" placeholder="optional" /></label>
          </div>
          <div className="korb-summen" style={{ marginTop: 12 }}>
            <Zeile label="Bar-Umsatz" wert={x.bar_cent} />
            <Zeile label="Erwartet in Kasse" wert={erwartet} />
            {differenz != null && (
              <div className="row korb-gesamt" style={{ justifyContent: "space-between" }}>
                <span>Differenz</span>
                <span style={{ color: differenz === 0 ? "var(--ok, #0e7c6b)" : "var(--danger, #b3261e)" }}>
                  {differenz > 0 ? "+" : ""}{formatCents(differenz)}
                </span>
              </div>
            )}
          </div>

          {fehler && <p className="login-error" style={{ marginTop: 10 }}>{fehler}</p>}

          {!confirm ? (
            <div className="row" style={{ marginTop: 14 }}>
              <button className="btn btn-primary" disabled={x.anzahl_verkaeufe === 0} onClick={() => setConfirm(true)}>
                Z-Abschluss durchführen
              </button>
              {x.anzahl_verkaeufe === 0 && <span style={{ color: "var(--muted)", marginLeft: 10, alignSelf: "center" }}>Keine offenen Verkäufe.</span>}
            </div>
          ) : (
            <div className="verkauf-ok" style={{ marginTop: 14 }}>
              <div>Tagesabschluss durchführen? Das schließt <strong>{x.anzahl_verkaeufe} Verkäufe</strong> unwiderruflich ab.</div>
              <div className="row" style={{ gap: 10 }}>
                <button className="btn btn-primary" disabled={busy} onClick={zAbschluss}>Ja, abschließen</button>
                <button className="btn" disabled={busy} onClick={() => setConfirm(false)}>Abbrechen</button>
              </div>
            </div>
          )}

          {erfolg && (
            <div className="verkauf-ok" style={{ marginTop: 14 }}>
              <div><strong>{erfolg.nummer}</strong> abgeschlossen · {erfolg.anzahl_verkaeufe} Verkäufe · {formatCents(erfolg.gesamt_cent)}</div>
              {erfolg.differenz_cent != null && <div>Kassendifferenz: {erfolg.differenz_cent > 0 ? "+" : ""}{formatCents(erfolg.differenz_cent)}</div>}
              {erfolg.abschluss_id && <button className="btn btn-sm" onClick={() => api.abschlussNachdruck(erfolg.abschluss_id!)}>Bericht nachdrucken</button>}
            </div>
          )}
        </div>
      )}

      <div className="section-title" style={{ marginBottom: 8 }}>Bisherige Abschlüsse</div>
      <table className="tabelle">
        <thead><tr><th>Nummer</th><th>Zeitpunkt</th><th className="num">Verkäufe</th><th className="num">Gesamt</th><th className="num">Differenz</th><th className="num">Aktionen</th></tr></thead>
        <tbody>
          {liste.map((a) => (
            <tr key={a.id}>
              <td><strong>{a.nummer}</strong></td>
              <td>{zeit(a.erstellt_am)}</td>
              <td className="num">{a.anzahl_verkaeufe}</td>
              <td className="num">{formatCents(a.gesamt_cent)}</td>
              <td className="num" style={{ color: a.differenz_cent && a.differenz_cent !== 0 ? "var(--danger, #b3261e)" : undefined }}>
                {a.differenz_cent == null ? "–" : `${a.differenz_cent > 0 ? "+" : ""}${formatCents(a.differenz_cent)}`}
              </td>
              <td className="num">
                <button className="btn btn-sm" onClick={() => zeigeDetail(a.id)}>Detail</button>
                <button className="btn btn-sm" onClick={() => api.abschlussNachdruck(a.id)}>Nachdruck</button>
              </td>
            </tr>
          ))}
          {liste.length === 0 && <tr><td colSpan={6} style={{ color: "var(--muted)" }}>Noch keine Abschlüsse.</td></tr>}
        </tbody>
      </table>

      {detail && (
        <div className="card" style={{ marginTop: 16 }}>
          <div className="row" style={{ justifyContent: "space-between", alignItems: "baseline" }}>
            <div className="section-title">{detail.nummer} · {zeit(detail.bis)}</div>
            <button className="btn btn-sm" onClick={() => setDetail(null)}>Schließen</button>
          </div>
          <div className="korb-summen" style={{ marginTop: 8 }}>
            <Zeile label="Waren" wert={detail.waren_cent} />
            {detail.pfand_cent !== 0 && <Zeile label="Pfand" wert={detail.pfand_cent} />}
            <Zeile label="Gesamt" wert={detail.gesamt_cent} gross />
            <Zeile label="Bar-Umsatz" wert={detail.bar_cent} />
            <Zeile label="Erwartet" wert={detail.erwartet_cent} />
            {detail.gezaehlt_cent != null && <Zeile label="Gezählt" wert={detail.gezaehlt_cent} />}
            {detail.differenz_cent != null && (
              <div className="row" style={{ justifyContent: "space-between", maxWidth: 360 }}>
                <span>Differenz</span>
                <span style={{ color: detail.differenz_cent === 0 ? "var(--ok, #0e7c6b)" : "var(--danger, #b3261e)" }}>
                  {detail.differenz_cent > 0 ? "+" : ""}{formatCents(detail.differenz_cent)}
                </span>
              </div>
            )}
          </div>
          {detail.artikel.length > 0 && (
            <div style={{ marginTop: 12 }}>
              <div className="eyebrow" style={{ marginBottom: 6 }}>Artikel</div>
              {detail.artikel.map((ar) => (
                <div key={ar.bezeichnung} className="row" style={{ justifyContent: "space-between", maxWidth: 360 }}>
                  <span>{ar.menge}× {ar.bezeichnung}</span><span>{formatCents(ar.betrag_cent)}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      <p style={{ color: "var(--muted)", fontSize: 13, marginTop: 12 }}>
        Der X-Bericht ist ein Zwischenstand und ändert nichts. Der Z-Abschluss schließt die offenen Verkäufe
        unwiderruflich ab, wird gespeichert und automatisch gedruckt.
      </p>
    </section>
  );
}

function Zeile({ label, wert, gross }: { label: string; wert: number; gross?: boolean }) {
  return (
    <div className={`row ${gross ? "korb-gesamt" : ""}`} style={{ justifyContent: "space-between", maxWidth: 360 }}>
      <span>{label}</span><span>{formatCents(wert)}</span>
    </div>
  );
}
