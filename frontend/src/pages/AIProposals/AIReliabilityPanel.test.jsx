import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';

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
    expect(api.ai.getPlanSummary).toHaveBeenCalledWith(30, null);
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
});
