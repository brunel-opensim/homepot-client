import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import api from '@/services/api';
import AIProposalsList from '@/pages/AIProposals/AIProposalsList';

vi.mock('@/services/api');

const mockPlans = [
  {
    plan_id: '550e8400-e29b-41d4-a716-446655440001',
    status: 'pending_approval',
    risk_tier: 'T2',
    reversible: true,
    rationale: 'Device is reporting elevated temperature; restart the collector.',
    created_at: new Date().toISOString(),
    created_by: 'ai',
    trust: { mode: 'assisted', score: 0.82, passed_gates: [], failed_gate: null },
    steps: [
      {
        seq: 1,
        action: 'restart',
        target_device_id: 'sensor-temp-01',
        params: {},
        status: 'pending',
      },
    ],
    approvals: [],
  },
  {
    plan_id: '550e8400-e29b-41d4-a716-446655440002',
    status: 'approved',
    risk_tier: 'T2',
    reversible: true,
    rationale: 'Apply updated reporting interval.',
    created_at: new Date().toISOString(),
    created_by: 'ai',
    trust: { mode: 'assisted', score: 0.9, passed_gates: [], failed_gate: null },
    steps: [
      {
        seq: 1,
        action: 'update_config',
        target_device_id: 'sensor-temp-02',
        params: { interval: 30 },
        status: 'pending',
      },
    ],
    approvals: [{ actor: 'tech@example.com', decision: 'approved', reason: null }],
  },
];

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/ai-proposals']}>
      <AIProposalsList />
    </MemoryRouter>
  );
}

describe('AIProposalsList', () => {
  beforeEach(() => {
    api.aiProposals.list.mockResolvedValue({ plans: mockPlans, count: mockPlans.length });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders the header and plan rationale', async () => {
    renderPage();
    expect(await screen.findByText('AI Action Proposals')).toBeInTheDocument();
    expect(screen.getByText(/elevated temperature/)).toBeInTheDocument();
  });

  it('shows Approve/Reject only for reviewable plans', async () => {
    renderPage();
    await screen.findByText('AI Action Proposals');
    expect(screen.getAllByText('Approve')).toHaveLength(1);
    expect(screen.getAllByText('Reject')).toHaveLength(1);
  });

  it('approves a plan and refreshes the list', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    api.aiProposals.approve.mockResolvedValue({ ...mockPlans[0], status: 'approved' });

    renderPage();
    await screen.findByText('AI Action Proposals');
    await userEvent.click(screen.getByText('Approve'));

    await waitFor(() => {
      expect(api.aiProposals.approve).toHaveBeenCalledWith(mockPlans[0].plan_id, null);
    });
    expect(api.aiProposals.list).toHaveBeenCalledTimes(2);
  });

  it('rejects a plan with a prompted reason', async () => {
    vi.spyOn(window, 'prompt').mockReturnValue('not now');
    api.aiProposals.reject.mockResolvedValue({ ...mockPlans[0], status: 'rejected' });

    renderPage();
    await screen.findByText('AI Action Proposals');
    await userEvent.click(screen.getByText('Reject'));

    await waitFor(() => {
      expect(api.aiProposals.reject).toHaveBeenCalledWith(mockPlans[0].plan_id, 'not now');
    });
  });

  it('shows an empty state when there are no plans', async () => {
    api.aiProposals.list.mockResolvedValue({ plans: [], count: 0 });
    renderPage();
    expect(await screen.findByText(/No AI action proposals/)).toBeInTheDocument();
  });

  it('shows a loading spinner while fetching', () => {
    api.aiProposals.list.mockImplementation(() => new Promise(() => {}));
    renderPage();
    expect(document.querySelector('.animate-spin')).toBeInTheDocument();
  });
});
