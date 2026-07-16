import { useEffect, useMemo, useState } from "react";
import {
  api, ApiError, euroToCents, formatCents,
  type Artikel, type Berechnung, type Kassenprofil, type Kategorie, type Pfandart,
  type Veranstaltung, type Verkauf as V, type Zahlungsmethode,
} from "../api";

export function Verkauf({ profil }: { profil: Kassenprofil }) {
  const [kategorien, setKategorien] = useState<Kategorie[]>([]);
  const [artikel, setArtikel] = useState<Artikel[]>([]);
  const [pfandarten, setPfandarten] = useState<Pfandart[]>([]);
  const [zahlarten, setZahlarten] = useState<Zahlungsmethode[]>([]);
  const [events, setEvents] = useState<Veranstaltung[]>([]);

  const [katFilter, setKatFilter] = useState<number | "alle">("alle");
  const [warenkorb, setWarenkorb] = useState<Record<number, number>>({});
  const [pfandRueck, setPfandRueck] = useState<Record<number, number>>({});
  const [eventId, setEventId] = useState<number | "">("");
  const [berech, setBerech] = useState<Berechnung | null>(null);

  const [zahlId, setZahlId] = useState<number | null>(null);
  const [gegeben, setGegeben] = useState("");
  const [busy, setBusy] = useState(false);
  const [fehler, setFehler] = useState<string | null>(null);
  const [erfolg, setErfolg] = useState<V | null>(null);
  const [zeigePfand, setZeigePfand] = useState(false);

  const artById = useMemo(() => new Map(artikel.map((a) => [a.id, a])), [artikel]);

  useEffect(() => {
    setFehler(null); setWarenkorb({}); setPfandRueck({}); setBerech(null); setErfolg(null);
    Promise.all([
      api.kategorien(profil.id), api.artikel(profil.id), api.pfandarten(profil.id),
      api.zahlungsmethoden(profil.id), api.veranstaltungen(profil.id),
    ]).then(([k, a, p, z, ev]) => {
      setKategorien(k.filter((x) => x.aktiv));
      setArtikel(a.filter((x) => x.aktiv && !x.archiviert));
      setPfandarten(p.filter((x) => x.aktiv && x.rueckgabe_erlaubt));
      setZahlarten(z.filter((x) => x.aktiv));
      setEvents(ev.filter((x) => x.status === "aktiv"));
      setZahlId((z.find((x) => x.aktiv)?.id) ?? null);
    }).catch((e) => setFehler(e instanceof ApiError ? e.message : "Fehler beim Laden."));
  }, [profil.id]);

  const artikelItems = useMemo(
    () => Object.entries(warenkorb).filter(([, m]) => m > 0).map(([id, m]) => ({ artikel_id: Number(id), menge: m })),
    [warenkorb],
  );
  const pfandItems = useMemo(
    () => Object.entries(pfandRueck).filter(([, m]) => m > 0).map(([id, m]) => ({ pfandart_id: Number(id), menge: m })),
    [pfandRueck],
  );

  useEffect(() => {
    if (artikelItems.length === 0 && pfandItems.length === 0) { setBerech(null); return; }
    let aktiv = true;
    api.berechnung({
      kassenprofil_id: profil.id, veranstaltung_id: eventId === "" ? null : eventId,
      artikel: artikelItems, pfand_rueckgaben: pfandItems,
    }).then((b) => { if (aktiv) setBerech(b); }).catch(() => { /* Anzeige bleibt */ });
    return () => { aktiv = false; };
  }, [artikelItems, pfandItems, eventId, profil.id]);

  const sichtbar = katFilter === "alle" ? artikel : artikel.filter((a) => a.kategorie_id === katFilter);
  const zahlart = zahlarten.find((z) => z.id === zahlId) ?? null;
  const gesamt = berech?.gesamt_cent ?? 0;
  const gegebenCent = euroToCents(gegeben);
  const rueckgeld = zahlart?.rueckgeld_berechnen && gegebenCent !== null && gegebenCent >= gesamt ? gegebenCent - gesamt : null;

  function plus(id: number) { setWarenkorb((w) => ({ ...w, [id]: (w[id] ?? 0) + 1 })); }
  function setMenge(id: number, n: number) {
    setWarenkorb((w) => { const c = { ...w }; if (n <= 0) delete c[id]; else c[id] = n; return c; });
  }
  function setRueck(id: number, n: number) {
    setPfandRueck((p) => { const c = { ...p }; if (n <= 0) delete c[id]; else c[id] = n; return c; });
  }
  function leeren() { setWarenkorb({}); setPfandRueck({}); setGegeben(""); setFehler(null); }

  async function abschliessen() {
    if (!zahlart) { setFehler("Zahlungsart wählen."); return; }
    if (zahlart.rueckgeld_berechnen && gegebenCent !== null && gegebenCent < gesamt) { setFehler("Gegebener Betrag ist zu gering."); return; }
    setBusy(true); setFehler(null);
    try {
      const v = await api.verkaufAbschluss({
        kassenprofil_id: profil.id, veranstaltung_id: eventId === "" ? null : eventId,
        artikel: artikelItems, pfand_rueckgaben: pfandItems,
        zahlungsmethode_id: zahlart.id,
        gegeben_cent: zahlart.rueckgeld_berechnen && gegebenCent !== null ? gegebenCent : null,
      });
      setErfolg(v); leeren();
    } catch (e) { setFehler(e instanceof ApiError ? e.message : "Abschluss fehlgeschlagen."); }
    finally { setBusy(false); }
  }

  if (fehler && artikel.length === 0) return <p className="login-error">{fehler}</p>;

  return (
    <section className="pos-layout">
      <div className="pos-artikel">
        <div className="kat-filter">
          <button className={`chip ${katFilter === "alle" ? "on" : ""}`} onClick={() => setKatFilter("alle")}>Alle</button>
          {kategorien.map((k) => (
            <button key={k.id} className={`chip ${katFilter === k.id ? "on" : ""}`} onClick={() => setKatFilter(k.id)}
              style={katFilter === k.id && k.farbe ? { background: k.farbe, borderColor: k.farbe, color: "#fff" } : undefined}>
              {k.name}
            </button>
          ))}
        </div>
        <div className="kachel-grid">
          {sichtbar.map((a) => (
            <button key={a.id} className="artikel-kachel" onClick={() => plus(a.id)}>
              <span className="kachel-name">{a.name}</span>
              <span className="kachel-preis">{formatCents(a.preis_cent)}</span>
            </button>
          ))}
          {sichtbar.length === 0 && <p style={{ color: "var(--muted)" }}>Keine Artikel in dieser Kategorie.</p>}
        </div>
      </div>

      <aside className="pos-korb">
        {events.length > 0 && (
          <label className="korb-event">Veranstaltung
            <select value={eventId} onChange={(e) => setEventId(e.target.value === "" ? "" : Number(e.target.value))}>
              <option value="">– ohne –</option>
              {events.map((ev) => <option key={ev.id} value={ev.id}>{ev.name}</option>)}
            </select>
          </label>
        )}

        <div className="korb-liste">
          {artikelItems.length === 0 && pfandItems.length === 0 && (
            <p style={{ color: "var(--muted)" }}>Warenkorb ist leer. Artikel antippen.</p>
          )}
          {Object.entries(warenkorb).filter(([, m]) => m > 0).map(([id, m]) => {
            const a = artById.get(Number(id));
            if (!a) return null;
            return (
              <div key={id} className="korb-zeile">
                <span className="korb-name">{a.name}</span>
                <span className="stepper">
                  <button onClick={() => setMenge(a.id, m - 1)}>−</button>
                  <span>{m}</span>
                  <button onClick={() => setMenge(a.id, m + 1)}>+</button>
                </span>
                <span className="korb-summe">{formatCents(a.preis_cent * m)}</span>
              </div>
            );
          })}
          {pfandItems.map((pi) => {
            const p = pfandarten.find((x) => x.id === pi.pfandart_id);
            return (
              <div key={`r${pi.pfandart_id}`} className="korb-zeile" style={{ color: "var(--accent)" }}>
                <span className="korb-name">Pfand zurück: {p?.name}</span>
                <span className="stepper">
                  <button onClick={() => setRueck(pi.pfandart_id, pi.menge - 1)}>−</button>
                  <span>{pi.menge}</span>
                  <button onClick={() => setRueck(pi.pfandart_id, pi.menge + 1)}>+</button>
                </span>
                <span className="korb-summe">−{formatCents((p?.betrag_cent ?? 0) * pi.menge).replace("-", "")}</span>
              </div>
            );
          })}
        </div>

        {pfandarten.length > 0 && (
          <div className="pfand-rueck">
            <button className="btn btn-sm" onClick={() => setZeigePfand((v) => !v)}>{zeigePfand ? "Pfandrückgabe schließen" : "Pfand zurücknehmen"}</button>
            {zeigePfand && (
              <div className="row" style={{ flexWrap: "wrap", gap: 8, marginTop: 8 }}>
                {pfandarten.map((p) => (
                  <button key={p.id} className="chip" onClick={() => setRueck(p.id, (pfandRueck[p.id] ?? 0) + 1)}>
                    + {p.name} ({formatCents(p.betrag_cent)})
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        <div className="korb-summen">
          <div className="row" style={{ justifyContent: "space-between" }}><span>Waren</span><span>{formatCents(berech?.waren_cent ?? 0)}</span></div>
          {(berech?.pfand_cent ?? 0) !== 0 && (
            <div className="row" style={{ justifyContent: "space-between" }}><span>Pfand</span><span>{formatCents(berech?.pfand_cent ?? 0)}</span></div>
          )}
          <div className="row korb-gesamt" style={{ justifyContent: "space-between" }}><span>Gesamt</span><span>{formatCents(gesamt)}</span></div>
        </div>

        <div className="zahl-wahl">
          {zahlarten.map((z) => (
            <button key={z.id} className={`btn ${zahlId === z.id ? "btn-primary" : ""}`} onClick={() => setZahlId(z.id)}>{z.name}</button>
          ))}
        </div>

        {zahlart?.rueckgeld_berechnen && (
          <div className="bar-zahlung">
            <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
              {[500, 1000, 2000, 5000].map((c) => (
                <button key={c} className="chip" onClick={() => setGegeben((c / 100).toFixed(2).replace(".", ","))}>{formatCents(c)}</button>
              ))}
              <button className="chip" onClick={() => setGegeben((gesamt / 100).toFixed(2).replace(".", ","))}>Passend</button>
            </div>
            <label style={{ marginTop: 8 }}>Gegeben (€)
              <input value={gegeben} onChange={(e) => setGegeben(e.target.value)} inputMode="decimal" placeholder="z. B. 20,00" />
            </label>
            {rueckgeld !== null && <div className="rueckgeld">Rückgeld: <strong>{formatCents(rueckgeld)}</strong></div>}
          </div>
        )}

        {fehler && <p className="login-error">{fehler}</p>}

        <div className="row" style={{ gap: 10, marginTop: 8 }}>
          <button className="btn" onClick={leeren} disabled={busy}>Leeren</button>
          <button className="btn btn-primary" style={{ flex: 1 }} disabled={busy || gesamt === 0 && pfandItems.length === 0} onClick={abschliessen}>
            Kassieren · {formatCents(gesamt)}
          </button>
        </div>

        {erfolg && (
          <div className="verkauf-ok">
            <div><strong>Beleg {erfolg.belegnummer}</strong> abgeschlossen</div>
            {erfolg.zahlung && erfolg.zahlung.rueckgeld_cent > 0 && (
              <div className="rueckgeld-gross">Rückgeld {formatCents(erfolg.zahlung.rueckgeld_cent)}</div>
            )}
            <button className="btn btn-sm" onClick={() => api.nachdruck(erfolg.id)}>Bon nachdrucken</button>
          </div>
        )}
      </aside>
    </section>
  );
}
