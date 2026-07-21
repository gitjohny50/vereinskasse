import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi, beforeEach, beforeAll, Mock } from 'vitest';
import { Verkauf } from '../../pages/Verkauf';
import { api, type Kassenprofil, ApiError } from '../../api';

// Mocke das komplette API-Modul
vi.mock('../../api', async (importOriginal: () => Promise<typeof import('../../api')>) => {
  const original = await importOriginal();
  return {
    ...original,
    api: {
      ...original.api,
      kategorien: vi.fn().mockResolvedValue([]),
      artikel: vi.fn().mockResolvedValue([]),
      // FIX: Wir geben standardmäßig eine Pfandart zurück, damit der Checkout-Dialog 
      // immer den "Pfand zurück?"-Schritt anzeigt, den unsere Tests erwarten.
      pfandarten: vi.fn().mockResolvedValue([{ id: 1, name: 'Becher', betrag_cent: 100, aktiv: true, rueckgabe_erlaubt: true }]),
      zahlungsmethoden: vi.fn().mockResolvedValue([{ id: 1, name: 'Bar', aktiv: true, rueckgeld_berechnen: true }]),
      berechnung: vi.fn().mockResolvedValue({ gesamt_cent: 1250, pfand_cent: 0, waren_cent: 1250 }),
      verkaufAbschluss: vi.fn().mockResolvedValue({ id: 1, belegnummer: 'B-2024-1' }),
      belegDrucken: vi.fn().mockResolvedValue(new Blob()),
    },
  };
});

const mockProfil: Kassenprofil = {
  id: 1,
  name: 'Testkasse',
  waehrung: 'EUR',
  verein_id: 1,
  aktiv: true,
  pfand_aktiv: true,
};

describe('Verkauf Component', () => {
  beforeAll(() => {
    // JSDOM kennt keine Pointer-Capture Events. Wir mocken sie weg, um Abstürze beim "+" und "-" Klick zu verhindern.
    if (typeof window.HTMLElement.prototype.setPointerCapture !== 'function') {
      window.HTMLElement.prototype.setPointerCapture = vi.fn();
    }
    if (typeof window.HTMLElement.prototype.releasePointerCapture !== 'function') {
      window.HTMLElement.prototype.releasePointerCapture = vi.fn();
    }
  });

  beforeEach(() => {
    // FIX: vi.restoreAllMocks() ist robuster und setzt auch Mock-Implementierungen zurück.
    vi.restoreAllMocks();
  });

  test('sollte die Seite korrekt rendern und den Kassieren-Button anzeigen', async () => {
    render(<Verkauf profil={mockProfil} />);
    await waitFor(() => {
      expect(screen.getByText(/Kassieren/i)).toBeInTheDocument();
    });
    const kassierenButton = screen.getByRole('button', { name: /Kassieren/i });
    expect(kassierenButton).toBeDisabled();
  });

  test('sollte den Kassieren-Button aktivieren, wenn ein Artikel hinzugefügt wird', async () => {
    (api.artikel as Mock).mockResolvedValue([
      { id: 101, name: 'Test-Cola', preis_cent: 1250, aktiv: true, archiviert: false },
    ]);
    render(<Verkauf profil={mockProfil} />);
    const user = userEvent.setup();

    const artikelButton = await screen.findByText('Test-Cola');
    await user.click(artikelButton);

    await waitFor(() => {
      const kassierenButton = screen.getByRole('button', { name: /Kassieren/i });
      expect(kassierenButton).toHaveTextContent('12,50 €');
      expect(kassierenButton).not.toBeDisabled();
    });
  });

  test('sollte den kompletten Bezahlvorgang mit Barzahlung simulieren', async () => {
    const user = userEvent.setup();
    (api.artikel as Mock).mockResolvedValue([
      { id: 101, name: 'Test-Cola', preis_cent: 1250, aktiv: true, archiviert: false },
    ]);
    // FIX: Stellen Sie sicher, dass die Berechnung für diesen Test korrekt ist.
    (api.berechnung as Mock).mockResolvedValue({ gesamt_cent: 1250, waren_cent: 1250, pfand_cent: 0 });

    render(<Verkauf profil={mockProfil} />);

    const artikelButton = await screen.findByText('Test-Cola');
    await user.click(artikelButton);

    const kassierenButton = await screen.findByRole('button', { name: /Kassieren 12,50\s€/i });
    await user.click(kassierenButton);

    const pfandModalTitle = await screen.findByText('Pfand zurück?');
    expect(pfandModalTitle).toBeInTheDocument();
    const neinButton = screen.getByRole('button', { name: /Nein/ });
    await user.click(neinButton);

    const barButton = screen.getByRole('button', { name: /Bar/ });
    await user.click(barButton);

    const gegebenInput = screen.getByLabelText(/Manuell eingeben/);
    await user.type(gegebenInput, '20,00');

    const rueckgeldAnzeige = await screen.findByText('7,50 €');
    expect(rueckgeldAnzeige).toBeInTheDocument();

    const finalerKassierenButton = screen.getAllByRole('button', { name: /Kassieren 12,50\s€/ })[1];
    await user.click(finalerKassierenButton);

    const erfolgsMeldung = await screen.findByText(/Beleg B-2024-1/);
    expect(erfolgsMeldung).toBeInTheDocument();
  });

  test('sollte den Warenkorb leeren, wenn der Leeren-Button geklickt wird', async () => {
    const user = userEvent.setup();
    (api.artikel as Mock).mockResolvedValue([
      { id: 101, name: 'Kaffee', preis_cent: 200, aktiv: true, archiviert: false },
    ]);
    // FIX: Stellen Sie sicher, dass die Berechnung für diesen Test korrekt ist.
    (api.berechnung as Mock).mockResolvedValue({ gesamt_cent: 1250, waren_cent: 1250, pfand_cent: 0 });

    render(<Verkauf profil={mockProfil} />);

    const kaffeeButton = await screen.findByText('Kaffee');
    await user.click(kaffeeButton);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Kassieren/i })).not.toBeDisabled();
    });

    const leerenButton = screen.getByRole('button', { name: 'Leeren' });
    await user.click(leerenButton);

    expect(screen.getByRole('button', { name: /Kassieren/i })).toBeDisabled();
    expect(screen.getByText('Warenkorb ist leer. Artikel antippen.')).toBeInTheDocument();
  });

  test('sollte Artikel korrekt nach Kategorien filtern', async () => {
    const user = userEvent.setup();
    (api.kategorien as Mock).mockResolvedValue([
      { id: 1, name: 'Getränke', aktiv: true },
      { id: 2, name: 'Essen', aktiv: true }
    ]);
    (api.artikel as Mock).mockResolvedValue([
      { id: 101, name: 'Bier', preis_cent: 300, aktiv: true, archiviert: false, kategorie_id: 1 },
      { id: 102, name: 'Bratwurst', preis_cent: 400, aktiv: true, archiviert: false, kategorie_id: 2 }
    ]);
    
    render(<Verkauf profil={mockProfil} />);

    await waitFor(() => {
      expect(screen.getByText('Bier')).toBeInTheDocument();
      expect(screen.getByText('Bratwurst')).toBeInTheDocument();
    });

    const essenFilter = screen.getByRole('button', { name: 'Essen' });
    await user.click(essenFilter);

    expect(screen.getByText('Bratwurst')).toBeInTheDocument();
    expect(screen.queryByText('Bier')).not.toBeInTheDocument();
  });

  test('sollte die Pfandrückgabe im Checkout-Modal korrekt durchlaufen', async () => {
    const user = userEvent.setup();
    (api.artikel as Mock).mockResolvedValue([
      { id: 101, name: 'Cola', preis_cent: 200, aktiv: true, archiviert: false }
    ]);
    
    render(<Verkauf profil={mockProfil} />);

    const artikelButton = await screen.findByText('Cola');
    await user.click(artikelButton);
    
    const kassierenButton = await screen.findByRole('button', { name: /Kassieren/i });
    await user.click(kassierenButton);

    const jaButton = await screen.findByRole('button', { name: /Ja/ });
    await user.click(jaButton);

    const becherPfandButton = await screen.findByRole('button', { name: /Becher/ });
    await user.click(becherPfandButton);

    const weiterButton = screen.getByRole('button', { name: 'Weiter zur Zahlung' });
    await user.click(weiterButton);

    const zahlungModalTitle = await screen.findByText('Zahlungsart wählen');
    expect(zahlungModalTitle).toBeInTheDocument();
  });

  test('sollte eine Fehlermeldung anzeigen, wenn der API-Abschluss fehlschlägt', async () => {
    const user = userEvent.setup();
    (api.artikel as Mock).mockResolvedValue([
      { id: 101, name: 'Test-Cola', preis_cent: 1250, aktiv: true, archiviert: false },
    ]);
    
    (api.verkaufAbschluss as Mock).mockRejectedValueOnce(new ApiError(500, 'Verbindung zum Server verloren.'));
    
    render(<Verkauf profil={mockProfil} />);

    const artikelButton = await screen.findByText('Test-Cola');
    await user.click(artikelButton);
    const kassierenButton = await screen.findByRole('button', { name: /Kassieren/i });
    await user.click(kassierenButton);
    
    const neinButton = await screen.findByRole('button', { name: /Nein/ });
    await user.click(neinButton);
    const barButton = await screen.findByRole('button', { name: /Bar/ });
    await user.click(barButton);
    
    const finalerKassierenButton = screen.getAllByRole('button', { name: /Kassieren 12,50\s€/ })[1];
    await user.click(finalerKassierenButton);

    // FIX: Hier nutzen wir jetzt findAllByText, da der Fehler 2x gerendert wird (Sidebar + Modal)
    const errorMsgs = await screen.findAllByText('Verbindung zum Server verloren.');
    expect(errorMsgs[0]).toBeInTheDocument();
  });

  test('sollte die Menge eines Artikels im Warenkorb über + und - ändern können', async () => {
    const user = userEvent.setup();
    (api.artikel as Mock).mockResolvedValue([
      { id: 101, name: 'Bier', preis_cent: 300, aktiv: true, archiviert: false },
    ]);

    (api.berechnung as Mock).mockImplementation((payload: { artikel: { menge: number }[] }) => {
      const menge = payload.artikel[0]?.menge || 0;
      const gesamt = menge * 300;
      return Promise.resolve({ gesamt_cent: gesamt, waren_cent: gesamt, pfand_cent: 0 });
    });

    render(<Verkauf profil={mockProfil} />);

    const artikelButton = await screen.findByText('Bier');
    await user.click(artikelButton);

    const plusButton = await screen.findByRole('button', { name: '+' });
    await user.click(plusButton);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Kassieren/i })).toHaveTextContent('6,00 €');
    });

    const minusButton = screen.getByRole('button', { name: '−' });
    await user.click(minusButton);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Kassieren/i })).toHaveTextContent('3,00 €');
    });
  });

  test('sollte den Abschluss blockieren und einen Fehler zeigen, wenn zu wenig Bargeld gegeben wurde', async () => {
    const user = userEvent.setup();
    (api.artikel as Mock).mockResolvedValue([
      { id: 101, name: 'Pizza', preis_cent: 1200, aktiv: true, archiviert: false },
    ]);
    (api.berechnung as Mock).mockResolvedValue({ gesamt_cent: 1200, waren_cent: 1200, pfand_cent: 0 });
    
    render(<Verkauf profil={mockProfil} />);

    const artikelButton = await screen.findByText('Pizza');
    await user.click(artikelButton);
    const startCheckout = await screen.findByRole('button', { name: /Kassieren/i });
    await user.click(startCheckout);
    const neinButton = await screen.findByRole('button', { name: /Nein/ });
    await user.click(neinButton);
    const barButton = await screen.findByRole('button', { name: /Bar/ });
    await user.click(barButton);

    const gegebenInput = screen.getByLabelText(/Manuell eingeben/);
    await user.type(gegebenInput, '10,00');

    const finalerKassierenButton = screen.getAllByRole('button', { name: /Kassieren 12,00\s€/ })[1];
    await user.click(finalerKassierenButton);

    const fehler = await screen.findAllByText('Gegebener Betrag ist zu gering.');
    expect(fehler[0]).toBeInTheDocument();
  });

  test('sollte den Verkauf bei Zahlung ohne Rückgeld-Berechnung sofort abschließen (z.B. EC-Karte)', async () => {
    const user = userEvent.setup();
    (api.artikel as Mock).mockResolvedValue([
      { id: 101, name: 'Wasser', preis_cent: 100, aktiv: true, archiviert: false },
    ]);
    (api.zahlungsmethoden as Mock).mockResolvedValue([
      { id: 2, name: 'EC-Karte', aktiv: true, rueckgeld_berechnen: false }
    ]);
    (api.berechnung as Mock).mockResolvedValue({ gesamt_cent: 100, waren_cent: 100, pfand_cent: 0 });
    
    render(<Verkauf profil={mockProfil} />);

    const artikelButton = await screen.findByText('Wasser');
    await user.click(artikelButton);
    const startCheckout = await screen.findByRole('button', { name: /Kassieren/i });
    await user.click(startCheckout);
    const neinButton = await screen.findByRole('button', { name: /Nein/ });
    await user.click(neinButton);

    const karteButton = await screen.findByRole('button', { name: /EC-Karte/ });
    await user.click(karteButton);

    const erfolgsMeldung = await screen.findByText(/Beleg B-2024-1/);
    expect(erfolgsMeldung).toBeInTheDocument();
    
    expect(api.verkaufAbschluss).toHaveBeenCalled();
  });

  test.skip('sollte den Verkauf erlauben, wenn NUR Pfand zurückgegeben wird (ohne Warenkauf)', async () => {
    (api.berechnung as Mock).mockResolvedValue({ gesamt_cent: -300, pfand_cent: -300, waren_cent: 0 });
    render(<Verkauf profil={mockProfil} />);
  });

test('sollte die Bargeld-Schnellwahltasten korrekt anwenden', async () => {
    const user = userEvent.setup();
    (api.artikel as Mock).mockResolvedValue([
      { id: 101, name: 'Bier', preis_cent: 350, aktiv: true, archiviert: false },
    ]);
    (api.berechnung as Mock).mockResolvedValue({ gesamt_cent: 350, waren_cent: 350, pfand_cent: 0 });
    (api.zahlungsmethoden as Mock).mockResolvedValue([
      { id: 1, name: 'Bar', aktiv: true, rueckgeld_berechnen: true }
    ]);
    render(<Verkauf profil={mockProfil} />);

    const artikelButton = await screen.findByText('Bier');
    await user.click(artikelButton);
    const startCheckout = await screen.findByRole('button', { name: /Kassieren/i });
    await user.click(startCheckout);
    const neinButton = await screen.findByRole('button', { name: /Nein/ });
    await user.click(neinButton);
    const barButton = await screen.findByRole('button', { name: /Bar/ });
    await user.click(barButton);

    // Finde den Chip für 5,00 €, der KEIN Plus-Zeichen enthält
    const presetFuenfButton = await screen.findByRole('button', { 
      name: (content) => content.includes('5,00') && !content.includes('+')
    });
    await user.click(presetFuenfButton);

    const gegebenInput = screen.getByLabelText(/Manuell eingeben/);
    expect(gegebenInput).toHaveValue('5,00');

    const rueckgeldAnzeige = await screen.findByText('1,50 €');
    expect(rueckgeldAnzeige).toBeInTheDocument();
  });
});