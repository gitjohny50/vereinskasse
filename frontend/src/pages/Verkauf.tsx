import { useEffect, useMemo, useRef, useState, type CSSProperties, type PointerEvent, type ReactNode } from "react";
import {
  api, ApiError, euroToCents, formatCents,
  type Artikel, type Berechnung, type Kassenprofil, type Kategorie, type Pfandart,
  type Verkauf as V, type Zahlungsmethode,
} from "../api";

type CheckoutStep = "pfand-frage" | "pfand-auswahl" | "zahlung" | "bar";

export function Verkauf({ profil }: { profil: Kassenprofil }) {
  const [kategorien, setKategorien] = useState<Kategorie[]>([]);
  const [artikel, setArtikel] = useState<Artikel[]>([]);
  const [pfandarten, setPfandarten] = useState<Pfandart[]>([]);
  const [zahlarten, setZahlarten] = useState<Zahlungsmethode[]>([]);

  const [katFilter, setKatFilter] = useState<number | "alle">("alle");
  const [warenkorb, setWarenkorb] = useState<Record<number, number>>({});
  const [pfandRueck, setPfandRueck] = useState<Record<number, number>>({});
  const [berech, setBerech] = useState<Berechnung | null>(null);

  const [zahlId, setZahlId] = useState<number | null>(null);
  const [gegeben, setGegeben] = useState("");
  const [busy, setBusy] = useState(false);
  const [fehler, setFehler] = useState<string | null>(null);
  const [erfolg, setErfolg] = useState<V | null>(null);
  const [checkoutOpen, setCheckoutOpen] = useState(false);
  const [checkoutStep, setCheckoutStep] = useState<CheckoutStep>("pfand-frage");
  const [korbScroll, setKorbScroll] = useState({ show: false, top: 0, height: 100 });
  const korbListeRef = useRef<HTMLDivElement | null>(null);
  const sliderDrag = useRef(false);

  const artById = useMemo(() => new Map(artikel.map((a) => [a.id, a])), [artikel]);
  const katById = useMemo(() => new Map(kategorien.map((k) => [k.id, k])), [kategorien]);

  useEffect(() => {
    setFehler(null); setWarenkorb({}); setPfandRueck({}); setBerech(null); setErfolg(null);
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

  useEffect(() => {
    if (artikelItems.length === 0 && pfandItems.length === 0) { setBerech(null); return; }
    let aktiv = true;
    api.berechnung({
      kassenprofil_id: profil.id, veranstaltung_id: null,
      artikel: artikelItems, pfand_rueckgaben: pfandItems,
    }).then((b) => { if (aktiv) setBerech(b); }).catch(() => { /* Anzeige bleibt */ });
    return () => { aktiv = false; };
  }, [artikelItems, pfandItems, profil.id]);

  const sichtbar = katFilter === "alle" ? artikel : artikel.filter((a) => a.kategorie_id === katFilter);
  const zahlart = zahlarten.find((z) => z.id === zahlId) ?? null;
  const pfandAktiv = profil.pfand_aktiv !== false;
  const gesamt = berech?.gesamt_cent ?? 0;
  const gegebenCent = euroToCents(gegeben);
  const rueckgeld = zahlart?.rueckgeld_berechnen && gegebenCent !== null && gegebenCent >= gesamt ? gegebenCent - gesamt : null;
  const kannKassieren = !busy && (gesamt !== 0 || pfandItems.length > 0);
  const offenePositionen = artikelItems.reduce((sum, i) => sum + i.menge, 0) + pfandItems.reduce((sum, i) => sum + i.menge, 0);
  const cashPresets = useMemo(() => {
    const basis = [500, 1000, 2000, 5000];
    const gerundet = [500, 1000, 2000, 5000].find((v) => v >= gesamt);
    return Array.from(new Set([gesamt, gerundet, ...basis].filter((v): v is number => typeof v === "number" && v > 0))).sort((a, b) => a - b);
  }, [gesamt]);

  useEffect(() => {
    const frame = requestAnimationFrame(updateKorbScroll);
    window.addEventListener("resize", updateKorbScroll);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("resize", updateKorbScroll);
    };
  }, [warenkorb, pfandRueck, berech]);

  function plus(id: number) { setWarenkorb((w) => ({ ...w, [id]: (w[id] ?? 0) + 1 })); }
  function setMenge(id: number, n: number) {
    setWarenkorb((w) => { const c = { ...w }; if (n <= 0) delete c[id]; else c[id] = n; return c; });
  }
  function setRueck(id: number, n: number) {
    setPfandRueck((p) => { const c = { ...p }; if (n <= 0) delete c[id]; else c[id] = n; return c; });
  }
  function leeren() { setWarenkorb({}); setPfandRueck({}); setGegeben(""); setFehler(null); }
  function checkoutSchliessen() {
    setCheckoutOpen(false);
    setFehler(null);
  }
  function checkoutStarten() {
    setFehler(null);
    setCheckoutStep(pfandAktiv && pfandarten.length > 0 ? "pfand-frage" : "zahlung");
    setCheckoutOpen(true);
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
      setKorbScroll({ show: false, top: 0, height: 100 });
      return;
    }
    const height = Math.max(18, Math.min(96, (el.clientHeight / el.scrollHeight) * 100));
    const top = (el.scrollTop / max) * (100 - height);
    setKorbScroll({ show: true, top, height });
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
    if (!methode) { setFehler("Zahlungsart wählen."); return; }
    if (methode.rueckgeld_berechnen && gegebenCent !== null && gegebenCent < gesamt) { setFehler("Gegebener Betrag ist zu gering."); return; }
    setBusy(true); setFehler(null);
    try {
      const v = await api.verkaufAbschluss({
        kassenprofil_id: profil.id, veranstaltung_id: null,
        artikel: artikelItems, pfand_rueckgaben: pfandItems,
        zahlungsmethode_id: methode.id,
        gegeben_cent: methode.rueckgeld_berechnen && gegebenCent !== null ? gegebenCent : null,
      });
      setErfolg(v); setCheckoutOpen(false); setBerech(null); leeren();
    } catch (e) { setFehler(e instanceof ApiError ? e.message : "Abschluss fehlgeschlagen."); }
    finally { setBusy(false); }
  }

  function zahlungWaehlen(z: Zahlungsmethode) {
    setZahlId(z.id);
    setFehler(null);
    if (z.rueckgeld_berechnen) setCheckoutStep("bar");
    else abschliessen(z);
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

          <div className="checkout-actions">
            <button className="btn" data-tour="verkauf-leeren" onClick={leeren} disabled={busy}>Leeren</button>
            <button className="btn btn-primary kassieren-btn" data-tour="verkauf-kassieren" disabled={!kannKassieren} onClick={checkoutStarten}>
              Kassieren <span>{formatCents(gesamt)}</span>
            </button>
          </div>
        </div>

        {erfolg && (
          <div className="verkauf-ok" data-tour="verkauf-erfolg">
            <div><strong>Beleg {erfolg.belegnummer}</strong> abgeschlossen</div>
            {erfolg.zahlung && erfolg.zahlung.rueckgeld_cent > 0 && (
              <div className="rueckgeld-gross">Rückgeld {formatCents(erfolg.zahlung.rueckgeld_cent)}</div>
            )}
            <button className="btn btn-sm" onClick={() => api.belegDrucken(erfolg.id)}>Beleg drucken</button>
          </div>
        )}
      </aside>

      {checkoutOpen && (
        <div className="checkout-modal-backdrop">
          <div className="checkout-modal" role="dialog" aria-modal="true" aria-label="Kassieren">
            <div className="checkout-modal-head">
              <div>
                <div className="eyebrow">Kassieren</div>
                <strong>{formatCents(gesamt)}</strong>
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
                  <button type="button" className="checkout-choice primary-choice" onClick={() => { setPfandRueck({}); setCheckoutStep("zahlung"); }}>
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
                  <button type="button" className="btn btn-primary" onClick={() => setCheckoutStep("zahlung")}>Weiter zur Zahlung</button>
                </div>
              </div>
            )}

            {checkoutStep === "zahlung" && (
              <div className="checkout-step center-step" data-tour="verkauf-zahlung">
                <h2>Zahlungsart wählen</h2>
                <div className="payment-big-grid">
                  {zahlarten.map((z) => (
                    <button type="button" key={z.id} className="payment-big" disabled={busy} onClick={() => zahlungWaehlen(z)}>
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
              <div className="checkout-step center-step" data-tour="verkauf-bar">
                <h2>Wie viel Bargeld wurde gegeben?</h2>
                <div className="cash-total-display">
                  <span>Zu zahlen</span><strong>{formatCents(gesamt)}</strong>
                  <span>Gegeben</span><strong>{gegebenCent == null ? "–" : formatCents(gegebenCent)}</strong>
                </div>
                <div className="cash-presets modal-cash">
                  <button type="button" className="chip chip-strong" onClick={() => setBargeld(gesamt)}>Passend</button>
                  {cashPresets.map((c) => (
                    <button type="button" key={c} className="chip" onClick={() => setBargeld(c)}>{formatCents(c)}</button>
                  ))}
                </div>
                <div className="cash-adjust modal-cash-adjust">
                  {[100, 200, 500, 1000].map((c) => (
                    <button type="button" key={c} className="chip" onClick={() => addBargeld(c)}>+{formatCents(c)}</button>
                  ))}
                  <button type="button" className="chip" onClick={() => setGegeben("")}>C</button>
                </div>
                <label className="cash-manual">Manuell eingeben (€)
                  <input value={gegeben} onChange={(e) => setGegeben(e.target.value)} inputMode="decimal" placeholder="z. B. 20,00" />
                </label>
                {rueckgeld !== null && <div className="rueckgeld rueckgeld-modal">Rückgeld: <strong>{formatCents(rueckgeld)}</strong></div>}
                {gegebenCent === null && <p className="cash-hint">Ohne Eingabe wird passend kassiert.</p>}
                {fehler && <p className="login-error">{fehler}</p>}
                <div className="checkout-footer-actions">
                  <button type="button" className="btn" disabled={busy} onClick={() => setCheckoutStep("zahlung")}>Zurück</button>
                  <button type="button" className="btn btn-primary kassieren-btn" disabled={busy} onClick={() => abschliessen()}>
                    Kassieren <span>{formatCents(gesamt)}</span>
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

  function up() {
    if (offset < -62) onRemove();
    setOffset(0);
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
