import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties, type PointerEvent, type ReactNode } from "react";
import {
  api, ApiError, euroToCents, formatCents,
  type Artikel, type Berechnung, type Kassenprofil, type Kategorie, type Pfandart,
  type Verkauf as V, type Zahlungsmethode,
} from "../api";

type CheckoutStep = "pfand-frage" | "pfand-auswahl" | "zahlung" | "bar";

const EURO_STUECKELUNG = [5000, 2000, 1000, 500, 200, 100, 50, 20, 10, 5, 2, 1];
const BERECHNUNG_RETRY_DELAYS_MS = [120, 300];

function warten(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function istRetrybarerBerechnungsfehler(e: unknown): boolean {
  return !(e instanceof ApiError) || e.status === 429 || e.status >= 500;
}

async function berechnungMitRetry(payload: Parameters<typeof api.berechnung>[0]): Promise<Berechnung> {
  let letzterFehler: unknown;
  for (let versuch = 0; versuch <= BERECHNUNG_RETRY_DELAYS_MS.length; versuch += 1) {
    try {
      return await api.berechnung(payload);
    } catch (e) {
      letzterFehler = e;
      if (!istRetrybarerBerechnungsfehler(e) || versuch >= BERECHNUNG_RETRY_DELAYS_MS.length) break;
      await warten(BERECHNUNG_RETRY_DELAYS_MS[versuch]);
    }
  }
  throw letzterFehler;
}

async function abschlussMitRetry(payload: Parameters<typeof api.verkaufAbschluss>[0]): Promise<V> {
  let letzterFehler: unknown;
  for (let versuch = 0; versuch <= BERECHNUNG_RETRY_DELAYS_MS.length; versuch += 1) {
    try {
      return await api.verkaufAbschluss(payload);
    } catch (e) {
      letzterFehler = e;
      if (!istRetrybarerBerechnungsfehler(e) || versuch >= BERECHNUNG_RETRY_DELAYS_MS.length) break;
      await warten(BERECHNUNG_RETRY_DELAYS_MS[versuch]);
    }
  }
  throw letzterFehler;
}

export function Verkauf({ profil }: { profil: Kassenprofil }) {
  const [kategorien, setKategorien] = useState<Kategorie[]>([]);
  const [artikel, setArtikel] = useState<Artikel[]>([]);
  const [pfandarten, setPfandarten] = useState<Pfandart[]>([]);
  const [zahlarten, setZahlarten] = useState<Zahlungsmethode[]>([]);

  const [katFilter, setKatFilter] = useState<number | "alle">("alle");
  const [warenkorb, setWarenkorb] = useState<Record<number, number>>({});
  const [pfandRueck, setPfandRueck] = useState<Record<number, number>>({});
  const [berech, setBerech] = useState<Berechnung | null>(null);
  const [berechnungBusy, setBerechnungBusy] = useState(false);
  const [berechnungFehler, setBerechnungFehler] = useState<string | null>(null);

  const [zahlId, setZahlId] = useState<number | null>(null);
  const [gegeben, setGegeben] = useState("");
  const [busy, setBusy] = useState(false);
  const [belegDruckBusy, setBelegDruckBusy] = useState(false);
  const [fehler, setFehler] = useState<string | null>(null);
  const [erfolg, setErfolg] = useState<V | null>(null);
  const [checkoutOpen, setCheckoutOpen] = useState(false);
  const [checkoutStep, setCheckoutStep] = useState<CheckoutStep>("pfand-frage");
  const [korbScroll, setKorbScroll] = useState({ show: false, top: 0, height: 100 });
  const korbListeRef = useRef<HTMLDivElement | null>(null);
  const sliderDrag = useRef(false);
  const abschlussLaeuft = useRef(false);
  const berechnungSeq = useRef(0);
  const berechnungKeyRef = useRef<string | null>(null);
  const berechnungPromise = useRef<{ key: string; promise: Promise<Berechnung | null> } | null>(null);

  const artById = useMemo(() => new Map(artikel.map((a) => [a.id, a])), [artikel]);
  const katById = useMemo(() => new Map(kategorien.map((k) => [k.id, k])), [kategorien]);

  useEffect(() => {
    setFehler(null); setWarenkorb({}); setPfandRueck({}); setBerech(null); setBerechnungFehler(null); setErfolg(null);
    Promise.all([
      api.kategorien(profil.id), api.artikel(profil.id), api.pfandarten(profil.id),
      api.zahlungsmethoden(profil.id),
    ]).then(([k, a, p, z]) => {
      setKategorien(k.filter((x) => x.aktiv));
      setArtikel(a.filter((x) => x.aktiv && !x.archiviert));
      setPfandarten(p.filter((x) => x.aktiv && x.rueckgabe_erlaubt));
      setZahlarten(z.filter((x) => x.aktiv));
      setZahlId((z.find((x) => x.aktiv)?.id) ?? null);
    }).catch((e) => setFehler(e instanceof ApiError ? e.message : "Fehler beim Laden."));
  }, [profil.id]);
  useEffect(() => {
    if (!profil.pfand_aktiv) setPfandRueck({});
  }, [profil.pfand_aktiv]);

  const artikelItems = useMemo(
    () => Object.entries(warenkorb).filter(([, m]) => m > 0).map(([id, m]) => ({ artikel_id: Number(id), menge: m })),
    [warenkorb],
  );
  const pfandItems = useMemo(
    () => profil.pfand_aktiv ? Object.entries(pfandRueck).filter(([, m]) => m > 0).map(([id, m]) => ({ pfandart_id: Number(id), menge: m })) : [],
    [pfandRueck, profil.pfand_aktiv],
  );

  const sichtbar = katFilter === "alle" ? artikel : artikel.filter((a) => a.kategorie_id === katFilter);
  const zahlart = zahlarten.find((z) => z.id === zahlId) ?? null;
  const pfandAktiv = profil.pfand_aktiv !== false;
  const hatPositionen = artikelItems.length > 0 || pfandItems.length > 0;
  const berechnungPayload = useMemo(() => ({
    kassenprofil_id: profil.id, veranstaltung_id: null,
    artikel: artikelItems, pfand_rueckgaben: pfandItems,
  }), [artikelItems, pfandItems, profil.id]);
  const berechnungKey = useMemo(() => JSON.stringify(berechnungPayload), [berechnungPayload]);
  const berechnungAktuell = berech !== null && berechnungKeyRef.current === berechnungKey;
  const gesamt = berech?.gesamt_cent ?? 0;
  const gegebenCent = euroToCents(gegeben);
  const kannKassieren = !busy && hatPositionen;
  const sichtbarerBerechnungFehler = berechnungFehler && !berechnungBusy && !berechnungAktuell ? berechnungFehler : null;
  const offenePositionen = artikelItems.reduce((sum, i) => sum + i.menge, 0) + pfandItems.reduce((sum, i) => sum + i.menge, 0);
  const cashPresets = useMemo(() => {
    const basis = [500, 1000, 2000, 5000];
    const naechsterSchein = [500, 1000, 2000, 5000, 10000].find((v) => v >= gesamt);
    const naechsterZehner = Math.ceil(gesamt / 1000) * 1000;
    return Array.from(new Set([gesamt, naechsterZehner, naechsterSchein, ...basis].filter((v): v is number => typeof v === "number" && v >= gesamt && v > 0))).sort((a, b) => a - b);
  }, [gesamt]);
  const gegebenAnzeige = gegebenCent === null ? gesamt : gegebenCent;
  const rueckgeldAnzeige = zahlart?.rueckgeld_berechnen && gegebenAnzeige >= gesamt ? gegebenAnzeige - gesamt : 0;
  const rueckgeldAnzeigeStueckelung = useMemo(() => berechneStueckelung(rueckgeldAnzeige), [rueckgeldAnzeige]);
  const nochOffen = gegebenCent !== null && gegebenCent < gesamt ? gesamt - gegebenCent : 0;

  const berechnungLaden = useCallback(async (): Promise<Berechnung | null> => {
    if (!hatPositionen) return null;
    if (berechnungAktuell) return berech;
    if (berechnungPromise.current?.key === berechnungKey) return berechnungPromise.current.promise;

    const seq = ++berechnungSeq.current;
    setBerechnungBusy(true);
    setBerechnungFehler(null);
    const promise = berechnungMitRetry(berechnungPayload).then((b) => {
      if (seq === berechnungSeq.current) {
        berechnungKeyRef.current = berechnungKey;
        setBerech(b);
      }
      return b;
    }).catch((e) => {
      const meldung = e instanceof ApiError ? e.message : "Berechnung fehlgeschlagen.";
      if (seq === berechnungSeq.current) {
        setBerechnungFehler(meldung);
      }
      return null;
    }).finally(() => {
      if (seq === berechnungSeq.current) setBerechnungBusy(false);
      if (berechnungPromise.current?.key === berechnungKey) berechnungPromise.current = null;
    });
    berechnungPromise.current = { key: berechnungKey, promise };
    return promise;
  }, [berech, berechnungAktuell, berechnungKey, berechnungPayload, hatPositionen]);

  useEffect(() => {
    if (!hatPositionen) {
      berechnungSeq.current += 1;
      berechnungKeyRef.current = null;
      berechnungPromise.current = null;
      setBerech(null);
      setBerechnungBusy(false);
      setBerechnungFehler(null);
      return;
    }
    void berechnungLaden();
  }, [berechnungKey, berechnungLaden, hatPositionen]);

  useEffect(() => {
    const frame = requestAnimationFrame(updateKorbScroll);
    window.addEventListener("resize", updateKorbScroll);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("resize", updateKorbScroll);
    };
  }, [warenkorb, pfandRueck, berech]);

  function warenkorbGeaendert() {
    setFehler(null);
    setBerechnungFehler(null);
    setGegeben("");
  }
  function plus(id: number) {
    warenkorbGeaendert();
    setWarenkorb((w) => ({ ...w, [id]: (w[id] ?? 0) + 1 }));
  }
  function setMenge(id: number, n: number) {
    warenkorbGeaendert();
    setWarenkorb((w) => { const c = { ...w }; if (n <= 0) delete c[id]; else c[id] = n; return c; });
  }
  function setRueck(id: number, n: number) {
    warenkorbGeaendert();
    setPfandRueck((p) => { const c = { ...p }; if (n <= 0) delete c[id]; else c[id] = n; return c; });
  }
  function leeren() {
    setWarenkorb({});
    setPfandRueck({});
    setGegeben("");
    setFehler(null);
    setBerechnungFehler(null);
  }
  function checkoutSchliessen() {
    setCheckoutOpen(false);
    setFehler(null);
  }
  async function checkoutStarten() {
    if (!hatPositionen) return;
    const aktuelleBerechnung = await berechnungLaden();
    if (!aktuelleBerechnung) { setFehler("Summe konnte nicht berechnet werden."); return; }
    if (aktuelleBerechnung.gesamt_cent === 0 && pfandItems.length === 0) { setFehler("Summe ist 0,00 €."); return; }
    setFehler(null);
    setCheckoutOpen(true);
    if (pfandAktiv && pfandarten.length > 0) setCheckoutStep("pfand-frage");
    else weiterZurZahlung();
  }
  function weiterZurZahlung() {
    setFehler(null);
    if (zahlarten.length === 1) {
      zahlungWaehlen(zahlarten[0]);
      return;
    }
    setCheckoutStep("zahlung");
  }
  function setBargeld(cents: number) { setGegeben((cents / 100).toFixed(2).replace(".", ",")); }
  function addBargeld(cents: number) {
    const aktuell = euroToCents(gegeben) ?? 0;
    setBargeld(aktuell + cents);
  }
  function artikelFarbe(a: Artikel) {
    return a.kategorie_id ? katById.get(a.kategorie_id)?.farbe || "var(--accent)" : "var(--accent)";
  }
  
  function updateKorbScroll() {
    const el = korbListeRef.current;
    if (!el) return;
    const max = el.scrollHeight - el.clientHeight;
    
    if (max <= 4) {
      setKorbScroll((s) => !s.show ? s : { show: false, top: 0, height: 100 });
      return;
    }
    
    const height = Math.max(18, Math.min(96, (el.clientHeight / el.scrollHeight) * 100));
    const top = (el.scrollTop / max) * (100 - height);
    
    setKorbScroll((s) => (s.show && s.top === top && s.height === height) ? s : { show: true, top, height });
  }

  function sliderToScroll(e: PointerEvent<HTMLDivElement>) {
    const el = korbListeRef.current;
    if (!el) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const pct = Math.max(0, Math.min(1, (e.clientY - rect.top) / rect.height));
    el.scrollTop = pct * (el.scrollHeight - el.clientHeight);
    updateKorbScroll();
  }
  function sliderDown(e: PointerEvent<HTMLDivElement>) {
    sliderDrag.current = true;
    e.currentTarget.setPointerCapture(e.pointerId);
    sliderToScroll(e);
  }
  function sliderMove(e: PointerEvent<HTMLDivElement>) {
    if (sliderDrag.current) sliderToScroll(e);
  }
  function sliderUp() {
    sliderDrag.current = false;
  }

  async function abschliessen(methode: Zahlungsmethode | null = zahlart) {
    if (abschlussLaeuft.current) return;
    if (!methode) { setFehler("Zahlungsart wählen."); return; }
    abschlussLaeuft.current = true;
    setBusy(true); setFehler(null);
    try {
      const aktuelleBerechnung = await berechnungLaden();
      if (!aktuelleBerechnung) { setFehler("Summe konnte nicht berechnet werden."); return; }
      if (aktuelleBerechnung.gesamt_cent === 0 && pfandItems.length === 0) { setFehler("Summe ist 0,00 €."); return; }
      if (methode.rueckgeld_berechnen && gegebenCent !== null && gegebenCent < aktuelleBerechnung.gesamt_cent) { setFehler("Gegebener Betrag ist zu gering."); return; }
      const v = await abschlussMitRetry({
        kassenprofil_id: profil.id, veranstaltung_id: null,
        artikel: artikelItems, pfand_rueckgaben: pfandItems,
        zahlungsmethode_id: methode.id,
        gegeben_cent: methode.rueckgeld_berechnen && gegebenCent !== null ? gegebenCent : null,
      });
      setErfolg(v); setCheckoutOpen(false); setBerech(null); leeren();
    } catch (e) { setFehler(e instanceof ApiError ? e.message : "Abschluss fehlgeschlagen."); }
    finally {
      abschlussLaeuft.current = false;
      setBusy(false);
    }
  }

  function zahlungWaehlen(z: Zahlungsmethode) {
    setZahlId(z.id);
    setFehler(null);
    if (z.rueckgeld_berechnen) setCheckoutStep("bar");
    else void abschliessen(z);
  }
  async function belegDrucken() {
    if (!erfolg || belegDruckBusy) return;
    setBelegDruckBusy(true);
    setFehler(null);
    try {
      await api.belegDrucken(erfolg.id);
    } catch (e) {
      setFehler(e instanceof ApiError ? e.message : "Belegdruck fehlgeschlagen.");
    } finally {
      setBelegDruckBusy(false);
    }
  }

  if (fehler && artikel.length === 0) return <p className="login-error">{fehler}</p>;

  return (
    <section className="pos-layout">
      <div className="pos-artikel">
        <div className="kat-filter" data-tour="verkauf-kategorien">
          <button className={`chip ${katFilter === "alle" ? "on" : ""}`} onClick={() => setKatFilter("alle")}>Alle</button>
          {kategorien.map((k) => (
            <button key={k.id} className={`chip ${katFilter === k.id ? "on" : ""}`} onClick={() => setKatFilter(k.id)}
              style={katFilter === k.id && k.farbe ? { background: k.farbe, borderColor: k.farbe, color: "#fff" } : undefined}>
              {k.farbe && <span className="chip-dot" style={{ background: k.farbe }} />}
              {k.name}
            </button>
          ))}
        </div>
        <div className="kachel-grid" data-tour="verkauf-kacheln">
          {sichtbar.map((a) => {
            const menge = warenkorb[a.id] ?? 0;
            const kat = a.kategorie_id ? katById.get(a.kategorie_id) : null;
            return (
              <button key={a.id} className={`artikel-kachel ${menge > 0 ? "im-korb" : ""}`} onClick={() => plus(a.id)}
                style={{ "--tile-color": artikelFarbe(a) } as CSSProperties}>
                <span className="kachel-akzent" />
                {menge > 0 && <span className="kachel-menge">{menge}</span>}
                <span className="kachel-name">{a.name}</span>
                {kat && <span className="kachel-kat">{kat.name}</span>}
                <span className="kachel-preis">{formatCents(a.preis_cent)}</span>
              </button>
            );
          })}
          {sichtbar.length === 0 && <p style={{ color: "var(--muted)" }}>Keine Artikel in dieser Kategorie.</p>}
        </div>
      </div>

      <aside className="pos-korb">
        <div className="korb-list-wrap" data-tour="verkauf-warenkorb">
          <div className="korb-liste" ref={korbListeRef} onScroll={updateKorbScroll}>
            {artikelItems.length === 0 && pfandItems.length === 0 && (
              <p style={{ color: "var(--muted)" }}>Warenkorb ist leer. Artikel antippen.</p>
            )}
            {Object.entries(warenkorb).filter(([, m]) => m > 0).map(([id, m]) => {
              const a = artById.get(Number(id));
              if (!a) return null;
              return (
                <SwipeKorbZeile key={id} onRemove={() => setMenge(a.id, 0)}>
                  <div className="korb-zeile">
                    <span className="korb-name">{a.name}</span>
                    <span className="stepper">
                      <button type="button" onClick={() => setMenge(a.id, m - 1)}>−</button>
                      <span>{m}</span>
                      <button type="button" onClick={() => setMenge(a.id, m + 1)}>+</button>
                    </span>
                    <span className="korb-summe">{formatCents(a.preis_cent * m)}</span>
                  </div>
                </SwipeKorbZeile>
              );
            })}
            {pfandItems.map((pi) => {
              const p = pfandarten.find((x) => x.id === pi.pfandart_id);
              return (
                <div key={`r${pi.pfandart_id}`} className="korb-zeile" style={{ color: "var(--accent)" }}>
                  <span className="korb-name">Pfand zurück: {p?.name}</span>
                  <span className="stepper">
                    <button type="button" onClick={() => setRueck(pi.pfandart_id, pi.menge - 1)}>−</button>
                    <span>{pi.menge}</span>
                    <button type="button" onClick={() => setRueck(pi.pfandart_id, pi.menge + 1)}>+</button>
                  </span>
                  <span className="korb-summe">−{formatCents((p?.betrag_cent ?? 0) * pi.menge).replace("-", "")}</span>
                </div>
              );
            })}
          </div>
          {korbScroll.show && (
            <div
              className="korb-slider"
              onPointerDown={sliderDown}
              onPointerMove={sliderMove}
              onPointerUp={sliderUp}
              onPointerCancel={sliderUp}
            >
              <span style={{ top: `${korbScroll.top}%`, height: `${korbScroll.height}%` }} />
            </div>
          )}
        </div>

        <div className="pos-checkout">
          <div className="korb-summen">
            <div className="row" style={{ justifyContent: "space-between" }}><span>Positionen</span><span>{offenePositionen}</span></div>
            <div className="row" style={{ justifyContent: "space-between" }}><span>Waren</span><span>{formatCents(berech?.waren_cent ?? 0)}</span></div>
            {(berech?.pfand_cent ?? 0) !== 0 && (
              <div className="row" style={{ justifyContent: "space-between" }}><span>Pfand</span><span>{formatCents(berech?.pfand_cent ?? 0)}</span></div>
            )}
            <div className="row korb-gesamt" style={{ justifyContent: "space-between" }}><span>Gesamt</span><span>{formatCents(gesamt)}</span></div>
          </div>

          {fehler && <p className="login-error">{fehler}</p>}
          {!fehler && sichtbarerBerechnungFehler && <p className="login-error">{sichtbarerBerechnungFehler}</p>}

          <div className="checkout-actions">
            <button className="btn" data-tour="verkauf-leeren" onClick={leeren} disabled={busy}>Leeren</button>
            <button className="btn btn-primary kassieren-btn" data-tour="verkauf-kassieren" disabled={!kannKassieren} onClick={checkoutStarten}>
              {berechnungBusy ? "Berechne…" : "Kassieren"} <span>{formatCents(gesamt)}</span>
            </button>
          </div>
        </div>

        {erfolg && (
          <div className="verkauf-ok" data-tour="verkauf-erfolg">
            <div><strong>Beleg {erfolg.belegnummer}</strong> abgeschlossen</div>
            {erfolg.zahlung && erfolg.zahlung.rueckgeld_cent > 0 && (
              <div className="rueckgeld-gross">Rückgeld {formatCents(erfolg.zahlung.rueckgeld_cent)}</div>
            )}
            <button className="btn btn-sm" disabled={belegDruckBusy} onClick={belegDrucken}>
              {belegDruckBusy ? "Drucke…" : "Beleg drucken"}
            </button>
          </div>
        )}
      </aside>

      {checkoutOpen && (
        <div className="checkout-modal-backdrop">
          <div className="checkout-modal" role="dialog" aria-modal="true" aria-label="Kassieren">
            <div className="checkout-modal-head">
              <div>
                <div className="eyebrow">Kassieren</div>
                <strong>{berechnungBusy ? "…" : formatCents(gesamt)}</strong>
              </div>
              <button type="button" className="btn btn-sm" onClick={checkoutSchliessen}>Schließen</button>
            </div>

            {checkoutStep === "pfand-frage" && (
              <div className="checkout-step center-step" data-tour="verkauf-pfand-rueckgabe">
                <h2>Pfand zurück?</h2>
                <p>{pfandItems.length > 0 ? `${pfandItems.length} Pfandpositionen sind bereits erfasst.` : "Soll Pfand zurückgenommen werden?"}</p>
                <div className="checkout-choice-grid">
                  <button type="button" className="checkout-choice" onClick={() => setCheckoutStep("pfand-auswahl")}>
                    <span>Ja</span><small>Pfand auswählen</small>
                  </button>
                  <button type="button" className="checkout-choice primary-choice" onClick={() => { setPfandRueck({}); weiterZurZahlung(); }}>
                    <span>Nein</span><small>Weiter zur Zahlung</small>
                  </button>
                </div>
              </div>
            )}

            {checkoutStep === "pfand-auswahl" && (
              <div className="checkout-step">
                <h2>Pfand auswählen</h2>
                <div className="pfand-big-grid">
                  {pfandarten.map((p) => (
                    <button type="button" key={p.id} className="pfand-big" onClick={() => setRueck(p.id, (pfandRueck[p.id] ?? 0) + 1)}>
                      <span>{p.name}</span>
                      <strong>{formatCents(p.betrag_cent)}</strong>
                      {(pfandRueck[p.id] ?? 0) > 0 && <b>{pfandRueck[p.id]}</b>}
                    </button>
                  ))}
                </div>
                {pfandItems.length > 0 && (
                  <div className="checkout-mini-list">
                    {pfandItems.map((pi) => {
                      const p = pfandarten.find((x) => x.id === pi.pfandart_id);
                      return (
                        <div key={pi.pfandart_id} className="korb-zeile">
                          <span className="korb-name">{p?.name}</span>
                          <span className="stepper">
                            <button type="button" onClick={() => setRueck(pi.pfandart_id, pi.menge - 1)}>−</button>
                            <span>{pi.menge}</span>
                            <button type="button" onClick={() => setRueck(pi.pfandart_id, pi.menge + 1)}>+</button>
                          </span>
                          <span className="korb-summe">−{formatCents((p?.betrag_cent ?? 0) * pi.menge).replace("-", "")}</span>
                        </div>
                      );
                    })}
                  </div>
                )}
                <div className="checkout-footer-actions">
                  <button type="button" className="btn" onClick={() => setCheckoutStep("pfand-frage")}>Zurück</button>
                  <button type="button" className="btn btn-primary" onClick={weiterZurZahlung}>Weiter zur Zahlung</button>
                </div>
              </div>
            )}

            {checkoutStep === "zahlung" && (
              <div className="checkout-step center-step" data-tour="verkauf-zahlung">
                <h2>Zahlungsart wählen</h2>
                <div className="payment-big-grid">
                  {zahlarten.map((z) => (
                    <button type="button" key={z.id} className="payment-big" disabled={busy || !kannKassieren} onClick={() => zahlungWaehlen(z)}>
                      <span>{z.name}</span>
                      <small>{z.rueckgeld_berechnen ? "Bargeld mit Rückgeld" : "Direkt kassieren"}</small>
                    </button>
                  ))}
                </div>
                <div className="checkout-footer-actions">
                  {pfandAktiv && pfandarten.length > 0 && <button type="button" className="btn" onClick={() => setCheckoutStep("pfand-frage")}>Zurück</button>}
                </div>
              </div>
            )}

            {checkoutStep === "bar" && (
              <div className="checkout-step cash-step" data-tour="verkauf-bar">
                <div className="cash-step-title">
                  <h2>Barzahlung</h2>
                </div>

                <div className="cash-flow">
                  <section className="cash-entry-panel">
                    <div className="cash-total-display">
                      <span>Zu zahlen</span><strong>{formatCents(gesamt)}</strong>
                      <span>Gegeben</span><strong>{formatCents(gegebenAnzeige)}</strong>
                    </div>

                    <div className="cash-section-label">Schnellwahl</div>
                    <div className="cash-presets modal-cash">
                      <button type="button" className="cash-choice exact" onClick={() => setBargeld(gesamt)}>
                        <span>Passend</span>
                        <strong>{formatCents(gesamt)}</strong>
                      </button>
                      {cashPresets.filter((c) => c !== gesamt).map((c) => (
                        <button type="button" key={c} className="cash-choice" onClick={() => setBargeld(c)}>{formatCents(c)}</button>
                      ))}
                    </div>

                    <div className="cash-section-label">Aufschlag</div>
                    <div className="cash-adjust modal-cash-adjust">
                      {[100, 200, 500, 1000].map((c) => (
                        <button type="button" key={c} className="chip" onClick={() => addBargeld(c)}>+{formatCents(c)}</button>
                      ))}
                      <button type="button" className="chip" onClick={() => setGegeben("")}>C</button>
                    </div>

                    <label className="cash-manual">Manuell eingeben (€)
                      <input value={gegeben} onChange={(e) => setGegeben(e.target.value)} inputMode="decimal" placeholder="z. B. 30,00" />
                    </label>
                  </section>

                  <section className="cash-change-panel">
                    <span>{nochOffen > 0 ? "Noch offen" : "Rückgeld"}</span>
                    <strong>{formatCents(nochOffen > 0 ? nochOffen : rueckgeldAnzeige)}</strong>
                    {nochOffen > 0 ? (
                      <div className="cash-change-note">Gegebener Betrag ist zu gering.</div>
                    ) : rueckgeldAnzeige > 0 ? (
                      <div className="stueckelung-grid" aria-label="Empfohlene Rückgeld-Stückelung">
                        {rueckgeldAnzeigeStueckelung.map((s) => (
                          <div key={s.wert} className={s.wert >= 500 ? "stueckelung-chip schein" : "stueckelung-chip muenze"}>
                            <span>{s.anzahl}×</span>
                            <strong>{formatCents(s.wert)}</strong>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="stueckelung-passend">Passend gegeben.</div>
                    )}
                  </section>
                </div>
                {fehler && <p className="login-error">{fehler}</p>}
                {!fehler && sichtbarerBerechnungFehler && <p className="login-error">{sichtbarerBerechnungFehler}</p>}
                <div className="checkout-footer-actions cash-footer-actions">
                  <button type="button" className="btn" disabled={busy} onClick={() => setCheckoutStep("zahlung")}>Zurück</button>
                  <button type="button" className="btn btn-primary kassieren-btn" disabled={busy || !kannKassieren} onClick={() => abschliessen()}>
                    {berechnungBusy ? "Berechne…" : "Kassieren"} <span>{formatCents(gesamt)}</span>
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  );
}

function berechneStueckelung(betragCent: number) {
  let rest = Math.max(0, betragCent);
  const result: { wert: number; anzahl: number }[] = [];
  for (const wert of EURO_STUECKELUNG) {
    const anzahl = Math.floor(rest / wert);
    if (anzahl > 0) {
      result.push({ wert, anzahl });
      rest -= anzahl * wert;
    }
  }
  return result;
}

function SwipeKorbZeile({ children, onRemove }: { children: ReactNode; onRemove: () => void }) {
  const startX = useRef<number | null>(null);
  const [offset, setOffset] = useState(0);

  function down(e: PointerEvent<HTMLDivElement>) {
    startX.current = e.clientX;
    e.currentTarget.setPointerCapture(e.pointerId);
  }

  function move(e: PointerEvent<HTMLDivElement>) {
    if (startX.current == null) return;
    const diff = e.clientX - startX.current;
    setOffset(Math.max(-96, Math.min(0, diff)));
  }

  function up(e: PointerEvent<HTMLDivElement>) {
    try {
      e.currentTarget.releasePointerCapture(e.pointerId);
    } catch (err) { /* Der Fehler beim Freigeben des Pointers ist hier nicht kritisch, die Geste wird trotzdem beendet. */ }

    if (offset < -62) {
      onRemove();
    } else {
      setOffset(0);
    }
    startX.current = null;
  }

  return (
    <div className="swipe-row">
      <div className="swipe-remove">Entfernen</div>
      <div
        className="swipe-content"
        onPointerDown={down}
        onPointerMove={move}
        onPointerUp={up}
        onPointerCancel={up}
        style={{ transform: `translateX(${offset}px)` }}
      >
        {children}
      </div>
    </div>
  );
}