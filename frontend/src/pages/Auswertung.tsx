import { useEffect, useMemo, useState, useCallback } from "react";
import { api, ApiError, formatCents, type Kassenprofil } from "../api";

export interface ZeitreiheBucket {
  start: string;
  label: string;
  gesamt_cent: number;
  anzahl: number;
  menge: number;
  segmente: { schluessel: string; name: string; wert_cent: number; anzahl: number; menge: number }[];
}

export interface Zeitreihe {
  summe: {
    umsatz_cent: number;
    anzahl: number;
    menge: number;
    durchschnitt_cent: number;
    pfand_ausgegeben_cent: number;
    pfand_zurueck_cent: number;
    bar_cent: number;
    unbar_cent: number;
  };
  buckets: ZeitreiheBucket[];
  top_artikel: { bezeichnung: string; menge: number; umsatz_cent: number }[];
  verkaeufe: {
    id: number;
    zeitpunkt: string;
    belegnummer: string;
    zahlung: string;
    gesamt_cent: number;
    items: { bezeichnung: string; menge: number }[];
  }[];
}

type Granularitaet = "stunde" | "tag" | "woche";
type Metrik = "umsatz" | "anzahl" | "menge";
type Gruppierung = "keine" | "kategorie" | "artikel" | "zahlart" | "bediener";
type Bereich = "heute" | "gestern" | "7tage" | "gesamt" | "custom";

interface ZeitreiheParams {
  kassenprofil_id: number;
  von: string;
  bis: string;
  granularitaet: Granularitaet;
  metrik: Metrik;
  gruppierung: Gruppierung;
  pfand_einbeziehen: boolean;
  ausrichtung: string;
}

interface ExtendedApi {
  zeitreihe(params: ZeitreiheParams): Promise<Zeitreihe>;
}

const COLORS = ["var(--accent)", "var(--ok)", "var(--warn)", "var(--danger)", "#2563eb", "#7c3aed", "#0ea5e9", "#475569"];

function startOfDay(d: Date) {
  const x = new Date(d);
  x.setHours(0, 0, 0, 0);
  return x;
}

function add(d: Date, granularitaet: Granularitaet, amount: number) {
  const x = new Date(d);
  if (granularitaet === "stunde") x.setDate(x.getDate() + amount);
  else if (granularitaet === "tag") x.setDate(x.getDate() + amount);
  else x.setDate(x.getDate() + amount * 7);
  return x;
}

function isoLocal(d: Date) {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

function dateInput(d: Date) {
  return isoLocal(d).slice(0, 10);
}

function fromDateInput(value: string) {
  return startOfDay(new Date(`${value}T00:00:00`));
}

function fmtDate(d: Date) {
  return d.toLocaleDateString("de-DE", { weekday: "short", day: "2-digit", month: "2-digit", year: "numeric" });
}

function fmtRange(von: Date, bis: Date) {
  const bisDisplay = new Date(bis.getTime() - 1000);
  return `${fmtDate(von)} · ${von.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })}-${bisDisplay.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })}`;
}

function metricValue(bucket: ZeitreiheBucket | undefined, metric: Metrik, selectedKey: string | null) {
  if (!bucket) return 0;
  if (selectedKey) {
    const seg = bucket.segmente.find((s) => s.schluessel === selectedKey || s.name === selectedKey);
    if (!seg) return 0;
    if (metric === "umsatz") return Math.max(0, seg.wert_cent);
    if (metric === "anzahl") return seg.anzahl;
    return seg.menge;
  }
  if (metric === "umsatz") return Math.max(0, bucket.gesamt_cent);
  if (metric === "anzahl") return bucket.anzahl;
  return bucket.menge;
}

function metricText(value: number, metric: Metrik) {
  return metric === "umsatz" ? formatCents(value) : String(value);
}

function itemText(items: { bezeichnung: string; menge: number }[]) {
  if (items.length === 0) return "Keine Artikelpositionen";
  return items.map((i) => `${i.menge} x ${i.bezeichnung}`).join(", ");
}

function delta(a: number, b: number) {
  const diff = a - b;
  const pct = b === 0 ? null : Math.round((diff / b) * 100);
  return { diff, pct };
}

function Delta({ a, b, money = false }: { a: number; b: number; money?: boolean }) {
  const d = delta(a, b);
  const ok = d.diff >= 0;
  return (
    <small style={{ color: ok ? "var(--ok)" : "var(--danger)", fontWeight: 700 }}>
      {d.diff >= 0 ? "+" : ""}{money ? formatCents(d.diff) : d.diff}
      {d.pct !== null ? ` · ${d.pct >= 0 ? "+" : ""}${d.pct}%` : ""}
    </small>
  );
}

function useRange(bereich: Bereich, granularitaet: Granularitaet, offset: number, customVon: string, customBis: string) {
  return useMemo(() => {
    const today = startOfDay(new Date());
    let von = today;
    let bis = new Date(today);
    bis.setDate(bis.getDate() + 1);
    if (bereich === "gestern") {
      von.setDate(von.getDate() - 1);
      bis = new Date(today);
    } else if (bereich === "7tage") {
      von.setDate(von.getDate() - 6);
      bis = new Date(today);
      bis.setDate(bis.getDate() + 1);
    } else if (bereich === "gesamt") {
      von.setFullYear(von.getFullYear() - 5);
      bis = new Date(today);
      bis.setDate(bis.getDate() + 1);
    } else if (bereich === "custom") {
      von = fromDateInput(customVon);
      bis = fromDateInput(customBis);
      bis.setDate(bis.getDate() + 1);
    }
    const shiftedVon = add(von, granularitaet, offset);
    const shiftedBis = add(bis, granularitaet, offset);
    return { von: shiftedVon, bis: shiftedBis };
  }, [bereich, granularitaet, offset, customVon, customBis]);
}

function Chart({
  daten, vergleich, metrik, selectedKey, onSelectKey,
}: {
  daten: Zeitreihe; vergleich: Zeitreihe | null; metrik: Metrik; selectedKey: string | null; onSelectKey: (key: string | null, name?: string) => void;
}) {
  const [aktiv, setAktiv] = useState<number | null>(null);
  const keys = new Map<string, string>();
  daten.buckets.forEach((b) => b.segmente.forEach((s) => keys.set(s.schluessel, s.name)));
  const colorByKey = new Map([...keys.keys()].map((key, i) => [key, COLORS[i % COLORS.length]]));
  const max = Math.max(1, ...daten.buckets.map((b, i) => Math.max(metricValue(b, metrik, selectedKey), metricValue(vergleich?.buckets[i], metrik, selectedKey))));
  const activeBucket = aktiv == null ? null : daten.buckets[aktiv] ?? null;
  const peak = daten.buckets.reduce((best, b, i) => metricValue(b, metrik, selectedKey) > metricValue(daten.buckets[best], metrik, selectedKey) ? i : best, 0);

  function segments(bucket: ZeitreiheBucket) {
    if (selectedKey) {
      const seg = bucket.segmente.find((s) => s.schluessel === selectedKey || s.name === selectedKey);
      return seg ? [seg] : [];
    }
    return bucket.segmente.length ? bucket.segmente : [{ schluessel: "gesamt", name: "Gesamt", wert_cent: bucket.gesamt_cent, anzahl: bucket.anzahl, menge: bucket.menge }];
  }

  return (
    <section className="analytics-card">
      <div className="row" style={{ justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
        <strong>Zeitverlauf</strong>
        {selectedKey && <button className="btn btn-sm" onClick={() => onSelectKey(null)}>Filter lösen</button>}
      </div>
      <div className="analytics-chart" role="img" aria-label="Interaktiver Zeitverlauf">
        {daten.buckets.every((b) => metricValue(b, metrik, selectedKey) === 0) && <div className="empty-chart">Keine Verkäufe im Zeitraum.</div>}
        {daten.buckets.map((bucket, idx) => {
          const value = metricValue(bucket, metrik, selectedKey);
          const height = Math.max(value > 0 ? 5 : 1, Math.round((value / max) * 180));
          const compValue = metricValue(vergleich?.buckets[idx], metrik, selectedKey);
          const compHeight = Math.max(compValue > 0 ? 5 : 1, Math.round((compValue / max) * 180));
          const bucketSegments = segments(bucket);
          const segmentTotal = Math.max(1, bucketSegments.reduce((sum, s) => sum + Math.max(0, metrik === "umsatz" ? s.wert_cent : metrik === "anzahl" ? s.anzahl : s.menge), 0));
          return (
            <button
              key={`${bucket.start}-${idx}`}
              className={`bar ${aktiv === idx ? "active" : ""}`}
              onClick={() => setAktiv(aktiv === idx ? null : idx)}
              style={{ outline: idx === peak && value > 0 ? "1px solid var(--accent)" : undefined, borderRadius: 8 }}
              aria-label={`${bucket.label}: ${metricText(value, metrik)}`}
            >
              <span className="row" style={{ alignItems: "flex-end", gap: vergleich ? 3 : 0, width: "100%", justifyContent: "center" }}>
                <span className="bar-stack" style={{ height, maxWidth: vergleich ? 20 : 40 }}>
                  {bucketSegments.map((s) => {
                    const segValue = metrik === "umsatz" ? Math.max(0, s.wert_cent) : metrik === "anzahl" ? s.anzahl : s.menge;
                    return (
                      <span
                        key={s.schluessel}
                        style={{ height: `${(segValue / segmentTotal) * 100}%`, background: colorByKey.get(s.schluessel) ?? COLORS[0] }}
                        title={`${s.name}: ${metricText(segValue, metrik)}`}
                        onClick={(e) => { e.stopPropagation(); onSelectKey(s.schluessel, s.name); }}
                      />
                    );
                  })}
                </span>
                {vergleich && <span className="bar-stack" style={{ height: compHeight, maxWidth: 20, opacity: .45 }}><span style={{ height: "100%", background: "var(--muted)" }} /></span>}
              </span>
              <span className="bar-label">{bucket.label}</span>
            </button>
          );
        })}
      </div>
      <div className="legend-row">
        {[...keys.entries()].slice(0, 8).map(([key, name]) => (
          <button key={key} className="legend-item" onClick={() => onSelectKey(selectedKey === key ? null : key)} style={{ border: "none", background: "transparent", cursor: "pointer" }}>
            <span style={{ background: colorByKey.get(key) }} />{name}
          </button>
        ))}
        {vergleich && <span className="legend-item"><span style={{ background: "var(--muted)" }} />Vergleich B</span>}
      </div>
      <div className="chart-detail">
        {activeBucket
          ? `${activeBucket.label} · ${metricText(metricValue(activeBucket, metrik, selectedKey), metrik)} · ${activeBucket.anzahl} Verkäufe · Top: ${activeBucket.segmente.slice(0, 3).map((s) => s.name).join(", ") || "keine"}`
          : selectedKey ? "Gefilterter Zeitverlauf. Balken antippen für Details." : "Balken antippen, Segmente oder Ranking anklicken zum Filtern."}
      </div>
    </section>
  );
}

function Kpis({ daten, vergleich }: { daten: Zeitreihe | null; vergleich: Zeitreihe | null }) {
  const s = daten?.summe;
  const b = vergleich?.summe;
  const durchsatz = daten ? Math.round(daten.summe.anzahl / Math.max(1, daten.buckets.length)) : 0;
  const durchsatzB = vergleich ? Math.round(vergleich.summe.anzahl / Math.max(1, vergleich.buckets.length)) : 0;
  return (
    <div className="analytics-stats">
      <div><span>Umsatz</span><strong>{formatCents(s?.umsatz_cent ?? 0)}</strong>{b && <Delta a={s?.umsatz_cent ?? 0} b={b.umsatz_cent} money />}</div>
      <div><span>Verkäufe</span><strong>{s?.anzahl ?? 0}</strong>{b && <Delta a={s?.anzahl ?? 0} b={b.anzahl} />}</div>
      <div><span>Ø Bon</span><strong>{formatCents(s?.durchschnitt_cent ?? 0)}</strong>{b && <Delta a={s?.durchschnitt_cent ?? 0} b={b.durchschnitt_cent} money />}</div>
      <div><span>Durchsatz</span><strong>{durchsatz}/Intervall</strong>{b && <Delta a={durchsatz} b={durchsatzB} />}</div>
      <div><span>Pfand-Saldo</span><strong>{formatCents((s?.pfand_ausgegeben_cent ?? 0) - (s?.pfand_zurueck_cent ?? 0))}</strong></div>
      <div>
        <span>Bar / Unbar</span>
        <strong>{formatCents(s?.bar_cent ?? 0)} / {formatCents(s?.unbar_cent ?? 0)}</strong>
      </div>
    </div>
  );
}

function ranking(daten: Zeitreihe | null, gruppierung: Gruppierung) {
  if (!daten) return [];
  if (gruppierung === "artikel") return daten.top_artikel.map((i) => ({ key: i.bezeichnung, name: i.bezeichnung, menge: i.menge, wert: i.umsatz_cent }));
  const map = new Map<string, { key: string; name: string; menge: number; wert: number; anzahl: number }>();
  daten.buckets.forEach((b) => b.segmente.forEach((s) => {
    const row = map.get(s.schluessel) ?? { key: s.schluessel, name: s.name, menge: 0, wert: 0, anzahl: 0 };
    row.menge += s.menge; row.wert += s.wert_cent; row.anzahl += s.anzahl;
    map.set(s.schluessel, row);
  }));
  return [...map.values()].sort((a, b) => b.wert - a.wert).slice(0, 10);
}

export function Auswertung({ profil }: { profil: Kassenprofil }) {
  const [granularitaet, setGranularitaet] = useState<Granularitaet>("stunde");
  const [bereich, setBereich] = useState<Bereich>("heute");
  const [offset, setOffset] = useState(0);
  const [customVon, setCustomVon] = useState(dateInput(new Date()));
  const [customBis, setCustomBis] = useState(dateInput(new Date()));
  const [metrik, setMetrik] = useState<Metrik>("umsatz");
  const [gruppierung, setGruppierung] = useState<Gruppierung>("artikel");
  const [pfand, setPfand] = useState(true);
  const [vergleichAktiv, setVergleichAktiv] = useState(false);
  const [vergleichOffset, setVergleichOffset] = useState(-1);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [selectedName, setSelectedName] = useState<string | null>(null);
  const [daten, setDaten] = useState<Zeitreihe | null>(null);
  const [vergleich, setVergleich] = useState<Zeitreihe | null>(null);
  const [fehler, setFehler] = useState<string | null>(null);

  const rangeA = useRange(bereich, granularitaet, offset, customVon, customBis);
  const rangeB = useRange(bereich, granularitaet, offset + vergleichOffset, customVon, customBis);

  const laden = useCallback(async () => {
    setFehler(null);
    const params: ZeitreiheParams = {
      kassenprofil_id: profil.id,
      von: isoLocal(rangeA.von),
      bis: isoLocal(rangeA.bis),
      granularitaet,
      metrik,
      gruppierung,
      pfand_einbeziehen: pfand,
      ausrichtung: vergleichAktiv ? "relativ" : "absolut",
    };
    try {
      const erweiterteApi = api as unknown as ExtendedApi;
      const a = await erweiterteApi.zeitreihe(params);
      setDaten(a);
      if (vergleichAktiv) {
        setVergleich(await erweiterteApi.zeitreihe({ ...params, von: isoLocal(rangeB.von), bis: isoLocal(rangeB.bis), ausrichtung: "relativ" }));
      } else {
        setVergleich(null);
      }
    } catch (e) {
      setFehler(e instanceof ApiError ? e.message : "Auswertung konnte nicht geladen werden.");
    }
  }, [profil.id, rangeA, rangeB, granularitaet, metrik, gruppierung, pfand, vergleichAktiv]);

  useEffect(() => {
    laden();
  }, [laden]);

  useEffect(() => {
    if (daten && selectedKey && !daten.top_artikel.some((i) => i.bezeichnung === selectedKey) && !daten.buckets.some(b => b.segmente.some(s => s.schluessel === selectedKey))) {
      setSelectedKey(null);
      setSelectedName(null);
    }
  }, [daten, selectedKey]);

  const rows = useMemo(() => ranking(daten, gruppierung), [daten, gruppierung]);
  const maxRank = Math.max(1, ...rows.map((r) => r.wert));

  const verkaeufe = selectedKey
    ? (daten?.verkaeufe ?? []).filter((v) => v.items.some((i) => i.bezeichnung === selectedName || i.bezeichnung === selectedKey))
    : daten?.verkaeufe ?? [];

  function setRange(b: Bereich) {
    setBereich(b);
    setOffset(0);
  }

  if (fehler) return <p className="login-error">{fehler}</p>;

  return (
    <section>
      <div className="analytics-card" style={{ position: "sticky", top: 0, zIndex: 5 }}>
        <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-start", gap: 12, flexWrap: "wrap" }}>
          <div>
            <div className="eyebrow">Auswertung</div>
            <strong style={{ fontSize: 18 }}>Verkaufs-Dashboard</strong>
            <div style={{ color: "var(--muted)", marginTop: 4 }}>
              {fmtRange(rangeA.von, rangeA.bis)} · {daten?.summe.anzahl ?? 0} Verkäufe · {formatCents(daten?.summe.umsatz_cent ?? 0)}
            </div>
          </div>
          <button className="btn btn-sm" onClick={laden}>Aktualisieren</button>
        </div>
        <div className="row" style={{ gap: 10, marginTop: 12, flexWrap: "wrap" }}>
          <div className="segmented">
            {(["stunde", "tag", "woche"] as Granularitaet[]).map((g) => <button key={g} className={granularitaet === g ? "on" : ""} onClick={() => setGranularitaet(g)}>{g === "stunde" ? "Stunde" : g === "tag" ? "Tag" : "Woche"}</button>)}
          </div>
          <div className="segmented">
            {([["heute", "Heute"], ["gestern", "Gestern"], ["7tage", "Letzte 7 Tage"], ["gesamt", "Gesamt"], ["custom", "Benutzerdefiniert"]] as [Bereich, string][]).map(([key, label]) => (
              <button key={key} className={bereich === key ? "on" : ""} onClick={() => setRange(key)}>{label}</button>
            ))}
          </div>
          <div className="segmented">
            <button onClick={() => setOffset((n) => n - 1)}>‹</button>
            <button className="on">{bereich === "gesamt" ? "Gesamt" : fmtDate(rangeA.von)}</button>
            <button onClick={() => setOffset((n) => n + 1)}>›</button>
          </div>
          <button className={`btn btn-sm ${vergleichAktiv ? "btn-primary" : ""}`} onClick={() => setVergleichAktiv((v) => !v)}>Vergleichen</button>
          <button className={`btn btn-sm ${pfand ? "btn-primary" : ""}`} onClick={() => setPfand((v) => !v)}>Pfand {pfand ? "inkl." : "exkl."}</button>
        </div>
        {bereich === "custom" && (
          <div className="row" style={{ gap: 12, marginTop: 12 }}>
            <label>Von<input type="date" value={customVon} onChange={(e) => setCustomVon(e.target.value)} /></label>
            <label>Bis<input type="date" value={customBis} onChange={(e) => setCustomBis(e.target.value)} /></label>
          </div>
        )}
        {vergleichAktiv && (
          <div className="row" style={{ gap: 10, marginTop: 12, color: "var(--muted)", flexWrap: "wrap" }}>
            <span>Vergleich B: {fmtRange(rangeB.von, rangeB.bis)}</span>
            <button className="btn btn-sm" onClick={() => setVergleichOffset((n) => n - 1)}>B früher</button>
            <button className="btn btn-sm" onClick={() => setVergleichOffset((n) => n + 1)}>B später</button>
          </div>
        )}
      </div>

      <Kpis daten={daten} vergleich={vergleich} />

      <div className="analytics-card">
        <div className="row" style={{ gap: 12, flexWrap: "wrap" }}>
          <div className="segmented">
            {([["umsatz", "Umsatz €"], ["anzahl", "Anzahl Verkäufe"], ["menge", "Menge"]] as [Metrik, string][]).map(([key, label]) => <button key={key} className={metrik === key ? "on" : ""} onClick={() => setMetrik(key)}>{label}</button>)}
          </div>
          <div className="segmented">
            {([["keine", "Keine"], ["kategorie", "Kategorie"], ["artikel", "Top-Artikel"], ["zahlart", "Zahlart"], ["bediener", "Bediener"]] as [Gruppierung, string][]).map(([key, label]) => <button key={key} className={gruppierung === key ? "on" : ""} onClick={() => { setGruppierung(key); setSelectedKey(null); setSelectedName(null); }}>{label}</button>)}
          </div>
        </div>
      </div>

      {daten && <Chart daten={daten} vergleich={vergleich} metrik={metrik} selectedKey={selectedKey} onSelectKey={(key, name) => { setSelectedKey(key); setSelectedName(name ?? key); }} />}

      <div className="analytics-card">
        <div className="section-title">Drill-down</div>
        <div className="item-filter">
          <button className={!selectedKey ? "on" : ""} onClick={() => { setSelectedKey(null); setSelectedName(null); }}>Alle</button>
          {rows.map((row, index) => (
            <button key={row.key} className={selectedKey === row.key ? "on" : ""} onClick={() => { setSelectedKey(selectedKey === row.key ? null : row.key); setSelectedName(selectedKey === row.key ? null : row.name); }}>
              <span className="legend-dot" style={{ background: COLORS[index % COLORS.length] }} />
              {row.name}
              <span className="item-count">{row.menge}x · {formatCents(row.wert)}</span>
            </button>
          ))}
        </div>
        {rows.map((row, index) => (
          <button key={row.key} onClick={() => { setSelectedKey(row.key); setSelectedName(row.name); }} style={{ display: "grid", gridTemplateColumns: "minmax(140px, 1fr) 3fr auto", gap: 10, alignItems: "center", width: "100%", minHeight: 44, border: "none", background: "transparent", textAlign: "left", cursor: "pointer" }}>
            <strong>{row.name}</strong>
            <span style={{ height: 12, borderRadius: 999, background: "var(--surface-2)", overflow: "hidden" }}>
              <span style={{ display: "block", height: "100%", width: `${Math.max(3, (row.wert / maxRank) * 100)}%`, background: COLORS[index % COLORS.length] }} />
            </span>
            <span className="num">{formatCents(row.wert)}</span>
          </button>
        ))}
      </div>

      {vergleichAktiv && daten && vergleich && (
        <div className="analytics-card">
          <div className="section-title">Top-Artikel-Vergleich</div>
          <table className="tabelle">
            <thead><tr><th>Artikel</th><th className="num">A</th><th className="num">B</th><th className="num">Δ</th></tr></thead>
            <tbody>
              {daten.top_artikel.slice(0, 8).map((a) => {
                const b = vergleich.top_artikel.find((x) => x.bezeichnung === a.bezeichnung);
                return <tr key={a.bezeichnung}><td>{a.bezeichnung}</td><td className="num">{formatCents(a.umsatz_cent)}</td><td className="num">{formatCents(b?.umsatz_cent ?? 0)}</td><td className="num"><Delta a={a.umsatz_cent} b={b?.umsatz_cent ?? 0} money /></td></tr>;
              })}
            </tbody>
          </table>
        </div>
      )}

      <div className="section-title">Verkaufsliste</div>
      <table className="tabelle">
        <thead><tr><th>Zeit</th><th>Beleg</th><th>Artikel</th><th>Zahlung</th><th className="num">Gesamt</th></tr></thead>
        <tbody>
          {verkaeufe.map((v) => (
            <tr key={v.id}>
              <td className="mono">{new Date(v.zeitpunkt).toLocaleString("de-DE", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}</td>
              <td><strong>{v.belegnummer}</strong></td>
              <td>{itemText(v.items)}</td>
              <td>{v.zahlung}</td>
              <td className="num">{formatCents(v.gesamt_cent)}</td>
            </tr>
          ))}
          {verkaeufe.length === 0 && <tr><td colSpan={5} style={{ color: "var(--muted)" }}>Keine passenden Verkäufe im Zeitraum.</td></tr>}
        </tbody>
      </table>
    </section>
  );
}