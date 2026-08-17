import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import api from '@/services/api';
import SitesList from '@/pages/Sites/SitesList';

vi.mock('@/services/api');
vi.mock('@/utils/analytics', () => ({
  trackActivity: vi.fn().mockResolvedValue(undefined),
  trackSearch: vi.fn().mockResolvedValue(undefined),
}));

const mockActiveSites = {
  sites: [
    {
      site_id: 'SITE-AAA',
      id: 'SITE-AAA',
      name: 'Head Office',
      location: 'London',
      status: 'Online',
      is_active: true,
      lifecycle_state: 'active',
      devices_count: 2,
      os_types: [],
    },
  ],
};

const mockArchivedSites = {
  sites: [
    {
      site_id: 'SITE-AAA',
      id: 'SITE-AAA',
      name: 'Head Office',
      location: 'London',
      status: 'Offline',
      is_active: false,
      lifecycle_state: 'archived',
      devices_count: 2,
      os_types: [],
    },
  ],
};

describe('SitesList', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.sites.list.mockResolvedValue(mockActiveSites);
    api.sites.restore = vi.fn().mockResolvedValue({ message: 'restored' });
  });

  const renderList = () =>
    render(
      <MemoryRouter>
        <SitesList />
      </MemoryRouter>
    );

  it('renders active sites by default with Active and Archived tabs', async () => {
    renderList();

    expect(await screen.findByText('Head Office')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Active' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Archived' })).toBeInTheDocument();
    expect(api.sites.list).toHaveBeenCalledWith({ includeArchived: false });
  });

  it('fetches archived sites when the Archived tab is clicked and shows a restore button', async () => {
    api.sites.list.mockResolvedValueOnce(mockActiveSites).mockResolvedValueOnce(mockArchivedSites);

    renderList();

    fireEvent.click(await screen.findByRole('button', { name: 'Archived' }));

    await waitFor(() => expect(api.sites.list).toHaveBeenLastCalledWith({ includeArchived: true }));

    expect(await screen.findByRole('button', { name: 'Restore' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Edit' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Delete' })).not.toBeInTheDocument();
  });

  it('calls sites.restore and removes the site when restore is clicked', async () => {
    api.sites.list.mockResolvedValueOnce(mockActiveSites).mockResolvedValueOnce(mockArchivedSites);

    renderList();

    fireEvent.click(await screen.findByRole('button', { name: 'Archived' }));

    const restoreButton = await screen.findByRole('button', { name: 'Restore' });
    fireEvent.click(restoreButton);

    await waitFor(() => expect(api.sites.restore).toHaveBeenCalledWith('SITE-AAA'));

    await waitFor(() => expect(screen.queryByText('Head Office')).not.toBeInTheDocument());
  });
});
