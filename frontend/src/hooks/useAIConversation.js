import { useState, useEffect, useRef, useCallback } from 'react';
import api from '@/services/api';
import { useAuth } from '@/hooks/useAuth';
import { aiErrorMessage, isCancel } from '@/utils/aiErrorMessage';
import { newQueryId } from '@/utils/aiQueryId';

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
  const [slowHint, setSlowHint] = useState(false);
  const [llmProvider, setLlmProvider] = useState(null);
  const [llmSwitching, setLlmSwitching] = useState(false);
  const [messages, setMessages] = useState(() => loadStored('homepot_ai_thread', [], true));

  const abortRef = useRef(null);
  const queryIdRef = useRef(null);

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
    setQuery('');
    setResponse(null);
    setTrust(null);
    setRouting(null);
    setSources([]);
    setProposal(null);
    setMessages([]);
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
  }, []);

  const handleCopy = useCallback(() => {
    if (!response) return;
    navigator.clipboard.writeText(response);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [response]);

  // Loading message rotation
  useEffect(() => {
    let interval;
    let slowTimer;
    if (loading) {
      const gateMessages = [
        'Reviewing conversation history...',
        'Running Gate A: Contract & Infrastructure...',
        'Accessing long-term memory & vector store...',
        'Running Gate B: Data Integrity...',
        'Scanning active sites & devices...',
        'Running Gate C: Context Readiness...',
        'Analyzing push notification metrics...',
        'Running Gate D: Permission & Capability...',
        'Checking for system anomalies...',
        'Running Gate E: Lifecycle Integrity...',
        'Synthesizing insights...',
      ];
      const knowledgeMessages = [
        'Searching documentation...',
        'Reviewing product guides & SOPs...',
        'Gathering relevant references...',
        'Synthesizing an answer...',
      ];
      const messages = mode === 'knowledge' ? knowledgeMessages : gateMessages;
      let i = 0;
      setLoadingMessage(messages[0]);
      setSlowHint(false);
      slowTimer = setTimeout(() => setSlowHint(true), 90000);
      interval = setInterval(() => {
        i = i + 1;
        if (i < messages.length) setLoadingMessage(messages[i]);
      }, 1500);
    }
    return () => {
      clearInterval(interval);
      clearTimeout(slowTimer);
    };
  }, [loading, mode]);

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
      if (!query.trim()) return;
      setLoading(true);
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
      try {
        const userRole = user?.role || (user?.isAdmin ? 'Admin' : 'Client');
        const modeArg = mode === 'auto' ? null : mode;
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
          historyPayload
        );
        setResponse(result.response);
        setTrust(result.trust || null);
        setRouting(result.routing || null);
        setSources(result.sources || []);
        setProposal(result.proposal || null);
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
          },
        ]);
      } catch (err) {
        if (isCancel(err)) {
          setCancelled(true);
        } else {
          console.error('AI Query failed:', err);
          setError(aiErrorMessage(err));
        }
      } finally {
        abortRef.current = null;
        queryIdRef.current = null;
        setLoading(false);
      }
    },
    [query, mode, user, messages]
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
