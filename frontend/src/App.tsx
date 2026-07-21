import { useEffect, useState } from "react";
import { api, getToken, setToken, type Kassenprofil, type Session } from "./api";
import { Tutorial, tutorialKey } from "./components/Tutorial";
import { Login } from "./pages/Login";
import { Verkauf } from "./pages/Verkauf";
import { Belege } from "./pages/Belege";
import { Artikel } from "./pages/Artikel";
import { Kategorien } from "./pages/Kategorien";
import { Pfandarten } from "./pages/Pfandarten";
import { Zahlungsmethoden } from "./pages/Zahlungsmethoden";
import { Veranstaltungen } from "./pages/Veranstaltungen";
import { Benutzer } from "./pages/Benutzer";
import { Kassenabschluss } from "./pages/Kassenabschluss";
import { Druckwarteschlange } from "./pages/Druckwarteschlange";
import { Diagnose } from "./pages/Diagnose";
import { Auswertung } from "./pages/Auswertung";

export type Tab = "verkauf" | "belege" | "drucke" | "auswertung" | "abschluss" | "artikel" | "kategorien" | "pfand" | "zahlarten" | "veranstaltungen" | "benutzer" | "service";
const PROFIL_TABS: Tab[] = ["verkauf", "belege", "auswertung", "abschluss", "artikel", "kategorien", "pfand", "zahlarten"];

const TAB_TITEL: Record<Tab, string> = {
  verkauf: "Kasse", belege: "Belege", drucke: "Druckwarteschlange", auswertung: "Auswertung",
  abschluss: "Kassenabschluss", artikel: "Artikel", kategorien: "Kategorien", pfand: "Pfandarten",
  zahlarten: "Zahlungsmethoden", veranstaltungen: "Struktur", benutzer: "Benutzer", service: "Service",
};

const THEMES = [
  { id: "indigo", label: "Indigo" },
  { id: "ozean", label: "Ozean" },
  { id: "bernstein", label: "Bernstein" },
] as const;

export function App() {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<Tab>("verkauf");
  const [profile, setProfile] = useState<Kassenprofil[]>([]);
  const [profilId, setProfilId] = useState<number | null>(null);
  const [druckOffen, setDruckOffen] = useState(0);
  const [theme, setTheme] = useState<string>(() => localStorage.getItem("vk_theme") || "indigo");
  const [headerHidden, setHeaderHidden] = useState<boolean>(() => localStorage.getItem("vk_header_hidden") === "1");
  const [tutorialOpen, setTutorialOpen] = useState(false);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("vk_theme", theme);
  }, [theme]);
  useEffect(() => {
    localStorage.setItem("vk_header_hidden", headerHidden ? "1" : "0");
  }, [headerHidden]);

  useEffect(() => {
    if (!getToken()) { setLoading(false); return; }
    api.me().then(setSession).catch(() => setToken(null)).finally(() => setLoading(false));
  }, []);

  async function ladeProfile() {
    const ps = await api.profile();
    setProfile(ps);
    setProfilId((cur) => (cur && ps.some((p) => p.id === cur) ? cur : ps[0]?.id ?? null));
  }
  useEffect(() => {
    if (session) ladeProfile().catch(() => { /* ignoriert */ });
  }, [session]);
  useEffect(() => {
    if (!session) return;
    if (localStorage.getItem(tutorialKey(session.benutzer_id)) !== "1") {
      setTutorialOpen(true);
    }
  }, [session]);

  useEffect(() => {
    if (!session) return;
    let stop = false;
    const pruefe = () => api.druckStatus()
      .then((s) => { if (!stop) setDruckOffen(s.offen + s.fehlgeschlagen); })
      .catch(() => { /* ignoriert */ });
    pruefe();
    const iv = setInterval(pruefe, 15000);
    return () => { stop = true; clearInterval(iv); };
  }, [session, tab]);

  async function handleLogout() {
    try { await api.logout(); } catch { /* Token evtl. abgelaufen */ }
    setToken(null);
    setSession(null);
  }

  const themeSwitch = (
    <div className="theme-switch" role="group" aria-label="Farbschema">
      {THEMES.map((t) => (
        <button
          key={t.id}
          className={`theme-dot ${t.id} ${theme === t.id ? "on" : ""}`}
          title={t.label}
          aria-label={t.label}
          aria-pressed={theme === t.id}
          onClick={() => setTheme(t.id)}
        />
      ))}
    </div>
  );

  if (loading) return <div className="app"><div className="inhalt"><p style={{ color: "var(--muted)" }}>Lade…</p></div></div>;

  if (!session) {
    return <div className="app"><div className="inhalt"><Login onLogin={(s) => { setToken(s.token); setSession(s); }} /></div></div>;
  }

  const canAdmin = session.stufe >= 20;
  const canService = session.stufe >= 30;
  const activeProfil = profile.find((p) => p.id === profilId) ?? null;
  const zeigeProfilwahl = PROFIL_TABS.includes(tab) && profile.length > 1;

  const tabBtn = (id: Tab, label: string, badge?: number) => (
    <button className={`tab ${tab === id ? "active" : ""}`} onClick={() => setTab(id)} data-tour={`tab-${id}`}>
      {label}{badge != null && badge > 0 && <span className="tab-badge">{badge}</span>}
    </button>
  );

  function tutorialSchliessen(gesehen: boolean) {
    if (gesehen) localStorage.setItem(tutorialKey(session!.benutzer_id), "1");
    setTutorialOpen(false);
  }

  return (
    <div className={`app ${headerHidden ? "header-collapsed" : ""}`}>
      <button
        className="header-toggle"
        aria-label={headerHidden ? "Header einblenden" : "Header ausblenden"}
        title={headerHidden ? "Header einblenden" : "Header ausblenden"}
        onClick={() => setHeaderHidden((v) => !v)}
      >
        {headerHidden ? "⌄" : "⌃"}
      </button>
      <header className="topbar" data-tour="kopfzeile">
        <div className="topbar-inner">
          <div className="brand">
            <div className="brand-logo">VK</div>
            <div className="brand-text">
              <div className="brand-title">Vereinskasse</div>
              <div className="brand-sub">{TAB_TITEL[tab]}</div>
            </div>
          </div>
          <div className="top-actions">
            {themeSwitch}
            <div className="user-chip"><b>{session.name}</b><span>{session.rolle}</span></div>
            <button className="btn btn-sm tutorial-help" aria-label="Tutorial starten" title="Tutorial starten" onClick={() => setTutorialOpen(true)}>?</button>
            <button className="btn btn-sm" onClick={handleLogout}>Abmelden</button>
          </div>
        </div>
      </header>

      <div className="tabbar" data-tour="reiterleiste">
        <nav className="tabs">
          {tabBtn("verkauf", "Verkauf")}
          {tabBtn("belege", "Belege")}
          {tabBtn("drucke", "Drucke", druckOffen)}
          {canAdmin && tabBtn("auswertung", "Auswertung")}
          {canAdmin && tabBtn("abschluss", "Abschluss")}
          {canAdmin && tabBtn("artikel", "Artikel")}
          {canAdmin && tabBtn("kategorien", "Kategorien")}
          {canAdmin && tabBtn("pfand", "Pfand")}
          {canAdmin && tabBtn("zahlarten", "Zahlarten")}
          {canAdmin && tabBtn("veranstaltungen", "Struktur")}
          {canAdmin && tabBtn("benutzer", "Benutzer")}
          {canService && tabBtn("service", "Service")}
        </nav>
      </div>

      <main className="inhalt">
        {zeigeProfilwahl && (
          <div className="row" data-tour="profilwahl" style={{ gap: 10, alignItems: "center", margin: "0 0 18px", flexWrap: "wrap" }}>
            <span className="eyebrow">Aktives Kassenprofil</span>
            <select value={profilId ?? ""} onChange={(e) => setProfilId(Number(e.target.value))} style={{ maxWidth: 280 }}>
              {profile.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </div>
        )}

        {PROFIL_TABS.includes(tab) && !activeProfil && (
          <p style={{ color: "var(--muted)" }}>
            Noch kein Kassenprofil vorhanden. Ein Administrator legt es unter „Struktur“ an.
          </p>
        )}

        {tab === "verkauf" && activeProfil && <Verkauf profil={activeProfil} />}
        {tab === "belege" && activeProfil && <Belege profil={activeProfil} />}
        {tab === "drucke" && <Druckwarteschlange canAdmin={canAdmin} />}
        {tab === "auswertung" && canAdmin && activeProfil && <Auswertung profil={activeProfil} />}
        {tab === "abschluss" && canAdmin && activeProfil && <Kassenabschluss profil={activeProfil} />}
        {tab === "artikel" && canAdmin && activeProfil && <Artikel profil={activeProfil} />}
        {tab === "kategorien" && canAdmin && activeProfil && <Kategorien profil={activeProfil} />}
        {tab === "pfand" && canAdmin && activeProfil && <Pfandarten profil={activeProfil} />}
        {tab === "zahlarten" && canAdmin && activeProfil && <Zahlungsmethoden profil={activeProfil} />}
        {tab === "veranstaltungen" && canAdmin && <Veranstaltungen onProfilesChanged={ladeProfile} />}
        {tab === "benutzer" && canAdmin && <Benutzer />}
        {tab === "service" && canService && <Diagnose />}
      </main>
      <Tutorial session={session} open={tutorialOpen} onClose={tutorialSchliessen} onTabChange={setTab} />
    </div>
  );
}
