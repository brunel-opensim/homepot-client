import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import api from '@/services/api';
import EnrolmentIntentsList from '@/pages/EnrolmentIntents/EnrolmentIntentsList';

vi.mock('@/services/api');

const mockIntents = [
  {
    id: 1,
    intent_id: '550e8400-e29b-41d4-a716-446655440001',
    site_id: 'site-001',
    tenant_id: null,
    enrolment_method: 'pre-provisioned',
    expected_device_identity: 'SN-ABC-001',
    expires_at: new Date(Date.now() + 86400000).toISOString(),
    consumed_at: null,
    creator_id: 1,
    status: 'pending',
    idempotency_key: null,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: 2,
    intent_id: '550e8400-e29b-41d4-a716-446655440002',
    site_id: 'site-001',
    tenant_id: null,
    enrolment_method: 'pre-provisioned',
    expected_device_identity: null,
    expires_at: new Date(Date.now() - 86400000).toISOString(),
    consumed_at: null,
    creator_id: 1,
    status: 'approved',
    idempotency_key: 'req-abc-123',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: 3,
    intent_id: '550e8400-e29b-41d4-a716-446655440003',
    site_id: 'site-001',
    tenant_id: null,
    enrolment_method: 'pre-provisioned',
    expected_device_identity: 'SN-DEF-002',
    expires_at: null,
    consumed_at: new Date().toISOString(),
    creator_id: 1,
    status: 'consumed',
    idempotency_key: null,
    created_at: new Date(Date.now() - 604800000).toISOString(),
    updated_at: new Date().toISOString(),
  },
];

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/sites/site-001/enrolment-intents']}>
      <Routes>
        <Route path="/sites/:id/enrolment-intents" element={<EnrolmentIntentsList />} />
        <Route path="/sites/:id" element={<div>Site Detail Page</div>} />
      </Routes>
    </MemoryRouter>
  );
}

describe('EnrolmentIntentsList', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.enrolmentIntents.list.mockResolvedValue({ intents: mockIntents, total: 3 });
  });

  it('renders the page title and navigation', async () => {
    renderPage();
    expect(await screen.findByText('Enrolment Intents')).toBeInTheDocument();
    expect(screen.getByText('Back to Site')).toBeInTheDocument();
  });

  it('renders stats cards with correct counts', async () => {
    renderPage();
    await screen.findByText('Enrolment Intents');
    const allActive = screen.getAllByText('Active');
    const allConsumed = screen.getAllByText('Consumed');
    const allExpired = screen.getAllByText('Expired');
    const allRevoked = screen.getAllByText('Revoked');
    const allRejected = screen.getAllByText('Rejected');
    expect(allActive.length).toBeGreaterThanOrEqual(1);
    expect(allConsumed.length).toBeGreaterThanOrEqual(1);
    expect(allExpired.length).toBeGreaterThanOrEqual(1);
    expect(allRevoked.length).toBeGreaterThanOrEqual(1);
    expect(allRejected.length).toBeGreaterThanOrEqual(1);
  });

  it('renders all intents in the table', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('SN-ABC-001')).toBeInTheDocument();
      expect(screen.getByText('SN-DEF-002')).toBeInTheDocument();
    });
  });

  it('shows Approve and Reject buttons for pending intents', async () => {
    renderPage();
    await screen.findByText('Enrolment Intents');
    const approveButtons = screen.getAllByText('Approve');
    const rejectButtons = screen.getAllByText('Reject');
    expect(approveButtons.length).toBeGreaterThanOrEqual(1);
    expect(rejectButtons.length).toBeGreaterThanOrEqual(1);
  });

  it('shows Consumed label for consumed intents', async () => {
    renderPage();
    await screen.findByText('Enrolment Intents');
    const consumedElements = screen.getAllByText('Consumed');
    expect(consumedElements.length).toBeGreaterThanOrEqual(1);
  });

  it('shows expired indicator for past expiration dates', async () => {
    renderPage();
    await screen.findByText('Enrolment Intents');
    const expiredLabels = screen.getAllByText('Expired');
    expect(expiredLabels.length).toBeGreaterThanOrEqual(1);
  });

  it('shows empty state when no intents exist', async () => {
    api.enrolmentIntents.list.mockResolvedValue({ intents: [], total: 0 });
    renderPage();
    expect(await screen.findByText('No enrolment intents found')).toBeInTheDocument();
  });

  it('shows loading spinner while fetching', () => {
    api.enrolmentIntents.list.mockImplementation(() => new Promise(() => {}));
    renderPage();
    const spinner = document.querySelector('.animate-spin');
    expect(spinner).toBeInTheDocument();
  });

  describe('intent creation', () => {
    it('create form appears when clicking Create Intent', async () => {
      renderPage();
      const createBtn = await screen.findByText('Create Intent');
      await userEvent.click(createBtn);
      await waitFor(() => {
        expect(screen.getByText('Create New Enrolment Intent')).toBeInTheDocument();
      });
    });

    it('calls API and shows claim token on successful creation', async () => {
      const claimToken = 'tok_random_abc123_def456';
      api.enrolmentIntents.create.mockResolvedValue({
        claim_token: claimToken,
        intent_id: '550e8400-e29b-41d4-a716-446655440099',
        status: 'pending',
      });

      renderPage();
      await screen.findByText('Enrolment Intents');

      const createBtn = screen.getByText('Create Intent');
      await userEvent.click(createBtn);
      await screen.findByText('Create New Enrolment Intent');

      const submitBtn = screen.getByText('Create Intent', { selector: 'button[type="submit"]' });
      await userEvent.click(submitBtn);

      await waitFor(() => {
        expect(api.enrolmentIntents.create).toHaveBeenCalledWith('site-001', {
          enrolment_method: 'pre-provisioned',
          expires_in_hours: 48,
        });
      });

      await waitFor(() => {
        expect(screen.getByText('Intent Created Successfully')).toBeInTheDocument();
        expect(screen.getByText(claimToken)).toBeInTheDocument();
        expect(screen.getByText(/will not be shown again/i)).toBeInTheDocument();
      });
    });
  });
});
