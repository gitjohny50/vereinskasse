import { useEffect, useState } from "react";
import { api, ApiError, type LoginUser, type Session } from "../api";

export function Login({ onLogin }: { onLogin: (s: Session) => void }) {
  const [users, setUsers] = useState<LoginUser[]>([]);
  const [selected, setSelected] = useState<LoginUser | null>(null);
  const [pin, setPin] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.loginUsers().then(setUsers).catch(() => setError("Benutzerliste konnte nicht geladen werden."));
  }, []);

  function tippe(z: string) {
    setError(null);
    setPin((p) => (p.length >= 12 ? p : p + z));
  }

  async function anmelden() {
    if (!selected || pin.length < 4) return;
    setBusy(true);
    setError(null);
    try {
      const s = await api.login(selected.id, pin);
      onLogin(s);
    } catch (e) {
      if (e instanceof ApiError && e.status === 423) setError("Benutzer gesperrt. Bitte Administrator kontaktieren.");
      else setError("Anmeldung fehlgeschlagen.");
      setPin("");
    } finally {
      setBusy(false);
    }
  }

  if (!selected) {
    return (
      <div className="login">
        <div className="eyebrow">Vereinskasse</div>
        <h1>Anmelden</h1>
        <p style={{ color: "var(--muted)", marginTop: 0 }}>Bitte Benutzer wählen.</p>
        <div className="user-grid">
          {users.map((u) => (
            <button key={u.id} className="user-card" onClick={() => { setSelected(u); setPin(""); setError(null); }}>
              {u.name}
            </button>
          ))}
          {users.length === 0 && !error && <p style={{ color: "var(--muted)" }}>Lade Benutzer…</p>}
        </div>
        {error && <p className="login-error">{error}</p>}
      </div>
    );
  }

  const keys = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "C", "0", "OK"];
  return (
    <div className="login">
      <button className="btn" style={{ minHeight: 40, alignSelf: "flex-start", padding: "0 14px" }} onClick={() => { setSelected(null); setPin(""); }}>
        ← Zurück
      </button>
      <h1 style={{ marginBottom: 4 }}>{selected.name}</h1>
      <p style={{ color: "var(--muted)", marginTop: 0 }}>PIN eingeben</p>
      <div className="pin-display">{pin.replace(/./g, "•") || <span style={{ color: "var(--muted)" }}>––––</span>}</div>
      <div className="pin-pad">
        {keys.map((k) => (
          <button
            key={k}
            className={`pin-key ${k === "OK" ? "pin-ok" : ""}`}
            disabled={busy}
            onClick={() => {
              if (k === "C") { setPin(""); setError(null); }
              else if (k === "OK") anmelden();
              else tippe(k);
            }}
          >
            {k}
          </button>
        ))}
      </div>
      {error && <p className="login-error">{error}</p>}
    </div>
  );
}
