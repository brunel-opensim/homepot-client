import { useState, useEffect, useRef, useCallback } from 'react';
import api from '@/services/api';
import { useAuth } from '@/hooks/useAuth';
import { aiErrorMessage, isCancel } from '@/utils/aiErrorMessage';
import { newQueryId } from '@/utils/aiQueryId';
import { useRunEvents } from '@/hooks/useRunEvents';

// Intent modes the technician can pick (docs/ai-query-routing.md §6.1).
export const AI_MODES = [
  { id: 'auto', label: 'Auto', title: 'Let the assistant decide (recommended)' },
  {
    id: 'knowledge',
    label: 'Knowledge',
    title: 'Answer how-to / definition questions from documentation',
  },
  {
    id: 'diagnostic',
    label: 'Diagnostic',
    title: 'Investigate live system state through the validation gates',
  },
];

const SUGGESTED_PROMPTS = [
  'How are devices performing today?',
  'What is currently offline?',
  'How do I enroll a device?',
  'Show recent anomalies',
];

// Friendly labels for the investigation lifecycle events the backend publishes
// over SSE (activity transparency PoC).
const ACTIVITY_LABELS = {
  run_started: 'Starting investigation',
  context_ready: 'Gathering context and evidence',
  gates_complete: 'Validating data through gate chain',
  llm_started: 'Generating answer',
  llm_complete: 'Answer generated',
  memory_written: 'Storing memory',
};

// Friendly labels for the agentic tool calls (surfaced after the run).
const TOOL_LABELS = {
  get_device_status: 'Checking device status',
  get_device_metrics: 'Reading device metrics',
  get_error_logs: 'Reading error logs',
  get_command_history: 'Reading command history',
  get_config_history: 'Reading config history',
  search_similar_incidents: 'Recalling similar incidents',
  get_fleet_summary: 'Summarizing fleet',
  find_device: 'Locating device',
  get_alerts: 'Reading alerts',
  propose_device_action: 'Proposing device action',
  propose_fleet_action: 'Proposing fleet action',
  get_action_plan_status: 'Checking action plan status',
};

function loadStored(key, fallback, parse = false) {
  try {
    const stored = localStorage.getItem(key);
    if (!stored) return fallback;
    return parse ? JSON.parse(stored) : stored;
  } catch {
    return fallback;
  }
}

/**
 * Shared conversation state + request handling for the Dashboard assistant and
 * the AI workspace. Both surfaces operate on the same active conversation:
 * draft, thread, mode, provider and in-flight request state are owned here.
 */
export function useAIConversation(variant = 'compact') {
  const isWorkspace = variant === 'workspace';
  const { user } = useAuth();

  const [query, setQuery] = useState(() => loadStored('homepot_ai_query', ''));
  const [response, setResponse] = useState(() => loadStored('homepot_ai_response', null));
  const [trust, setTrust] = useState(() => loadStored('homepot_ai_trust', null, true));
  const [trustExpanded, setTrustExpanded] = useState(false);
  const [mode, setMode] = useState(() => loadStored('homepot_ai_mode', 'auto'));
  const [routing, setRouting] = useState(null);
  const [sources, setSources] = useState(() => loadStored('homepot_ai_sources', [], true));
  const [proposal, setProposal] = useState(() => loadStored('homepot_ai_proposal', null, true));
  const [loading, setLoading] = useState(false);
  const [replaying, setReplaying] = useState(false);
  const [error, setError] = useState(null);
  const [cancelled, setCancelled] = useState(false);
  const [cancelConfirmed, setCancelConfirmed] = useState(false);
  const [copied, setCopied] = useState(false);
  const [loadingMessage, setLoadingMessage] = useState('Analyzing system metrics...');
  // Live activity steps (activity transparency PoC): lifecycle events streamed
  // over SSE, plus agentic tool calls captured from the response.
  const [activity, setActivity] = useState([]);
  const [toolCalls, setToolCalls] = useState([]);
  const [streamText, setStreamText] = useState('');
  const [slowHint, setSlowHint] = useState(false);
  const [llmProvider, setLlmProvider] = useState(null);
  const [llmSwitching, setLlmSwitching] = useState(false);
  const [messages, setMessages] = useState(() => loadStored('homepot_ai_thread', [], true));
  // Active investigation session/run for SSE event streaming.
  const [sessionId, setSessionId] = useState(() => loadStored('homepot_ai_session', null));
  const [runId, setRunId] = useState(null);

  const abortRef = useRef(null);
  const queryIdRef = useRef(null);

  // SSE event stream for the active run (no-op when sessionId/runId are null).
  const runEvents = useRunEvents(sessionId, runId);

  // Persist draft/response/trust/mode/sources/thread
  useEffect(() => {
    localStorage.setItem('homepot_ai_query', query);
  }, [query]);
  useEffect(() => {
    if (response) localStorage.setItem('homepot_ai_response', response);
    else localStorage.removeItem('homepot_ai_response');
  }, [response]);
  useEffect(() => {
    if (trust) localStorage.setItem('homepot_ai_trust', JSON.stringify(trust));
    else localStorage.removeItem('homepot_ai_trust');
  }, [trust]);
  useEffect(() => {
    localStorage.setItem('homepot_ai_mode', mode);
  }, [mode]);
  useEffect(() => {
    if (sources && sources.length)
      localStorage.setItem('homepot_ai_sources', JSON.stringify(sources));
    else localStorage.removeItem('homepot_ai_sources');
  }, [sources]);

  useEffect(() => {
    if (proposal) localStorage.setItem('homepot_ai_proposal', JSON.stringify(proposal));
    else localStorage.removeItem('homepot_ai_proposal');
  }, [proposal]);
  useEffect(() => {
    if (messages && messages.length)
      localStorage.setItem('homepot_ai_thread', JSON.stringify(messages));
    else localStorage.removeItem('homepot_ai_thread');
  }, [messages]);

  useEffect(() => {
    if (sessionId) localStorage.setItem('homepot_ai_session', sessionId);
    else localStorage.removeItem('homepot_ai_session');
  }, [sessionId]);

  // Fetch provider on mount
  useEffect(() => {
    api.ai
      .getProvider()
      .then((res) => {
        if (res?.data) setLlmProvider(res.data);
      })
      .catch(() => {});
  }, []);

  const handleGateReplayDone = useCallback(() => setReplaying(false), []);

  const handleCancel = useCallback(() => {
    const queryId = queryIdRef.current;
    if (queryId) {
      api.ai
        .cancel(queryId)
        .then((result) => setCancelConfirmed(result?.cancelled === true))
        .catch(() => setCancelConfirmed(false));
    }
    abortRef.current?.abort();
  }, []);

  const handleSwitchProvider = useCallback(async (provider) => {
    setLlmSwitching(true);
    try {
      const res = await api.ai.setProvider(provider);
      if (res?.data) setLlmProvider(res.data);
    } catch (err) {
      console.error('Failed to switch LLM provider:', err);
    } finally {
      setLlmSwitching(false);
    }
  }, []);

  const clearHistory = useCallback(() => {
    // Start a new conversation in the UI without deleting prior transcripts:
    // backend-held investigation sessions/messages remain intact and can be
    // reopened later. Only the locally active thread/draft is reset.
    setQuery('');
    setResponse(null);
    setTrust(null);
    setRouting(null);
    setSources([]);
    setProposal(null);
    setMessages([]);
    setSessionId(null);
    setRunId(null);
    setTrustExpanded(false);
    setReplaying(false);
    setError(null);
    setCancelled(false);
    setCancelConfirmed(false);
    localStorage.removeItem('homepot_ai_query');
    localStorage.removeItem('homepot_ai_response');
    localStorage.removeItem('homepot_ai_trust');
    localStorage.removeItem('homepot_ai_sources');
    localStorage.removeItem('homepot_ai_proposal');
    localStorage.removeItem('homepot_ai_thread');
    localStorage.removeItem('homepot_ai_session');
  }, []);

  const handleCopy = useCallback(() => {
    if (!response) return;
    navigator.clipboard.writeText(response);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [response]);

  // SSE-driven activity feed (activity transparency PoC). Builds an ordered
  // list of completed/in-progress steps from the lifecycle events and keeps the
  // single loading label in sync with the latest step.
  useEffect(() => {
    const steps = runEvents.events
      .map((ev) => {
        const type = ev.type || ev.data?.event;
        const data = ev.data || {};
        let label = ACTIVITY_LABELS[type];
        if (type === 'gates_complete') {
          label = data.failed_gate
            ? `Validation gate ${data.failed_gate} did not pass`
            : 'Validation gates passed';
        } else if (type === 'llm_started') {
          label = data.mode === 'agentic' ? 'Running agentic investigation' : 'Generating answer';
        }
        return label ? { key: `${type}-${ev.seq ?? ev.id}`, label } : null;
      })
      .filter(Boolean);
    if (steps.length) {
      setActivity(steps);
      setLoadingMessage(steps[steps.length - 1].label);
    }
  }, [runEvents.events]);

  // Accumulate the streamed answer from `response_delta` SSE events.
  useEffect(() => {
    const text = runEvents.events
      .filter((ev) => ev.type === 'response_delta')
      .map((ev) => ev.data?.text || '')
      .join('');
    if (text) setStreamText(text);
  }, [runEvents.events]);

  // Clear the transient activity feed at the start of each run.
  useEffect(() => {
    if (loading) {
      setActivity([]);
      setToolCalls([]);
      setStreamText('');
    }
  }, [loading]);

  // A neutral fallback until real backend events arrive. A timer cannot tell
  // whether a particular gate or retrieval operation has actually happened.
  useEffect(() => {
    if (!loading) return undefined;
    setSlowHint(false);
    const slowTimer = setTimeout(() => setSlowHint(true), 90000);
    return () => clearTimeout(slowTimer);
  }, [loading]);

  // Esc aborts
  useEffect(() => {
    if (!loading) return undefined;
    const onKeyDown = (event) => {
      if (event.key === 'Escape') handleCancel();
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [loading, handleCancel]);

  const handleAsk = useCallback(
    async (e) => {
      if (e && e.preventDefault) e.preventDefault();
      if (!query.trim() || loading) return;
      setLoading(true);
      setLoadingMessage('Waiting for the assistant...');
      setError(null);
      setCancelled(false);
      setCancelConfirmed(false);
      setResponse(null);
      setTrust(null);
      setRouting(null);
      setSources([]);
      setTrustExpanded(false);
      const controller = new AbortController();
      abortRef.current = controller;
      const queryId = newQueryId();
      queryIdRef.current = queryId;
      const startedAt = Date.now();
      let activeSessionId = sessionId;
      let activeRunId = null;
      const investigations = api.investigations;
      try {
        const userRole = user?.role || (user?.isAdmin ? 'Admin' : 'Client');
        const modeArg = mode === 'auto' ? null : mode;
        if (investigations) {
          if (!activeSessionId) {
            try {
              const created = await investigations.create(null, null, null);
              activeSessionId = created?.data?.session_id || null;
              if (activeSessionId) setSessionId(activeSessionId);
            } catch (e) {
              console.warn('Failed to create investigation session:', e);
            }
          }
          if (activeSessionId) {
            try {
              const runRes = await investigations.createRun(activeSessionId, null, 'running');
              activeRunId = runRes?.data?.run_id || null;
              if (activeRunId) setRunId(activeRunId);
            } catch (e) {
              console.warn('Failed to create investigation run:', e);
            }
          }
        }
        const historyPayload = messages
          .slice(-5)
          .map((m) => ({ role: m.role, content: m.content }));
        const result = await api.ai.query(
          query,
          null,
          userRole,
          modeArg,
          controller.signal,
          queryId,
          historyPayload,
          activeSessionId,
          activeRunId,
          // Ask AI must run the tool-calling loop so natural-language action
          // requests become tracked proposals in AI Proposals. Informational
          // queries still answer directly; the backend routes knowledge
          // questions down the documentation path regardless of this flag.
          true
        );
        setResponse(result.response);
        setTrust(result.trust || null);
        setRouting(result.routing || null);
        setSources(result.sources || []);
        setProposal(result.proposal || null);
        const toolSteps = (result.agentic?.tools_called || []).map((t) => ({
          key: `tool-${t.tool}-${t.iteration}`,
          label: TOOL_LABELS[t.tool] || t.tool,
        }));
        setToolCalls(toolSteps);
        if (result.trust?.gates?.length) setReplaying(true);
        setMessages((prev) => [
          ...prev,
          { role: 'user', content: query },
          {
            role: 'assistant',
            content: result.response,
            trust: result.trust || null,
            routing: result.routing || null,
            sources: result.sources || [],
            proposal: result.proposal || null,
            toolCalls: toolSteps,
            provider: llmProvider?.current || null,
            model: llmProvider?.model || null,
            elapsedMs: Date.now() - startedAt,
          },
        ]);
        setQuery('');
        if (activeRunId && investigations) {
          investigations
            .updateRun(activeSessionId, activeRunId, { status: 'completed' })
            .catch(() => {});
        }
      } catch (err) {
        if (isCancel(err)) {
          setCancelled(true);
          if (activeRunId && investigations) {
            investigations
              .updateRun(activeSessionId, activeRunId, { status: 'cancelled' })
              .catch(() => {});
          }
        } else {
          console.error('AI Query failed:', err);
          setError(aiErrorMessage(err));
          if (activeRunId && investigations) {
            investigations
              .updateRun(activeSessionId, activeRunId, {
                status: 'failed',
                error: aiErrorMessage(err),
              })
              .catch(() => {});
          }
        }
      } finally {
        abortRef.current = null;
        queryIdRef.current = null;
        setLoading(false);
      }
    },
    [query, mode, user, messages, sessionId, llmProvider, loading]
  );

  // Cancel in-flight request on unmount so navigation doesn't leave an orphan.
  useEffect(() => {
    return () => {
      if (abortRef.current) {
        const qid = queryIdRef.current;
        if (qid) api.ai.cancel(qid).catch(() => {});
        abortRef.current.abort();
      }
    };
  }, []);

  const isAdmin = user?.role === 'Admin' || !!user?.isAdmin;

  // Poll proposal status for any plan referenced in the thread, so the inline
  // cards reflect approval/execution outcomes. Stops once all are terminal.
  useEffect(() => {
    const planIds = messages.map((m) => m?.proposal?.plan_id).filter(Boolean);
    if (planIds.length === 0) return undefined;
    const terminal = new Set(['succeeded', 'failed', 'rejected', 'rolled_back', 'expired']);
    let cancelled = false;
    const poll = async () => {
      for (const pid of planIds) {
        try {
          const res = await api.aiProposals.get(pid);
          const plan = res?.data || res;
          if (!plan || cancelled) return;
          const newStatus = plan.status;
          setMessages((prev) =>
            prev.map((m) =>
              m?.proposal?.plan_id === pid
                ? {
                    ...m,
                    proposal: {
                      ...m.proposal,
                      status: newStatus,
                      risk_tier: plan.risk_tier || m.proposal.risk_tier,
                    },
                  }
                : m
            )
          );
        } catch {
          // ignore
        }
      }
    };
    const allTerminal = messages.every(
      (m) => !m?.proposal?.plan_id || terminal.has(m.proposal.status)
    );
    if (allTerminal) return undefined;
    const id = setInterval(poll, 5000);
    poll();
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [messages]);
  const isKnowledge = routing?.resolved === 'knowledge' || trust?.trust_mode === 'informational';

  return {
    variant,
    isWorkspace,
    query,
    setQuery,
    response,
    trust,
    trustExpanded,
    setTrustExpanded,
    mode,
    setMode,
    routing,
    sources,
    proposal,
    loading,
    replaying,
    error,
    cancelled,
    cancelConfirmed,
    copied,
    loadingMessage,
    activity,
    toolCalls,
    streamText,
    slowHint,
    llmProvider,
    llmSwitching,
    messages,
    isAdmin,
    isKnowledge,
    handleAsk,
    handleCancel,
    handleSwitchProvider,
    clearHistory,
    handleCopy,
    handleGateReplayDone,
    suggestedPrompts: SUGGESTED_PROMPTS,
    aiModes: AI_MODES,
  };
}
