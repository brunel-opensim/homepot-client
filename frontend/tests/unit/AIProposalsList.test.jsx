import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { act, render, screen, waitFor } from '@testing-library/react';
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

let eventSources;

class MockEventSource {
  constructor(url) {
    this.url = url;
    this.listeners = {};
    this.closed = false;
    eventSources.push(this);
  }

  addEventListener(type, listener) {
    this.listeners[type] = listener;
  }

  close() {
    this.closed = true;
  }

  emit(type, data) {
    const listener = this.listeners[type];
    if (listener) listener({ data: JSON.stringify(data) });
  }
}

function renderPage(route = '/ai-proposals') {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <AIProposalsList />
    </MemoryRouter>
  );
}

describe('AIProposalsList', () => {
  beforeEach(() => {
    eventSources = [];
    // jsdom does not implement scrollIntoView, which the deep-link highlight uses.
    Element.prototype.scrollIntoView = vi.fn();
    api.aiProposals.list.mockResolvedValue({ plans: mockPlans, count: mockPlans.length });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    delete Element.prototype.scrollIntoView;
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
    api.aiProposals.approve.mockResolvedValue({ ...mockPlans[0], status: 'approved' });

    renderPage();
    await screen.findByText('AI Action Proposals');
    await userEvent.click(screen.getByText('Approve'));
    // themed dialog confirm
    const approveButtons = await screen.findAllByText('Approve');
    await userEvent.click(approveButtons[approveButtons.length - 1]);

    await waitFor(() => {
      expect(api.aiProposals.approve).toHaveBeenCalledWith(mockPlans[0].plan_id, null);
    });
    expect(api.aiProposals.list).toHaveBeenCalledTimes(2);
  });

  it('rejects a plan with a prompted reason', async () => {
    api.aiProposals.reject.mockResolvedValue({ ...mockPlans[0], status: 'rejected' });

    renderPage();
    await screen.findByText('AI Action Proposals');
    await userEvent.click(screen.getByText('Reject'));
    // themed dialog: type reason and confirm
    const reasonInput = await screen.findByPlaceholderText('Reason (optional)');
    await userEvent.type(reasonInput, 'not now');
    const rejectButtons = screen.getAllByText('Reject');
    await userEvent.click(rejectButtons[rejectButtons.length - 1]);

    await waitFor(() => {
      expect(api.aiProposals.reject).toHaveBeenCalledWith(mockPlans[0].plan_id, 'not now');
    });
  });

  it('shows an empty state when there are no plans', async () => {
    api.aiProposals.list.mockResolvedValue({ plans: [], count: 0 });
    renderPage();
    expect(await screen.findByText(/No AI action proposals/)).toBeInTheDocument();
  });

  it('shows an Execute button only for approved plans', async () => {
    renderPage();
    await screen.findByText('AI Action Proposals');
    expect(screen.getAllByText('Execute')).toHaveLength(1);
  });

  it('executes an approved plan and refreshes the list', async () => {
    api.aiProposals.execute.mockResolvedValue({ ...mockPlans[1], status: 'executing' });

    renderPage();
    await screen.findByText('AI Action Proposals');
    await userEvent.click(screen.getByText('Execute'));
    const executeButtons = await screen.findAllByText('Execute');
    await userEvent.click(executeButtons[executeButtons.length - 1]);

    await waitFor(() => {
      expect(api.aiProposals.execute).toHaveBeenCalledWith(mockPlans[1].plan_id);
    });
    expect(api.aiProposals.list).toHaveBeenCalledTimes(2);
  });

  it('surfaces a policy block when execution is refused', async () => {
    api.aiProposals.execute.mockResolvedValue({
      ...mockPlans[1],
      status: 'blocked',
      policy: { allowed: false, reasons: ['Device is not active.'] },
    });

    renderPage();
    await screen.findByText('AI Action Proposals');
    await userEvent.click(screen.getByText('Execute'));
    const executeButtons = await screen.findAllByText('Execute');
    await userEvent.click(executeButtons[executeButtons.length - 1]);

    expect((await screen.findAllByText(/Device is not active/)).length).toBeGreaterThan(0);
  });

  it('shows a loading spinner while fetching', () => {
    api.aiProposals.list.mockImplementation(() => new Promise(() => {}));
    renderPage();
    expect(document.querySelector('.animate-spin')).toBeInTheDocument();
  });

  it('keeps a newer SSE status when an older REST response arrives late', async () => {
    const planId = '550e8400-e29b-41d4-a716-446655440003';
    let resolveList;
    api.aiProposals.list.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveList = resolve;
        })
    );
    api.aiProposals.list.mockResolvedValue({ plans: [], count: 0 });

    vi.stubGlobal('EventSource', MockEventSource);

    // The deep-link query param makes the page show all statuses, so a
    // 'succeeded' SSE update is not dropped by the default status filter.
    renderPage(`/ai-proposals?plan=${planId}`);

    await waitFor(() => expect(eventSources).toHaveLength(1));
    const es = eventSources[0];
    const ssePlan = {
      plan_id: planId,
      status: 'succeeded',
      risk_tier: 'T2',
      reversible: true,
      rationale: 'SSE reports the plan has succeeded.',
      created_at: new Date().toISOString(),
      created_by: 'ai',
      trust: { mode: 'assisted', score: 0.9, passed_gates: [], failed_gate: null },
      steps: [],
      approvals: [],
    };

    act(() => {
      es.emit('plan', ssePlan);
    });

    expect(await screen.findByText('Succeeded')).toBeInTheDocument();

    // The REST response that was already in flight still reports the old
    // status; it must not overwrite the fresher SSE update.
    await act(async () => {
      resolveList({ plans: [{ ...ssePlan, status: 'executing' }], count: 1 });
    });

    expect(screen.getByText('Succeeded')).toBeInTheDocument();
    expect(screen.queryByText('Executing')).not.toBeInTheDocument();
  });
});
