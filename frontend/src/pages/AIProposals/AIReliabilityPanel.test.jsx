import { describe, it, expect, vi, beforeEach } from 'vitest';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import AIReliabilityPanel from './AIReliabilityPanel';
import api from '@/services/api';

vi.mock('@/services/api', () => ({
  default: {
    ai: {
      getPlanSummary: vi.fn(),
      getReliability: vi.fn(),
      getAutonomy: vi.fn(),
    },
  },
  apiHelpers: {
    formatError: vi.fn(() => 'boom'),
  },
}));

const reliabilityFixture = {
  period_days: 30,
  total_plans: 3,
  action_types: {
    restart_service: {
      counts: {
        proposed: 2,
        approved: 1,
        rejected: 0,
        executed: 1,
        succeeded: 1,
        failed: 0,
        rolled_back: 0,
        verified_improvement: 1,
      },
      rates: {
        proposal_acceptance: 0.5,
        execution_success: 1.0,
        verified_improvement: 1.0,
        rollback_rate: 0.0,
      },
    },
  },
};

beforeEach(() => {
  vi.clearAllMocks();
});

const renderWithRouter = (ui) => render(<MemoryRouter>{ui}</MemoryRouter>);

describe('AIReliabilityPanel (Phase E: reliability + task aggregation)', () => {
  it('renders the panel heading and fetches autonomy levels', async () => {
    api.ai.getPlanSummary.mockResolvedValue({
      total: 3,
      period_days: 30,
      by_status: { pending_approval: 2, approved: 1 },
      recent: [],
    });
    api.ai.getReliability.mockResolvedValue(reliabilityFixture);
    api.ai.getAutonomy.mockResolvedValue({
      restart_service: { level: 1, sample_count: 4, success_rate: 0.9, rollback_proven: false },
    });

    render(<AIReliabilityPanel />);

    expect(await screen.findByText(/AI Reliability/i)).toBeInTheDocument();
    expect((await screen.findAllByText(/restart_service/)).length).toBeGreaterThan(0);
    expect(screen.getByText(/Autonomy levels/i)).toBeInTheDocument();
    expect(api.ai.getPlanSummary).toHaveBeenCalledWith(30, null, null, null);
    expect(api.ai.getReliability).toHaveBeenCalledWith(30, null, null);
    expect(api.ai.getAutonomy).toHaveBeenCalled();
  });

  it('renders a warning when every AI endpoint fails', async () => {
    api.ai.getPlanSummary.mockRejectedValue(new Error('network down'));
    api.ai.getReliability.mockRejectedValue(new Error('network down'));
    api.ai.getAutonomy.mockRejectedValue(new Error('network down'));

    render(<AIReliabilityPanel />);

    expect(await screen.findByText(/Some AI metrics could not be loaded/i)).toBeInTheDocument();
    expect(await screen.findAllByText(/boom/)).toHaveLength(3);
  });

  it('still renders loaded sections when only reliability fails', async () => {
    api.ai.getPlanSummary.mockResolvedValue({
      total: 3,
      period_days: 30,
      by_status: { pending_approval: 2, approved: 1 },
      recent: [],
    });
    api.ai.getReliability.mockRejectedValue(new Error('network down'));
    api.ai.getAutonomy.mockResolvedValue({
      restart_service: { level: 1, sample_count: 4, success_rate: 0.9, rollback_proven: false },
    });

    render(<AIReliabilityPanel />);

    expect(await screen.findByText(/Some AI metrics could not be loaded/i)).toBeInTheDocument();
    expect(screen.getByText(/Delegated tasks/i)).toBeInTheDocument();
    expect(screen.getByText(/Autonomy levels/i)).toBeInTheDocument();
  });

  it('treats an HTTP 200 {status:error} reliability payload as a failure', async () => {
    api.ai.getPlanSummary.mockResolvedValue({
      total: 0,
      period_days: 30,
      by_status: {},
      recent: [],
    });
    api.ai.getReliability.mockResolvedValue({ status: 'error', message: 'db down' });
    api.ai.getAutonomy.mockResolvedValue({});

    render(<AIReliabilityPanel />);

    expect(await screen.findByText(/Some AI metrics could not be loaded/i)).toBeInTheDocument();
    expect(screen.getByText(/db down/)).toBeInTheDocument();
    expect(screen.queryByText(/No action outcomes recorded yet/i)).not.toBeInTheDocument();
  });

  it('refetches the summary when a status badge is clicked', async () => {
    api.ai.getPlanSummary.mockResolvedValue({
      total: 1,
      period_days: 30,
      by_status: { succeeded: 1 },
      recent: [
        {
          plan_id: 'plan-click',
          status: 'succeeded',
          risk_tier: 'T2',
          created_at: '2026-11-20T10:00:00Z',
          created_by: 'ai',
          step_count: 1,
          target_device_id: 'DEV-1',
        },
      ],
    });
    api.ai.getReliability.mockResolvedValue(reliabilityFixture);
    api.ai.getAutonomy.mockResolvedValue({});
    const onStatusFilterChange = vi.fn();

    renderWithRouter(
      <AIReliabilityPanel statusFilter="" onStatusFilterChange={onStatusFilterChange} />
    );

    expect(await screen.findByText(/AI Reliability/i)).toBeInTheDocument();
    expect(api.ai.getPlanSummary).toHaveBeenCalledTimes(1);
    expect(api.ai.getPlanSummary).toHaveBeenNthCalledWith(1, 30, null, null, null);

    fireEvent.click(screen.getByRole('button', { name: /Succeeded/ }));

    expect(onStatusFilterChange).toHaveBeenCalledWith('succeeded');
    await waitFor(() => expect(api.ai.getPlanSummary).toHaveBeenCalledTimes(2));
    expect(api.ai.getPlanSummary).toHaveBeenLastCalledWith(30, null, null, 'succeeded');
  });

  it('lets the newest SSE-triggered refresh win over an older one', async () => {
    let resolveFirst;
    let resolveSecond;
    api.ai.getPlanSummary
      .mockResolvedValueOnce({ total: 0, period_days: 30, by_status: {}, recent: [] })
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveFirst = resolve;
          })
      )
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveSecond = resolve;
          })
      );
    api.ai.getReliability.mockResolvedValue(reliabilityFixture);
    api.ai.getAutonomy.mockResolvedValue({});

    renderWithRouter(
      <AIReliabilityPanel statusFilter="succeeded" onStatusFilterChange={vi.fn()} />
    );

    expect(await screen.findByText(/AI Reliability/i)).toBeInTheDocument();

    act(() => {
      window.dispatchEvent(new Event('ai:plan-updated'));
      window.dispatchEvent(new Event('ai:plan-updated'));
    });

    await waitFor(() => expect(api.ai.getPlanSummary).toHaveBeenCalledTimes(3));

    await act(async () => {
      resolveSecond({
        total: 1,
        period_days: 30,
        by_status: { succeeded: 1 },
        recent: [
          {
            plan_id: 'plan-latest',
            status: 'succeeded',
            risk_tier: 'T2',
            created_at: '2026-11-20T10:00:00Z',
            created_by: 'ai',
            step_count: 1,
            target_device_id: 'DEV-1',
          },
        ],
      });
    });
    expect(await screen.findByText('plan-latest')).toBeInTheDocument();

    await act(async () => {
      resolveFirst({
        total: 1,
        period_days: 30,
        by_status: { executing: 1 },
        recent: [
          {
            plan_id: 'plan-latest',
            status: 'executing',
            risk_tier: 'T2',
            created_at: '2026-11-20T10:00:00Z',
            created_by: 'ai',
            step_count: 1,
            target_device_id: 'DEV-1',
          },
        ],
      });
    });
    expect(screen.getByText('plan-latest')).toBeInTheDocument();
    expect(screen.queryByText('Executing')).not.toBeInTheDocument();
  });
});
