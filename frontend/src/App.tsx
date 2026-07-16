import { useEffect, useState } from "react";
import { api, getToken, setToken, type Kassenprofil, type Session } from "./api";
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

type Tab = "verkauf" | "belege" | "drucke" | "abschluss" | "artikel" | "kategorien" | "pfand" | "zahlarten" | "veranstaltungen" | "benutzer" | "service";
const PROFIL_TABS: Tab[] = ["verkauf", "belege", "abschluss", "artikel", "kategorien", "pfand", "zahlarten"];

export function App() {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<Tab>("verkauf");
  const [profile, setProfile] = useState<Kassenprofil[]>([]);
  const [profilId, setProfilId] = useState<number | null>(null);
  const [druckOffen, setDruckOffen] = useState(0);

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

  // Zähler für das Drucke-Abzeichen (offene + fehlgeschlagene Aufträge).
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

  if (loading) return <div className="app"><p style={{ color: "var(--muted)" }}>Lade…</p></div>;

  if (!session) {
    return <div className="app"><Login onLogin={(s) => { setToken(s.token); setSession(s); }} /></div>;
  }

  const canAdmin = session.stufe >= 20;
  const canService = session.stufe >= 30;
  const activeProfil = profile.find((p) => p.id === profilId) ?? null;
  const zeigeProfilwahl = PROFIL_TABS.includes(tab) && profile.length > 1;

  return (
    <div className="app">
      <header className="masthead">
        <div>
          <div className="eyebrow">Vereinskasse · Phase 3</div>
          <h1>{tab === "verkauf" ? "Kasse" : "Vereinskasse"}</h1>
        </div>
        <div className="row" style={{ gap: 12 }}>
          <span className="version">{session.name} · {session.rolle}</span>
          <button className="btn" style={{ minHeight: 40, padding: "0 14px" }} onClick={handleLogout}>Abmelden</button>
        </div>
      </header>

      <nav className="tabs">
        <button className={`tab ${tab === "verkauf" ? "active" : ""}`} onClick={() => setTab("verkauf")}>Verkauf</button>
        <button className={`tab ${tab === "belege" ? "active" : ""}`} onClick={() => setTab("belege")}>Belege</button>
        <button className={`tab ${tab === "drucke" ? "active" : ""}`} onClick={() => setTab("drucke")}>
          Drucke{druckOffen > 0 && <span className="tab-badge">{druckOffen}</span>}
        </button>
        {canAdmin && <button className={`tab ${tab === "abschluss" ? "active" : ""}`} onClick={() => setTab("abschluss")}>Abschluss</button>}
        {canAdmin && <button className={`tab ${tab === "artikel" ? "active" : ""}`} onClick={() => setTab("artikel")}>Artikel</button>}
        {canAdmin && <button className={`tab ${tab === "kategorien" ? "active" : ""}`} onClick={() => setTab("kategorien")}>Kategorien</button>}
        {canAdmin && <button className={`tab ${tab === "pfand" ? "active" : ""}`} onClick={() => setTab("pfand")}>Pfand</button>}
        {canAdmin && <button className={`tab ${tab === "zahlarten" ? "active" : ""}`} onClick={() => setTab("zahlarten")}>Zahlarten</button>}
        {canAdmin && <button className={`tab ${tab === "veranstaltungen" ? "active" : ""}`} onClick={() => setTab("veranstaltungen")}>Veranstaltungen</button>}
        {canAdmin && <button className={`tab ${tab === "benutzer" ? "active" : ""}`} onClick={() => setTab("benutzer")}>Benutzer</button>}
        {canService && <button className={`tab ${tab === "service" ? "active" : ""}`} onClick={() => setTab("service")}>Service</button>}
      </nav>

      {zeigeProfilwahl && (
        <div className="row" style={{ gap: 10, alignItems: "center", margin: "0 0 18px" }}>
          <span className="eyebrow">Aktives Kassenprofil</span>
          <select value={profilId ?? ""} onChange={(e) => setProfilId(Number(e.target.value))}>
            {profile.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        </div>
      )}

      {PROFIL_TABS.includes(tab) && !activeProfil && (
        <p style={{ color: "var(--muted)" }}>
          Noch kein Kassenprofil vorhanden. Ein Administrator legt es unter „Veranstaltungen“ an.
        </p>
      )}

      {tab === "verkauf" && activeProfil && <Verkauf profil={activeProfil} />}
      {tab === "belege" && activeProfil && <Belege profil={activeProfil} />}
      {tab === "drucke" && <Druckwarteschlange canAdmin={canAdmin} />}
      {tab === "abschluss" && canAdmin && activeProfil && <Kassenabschluss profil={activeProfil} />}
      {tab === "artikel" && canAdmin && activeProfil && <Artikel profil={activeProfil} />}
      {tab === "kategorien" && canAdmin && activeProfil && <Kategorien profil={activeProfil} />}
      {tab === "pfand" && canAdmin && activeProfil && <Pfandarten profil={activeProfil} />}
      {tab === "zahlarten" && canAdmin && activeProfil && <Zahlungsmethoden profil={activeProfil} />}
      {tab === "veranstaltungen" && canAdmin && <Veranstaltungen onProfilesChanged={ladeProfile} />}
      {tab === "benutzer" && canAdmin && <Benutzer />}
      {tab === "service" && canService && <Diagnose />}
    </div>
  );
}
