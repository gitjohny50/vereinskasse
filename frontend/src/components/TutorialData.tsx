import type { Tab } from "../App";

export const tutorialKey = (benutzerId: number) => `vk_tutorial_seen_${benutzerId}`;

export type TourStep = {
  anchor: string | null;
  tab?: Tab;
  minStufe?: number;
  title: string;
  text: string;
};

export const STEPS: TourStep[] = [
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
    text: "Du kennst jetzt die wichtigsten Funktionen. Dieses Tutorial kannst du jederzeit über das „?\"-Symbol oben rechts erneut starten. Viel Erfolg an der Kasse!",
  },
];