import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import AskAIWidget from './AskAIWidget';
import api from '@/services/api';

vi.mock('@/services/api', () => ({
  default: {
    ai: {
      query: vi.fn(),
      cancel: vi.fn(),
      getProvider: vi
        .fn()
        .mockResolvedValue({ data: { current: 'ollama', healthy: true, model: 'llama3.2' } }),
      setProvider: vi
        .fn()
        .mockResolvedValue({ data: { current: 'ollama', healthy: true, model: 'llama3.2' } }),
    },
  },
}));

vi.mock('@/hooks/useAuth', () => ({
  useAuth: () => ({ user: { role: 'Admin' } }),
}));

function modeGroup() {
  return screen.getByRole('group', { name: /ai query mode/i });
}

const knowledgeResult = {
  response: 'To enroll a device, ...',
  trust: {
    trust_mode: 'informational',
    trust_mode_label: 'Informational',
    trust_score: null,
    actionable: false,
    passed_gates: [],
    failed_gate: null,
    gates: [],
  },
  routing: {
    requested: 'knowledge',
    resolved: 'knowledge',
    reason: "how-to signal: 'how do'",
  },
  sources: ['docs/device-registration.md'],
};

const diagnosticResult = {
  response: 'No devices are currently connected.',
  trust: {
    trust_mode: 'mode_1',
    trust_mode_label: 'Status Only',
    trust_score: 0,
    actionable: false,
    passed_gates: [],
    failed_gate: null,
    gates: [],
  },
  routing: {
    requested: 'auto',
    resolved: 'diagnostic',
    reason: "operational signal: 'status'",
  },
};

beforeEach(() => {
  vi.clearAllMocks();
  // The server reports whether it still had the query in flight to cancel.
  api.ai.cancel.mockResolvedValue({ cancelled: true });
  localStorage.clear();
});

describe('AskAIWidget mode selector (docs/ai-query-routing.md §6.1)', () => {
  it('defaults to Auto', () => {
    render(<AskAIWidget />);
    expect(within(modeGroup()).getByRole('button', { name: 'Auto' })).toHaveAttribute(
      'aria-pressed',
      'true'
    );
  });

  it('sends an Auto query with no mode override', async () => {
    api.ai.query.mockResolvedValue(diagnosticResult);
    const user = userEvent.setup();
    render(<AskAIWidget />);

    await user.type(screen.getByRole('textbox'), 'What is the system status?');
    await user.click(screen.getByRole('button', { name: 'Send' }));

    expect(api.ai.query).toHaveBeenCalledWith(
      'What is the system status?',
      null,
      'Admin',
      null,
      expect.any(AbortSignal),
      expect.any(String),
      []
    );
  });

  it('forwards the chosen mode and remembers it per session', async () => {
    api.ai.query.mockResolvedValue(knowledgeResult);
    const user = userEvent.setup();
    render(<AskAIWidget />);

    await user.click(within(modeGroup()).getByRole('button', { name: 'Knowledge' }));
    await user.type(screen.getByRole('textbox'), 'How do I enroll a device?');
    await user.click(screen.getByRole('button', { name: 'Send' }));

    expect(api.ai.query).toHaveBeenCalledWith(
      'How do I enroll a device?',
      null,
      'Admin',
      'knowledge',
      expect.any(AbortSignal),
      expect.any(String),
      []
    );
    expect(localStorage.getItem('homepot_ai_mode')).toBe('knowledge');
  });

  it('forwards an explicit Diagnostic override', async () => {
    api.ai.query.mockResolvedValue(diagnosticResult);
    const user = userEvent.setup();
    render(<AskAIWidget />);

    await user.click(within(modeGroup()).getByRole('button', { name: 'Diagnostic' }));
    await user.type(screen.getByRole('textbox'), 'How do I enroll a device?');
    await user.click(screen.getByRole('button', { name: 'Send' }));

    expect(api.ai.query).toHaveBeenCalledWith(
      'How do I enroll a device?',
      null,
      'Admin',
      'diagnostic',
      expect.any(AbortSignal),
      expect.any(String),
      []
    );
  });

  it('shows a Knowledge chip (not the gate UI) for documentation answers', async () => {
    api.ai.query.mockResolvedValue(knowledgeResult);
    const user = userEvent.setup();
    render(<AskAIWidget />);

    await user.type(screen.getByRole('textbox'), 'How do I enroll a device?');
    await user.click(screen.getByRole('button', { name: 'Send' }));

    expect(await screen.findByText(/answered from documentation/i)).toBeInTheDocument();
    // The informational trust must not be rendered as a gate banner.
    expect(screen.queryByText('Informational')).toBeNull();
  });

  it('shows the real retrieved doc sources for knowledge answers', async () => {
    api.ai.query.mockResolvedValue(knowledgeResult);
    const user = userEvent.setup();
    render(<AskAIWidget />);

    await user.type(screen.getByRole('textbox'), 'How do I enroll a device?');
    await user.click(screen.getByRole('button', { name: 'Send' }));

    expect(await screen.findByText('docs/device-registration.md')).toBeInTheDocument();
    expect(localStorage.getItem('homepot_ai_sources')).toBe(
      JSON.stringify(['docs/device-registration.md'])
    );
  });

  it('does not show doc sources for diagnostic answers', async () => {
    api.ai.query.mockResolvedValue(diagnosticResult);
    const user = userEvent.setup();
    render(<AskAIWidget />);

    await user.type(screen.getByRole('textbox'), 'What is the system status?');
    await user.click(screen.getByRole('button', { name: 'Send' }));

    expect(await screen.findByText('Status Only')).toBeInTheDocument();
    expect(screen.queryByText('docs/device-registration.md')).toBeNull();
  });

  it('shows the gate trust banner for diagnostic answers', async () => {
    api.ai.query.mockResolvedValue(diagnosticResult);
    const user = userEvent.setup();
    render(<AskAIWidget />);

    await user.type(screen.getByRole('textbox'), 'What is the system status?');
    await user.click(screen.getByRole('button', { name: 'Send' }));

    expect(await screen.findByText('Status Only')).toBeInTheDocument();
    expect(screen.queryByText(/answered from documentation/i)).toBeNull();
  });
});

describe('AskAIWidget failure messages (frontend/src/utils/aiErrorMessage.js)', () => {
  async function ask() {
    const user = userEvent.setup();
    render(<AskAIWidget />);
    await user.type(screen.getByRole('textbox'), 'What is the system status?');
    await user.click(screen.getByRole('button', { name: 'Send' }));
  }

  it('explains a busy assistant (503) instead of failing generically', async () => {
    api.ai.query.mockRejectedValue({
      response: { status: 503, data: {}, headers: { 'retry-after': '5' } },
    });
    await ask();

    expect(await screen.findByText(/busy answering another question/i)).toBeInTheDocument();
    expect(screen.queryByText(/Failed to get a response/i)).toBeNull();
  });

  it('explains a timeout while the model is still thinking', async () => {
    api.ai.query.mockRejectedValue({ code: 'ECONNABORTED' });
    await ask();

    expect(await screen.findByText(/timed out/i)).toBeInTheDocument();
    expect(screen.queryByText(/Failed to get a response/i)).toBeNull();
  });

  it('explains a dropped connection', async () => {
    api.ai.query.mockRejectedValue({ request: {} });
    await ask();

    expect(await screen.findByText(/could not reach the server/i)).toBeInTheDocument();
  });
});

describe('AskAIWidget cancelling a query in flight', () => {
  /** A query that only settles when its AbortSignal fires, like axios does. */
  function pendingUntilAborted() {
    return vi.fn(
      (query, deviceId, role, mode, signal) =>
        new Promise((resolve, reject) => {
          signal.addEventListener('abort', () =>
            reject(Object.assign(new Error('canceled'), { code: 'ERR_CANCELED' }))
          );
        })
    );
  }

  async function startQuery() {
    const user = userEvent.setup();
    render(<AskAIWidget />);
    await user.type(screen.getByRole('textbox'), 'What is the system status?');
    await user.click(screen.getByRole('button', { name: 'Send' }));
    await screen.findByRole('button', { name: /^stop$/i });
    return user;
  }

  it('stops the query with the Stop button and shows a cancelled state', async () => {
    api.ai.query.mockImplementation(pendingUntilAborted());
    const user = await startQuery();

    await user.click(screen.getByRole('button', { name: /^stop$/i }));

    expect(await screen.findByText(/query cancelled/i)).toBeInTheDocument();
    // A cancel is the user's own action, not a failure: no error panel.
    expect(screen.queryByText(/couldn't answer that/i)).toBeNull();
    expect(screen.queryByText(/Failed to get a response/i)).toBeNull();
  });

  it('stops the query with the Escape key', async () => {
    api.ai.query.mockImplementation(pendingUntilAborted());
    const user = await startQuery();

    await user.keyboard('{Escape}');

    expect(await screen.findByText(/query cancelled/i)).toBeInTheDocument();
  });

  it('aborts the underlying request, not just the UI', async () => {
    api.ai.query.mockImplementation(pendingUntilAborted());
    const user = await startQuery();

    const signal = api.ai.query.mock.calls[0][4];
    expect(signal.aborted).toBe(false);

    await user.keyboard('{Escape}');

    expect(signal.aborted).toBe(true);
  });

  it('reports the query id to the server, not just the abort', async () => {
    api.ai.query.mockImplementation(pendingUntilAborted());
    const user = await startQuery();

    // The browser abort alone is swallowed by Apache and the analytics
    // middleware, so the id is what actually cancels the query server-side.
    const queryId = api.ai.query.mock.calls[0][5];
    expect(queryId).toBeTruthy();

    await user.click(screen.getByRole('button', { name: /^stop$/i }));

    expect(api.ai.cancel).toHaveBeenCalledWith(queryId);
  });

  it('confirms the answer was discarded when the server had it in flight', async () => {
    api.ai.query.mockImplementation(pendingUntilAborted());
    api.ai.cancel.mockResolvedValue({ cancelled: true });
    const user = await startQuery();

    await user.keyboard('{Escape}');

    expect(await screen.findByText(/nothing was saved/i)).toBeInTheDocument();
  });

  it('does not claim a discard when nothing was left to cancel', async () => {
    api.ai.query.mockImplementation(pendingUntilAborted());
    // The answer had already finished server-side: it was stored, so the panel
    // must not say otherwise.
    api.ai.cancel.mockResolvedValue({ cancelled: false });
    const user = await startQuery();

    await user.keyboard('{Escape}');

    expect(await screen.findByText(/may have finished server-side/i)).toBeInTheDocument();
    expect(screen.queryByText(/nothing was saved/i)).toBeNull();
  });

  it('does not claim a discard when the cancel report itself fails', async () => {
    api.ai.query.mockImplementation(pendingUntilAborted());
    api.ai.cancel.mockRejectedValue(new Error('offline'));
    const user = await startQuery();

    await user.keyboard('{Escape}');

    expect(await screen.findByText(/may have finished server-side/i)).toBeInTheDocument();
    expect(screen.queryByText(/nothing was saved/i)).toBeNull();
  });
});
