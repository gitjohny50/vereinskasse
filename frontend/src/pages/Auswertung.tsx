import { useEffect, useMemo, useState } from "react";
import { api, ApiError, formatCents, type AuswertungBucket, type Kassenprofil, type VerkaufsAuswertung } from "../api";

const COLORS = ["#6366f1", "#2563eb", "#b45309", "#7c3aed", "#be123c", "#0ea5e9", "#c2410c", "#475569"];

function zeit(iso: string) {
  const d = new Date(iso);
  return d.toLocaleString("de-DE", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function itemText(items: { bezeichnung: string; menge: number }[]) {
  if (items.length === 0) return "Keine Artikelpositionen";
  return items.map((i) => `${i.menge} x ${i.bezeichnung}`).join(", ");
}

function Chart({ daten, selectedItem }: { daten: VerkaufsAuswertung; selectedItem: string | null }) {
  const [aktiv, setAktiv] = useState<number | null>(null);
  const topNames = daten.top_artikel.map((i) => i.bezeichnung);
  const colorByName = new Map(topNames.map((name, i) => [name, COLORS[i % COLORS.length]]));
  const selectedColor = selectedItem ? colorByName.get(selectedItem) ?? COLORS[0] : null;
  const selectedMenge = (bucket: AuswertungBucket) => bucket.items.find((i) => i.bezeichnung === selectedItem)?.menge ?? 0;
  const max = selectedItem
    ? Math.max(1, ...daten.buckets.map(selectedMenge))
    : Math.max(1, ...daten.buckets.map((b) => Math.abs(b.gesamt_cent)));
  const activeBucket = aktiv == null ? null : daten.buckets[aktiv] ?? null;

  function segments(bucket: AuswertungBucket) {
    const known = bucket.items.filter((i) => colorByName.has(i.bezeichnung));
    const knownSum = known.reduce((sum, i) => sum + i.umsatz_cent, 0);
    const other = Math.max(0, bucket.gesamt_cent - knownSum);
    return [
      ...known.map((i) => ({ name: i.bezeichnung, value: i.umsatz_cent, color: colorByName.get(i.bezeichnung) ?? COLORS[0] })),
      ...(other > 0 ? [{ name: "Sonstiges", value: other, color: "#94a3b8" }] : []),
    ];
  }

  return (
    <section className="analytics-card">
      <div className="analytics-chart" role="img" aria-label="Umsatzverlauf nach Zeit">
        {daten.buckets.length === 0 && <div className="empty-chart">Keine Verkäufe im Zeitraum.</div>}
        {daten.buckets.map((bucket, idx) => {
          const bucketSegments = segments(bucket);
          const segmentTotal = Math.max(1, bucketSegments.reduce((sum, s) => sum + Math.max(0, s.value), 0));
          const selectedCount = selectedMenge(bucket);
          const height = Math.max(4, Math.round(((selectedItem ? selectedCount : Math.abs(bucket.gesamt_cent)) / max) * 180));
          return (
            <button
              key={bucket.start}
              className={`bar ${aktiv === idx ? "active" : ""}`}
              onClick={() => setAktiv(aktiv === idx ? null : idx)}
              aria-label={selectedItem
                ? `${bucket.label}: ${selectedCount} mal ${selectedItem}`
                : `${bucket.label}: ${formatCents(bucket.gesamt_cent)}, ${bucket.anzahl} Verkäufe`}
            >
              <span className="bar-stack" style={{ height }}>
                {selectedItem ? (
                  selectedCount > 0 && <span style={{ height: "100%", background: selectedColor ?? COLORS[0] }} title={`${selectedItem}: ${selectedCount}x`} />
                ) : (
                  bucketSegments.map((s) => (
                    <span
                      key={s.name}
                      style={{ height: `${(Math.max(0, s.value) / segmentTotal) * 100}%`, background: s.color }}
                      title={`${s.name}: ${formatCents(s.value)}`}
                    />
                  ))
                )}
              </span>
              <span className="bar-label">{bucket.label}</span>
            </button>
          );
        })}
      </div>
      <div className="legend-row">
        {topNames.map((name, i) => (
          <span key={name} className="legend-item"><span style={{ background: COLORS[i % COLORS.length] }} />{name}</span>
        ))}
        {topNames.length > 0 && <span className="legend-item"><span style={{ background: "#94a3b8" }} />Sonstiges</span>}
      </div>
      <div className="chart-detail">
        {activeBucket
          ? selectedItem
            ? `${activeBucket.label} · ${selectedItem}: ${selectedMenge(activeBucket)}x · Gesamt in diesem Zeitraum: ${formatCents(activeBucket.gesamt_cent)}`
            : `${activeBucket.label} · ${formatCents(activeBucket.gesamt_cent)} · ${itemText(activeBucket.items)}`
          : selectedItem
            ? `Zeitverlauf für ${selectedItem}. Balken antippen für Details.`
            : "Balken antippen, um die verkauften Artikel in diesem Zeitraum zu sehen."}
      </div>
    </section>
  );
}

export function Auswertung({ profil }: { profil: Kassenprofil }) {
  const [tage, setTage] = useState(1);
  const [pfand, setPfand] = useState(false);
  const [selectedItem, setSelectedItem] = useState<string | null>(null);
  const [daten, setDaten] = useState<VerkaufsAuswertung | null>(null);
  const [fehler, setFehler] = useState<string | null>(null);

  async function laden() {
    setFehler(null);
    try {
      setDaten(await api.verkaufsAuswertung(profil.id, tage, pfand));
    } catch (e) {
      setFehler(e instanceof ApiError ? e.message : "Auswertung konnte nicht geladen werden.");
    }
  }

  useEffect(() => { laden(); }, [profil.id, tage, pfand]);
  useEffect(() => {
    if (daten && selectedItem && !daten.top_artikel.some((i) => i.bezeichnung === selectedItem)) {
      setSelectedItem(null);
    }
  }, [daten, selectedItem]);

  const durchschnitt = useMemo(() => {
    if (!daten || daten.anzahl_verkaeufe === 0) return 0;
    return Math.round(daten.gesamt_cent / daten.anzahl_verkaeufe);
  }, [daten]);
  const gefilterteVerkaeufe = selectedItem
    ? (daten?.verkaeufe ?? []).filter((v) => v.items.some((i) => i.bezeichnung === selectedItem))
    : daten?.verkaeufe ?? [];

  if (fehler) return <p className="login-error">{fehler}</p>;

  return (
    <section>
      <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-end", marginBottom: 16, flexWrap: "wrap" }}>
        <div><div className="eyebrow">Auswertung</div><strong style={{ fontSize: 17 }}>Verkäufe nach Zeit</strong></div>
        <div className="segmented">
          {[1, 7, 30].map((n) => (
            <button key={n} className={tage === n ? "on" : ""} onClick={() => setTage(n)}>
              {n === 1 ? "Heute" : `${n} Tage`}
            </button>
          ))}
          <button className={pfand ? "on" : ""} onClick={() => setPfand((v) => !v)}>
            Pfand {pfand ? "inkl." : "exkl."}
          </button>
          <button onClick={laden}>Aktualisieren</button>
        </div>
      </div>

      <div className="analytics-stats">
        <div><span>Umsatz</span><strong>{formatCents(daten?.gesamt_cent ?? 0)}</strong></div>
        <div><span>Verkäufe</span><strong>{daten?.anzahl_verkaeufe ?? 0}</strong></div>
        <div><span>Schnitt</span><strong>{formatCents(durchschnitt)}</strong></div>
      </div>

      {daten && (
        <>
          <div className="item-filter">
            <button className={!selectedItem ? "on" : ""} onClick={() => setSelectedItem(null)}>Alle</button>
            {daten.top_artikel.map((item, index) => (
              <button
                key={item.bezeichnung}
                className={selectedItem === item.bezeichnung ? "on" : ""}
                onClick={() => setSelectedItem(selectedItem === item.bezeichnung ? null : item.bezeichnung)}
              >
                <span className="legend-dot" style={{ background: COLORS[index % COLORS.length] }} />
                {item.bezeichnung}
                <span className="item-count">{item.menge}x</span>
              </button>
            ))}
          </div>
          <Chart daten={daten} selectedItem={selectedItem} />
        </>
      )}

      <div className="section-title">Verkaufsliste</div>
      <table className="tabelle">
        <thead><tr><th>Zeit</th><th>Beleg</th><th>Artikel</th><th>Zahlung</th><th className="num">Gesamt</th></tr></thead>
        <tbody>
          {gefilterteVerkaeufe.map((v) => (
            <tr key={v.id}>
              <td className="mono">{zeit(v.zeitpunkt)}</td>
              <td><strong>{v.belegnummer}</strong></td>
              <td>{itemText(v.items)}</td>
              <td>{v.zahlung}</td>
              <td className="num">{formatCents(v.gesamt_cent)}</td>
            </tr>
          ))}
          {gefilterteVerkaeufe.length === 0 && <tr><td colSpan={5} style={{ color: "var(--muted)" }}>Keine passenden Verkäufe im Zeitraum.</td></tr>}
        </tbody>
      </table>
    </section>
  );
}
