import { useEffect, useState, useCallback } from "react";
import {
  api, ApiError, euroToCents, formatCents,
  type AbschlussArtikelResetResult, type AbschlussOffen, type AbschlussResetOptions, type Bericht, type KassenabschlussKopf as Kopf, type Kassenprofil,
} from "../api";

type UmfangTyp = "alle" | "kategorie" | "artikel" | "rest";

const DEFAULT_RESET_OPTIONS: AbschlussResetOptions = {
  belege_loeschen: true,
  abschluesse_loeschen: true,
  artikel_loeschen: true,
  pfandzuordnungen_loeschen: true,
  druckwarteschlange_loeschen: true,
  belegkreis_zuruecksetzen: true,
};

export function Kassenabschluss({ profil }: { profil: Kassenprofil }) {
  const [x, setX] = useState<Bericht | null>(null);
  const [offen, setOffen] = useState<AbschlussOffen | null>(null);
  const [liste, setListe] = useState<Kopf[]>([]);
  const [umfang, setUmfang] = useState<UmfangTyp>("alle");
  const [kategorieIds, setKategorieIds] = useState<number[]>([]);
  const [artikelIds, setArtikelIds] = useState<number[]>([]);
  const [anfang, setAnfang] = useState("");
  const [gezaehlt, setGezaehlt] = useState("");
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [fehler, setFehler] = useState<string | null>(null);
  const [erfolg, setErfolg] = useState<Bericht | null>(null);
  const [detail, setDetail] = useState<Bericht | null>(null);
  const [resetConfirm, setResetConfirm] = useState(false);
  const [resetText, setResetText] = useState("");
  const [resetResult, setResetResult] = useState<AbschlussArtikelResetResult | null>(null);
  const [resetOptions, setResetOptions] = useState<AbschlussResetOptions>(DEFAULT_RESET_OPTIONS);

  const anfangCent = euroToCents(anfang) ?? 0;
  const gezaehltCent = gezaehlt.trim() === "" ? null : euroToCents(gezaehlt);
  const kassensturzAktiv = umfang === "alle" || umfang === "rest";
  const erwartet = (x?.bar_cent ?? 0) + anfangCent;
  const differenz = gezaehltCent == null ? null : gezaehltCent - erwartet;
  const scopeGueltig = umfang === "alle" || umfang === "rest" || (umfang === "kategorie" && kategorieIds.length > 0) || (umfang === "artikel" && artikelIds.length > 0);
  const laden = useCallback(async () => {
    const [o, l] = await Promise.all([api.abschlussOffen(profil.id), api.abschluesse(profil.id)]);
    setOffen(o); setListe(l);
    if (scopeGueltig) {
      setX(await api.xBericht(profil.id, kassensturzAktiv ? anfangCent : 0, kassensturzAktiv ? gezaehltCent : null, {
        umfang_typ: umfang,
        kategorie_ids: kategorieIds,
        artikel_ids: artikelIds,
      }));
    }
  }, [anfangCent, gezaehltCent, kassensturzAktiv, profil.id, scopeGueltig, umfang, kategorieIds, artikelIds]);

  useEffect(() => {
    setFehler(null); setErfolg(null); setDetail(null); setConfirm(false);
    laden().catch((e) => setFehler(e instanceof ApiError ? e.message : "Fehler beim Laden."));
  }, [laden]);

  async function zAbschluss() {
    setBusy(true); setFehler(null);
    try {
      const z = await api.zAbschluss({
        kassenprofil_id: profil.id,
        umfang_typ: umfang,
        kategorie_ids: kategorieIds,
        artikel_ids: artikelIds,
        anfangsbestand_cent: kassensturzAktiv ? anfangCent : 0,
        gezaehlt_cent: kassensturzAktiv ? gezaehltCent : null,
      });
      setErfolg(z); setConfirm(false); setAnfang(""); setGezaehlt("");
      await laden();
    } catch (e) { setFehler(e instanceof ApiError ? e.message : "Abschluss fehlgeschlagen."); }
    finally { setBusy(false); }
  }

  async function artikeldatenZuruecksetzen() {
    if (resetText.trim().toUpperCase() !== "DATEN LOESCHEN") {
      setFehler('Bitte zur Sicherheit "DATEN LOESCHEN" eingeben.');
      return;
    }
    if (!Object.values(resetOptions).some(Boolean)) {
      setFehler("Bitte mindestens einen Datenbereich auswählen.");
      return;
    }
    setBusy(true); setFehler(null); setResetResult(null);
    try {
      const res = await api.abschlussArtikeldatenZuruecksetzen(profil.id, resetText, resetOptions);
      setResetResult(res); setResetConfirm(false); setResetText("");
      await laden();
    } catch (e) { setFehler(e instanceof ApiError ? e.message : "Artikeldaten konnten nicht zurückgesetzt werden."); }
    finally { setBusy(false); }
  }

  async function zeigeDetail(id: number) {
    try { setDetail(await api.abschlussDetail(id)); } catch (e) { setFehler(e instanceof ApiError ? e.message : "Detail nicht ladbar."); }
  }

  async function ladeCsv(id: number) {
    try {
      setFehler(null);
      await api.abschlussCsv(id);
    } catch (e) {
      setFehler(e instanceof ApiError ? e.message : "CSV konnte nicht heruntergeladen werden.");
    }
  }

  function setResetOption<K extends keyof AbschlussResetOptions>(key: K, value: AbschlussResetOptions[K]) {
    setResetOptions((alt) => {
      const next = { ...alt, [key]: value };
      if (key === "artikel_loeschen" && value) next.pfandzuordnungen_loeschen = true;
      if (key === "belege_loeschen" && !value) next.abschluesse_loeschen = false;
      if (key === "abschluesse_loeschen" && value) next.belege_loeschen = true;
      return next;
    });
  }

  function waehleUmfang(next: UmfangTyp) {
    setUmfang(next);
    setConfirm(false);
    if (next !== "kategorie") setKategorieIds([]);
    if (next !== "artikel") setArtikelIds([]);
  }

  function toggleId(liste: number[], id: number) {
    return liste.includes(id) ? liste.filter((x) => x !== id) : [...liste, id];
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

      {offen && (
        <div className="card" style={{ marginBottom: 18 }}>
          <div className="row" style={{ justifyContent: "space-between", alignItems: "baseline", gap: 12, flexWrap: "wrap" }}>
            <div>
              <div className="section-title">Noch offen</div>
              <p style={{ color: "var(--muted)", fontSize: 13, margin: "4px 0 0" }}>
                {offen.offen_gesamt.positionen === 0
                  ? "Alles abgeschlossen."
                  : `${offen.offen_gesamt.positionen} Positionen · ${offen.offen_gesamt.menge} Stück · ${formatCents(offen.offen_gesamt.umsatz_cent)}`}
              </p>
            </div>
            <button className="btn btn-sm" disabled={offen.offen_gesamt.positionen === 0} onClick={() => waehleUmfang("rest")}>Alle übrigen abschließen</button>
          </div>
          {offen.nach_kategorie.length > 0 && (
            <div className="row" style={{ gap: 8, flexWrap: "wrap", marginTop: 12 }}>
              {offen.nach_kategorie.map((k) => (
                <span key={k.kategorie_id ?? "pfand"} className="chip">
                  {k.name}: {k.menge} · {formatCents(k.umsatz_cent)}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {x && (
        <div className="card" style={{ marginBottom: 18 }}>
          <div className="row" style={{ justifyContent: "space-between", alignItems: "baseline" }}>
            <div className="section-title">Aktueller Stand (X-Bericht)</div>
            <span style={{ color: "var(--muted)", fontSize: 13 }}>{x.betroffene_belege || x.anzahl_verkaeufe} betroffene Belege</span>
          </div>

          <div className="row" style={{ gap: 8, flexWrap: "wrap", marginTop: 12 }}>
            {(["alle", "kategorie", "artikel", "rest"] as UmfangTyp[]).map((u) => (
              <button key={u} className={`chip ${umfang === u ? "on" : ""}`} onClick={() => waehleUmfang(u)}>
                {u === "alle" ? "Alle offenen" : u === "kategorie" ? "Nach Kategorie" : u === "artikel" ? "Nach Artikel" : "Rest"}
              </button>
            ))}
          </div>

          {umfang === "kategorie" && offen && (
            <div className="row" style={{ gap: 8, flexWrap: "wrap", marginTop: 10 }}>
              {offen.nach_kategorie.filter((k) => k.kategorie_id !== null).map((k) => (
                <button key={k.kategorie_id} className={`chip ${kategorieIds.includes(k.kategorie_id!) ? "on" : ""}`} onClick={() => setKategorieIds((ids) => toggleId(ids, k.kategorie_id!))}>
                  {k.name} · {formatCents(k.umsatz_cent)}
                </button>
              ))}
            </div>
          )}

          {umfang === "artikel" && offen && (
            <div className="row" style={{ gap: 8, flexWrap: "wrap", marginTop: 10 }}>
              {offen.nach_artikel.map((a) => (
                <button key={a.artikel_id} className={`chip ${artikelIds.includes(a.artikel_id) ? "on" : ""}`} onClick={() => setArtikelIds((ids) => toggleId(ids, a.artikel_id))}>
                  {a.bezeichnung} · {a.menge}× · {formatCents(a.umsatz_cent)}
                </button>
              ))}
            </div>
          )}

          <p style={{ color: "var(--muted)", fontSize: 13, margin: "10px 0 0" }}>
            Umfang: <strong>{x.umfang_beschreibung}</strong>
            {x.davon_teiloffen > 0 && <> · {x.davon_teiloffen} Belege danach noch teiloffen</>}
          </p>

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

          {kassensturzAktiv ? (
            <>
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
                    <span style={{ color: differenz === 0 ? "var(--ok, #2563eb)" : "var(--danger, #b3261e)" }}>
                      {differenz > 0 ? "+" : ""}{formatCents(differenz)}
                    </span>
                  </div>
                )}
              </div>
            </>
          ) : (
            <p style={{ color: "var(--muted)", fontSize: 13, marginTop: 14 }}>
              Produktgruppen-Abschlüsse enthalten nur Mengen und Umsätze. Der Bargeld-Kassensturz erfolgt beim Gesamt-/Rest-Abschluss.
            </p>
          )}

          {fehler && <p className="login-error" style={{ marginTop: 10 }}>{fehler}</p>}

          {!confirm ? (
            <div className="row" style={{ marginTop: 14 }}>
              <button className="btn btn-primary" disabled={x.anzahl_verkaeufe === 0 || !scopeGueltig} onClick={() => setConfirm(true)}>
                Z-Abschluss durchführen
              </button>
              {x.anzahl_verkaeufe === 0 && <span style={{ color: "var(--muted)", marginLeft: 10, alignSelf: "center" }}>Keine offenen Verkäufe.</span>}
              {!scopeGueltig && <span style={{ color: "var(--muted)", marginLeft: 10, alignSelf: "center" }}>Bitte Umfang auswählen.</span>}
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
              {erfolg.abschluss_id && (
                <div className="row" style={{ gap: 10 }}>
                  <button className="btn btn-sm" onClick={() => api.abschlussNachdruck(erfolg.abschluss_id!)}>Bericht nachdrucken</button>
                  <button className="btn btn-sm" onClick={() => ladeCsv(erfolg.abschluss_id!)}>CSV herunterladen</button>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      <div className="card" style={{ marginBottom: 18 }}>
        <div className="row" style={{ justifyContent: "space-between", alignItems: "baseline" }}>
          <div>
            <div className="section-title">Datenbank zurücksetzen</div>
            <p style={{ color: "var(--muted)", fontSize: 13, margin: "4px 0 0" }}>
              Für den Start nach einer abgeschlossenen Veranstaltung: ausgewählte Verkaufs-, Abschluss- und Stammdaten löschen.
              Belege lassen sich nur zurücksetzen, wenn vorher keine offenen Verkäufe mehr vorhanden sind.
            </p>
          </div>
        </div>

        {resetResult && (
          <div className="verkauf-ok" style={{ marginTop: 12 }}>
            <div>
              {resetResult.belege_geloescht} Belege gelöscht · {resetResult.abschluesse_geloescht} Abschlüsse gelöscht ·
              {" "}{resetResult.artikel_geloescht} Artikel gelöscht · {resetResult.pfandzuordnungen_geloescht} Pfandzuordnungen gelöscht ·
              {" "}{resetResult.druckauftraege_geloescht} Druckaufträge gelöscht
            </div>
            {resetResult.belegkreis_zurueckgesetzt && <div>Belegnummern starten beim nächsten Verkauf wieder bei 000001.</div>}
          </div>
        )}

        {!resetConfirm ? (
          <div className="row" style={{ marginTop: 14 }}>
            <button className="btn btn-danger" onClick={() => { setResetConfirm(true); setResetResult(null); }}>
              Datenbank zurücksetzen
            </button>
            <span style={{ color: "var(--muted)", fontSize: 13, alignSelf: "center" }}>
              Nur möglich, wenn keine offenen Verkäufe vorhanden sind.
            </span>
          </div>
        ) : (
          <div className="verkauf-ok" style={{ marginTop: 14, borderColor: "var(--danger)", background: "#fef2f2" }}>
            <div>
              Wähle aus, welche Daten wirklich gelöscht werden sollen. Bitte vorher den Z-Abschluss durchführen.
            </div>
            <div className="feld-grid" style={{ marginTop: 10 }}>
              <ResetOption
                label="Belege und Verkaufsdaten"
                text="löscht Belege, Positionen und Zahlungen"
                checked={resetOptions.belege_loeschen}
                onChange={(v) => setResetOption("belege_loeschen", v)}
              />
              <ResetOption
                label="Abschlüsse"
                text="löscht gespeicherte Z-Abschlüsse"
                checked={resetOptions.abschluesse_loeschen}
                onChange={(v) => setResetOption("abschluesse_loeschen", v)}
              />
              <ResetOption
                label="Artikel"
                text="löscht Artikeldaten aus diesem Profil"
                checked={resetOptions.artikel_loeschen}
                onChange={(v) => setResetOption("artikel_loeschen", v)}
              />
              <ResetOption
                label="Pfandzuordnungen"
                text="entfernt Pfand-Verknüpfungen an Artikeln"
                checked={resetOptions.pfandzuordnungen_loeschen}
                disabled={resetOptions.artikel_loeschen}
                onChange={(v) => setResetOption("pfandzuordnungen_loeschen", v)}
              />
              <ResetOption
                label="Druckwarteschlange"
                text="löscht alle Druckaufträge aus der Warteschlange"
                checked={resetOptions.druckwarteschlange_loeschen}
                onChange={(v) => setResetOption("druckwarteschlange_loeschen", v)}
              />
              <ResetOption
                label="Belegnummern zurücksetzen"
                text="nächster Beleg startet wieder bei 000001"
                checked={resetOptions.belegkreis_zuruecksetzen}
                onChange={(v) => setResetOption("belegkreis_zuruecksetzen", v)}
              />
            </div>
            <label style={{ maxWidth: 360 }}>
              Bestätigung
              <input value={resetText} onChange={(e) => setResetText(e.target.value)} placeholder="DATEN LOESCHEN" />
            </label>
            <div className="row" style={{ gap: 10 }}>
              <button className="btn btn-danger" disabled={busy || resetText.trim().toUpperCase() !== "DATEN LOESCHEN"} onClick={artikeldatenZuruecksetzen}>
                Ja, ausgewählte Daten löschen
              </button>
              <button className="btn" disabled={busy} onClick={() => { setResetConfirm(false); setResetText(""); setResetOptions(DEFAULT_RESET_OPTIONS); }}>Abbrechen</button>
            </div>
          </div>
        )}
      </div>

      <div className="section-title" style={{ marginBottom: 8 }}>Bisherige Abschlüsse</div>
      <table className="tabelle">
        <thead><tr><th>Nummer</th><th>Umfang</th><th>Zeitpunkt</th><th className="num">Verkäufe</th><th className="num">Gesamt</th><th className="num">Differenz</th><th className="num">Aktionen</th></tr></thead>
        <tbody>
          {liste.map((a) => (
            <tr key={a.id}>
              <td><strong>{a.nummer}</strong></td>
              <td>{a.umfang_beschreibung}</td>
              <td>{zeit(a.erstellt_am)}</td>
              <td className="num">{a.anzahl_verkaeufe}</td>
              <td className="num">{formatCents(a.gesamt_cent)}</td>
              <td className="num" style={{ color: a.differenz_cent && a.differenz_cent !== 0 ? "var(--danger, #b3261e)" : undefined }}>
                {a.differenz_cent == null ? "–" : `${a.differenz_cent > 0 ? "+" : ""}${formatCents(a.differenz_cent)}`}
              </td>
              <td className="num">
                <button className="btn btn-sm" onClick={() => zeigeDetail(a.id)}>Detail</button>
                <button className="btn btn-sm" onClick={() => ladeCsv(a.id)}>CSV</button>
                <button className="btn btn-sm" onClick={() => api.abschlussNachdruck(a.id)}>Nachdruck</button>
              </td>
            </tr>
          ))}
          {liste.length === 0 && <tr><td colSpan={7} style={{ color: "var(--muted)" }}>Noch keine Abschlüsse.</td></tr>}
        </tbody>
      </table>

      {detail && (
        <div className="card" style={{ marginTop: 16 }}>
          <div className="row" style={{ justifyContent: "space-between", alignItems: "baseline" }}>
            <div className="section-title">{detail.nummer} · {detail.umfang_beschreibung} · {zeit(detail.bis)}</div>
            <div className="row" style={{ gap: 10 }}>
              {detail.abschluss_id && <button className="btn btn-sm" onClick={() => ladeCsv(detail.abschluss_id!)}>CSV herunterladen</button>}
              <button className="btn btn-sm" onClick={() => setDetail(null)}>Schließen</button>
            </div>
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
                <span style={{ color: detail.differenz_cent === 0 ? "var(--ok, #2563eb)" : "var(--danger, #b3261e)" }}>
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

function ResetOption({
  label, text, checked, disabled, onChange,
}: { label: string; text: string; checked: boolean; disabled?: boolean; onChange: (checked: boolean) => void }) {
  return (
    <label className="row" style={{
      alignItems: "flex-start",
      gap: 10,
      padding: 12,
      border: "1px solid var(--line)",
      borderRadius: 8,
      background: disabled ? "#f8fafc" : "#fff",
      color: disabled ? "var(--muted)" : undefined,
    }}>
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
        style={{ width: 20, height: 20, marginTop: 2 }}
      />
      <span>
        <strong>{label}</strong>
        <span style={{ display: "block", color: "var(--muted)", fontSize: 13 }}>{text}</span>
      </span>
    </label>
  );
}
