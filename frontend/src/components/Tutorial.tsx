import { useCallback, useEffect, useMemo, useState } from "react";
import type { Session } from "../api";
import type { Tab } from "../App";

export const tutorialKey = (benutzerId: number) => `vk_tutorial_seen_${benutzerId}`;

type TourStep = {
  anchor: string | null;
  tab?: Tab;
  minStufe?: number;
  title: string;
  text: string;
};

type Rect = { top: number; left: number; width: number; height: number };

const STEPS: TourStep[] = [
  {
    anchor: null,
    title: "Willkommen bei der Vereinskasse",
    text: "Ich zeige dir in ein paar kurzen Schritten, wie du die Kasse bedienst. Du kannst jederzeit auf „Überspringen\" tippen. Bereit?",
  },
  {
    anchor: "kopfzeile",
    title: "Deine Kopfzeile",
    text: "Oben siehst du immer, in welchem Bereich du gerade bist. Rechts kannst du dich abmelden, und über die drei farbigen Punkte änderst du das Farbschema.",
  },
  {
    anchor: "reiterleiste",
    title: "Bereiche wechseln",
    text: "Über diese Reiter wechselst du zwischen den Bereichen. Sind nicht alle sichtbar, wische die Leiste einfach zur Seite.",
  },
  {
    anchor: "profilwahl",
    tab: "verkauf",
    title: "Aktive Kasse",
    text: "Falls es mehrere Kassen (Sortimente) gibt, wählst du hier aus, mit welcher du gerade arbeitest.",
  },
  {
    anchor: "verkauf-kategorien",
    tab: "verkauf",
    title: "Artikel filtern",
    text: "Tippe eine Kategorie an, um nur deren Artikel zu sehen. „Alle\" zeigt wieder alles.",
  },
  {
    anchor: "verkauf-kacheln",
    tab: "verkauf",
    title: "In den Warenkorb legen",
    text: "Tippe einen Artikel an, um ihn hinzuzufügen. Tippst du ihn mehrfach an, erhöht sich die Menge.",
  },
  {
    anchor: "verkauf-warenkorb",
    tab: "verkauf",
    title: "Der Warenkorb",
    text: "Hier steht, was gekauft wird. Mit − und + änderst du die Menge. Pfand wird, wenn hinterlegt, automatisch dazugerechnet.",
  },
  {
    anchor: "verkauf-pfand-rueckgabe",
    tab: "verkauf",
    title: "Pfand zurücknehmen",
    text: "Bringt ein Gast Leergut zurück? Tippe „Pfand zurücknehmen\" und wähle die Pfandart — der Betrag wird vom Gesamtbetrag abgezogen.",
  },
  {
    anchor: "verkauf-zahlung",
    tab: "verkauf",
    title: "Zahlung wählen",
    text: "Wähle, wie bezahlt wird — zum Beispiel Bar oder Karte.",
  },
  {
    anchor: "verkauf-bar",
    tab: "verkauf",
    title: "Bargeld & Rückgeld",
    text: "Bei Barzahlung tippst du den erhaltenen Betrag ein oder nutzt einen Schnellbetrag. Das Rückgeld rechnet die Kasse dir aus.",
  },
  {
    anchor: "verkauf-kassieren",
    tab: "verkauf",
    title: "Verkauf abschließen",
    text: "Mit „Kassieren\" buchst du den Verkauf. Für jeden Artikel kommt automatisch ein kleiner Bon aus dem Drucker.",
  },
  {
    anchor: "verkauf-erfolg",
    tab: "verkauf",
    title: "Beleg auf Wunsch",
    text: "Nach dem Abschluss siehst du das Rückgeld. Möchte der Gast einen vollständigen Beleg, tippe auf „Beleg drucken\".",
  },
  {
    anchor: "verkauf-leeren",
    tab: "verkauf",
    title: "Neu beginnen",
    text: "Verzählt oder falscher Artikel? Mit „Leeren\" setzt du den Warenkorb zurück.",
  },
  {
    anchor: "belegliste",
    tab: "belege",
    title: "Alle Verkäufe",
    text: "Unter „Belege\" findest du die abgeschlossenen Verkäufe. Du kannst Details öffnen oder einen Beleg erneut drucken.",
  },
  {
    anchor: "druckwarteschlange",
    tab: "drucke",
    title: "Druckaufträge",
    text: "Hier siehst du, ob Bons noch offen sind oder ein Druck fehlgeschlagen ist. Offene Aufträge werden automatisch wiederholt.",
  },
  {
    anchor: "tab-veranstaltungen",
    minStufe: 20,
    title: "Struktur",
    text: "In der Struktur pflegst du Vereinsname, Kassenprofile und zentrale Einstellungen wie Pfand aktiv oder inaktiv.",
  },
  {
    anchor: "tab-artikel",
    minStufe: 20,
    title: "Artikel",
    text: "Hier legst du Artikel an, änderst Preise, Kategorien, Pfandzuordnung und ob ein Artikel aktiv ist.",
  },
  {
    anchor: "tab-kategorien",
    minStufe: 20,
    title: "Kategorien",
    text: "Kategorien helfen beim schnellen Filtern im Verkauf. Farben machen die Artikelkacheln leichter erkennbar.",
  },
  {
    anchor: "tab-pfand",
    minStufe: 20,
    title: "Pfandarten",
    text: "Pfandarten bestimmen, welcher Betrag automatisch beim Verkauf dazukommt oder bei Rückgabe abgezogen wird.",
  },
  {
    anchor: "tab-zahlarten",
    minStufe: 20,
    title: "Zahlarten",
    text: "Hier steuerst du, welche Zahlungsarten es gibt und ob bei Barzahlung Rückgeld berechnet wird.",
  },
  {
    anchor: "tab-auswertung",
    minStufe: 20,
    title: "Auswertung",
    text: "In der Auswertung siehst du Umsätze, Verkaufszeiten und Artikelverteilung. Damit erkennst du später, wann was stark verkauft wurde.",
  },
  {
    anchor: "tab-abschluss",
    minStufe: 20,
    title: "Abschluss",
    text: "Unter Abschluss erzeugst du Kassenberichte, exportierst Daten und kannst nach einem Abschluss gezielt Daten zurücksetzen.",
  },
  {
    anchor: "tab-benutzer",
    minStufe: 20,
    title: "Benutzer",
    text: "Hier verwaltest du Bediener, Administratoren und Servicezugänge. PINs können zurückgesetzt und Benutzer deaktiviert werden.",
  },
  {
    anchor: "tab-service",
    minStufe: 30,
    title: "Service",
    text: "Der Servicebereich hilft bei Diagnose, Drucker, Schublade und technischen Tests.",
  },
  {
    anchor: null,
    title: "Geschafft!",
    text: "Du kennst jetzt die wichtigsten Funktionen. Dieses Tutorial kannst du jederzeit über das „?"-Symbol oben rechts erneut starten. Viel Erfolg an der Kasse!",
  },
];

export function Tutorial({
  session,
  open,
  onClose,
  onTabChange,
}: {
  session: Session;
  open: boolean;
  onClose: (gesehen: boolean) => void;
  onTabChange: (tab: Tab) => void;
}) {
  const steps = useMemo(() => STEPS.filter((s) => !s.minStufe || session.stufe >= s.minStufe), [session.stufe]);
  const [index, setIndex] = useState(0);
  const [rect, setRect] = useState<Rect | null>(null);

  const step = steps[index] ?? steps[0];

  const findTarget = useCallback((tourStep: TourStep) => {
    if (!tourStep.anchor) return null;
    return document.querySelector<HTMLElement>(`[data-tour="${tourStep.anchor}"]`);
  }, []);

  const syncRect = useCallback(() => {
    const el = findTarget(step);
    if (!el) {
      setRect(null);
      return;
    }
    el.scrollIntoView({ block: "center", inline: "center", behavior: "smooth" });
    const next = el.getBoundingClientRect();
    setRect({ top: next.top, left: next.left, width: next.width, height: next.height });
  }, [findTarget, step]);

  const goToUsableStep = useCallback((start: number, dir: 1 | -1) => {
    let next = start;
    while (next >= 0 && next < steps.length) {
      const candidate = steps[next];
      if (!candidate.tab) {
        if (!candidate.anchor || findTarget(candidate)) return next;
      } else {
        onTabChange(candidate.tab);
        return next;
      }
      next += dir;
    }
    return Math.max(0, Math.min(steps.length - 1, start));
  }, [findTarget, onTabChange, steps]);

  useEffect(() => {
    if (!open) return;
    setIndex(0);
  }, [open]);

  useEffect(() => {
    if (!open || !step) return;
    if (step.tab) onTabChange(step.tab);
    const timeout = window.setTimeout(() => {
      syncRect();
      if (step.anchor && !findTarget(step)) setIndex((cur) => goToUsableStep(cur + 1, 1));
    }, 220);
    window.addEventListener("resize", syncRect);
    window.addEventListener("scroll", syncRect, true);
    return () => {
      window.clearTimeout(timeout);
      window.removeEventListener("resize", syncRect);
      window.removeEventListener("scroll", syncRect, true);
    };
  }, [findTarget, goToUsableStep, onTabChange, open, step, syncRect]);

  useEffect(() => {
    if (!open || !step?.anchor || step.tab) return;
    if (!findTarget(step)) setIndex((cur) => goToUsableStep(cur + 1, 1));
  }, [findTarget, goToUsableStep, open, step]);

  if (!open) return null;

  const isWelcome = index === 0;
  const isFinish = index === steps.length - 1;
  const progress = Math.round(((index + 1) / steps.length) * 100);
  const cardStyle = popoverStyle(rect);

  return (
    <div className="tutorial-layer" data-has-target={rect ? "true" : "false"} role="dialog" aria-modal="true" aria-label="Tutorial">
      <div className="tutorial-dim" />
      {rect && (
        <div
          className="tutorial-spotlight"
          style={{
            top: rect.top - 8,
            left: rect.left - 8,
            width: rect.width + 16,
            height: rect.height + 16,
          }}
        />
      )}
      <div className={`tutorial-card ${rect ? "tutorial-popover" : "tutorial-center"}`} style={cardStyle}>
        <div className="tutorial-progress" aria-hidden="true"><span style={{ width: `${progress}%` }} /></div>
        <div className="eyebrow">Schritt {index + 1} von {steps.length}</div>
        <h2>{step.title}</h2>
        <p>{step.text}</p>
        <div className="tutorial-actions">
          {!isWelcome && !isFinish && (
            <button type="button" className="btn" onClick={() => setIndex((cur) => goToUsableStep(cur - 1, -1))}>Zurück</button>
          )}
          <button type="button" className="btn" onClick={() => onClose(true)}>Überspringen</button>
          {isFinish ? (
            <button type="button" className="btn btn-primary" onClick={() => onClose(true)}>Fertig</button>
          ) : (
            <button type="button" className="btn btn-primary" onClick={() => setIndex((cur) => goToUsableStep(cur + 1, 1))}>
              {isWelcome ? "Los geht's" : "Weiter"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function popoverStyle(rect: Rect | null) {
  if (!rect) return undefined;
  const width = Math.min(420, window.innerWidth - 32);
  const left = Math.max(16, Math.min(window.innerWidth - width - 16, rect.left + rect.width / 2 - width / 2));
  const below = rect.top + rect.height + 18;
  const top = below + 260 < window.innerHeight ? below : Math.max(16, rect.top - 278);
  return { width, left, top };
}
