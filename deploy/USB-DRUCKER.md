# Bon-Drucker per USB anschließen

Der Netzwerkweg ist nicht zwingend – der NS-8360L lässt sich auch per USB
betreiben. Das ist für eine feste Kasse oft der einfachere und stabilere Weg
(keine IP-Suche). So richtest du es ein:

## 1. Systemvoraussetzung (einmalig, auf dem Pi)

```bash
sudo apt install -y libusb-1.0-0
```

`pyusb` selbst wird über `requirements.txt` beim Deploy (`deploy/update.sh`)
mitinstalliert.

## 2. Drucker anschließen und IDs ermitteln

Drucker per USB an den Pi stecken und einschalten. Dann in der Oberfläche im
**Service-Reiter** bei `drucker.transport` auf **usb** stellen und **„USB-Geräte
suchen"** anklicken. Es erscheint eine Liste der angeschlossenen USB-Geräte mit
Hersteller-/Produkt-ID. Beim Drucker auf **„Übernehmen"** klicken – damit werden
`drucker.usb.vendor_id` und `drucker.usb.product_id` automatisch gesetzt.

(Alternativ auf dem Pi: `lsusb` – die Zeile des Druckers zeigt `ID vvvv:pppp`.)

## 3. USB-Zugriff ohne root erlauben (einmalig)

Damit der Kassendienst (Benutzer `kasse`) auf den Drucker zugreifen darf, eine
udev-Regel setzen. In `deploy/99-vereinskasse-usb.rules` die `idVendor`/
`idProduct` auf die eben ermittelten Werte anpassen (ohne „0x", vierstellig
klein), dann:

```bash
sudo cp /opt/vereinskasse/deploy/99-vereinskasse-usb.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger
```

Drucker einmal aus- und wieder einstecken.

## 4. Testen

Im Service-Reiter **Testseite drucken** auslösen. Kommt ein Ausdruck, passt
alles. Danach ist der normale Verkaufsdruck aktiv; ein zuvor in der
Druckwarteschlange hängender Auftrag lässt sich dort per **Wiederholen**
nachholen.

## Fehlersuche

- **„USB-Drucker … nicht gefunden"**: IDs stimmen nicht – nochmal über
  „USB-Geräte suchen" prüfen und übernehmen.
- **„No backend available"**: `libusb-1.0-0` fehlt (Schritt 1).
- **Zugriff verweigert / Permission**: udev-Regel fehlt oder IDs darin falsch
  (Schritt 3), oder Drucker nach dem Setzen der Regel nicht neu eingesteckt.
- **`drucker.usb.endpoint`**: Standard `0x01` passt fast immer; nur ändern, wenn
  der Drucker einen anderen Bulk-OUT-Endpunkt nutzt.
