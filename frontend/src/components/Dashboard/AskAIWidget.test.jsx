import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import AskAIWidget from './AskAIWidget';
import api from '@/services/api';

vi.mock('@/services/api', () => ({
  default: { ai: { query: vi.fn() } },
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

    expect(api.ai.query).toHaveBeenCalledWith('What is the system status?', null, 'Admin', null);
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
      'knowledge'
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
      'diagnostic'
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
