import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import { Auswertung, type Zeitreihe } from '../../pages/Auswertung';
import { api, type Kassenprofil, ApiError } from '../../api';

// Mock the API module, including the custom 'zeitreihe' function
vi.mock('../../api', async (importOriginal: () => Promise<typeof import('../../api')>) => {
  const original = await importOriginal();
  return {
    ...original,
    api: {
      ...original.api,
      zeitreihe: vi.fn(),
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

const mockZeitreiheData: Zeitreihe = {
  summe: {
    umsatz_cent: 15000,
    anzahl: 10,
    menge: 25,
    durchschnitt_cent: 1500,
    pfand_ausgegeben_cent: 500,
    pfand_zurueck_cent: 100,
    bar_cent: 10000,
    unbar_cent: 5000,
  },
  buckets: [
    { start: '2024-01-01T10:00:00', label: '10:00', gesamt_cent: 10000, anzahl: 5, menge: 10, segmente: [] },
    { start: '2024-01-01T11:00:00', label: '11:00', gesamt_cent: 5000, anzahl: 5, menge: 15, segmente: [] },
  ],
  top_artikel: [
    { bezeichnung: 'Test-Cola', menge: 5, umsatz_cent: 6250 },
    { bezeichnung: 'Bier', menge: 10, umsatz_cent: 3500 },
  ],
  verkaeufe: [
    { id: 1, zeitpunkt: '2024-01-01T10:05:00', belegnummer: 'B-1', zahlung: 'Bar', gesamt_cent: 6250, items: [{ bezeichnung: 'Test-Cola', menge: 5 }] },
    { id: 2, zeitpunkt: '2024-01-01T10:15:00', belegnummer: 'B-2', zahlung: 'Bar', gesamt_cent: 3500, items: [{ bezeichnung: 'Bier', menge: 10 }] },
  ],
};

describe('Auswertung Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Provide a default successful response for most tests
    (api.zeitreihe as any).mockResolvedValue(mockZeitreiheData);
  });

  test('should render and load initial data', async () => {
    render(<Auswertung profil={mockProfil} />);

    // Check for the main title
    expect(await screen.findByText('Verkaufs-Dashboard')).toBeInTheDocument();

    // Check if the API was called on mount
    expect(api.zeitreihe).toHaveBeenCalled();

    // Check if a key performance indicator (KPI) is displayed correctly
    // The total revenue from our mock data is 150.00 €
    expect(await screen.findByText('150,00 €')).toBeInTheDocument();
    // Check for the total number of sales
    expect(screen.getByText('10')).toBeInTheDocument();
  });

  test('should re-fetch data when changing granularity filter', async () => {
    const user = userEvent.setup();
    render(<Auswertung profil={mockProfil} />);

    // Wait for initial load
    await screen.findByText('Verkaufs-Dashboard');
    // The API is called once on initial render
    expect(api.zeitreihe).toHaveBeenCalledTimes(1);

    // Find and click the "Tag" button
    const tagButton = screen.getByRole('button', { name: 'Tag' });
    await user.click(tagButton);

    // The API should be called a second time with the new parameter
    await waitFor(() => {
      expect(api.zeitreihe).toHaveBeenCalledTimes(2);
    });

    // Verify that the second call included `granularitaet: 'tag'`
    expect(api.zeitreihe).toHaveBeenLastCalledWith(expect.objectContaining({
      granularitaet: 'tag',
    }));
  });

  test('should display an error message if data loading fails', async () => {
    // Override the mock to simulate a failure for this specific test
    (api.zeitreihe as any).mockRejectedValue(new ApiError(500, 'Datenbankfehler'));

    render(<Auswertung profil={mockProfil} />);

    // The component should catch the error and display a user-friendly message
    // FIX: The component correctly renders the specific error from the API.
    expect(await screen.findByText('Datenbankfehler')).toBeInTheDocument();
  });

  test('should fetch comparison data when comparison mode is activated', async () => {
    const user = userEvent.setup();
    render(<Auswertung profil={mockProfil} />);

    // Wait for initial load
    await screen.findByText('Verkaufs-Dashboard');
    // The API is called once on initial render
    expect(api.zeitreihe).toHaveBeenCalledTimes(1);

    // Find and click the "Vergleichen" (Compare) button
    const compareButton = screen.getByRole('button', { name: 'Vergleichen' });
    await user.click(compareButton);

    // The API should be called again for both the main and comparison data.
    // 1st call: initial load.
    // 2nd call: range A after activating comparison mode.
    // 3rd call: range B for comparison.
    await waitFor(() => {
      expect(api.zeitreihe).toHaveBeenCalledTimes(3);
    });

    // The first call is for range A, the second for range B.
    // Let's check the parameters of the second call.
    const secondCallParams = (api.zeitreihe as any).mock.calls[2][0];
    const firstCallParams = (api.zeitreihe as any).mock.calls[0][0];

    // The 'von' (from) date of the second call should be different from the first one
    expect(secondCallParams.von).not.toEqual(firstCallParams.von);
  });

  test('should re-fetch data when changing date range preset', async () => {
    const user = userEvent.setup();
    render(<Auswertung profil={mockProfil} />);

    await screen.findByText('Verkaufs-Dashboard');
    expect(api.zeitreihe).toHaveBeenCalledTimes(1);

    // Click on "Gestern" (Yesterday)
    const gesternButton = screen.getByRole('button', { name: 'Gestern' });
    await user.click(gesternButton);

    await waitFor(() => {
      expect(api.zeitreihe).toHaveBeenCalledTimes(2);
    });

    // Check if the API was called with dates for yesterday
    const today = new Date();
    const yesterday = new Date();
    yesterday.setDate(today.getDate() - 1);

    const expectedVon = `${yesterday.getFullYear()}-${String(yesterday.getMonth() + 1).padStart(2, '0')}-${String(yesterday.getDate()).padStart(2, '0')}`;

    expect(api.zeitreihe).toHaveBeenLastCalledWith(expect.objectContaining({
      von: expect.stringContaining(expectedVon),
    }));
  });

  test('should re-fetch data when changing the metric', async () => {
    const user = userEvent.setup();
    render(<Auswertung profil={mockProfil} />);

    await screen.findByText('Verkaufs-Dashboard');
    expect(api.zeitreihe).toHaveBeenCalledTimes(1);

    // Change metric to "Anzahl Verkäufe"
    const anzahlButton = screen.getByRole('button', { name: 'Anzahl Verkäufe' });
    await user.click(anzahlButton);

    await waitFor(() => {
      expect(api.zeitreihe).toHaveBeenCalledTimes(2);
    });

    expect(api.zeitreihe).toHaveBeenLastCalledWith(expect.objectContaining({
      metrik: 'anzahl',
    }));
  });

  test('should filter the sales list when a top article is clicked', async () => {
    const user = userEvent.setup();
    render(<Auswertung profil={mockProfil} />);

    // Both sales should be visible initially
    expect(await screen.findByText('B-1')).toBeInTheDocument();
    expect(await screen.findByText('B-2')).toBeInTheDocument();

    // Click on the "Test-Cola" article in the drill-down list.
    // We need to be specific because the name "Test-Cola" appears in multiple buttons.
    // We find the container for the filter chips and then the button within it.
    const drillDownContainer = (await screen.findByText('Drill-down')).nextElementSibling as HTMLElement;
    const colaFilterButton = within(drillDownContainer).getByRole('button', { name: /Test-Cola/ });
    await user.click(colaFilterButton);

    // Now, only the sale with "Test-Cola" should be visible
    await waitFor(() => {
      expect(screen.getByText('B-1')).toBeInTheDocument();
      expect(screen.queryByText('B-2')).not.toBeInTheDocument();
    });
  });

  test.skip('should filter sales list when a chart segment is clicked', async () => {
    const user = userEvent.setup();
    render(<Auswertung profil={mockProfil} />);

    // First, change the grouping to show segments in the chart
    const topArtikelButton = await screen.findByRole('button', { name: 'Top-Artikel' });
    await user.click(topArtikelButton);

    // Wait for the chart to be rendered with its segments
    const chartSegment = await screen.findByTitle('Test-Cola: 62,50 €');
    
    // Both sales should be visible initially
    expect(await screen.findByText('B-1')).toBeInTheDocument();
    expect(screen.getByText('B-2')).toBeInTheDocument();

    // Click the segment for "Test-Cola"
    await user.click(chartSegment);

    // Now, only the sale with "Test-Cola" should be visible
    await waitFor(() => {
      expect(screen.getByText('B-1')).toBeInTheDocument();
      expect(screen.queryByText('B-2')).not.toBeInTheDocument();
    });
  });

  test('should re-fetch data when using custom date range', async () => {
    const user = userEvent.setup();
    render(<Auswertung profil={mockProfil} />);

    await screen.findByText('Verkaufs-Dashboard');
    expect(api.zeitreihe).toHaveBeenCalledTimes(1);

    // Switch to custom date range
    const customButton = screen.getByRole('button', { name: 'Benutzerdefiniert' });
    await user.click(customButton);

    // Find the date inputs and change them
    const vonInput = screen.getByLabelText('Von');
    const bisInput = screen.getByLabelText('Bis');

    await user.clear(vonInput);
    await user.type(vonInput, '2024-05-01');
    await user.clear(bisInput);
    await user.type(bisInput, '2024-05-31');

    // The component should automatically re-fetch data
    await waitFor(() => {
      expect(api.zeitreihe).toHaveBeenLastCalledWith(expect.objectContaining({
        von: '2024-05-01T00:00:00',
        bis: '2024-06-01T00:00:00', // Note: 'bis' is exclusive, so it's the next day
      }));
    });
  });
});