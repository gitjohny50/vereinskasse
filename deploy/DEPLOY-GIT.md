# Git-Workflow & Deployment auf den Raspberry Pi

Ein Git-Repository ist für dieses Projekt sinnvoll: Versionsstände sind
nachvollziehbar, Rückschritte (Rollback) sind möglich, und das Ausrollen auf den
Pi wird ein einzelner Befehl. Die **Daten** (SQLite-Datenbank) liegen bewusst
außerhalb des Repos im `VK_DATA_DIR` und werden nie eingecheckt.

## 1. Repository lokal anlegen

Im Projektordner (auf dem Entwicklungsrechner):

```bash
git init
git add .
git commit -m "Vereinskasse: Stand Phase 5"
```

Die `.gitignore` sorgt dafür, dass `node_modules/`, `frontend/dist/`, virtuelle
Umgebungen, Datenbanken und `.env` außen vor bleiben. Eingecheckt wird nur der
Quellcode — das Frontend wird beim Deployen auf dem Pi gebaut.

## 2. Variante A — direkt auf den Pi pushen (empfohlen, offline-tauglich)

Auf dem Pi ein "bare" Repo anlegen und den Deploy-Hook einsetzen (einmalig):

```bash
# auf dem Pi
git init --bare /home/kasse/vereinskasse.git
cp /opt/vereinskasse/deploy/git-hooks/post-receive /home/kasse/vereinskasse.git/hooks/
chmod +x /home/kasse/vereinskasse.git/hooks/post-receive
```

Auf dem Entwicklungsrechner den Pi als Remote eintragen und pushen:

```bash
git remote add pi kasse@<pi-ip>:/home/kasse/vereinskasse.git
git push pi main
```

Jeder `git push pi main` checkt den Stand nach `/opt/vereinskasse` aus und ruft
`deploy/update.sh` auf: Abhängigkeiten, Migrationen, Frontend-Build und
Dienst-Neustart laufen automatisch. Kein Cloud-Konto nötig — nur SSH im LAN.

## 3. Variante B — über GitHub/GitLab

Wenn der Pi (gelegentlich) Internet hat:

```bash
# Entwicklungsrechner
git remote add origin git@github.com:<konto>/vereinskasse.git
git push -u origin main

# auf dem Pi
cd /opt/vereinskasse
git pull
sudo -u kasse ./deploy/update.sh
```

## 4. Erstinstallation

Die Erstinstallation (Grundsystem, Benutzer `kasse`, Datenverzeichnis, systemd-
Dienste) ist einmalig in `deploy/INSTALL.md` beschrieben. Danach übernimmt der
Git-Workflow oben alle weiteren Updates.

## 5. Nützliche Git-Befehle

```bash
git status                 # was hat sich geändert?
git log --oneline          # Verlauf
git tag phase5             # Version markieren
git checkout <tag>         # zu einem Stand zurück (Rollback)
```

## Hinweise

- **Daten bleiben erhalten:** Updates fassen die Datenbank in `VK_DATA_DIR`
  nicht an; Schemaänderungen laufen ausschließlich über `alembic upgrade head`.
- **Rollback:** Bei Problemen `git checkout <vorheriger-tag>` und erneut
  `deploy/update.sh`. Migrationen sind nur vorwärts ausgelegt — vor größeren
  Updates eine Kopie des Datenverzeichnisses sichern.
- **Erst-PIN:** Beim allerersten Start ohne gesetzte `VK_INITIAL_ADMIN_PIN`
  steht die generierte PIN im Log:
  `journalctl -u vereinskasse-backend | grep Start-PIN`.
