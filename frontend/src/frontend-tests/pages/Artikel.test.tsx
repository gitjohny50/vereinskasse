import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi, beforeEach, Mock } from 'vitest';
import { Artikel } from '../../pages/Artikel';
import { api, type Kassenprofil, ApiError } from '../../api';

// Mock the entire API module
vi.mock('../../api', async (importOriginal: () => Promise<typeof import('../../api')>) => {
  const original = await importOriginal();
  return {
    ...original,
    api: {
      ...original.api,
      kategorien: vi.fn().mockResolvedValue([]),
      pfandarten: vi.fn().mockResolvedValue([]),
      artikel: vi.fn().mockResolvedValue([]),
      artikelAnlegen: vi.fn().mockResolvedValue({ id: 101 }),
      artikelAendern: vi.fn().mockResolvedValue({ id: 1 }),
      artikelKopieren: vi.fn().mockResolvedValue({ id: 102 }),
      artikelArchivieren: vi.fn().mockResolvedValue({ id: 1 }),
      artikelAlleArchivieren: vi.fn(),
      artikelCsvImport: vi.fn(),
      artikelPfandZuruecksetzen: vi.fn(),
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

const mockKategorien = [{ id: 1, name: 'Getränke', aktiv: true }];
const mockArtikel = [
  { id: 1, name: 'Wasser', preis_cent: 250, aktiv: true, kategorie_id: 1, pfandzuordnungen: [], artikelticket_modus: 'pro_stueck', sortierung: 0, kurzname: '' },
];

describe('Artikel Component', () => {
  beforeEach(() => {
    // Restore all mocks before each test to ensure isolation
    vi.clearAllMocks(); // clearAllMocks ist hier besser, da wir die Mocks unten neu definieren
    // Mock initial data load for most tests
    (api.kategorien as Mock).mockResolvedValue(mockKategorien);
    (api.artikel as Mock).mockResolvedValue(mockArtikel);
  });

  test('should render the list of articles on initial load', async () => {
    render(<Artikel profil={mockProfil} />);

    // Wait for the article name to appear in the table
    expect(await screen.findByText('Wasser')).toBeInTheDocument();

    // Check if other details are rendered
    expect(screen.getByText('Getränke')).toBeInTheDocument();
    expect(screen.getByText('2,50 €')).toBeInTheDocument();
  });

  test('should open the create form, allow creating a new article, and reload the list', async () => {
    const user = userEvent.setup();
    render(<Artikel profil={mockProfil} />);

    // 1. Open the form
    const anlegenButton = screen.getByRole('button', { name: '+ Artikel anlegen' });
    await user.click(anlegenButton);

    // 2. Fill out the form
    await user.type(screen.getByLabelText('Name'), 'Neue Cola');
    await user.type(screen.getByLabelText('Preis (€)'), '3,00');
    await user.selectOptions(screen.getByLabelText('Kategorie'), 'Getränke');

    // 3. Save the new article
    const speichernButton = screen.getByRole('button', { name: 'Speichern' });
    await user.click(speichernButton);

    // 4. Assertions
    // Check if the API was called correctly
    await waitFor(() => {
      expect(api.artikelAnlegen).toHaveBeenCalledWith(expect.objectContaining({
        name: 'Neue Cola',
        preis_cent: 300,
        kategorie_id: 1,
      }));
    });

    // Check if the list was reloaded (api.artikel is called again)
    // It's called once on mount, and once after saving.
    expect(api.artikel).toHaveBeenCalledTimes(2);
  });

  test('should open the edit dialog and save changes', async () => {
    const user = userEvent.setup();
    render(<Artikel profil={mockProfil} />);

    // 1. Find the edit button for "Wasser" and click it
    const editButton = await screen.findByRole('button', { name: 'Bearbeiten' });
    await user.click(editButton);

    // 2. The dialog should appear. Change the name.
    const nameInput = await screen.findByDisplayValue('Wasser');
    await user.clear(nameInput);
    await user.type(nameInput, 'Stilles Wasser');

    // 3. Click save in the dialog
    const speichernButton = screen.getByRole('button', { name: 'Speichern' });
    await user.click(speichernButton);

    // 4. Assertions
    // Check if the API was called with the new name
    await waitFor(() => {
      expect(api.artikelAendern).toHaveBeenCalledWith(1, expect.objectContaining({
        name: 'Stilles Wasser',
      }));
    });

    // Check if the list was reloaded
    expect(api.artikel).toHaveBeenCalledTimes(2);
  });

  test('should toggle the active status of an article', async () => {
    const user = userEvent.setup();
    render(<Artikel profil={mockProfil} />);

    // 1. Find the toggle switch
    const toggle = await screen.findByRole('switch', { name: '' });
    expect(toggle).toBeChecked(); // Initially active

    // 2. Click the toggle
    await user.click(toggle);

    // 3. Assertions
    // Check if the API was called to deactivate the article
    await waitFor(() => {
      expect(api.artikelAendern).toHaveBeenCalledWith(1, { aktiv: false });
    });

    // Check if the list was reloaded
    expect(api.artikel).toHaveBeenCalledTimes(2);
  });

  test('should show validation errors when creating an article with invalid data', async () => {
    const user = userEvent.setup();
    render(<Artikel profil={mockProfil} />);

    // Open the form
    const anlegenButton = screen.getByRole('button', { name: '+ Artikel anlegen' });
    await user.click(anlegenButton);

    const speichernButton = screen.getByRole('button', { name: 'Speichern' });

    // 1. Try to save without a name
    await user.click(speichernButton);
    expect(await screen.findByText('Name fehlt.')).toBeInTheDocument();

    // 2. Enter a name, but an invalid price
    await user.type(screen.getByLabelText('Name'), 'Testartikel');
    await user.type(screen.getByLabelText('Preis (€)'), 'abc');
    await user.click(speichernButton);
    expect(await screen.findByText('Preis ungültig (z. B. 2,50).')).toBeInTheDocument();
  });

  test('should archive an article when archive button is clicked', async () => {
    const user = userEvent.setup();
    render(<Artikel profil={mockProfil} />);

    const archiveButton = await screen.findByRole('button', { name: 'Archivieren' });
    await user.click(archiveButton);

    await waitFor(() => {
      expect(api.artikelArchivieren).toHaveBeenCalledWith(1);
    });

    expect(api.artikel).toHaveBeenCalledTimes(2);
  });

  test('should copy an article when copy button is clicked', async () => {
    const user = userEvent.setup();
    render(<Artikel profil={mockProfil} />);

    const copyButton = await screen.findByRole('button', { name: 'Kopieren' });
    await user.click(copyButton);

    await waitFor(() => {
      expect(api.artikelKopieren).toHaveBeenCalledWith(1);
    });

    expect(api.artikel).toHaveBeenCalledTimes(2);
  });

  test('should archive all articles via maintenance action', async () => {
    const user = userEvent.setup();
    // Mock window.confirm to simulate user confirmation
    const confirmSpy = vi.spyOn(window, 'confirm').mockImplementation(() => true);

    (api.artikelAlleArchivieren as Mock).mockResolvedValue({ anzahl: 1 });

    render(<Artikel profil={mockProfil} />);

    const archiveAllButton = await screen.findByRole('button', { name: 'Alle Artikel archivieren' });
    await user.click(archiveAllButton);

    // Check that the confirmation dialog was shown
    expect(confirmSpy).toHaveBeenCalledWith('Alle bestehenden Artikel dieses Kassenprofils archivieren und deaktivieren? Alte Belege bleiben erhalten.');

    // Check that the API was called
    await waitFor(() => {
      expect(api.artikelAlleArchivieren).toHaveBeenCalledWith(mockProfil.id);
    });

    // Check that the list was reloaded
    expect(api.artikel).toHaveBeenCalledTimes(2);

    confirmSpy.mockRestore(); // Clean up the spy
  });

  test('should handle CSV import successfully', async () => {
    const user = userEvent.setup();
    const csvContent = 'name;preis\nTest-CSV-Artikel;5,00';
    const file = new File([csvContent], 'artikel.csv', { type: 'text/csv' });

    // Mock the API response for the import
    (api.artikelCsvImport as Mock).mockResolvedValue({
      angelegt: 1,
      aktualisiert: 0,
      kategorien_angelegt: 0,
      pfandarten_angelegt: 0,
      fehler: [],
    });

    render(<Artikel profil={mockProfil} />);

    // Find the file input. It's hidden, so we get it by its label.
    const fileInput = screen.getByLabelText<HTMLInputElement>('CSV auswählen');

    // Simulate file upload
    await user.upload(fileInput, file);

    // Check that the API was called with the correct content
    await waitFor(() => {
      expect(api.artikelCsvImport).toHaveBeenCalledWith(mockProfil.id, csvContent, ';');
    });

    // Check for the success message
    expect(await screen.findByText(/1 Artikel angelegt/)).toBeInTheDocument();

    // Check that the list was reloaded
    expect(api.artikel).toHaveBeenCalledTimes(2);
  });

  test('should reset deposit assignments via maintenance action', async () => {
    const user = userEvent.setup();
    const confirmSpy = vi.spyOn(window, 'confirm').mockImplementation(() => true);
    (api.artikelPfandZuruecksetzen as Mock).mockResolvedValue({ anzahl: 5 });

    render(<Artikel profil={mockProfil} />);

    const resetButton = await screen.findByRole('button', { name: 'Pfand zurücksetzen' });
    await user.click(resetButton);

    expect(confirmSpy).toHaveBeenCalledWith('Alle Pfandzuordnungen der Artikel in diesem Kassenprofil entfernen? Pfandarten selbst bleiben erhalten.');

    await waitFor(() => {
      expect(api.artikelPfandZuruecksetzen).toHaveBeenCalledWith(mockProfil.id);
    });

    expect(await screen.findByText('5 Pfandzuordnungen entfernt.')).toBeInTheDocument();
    expect(api.artikel).toHaveBeenCalledTimes(2);
  });

  test('should display an error message on a failed CSV import', async () => {
    const user = userEvent.setup();
    const file = new File(['test'], 'test.csv', { type: 'text/csv' });

    // Mock a failure from the API
    (api.artikelCsvImport as Mock).mockRejectedValue(new Error('Internal Server Error'));

    render(<Artikel profil={mockProfil} />);

    const fileInput = screen.getByLabelText<HTMLInputElement>('CSV auswählen');
    await user.upload(fileInput, file);

    // Check for the generic error message
    expect(await screen.findByText('CSV-Import fehlgeschlagen.')).toBeInTheDocument();
  });

  test('should show validation errors in the edit dialog', async () => {
    const user = userEvent.setup();
    render(<Artikel profil={mockProfil} />);

    // Open the edit dialog
    const editButton = await screen.findByRole('button', { name: 'Bearbeiten' });
    await user.click(editButton);

    // Find the name input and clear it
    const nameInput = await screen.findByDisplayValue('Wasser');
    await user.clear(nameInput);

    // Try to save
    const speichernButton = screen.getByRole('button', { name: 'Speichern' });
    await user.click(speichernButton);

    // Check for the validation error
    expect(await screen.findByText('Name fehlt.')).toBeInTheDocument();
    // Ensure the API was not called
    expect(api.artikelAendern).not.toHaveBeenCalled();
  });

  test('should display an error if the initial data load fails', async () => {
    // Override the mock for this specific test
    (api.artikel as Mock).mockRejectedValue(new Error('Ladefehler'));

    render(<Artikel profil={mockProfil} />);

    expect(await screen.findByText('Fehler beim Laden.')).toBeInTheDocument();
  });

  test('should display an error in the edit dialog if saving fails', async () => {
    const user = userEvent.setup();
    // Mock the API to throw an error on save
    (api.artikelAendern as Mock).mockRejectedValue(new ApiError(500, 'Server nicht erreichbar'));

    render(<Artikel profil={mockProfil} />);

    // Open the edit dialog
    const editButton = await screen.findByRole('button', { name: 'Bearbeiten' });
    await user.click(editButton);

    // Try to save
    const speichernButton = screen.getByRole('button', { name: 'Speichern' });
    await user.click(speichernButton);

    // Check for the error message within the dialog
    expect(await screen.findByText('Server nicht erreichbar')).toBeInTheDocument();

    // The dialog should still be open
    expect(screen.getByText('Artikel bearbeiten')).toBeInTheDocument();
  });

  test.skip('should handle deposit quantity changes in the create form', async () => {
    const user = userEvent.setup();
    (api.pfandarten as Mock).mockResolvedValue([
      { id: 5, name: 'Kastenpfand', betrag_cent: 150, aktiv: true }
    ]);

    render(<Artikel profil={mockProfil} />);

    // Open the form
    const anlegenButton = screen.getByRole('button', { name: '+ Artikel anlegen' });
    await user.click(anlegenButton);

    // Select the deposit
    const pfandChip = await screen.findByText(/Kastenpfand/);
    await user.click(pfandChip);

    // The quantity input should appear
    const mengeInput = await screen.findByRole('spinbutton');
    expect(mengeInput).toHaveValue(1);

    // Change the quantity. First clear the input, then type the new value.
    await user.clear(mengeInput);
    await user.type(mengeInput, '12');

    // Fill out the rest and save
    await user.type(screen.getByLabelText('Name'), 'Kasten Bier');
    await user.type(screen.getByLabelText('Preis (€)'), '15,00');
    await user.click(screen.getByRole('button', { name: 'Speichern' }));

    // Check if the API was called with the correct deposit assignment
    await waitFor(() => {
      expect(api.artikelAnlegen).toHaveBeenCalledWith(expect.objectContaining({
        pfandzuordnungen: expect.arrayContaining([
          expect.objectContaining({ pfandart_id: 5, menge_pro_einheit: 12 })
        ])
      }));
    });
  });
});