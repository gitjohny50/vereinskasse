import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import { Belege } from '../../pages/Belege';
import { api, type Kassenprofil, type Verkauf, ApiError } from '../../api';

// Mock the API module
vi.mock('../../api', async (importOriginal: () => Promise<typeof import('../../api')>) => {
  const original = await importOriginal();
  return {
    ...original,
    api: {
      ...original.api,
      verkaeufe: vi.fn(),
      nachdruck: vi.fn(),
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

const mockVerkaeufe: Verkauf[] = [
  {
    id: 1,
    belegnummer: 'B-2024-001',
    zeitpunkt: '2024-07-22T10:00:00Z',
    gesamt_cent: 1500,
    kassenprofil_id: 1,
    veranstaltung_id: null,
    benutzer_id: 1,
    waren_cent: 1500,
    pfand_cent: 0,
    status: 'abgeschlossen',
     zahlung: {
      bezeichnung: 'Bar',
      gegeben_cent: 2000,
      rueckgeld_cent: 500,
      // FIX: Add missing properties to satisfy the type definition
      zahlungsmethode_id: 1,
      betrag_cent: 1500,
    },
    positionen: [
      { typ: 'artikel', bezeichnung: 'Kaffee', menge: 1, gesamt_cent: 300, einzelpreis_cent: 300, artikelticket_modus: 'pro_stueck', steuersatz: 19 },
      { typ: 'artikel', bezeichnung: 'Kuchen', menge: 1, gesamt_cent: 1200, einzelpreis_cent: 1200, artikelticket_modus: 'pro_stueck', steuersatz: 19 },
    ],
  },
];

describe('Belege Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (api.verkaeufe as any).mockResolvedValue(mockVerkaeufe);
    (api.nachdruck as any).mockResolvedValue({});
  });

  test('should render and display receipts on initial load', async () => {
    render(<Belege profil={mockProfil} />);

    // Check if the API was called
    expect(api.verkaeufe).toHaveBeenCalledWith(mockProfil.id);

    // Check if the receipt number is displayed
    expect(await screen.findByText('B-2024-001')).toBeInTheDocument();
    // Check if the total amount is displayed
    expect(screen.getByText('15,00 €')).toBeInTheDocument();
  });

  test('should toggle receipt details on button click', async () => {
    const user = userEvent.setup();
    render(<Belege profil={mockProfil} />);

    // Find the "Details" button for the first receipt
    const detailsButton = await screen.findByRole('button', { name: 'Details' });

    // Initially, the details should not be visible
    expect(screen.queryByText(/1 × Kaffee/)).not.toBeInTheDocument();

    // Click to show details
    await user.click(detailsButton);
    expect(await screen.findByText(/1 × Kaffee/)).toBeInTheDocument();
    expect(screen.getByText(/Gegeben 20,00 €/)).toBeInTheDocument();

    // The button text should now be "Zu" (Close)
    const closeButton = await screen.findByRole('button', { name: 'Zu' });

    // Click again to hide details
    await user.click(closeButton);
    await waitFor(() => {
      expect(screen.queryByText(/1 × Kaffee/)).not.toBeInTheDocument();
    });
  });

  test('should call reprint API and show a success message', async () => {
    const user = userEvent.setup();
    render(<Belege profil={mockProfil} />);

    const reprintButton = await screen.findByRole('button', { name: 'Nachdruck' });
    await user.click(reprintButton);

    // Check if the API was called with the correct receipt ID
    expect(api.nachdruck).toHaveBeenCalledWith(1);

    // Check for the success message
    expect(await screen.findByText('Beleg B-2024-001 als Nachdruck gesendet.')).toBeInTheDocument();
  });

  test('should display an error message if data loading fails', async () => {
    // Override the mock to simulate a failure
    (api.verkaeufe as any).mockRejectedValue(new ApiError(500, 'Server nicht erreichbar'));

    render(<Belege profil={mockProfil} />);

    // Check for the error message
    expect(await screen.findByText('Server nicht erreichbar')).toBeInTheDocument();
  });
});