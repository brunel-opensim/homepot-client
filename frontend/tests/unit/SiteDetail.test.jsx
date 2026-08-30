import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import api from '@/services/api';
import SiteDetail from '@/pages/Sites/SiteDetail';

vi.mock('@/services/api');
vi.mock('@/utils/analytics', () => ({
  trackActivity: vi.fn().mockResolvedValue(undefined),
  trackSearch: vi.fn().mockResolvedValue(undefined),
}));

const activeDevice = {
  id: 1,
  device_id: 'DEV-ACTIVE',
  name: 'Active POS',
  device_type: 'pos_terminal',
  is_active: true,
  lifecycle_state: 'active',
  status: 'online',
  connectivity_state: 'online',
  health_state: 'healthy',
  enrollment_method: 'self-enrolled',
  active_alerts: 0,
  last_seen: null,
};

const suspendedDevice = {
  id: 2,
  device_id: 'DEV-SUSP',
  name: 'Suspended POS',
  device_type: 'pos_terminal',
  is_active: false,
  lifecycle_state: 'suspended',
  status: 'offline',
  connectivity_state: 'offline',
  health_state: 'unknown',
  enrollment_method: 'self-enrolled',
  active_alerts: 0,
  last_seen: null,
};

const activeSite = {
  site_id: 'SITE-RES',
  id: 'SITE-RES',
  name: 'Restored Co',
  location: 'London',
  is_active: true,
  lifecycle_state: 'active',
  is_monitored: false,
};

describe('SiteDetail Model B', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.sites.get.mockResolvedValue(activeSite);
    api.devices.getSiteId.mockResolvedValue([activeDevice, suspendedDevice]);
    api.sites.getDashboard.mockResolvedValue({
      total_devices: 2,
      connectivity_counts: { online: 1, offline: 1 },
      health_counts: { healthy: 1, warning: 0, error: 0, maintenance: 0, unknown: 1 },
    });
  });

  const renderDetail = () =>
    render(
      <MemoryRouter initialEntries={['/sites/SITE-RES']}>
        <Routes>
          <Route path="/sites/:id" element={<SiteDetail />} />
        </Routes>
      </MemoryRouter>
    );

  it('fetches devices with includeUnpaired on a restored (active) site', async () => {
    renderDetail();

    expect(await screen.findByText('Active POS')).toBeInTheDocument();
    expect(screen.getByText('Suspended POS')).toBeInTheDocument();
    expect(api.devices.getSiteId).toHaveBeenCalledWith('SITE-RES', { includeUnpaired: true });
  });

  it('shows a view action for suspended devices and edit for active devices', async () => {
    renderDetail();

    await screen.findByText('Active POS');

    // Suspended device gets a View action
    expect(screen.getByTitle('View device details')).toBeInTheDocument();
  });

  it('does not show a view action for active devices', async () => {
    renderDetail();

    await screen.findByText('Active POS');

    // Only one view button (for the suspended device), not two
    expect(screen.getAllByTitle('View device details')).toHaveLength(1);
  });
});
