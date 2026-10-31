import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  Sparkles,
  Send,
  Loader2,
  AlertCircle,
  Trash2,
  Copy,
  Check,
  ShieldCheck,
  ShieldAlert,
  ShieldX,
  ChevronDown,
  X,
  Square,
  ListChecks,
  BookOpen,
  FileText,
  Maximize2,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import api from '@/services/api';
import { useAuth } from '@/hooks/useAuth';
import { aiErrorMessage, isCancel } from '@/utils/aiErrorMessage';
import { newQueryId } from '@/utils/aiQueryId';

// Intent modes the technician can pick (docs/ai-query-routing.md §6.1).
// `auto` (default) lets the backend heuristics resolve the mode; the explicit
// choices override them. The LLM never chooses the mode.
const AI_MODES = [
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

// Suggested prompts shown in the empty state (workspace) and compact empty state.
const SUGGESTED_PROMPTS = [
  'How are devices performing today?',
  'What is currently offline?',
  'How do I enroll a device?',
  'Show recent anomalies',
];

// Visual treatment per backend trust mode (ai/gates/base.py Mode instances).
// Covers all five canonical modes plus grounded. Falls back to mode_1
// (status-only / least trusted) styling for any unknown mode id.
const TRUST_MODE_STYLES = {
  grounded: {
    icon: ShieldCheck,
    text: 'text-green-700 dark:text-green-400',
    bg: 'bg-green-50 dark:bg-green-950/30',
    border: 'border-green-200 dark:border-green-900',
    chipPass: 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-400',
  },
  mode_4: {
    icon: ShieldAlert,
    text: 'text-indigo-700 dark:text-indigo-400',
    bg: 'bg-indigo-50 dark:bg-indigo-950/30',
    border: 'border-indigo-200 dark:border-indigo-900',
    chipPass: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-400',
  },
  mode_3: {
    icon: ShieldAlert,
    text: 'text-amber-700 dark:text-amber-400',
    bg: 'bg-amber-50 dark:bg-amber-950/30',
    border: 'border-amber-200 dark:border-amber-900',
    chipPass: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-400',
  },
  mode_5: {
    icon: ShieldAlert,
    text: 'text-rose-700 dark:text-rose-400',
    bg: 'bg-rose-50 dark:bg-rose-950/30',
    border: 'border-rose-200 dark:border-rose-900',
    chipPass: 'bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-400',
  },
  mode_2: {
    icon: ShieldAlert,
    text: 'text-orange-700 dark:text-orange-400',
    bg: 'bg-orange-50 dark:bg-orange-950/30',
    border: 'border-orange-200 dark:border-orange-900',
    chipPass: 'bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-400',
  },
  mode_1: {
    icon: ShieldX,
    text: 'text-red-700 dark:text-red-400',
    bg: 'bg-red-50 dark:bg-red-950/30',
    border: 'border-red-200 dark:border-red-900',
    chipPass: 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-400',
  },
};

/**
 * Technician-facing summary of the validation envelope (Gate A -> B -> C...)
 * behind a given AI response: which gates passed/failed, the resulting trust
 * mode, and an overall trust score -- so a recommendation is never presented
 * without first showing how much confidence to place in it.
 */
function TrustBanner({ trust, expanded, onToggle }) {
  if (!trust) return null;
  const style = TRUST_MODE_STYLES[trust.trust_mode] || TRUST_MODE_STYLES.mode_1;
  const Icon = style.icon;
  const scorePct = Math.round((trust.trust_score ?? 0) * 100);
  // De-duplicate gate ids (Gate C can appear twice: pre- and post-insight
  // re-validation) for a clean row of chips.
  const gateIds = [...new Set((trust.gates || []).map((g) => g.gate_id))];

  return (
    <div className={`mb-3 rounded-lg border ${style.border} ${style.bg} text-xs overflow-hidden`}>
      <button
        type="button"
        onClick={onToggle}
        className="w-full flex items-center gap-2 px-3 py-2 text-left"
      >
        <Icon className={`w-4 h-4 shrink-0 ${style.text}`} />
        <span className={`font-semibold ${style.text}`}>{trust.trust_mode_label}</span>
        <span className="flex items-center gap-1 ml-1">
          {gateIds.map((id) => {
            const failed = trust.failed_gate === id || trust.failed_gate?.startsWith(`${id} `);
            return (
              <span
                key={id}
                className={`inline-flex items-center justify-center w-5 h-5 rounded-full text-[10px] font-bold ${
                  failed
                    ? 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-400'
                    : style.chipPass
                }`}
                title={failed ? `Gate ${id} failed` : `Gate ${id} passed`}
              >
                {id}
              </span>
            );
          })}
        </span>
        <span className="ml-auto font-mono text-gray-500 dark:text-gray-400">
          Trust {scorePct}%
        </span>
        <ChevronDown
          className={`w-3.5 h-3.5 text-gray-400 transition-transform shrink-0 ${
            expanded ? 'rotate-180' : ''
          }`}
        />
      </button>
      {expanded && (
        <div className="px-3 pb-2.5 pt-0 border-t border-inherit space-y-1.5">
          {(trust.gates || []).map((g, i) => (
            <div key={`${g.gate_id}-${i}`} className="flex items-start gap-1.5 pt-1.5">
              {g.status === 'pass' ? (
                <Check className="w-3 h-3 text-green-600 mt-0.5 shrink-0" />
              ) : (
                <X className="w-3 h-3 text-red-600 mt-0.5 shrink-0" />
              )}
              <span className="text-gray-600 dark:text-gray-400">
                <span className="font-medium text-gray-800 dark:text-gray-200">
                  Gate {g.gate_id} ({g.name}):
                </span>{' '}
                {(g.checks || []).length > 0
                  ? g.checks.map((c) => c.message).join(' ')
                  : g.error || 'No detail available.'}
              </span>
            </div>
          ))}
          {!trust.actionable && (
            <p className="pt-1.5 text-gray-500 dark:text-gray-400 italic">
              Recommendation below is non-actionable/advisory only until all gates pass.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * Animated replay of the validation gate chain shown after the response
 * arrives. Each gate appears sequentially with a check/cross icon so the
 * technician sees the same A → B → C → D → E order the backend evaluated.
 */
function GateReplay({ trust, onDone }) {
  const [idx, setIdx] = useState(0);
  const onDoneRef = useRef(onDone);
  onDoneRef.current = onDone;

  const gates = trust?.gates || [];
  const total = gates.length;
  const done = idx > total;

  useEffect(() => {
    if (total === 0) {
      onDoneRef.current?.();
      return;
    }
    const t = setTimeout(
      () => {
        if (idx <= total) setIdx((i) => i + 1);
      },
      idx === 0 ? 200 : 300
    );
    return () => clearTimeout(t);
  }, [idx, total]);

  useEffect(() => {
    if (done && total > 0) {
      const t = setTimeout(() => onDoneRef.current?.(), 700);
      return () => clearTimeout(t);
    }
  }, [done, total]);

  if (total === 0) return null;

  const scorePct = Math.round((trust?.trust_score ?? 0) * 100);

  return (
    <div className="flex flex-col items-center justify-center h-full gap-3">
      <div className="flex items-center gap-2 text-xs text-gray-400 mb-1">
        <ListChecks className="w-3.5 h-3.5" />
        <span>Validating data through gate chain...</span>
      </div>
      <div className="space-y-1.5 text-xs">
        {gates.slice(0, Math.min(idx, total)).map((g, i) => (
          <div
            key={`${g.gate_id}-${i}`}
            className="flex items-center gap-2 animate-in fade-in slide-in-from-left-2 duration-200"
          >
            {g.status === 'pass' ? (
              <Check className="w-3.5 h-3.5 text-green-500 shrink-0" />
            ) : (
              <X className="w-3.5 h-3.5 text-red-500 shrink-0" />
            )}
            <span className="font-semibold text-gray-800 dark:text-gray-200">Gate {g.gate_id}</span>
            <span className="text-gray-400">—</span>
            <span className="text-gray-500 dark:text-gray-400">{g.name}</span>
            {g.status === 'pass' ? (
              <span className="text-green-600 font-semibold ml-auto">PASS</span>
            ) : (
              <span className="text-red-600 font-semibold ml-auto">FAIL</span>
            )}
          </div>
        ))}
        {idx > total && (
          <div className="flex items-center gap-2 pt-2 text-gray-500 animate-in fade-in duration-300">
            <span className="font-medium text-gray-700 dark:text-gray-300">
              {trust?.trust_mode_label}
            </span>
            <span className="font-mono">Trust {scorePct}%</span>
            {!trust?.actionable && (
              <span className="text-amber-600 text-[10px] italic">(non-actionable)</span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * AskAIWidget
 *
 * @param {object} props
 * @param {'compact'|'workspace'} [props.variant='compact'] - Layout variant.
 *   `compact` is the Dashboard assistant; `workspace` is the full-height AI
 *   workspace. Both share all state, handlers and API calls.
 * @param {string} [props.className] - Extra classes for the outer container.
 */
export default function AskAIWidget({
  variant = 'compact',
  className = '',
  onOpenWorkspace = () => {
    if (typeof window !== 'undefined') window.location.assign('/ai-workspace');
  },
}) {
  const isWorkspace = variant === 'workspace';
  const { user } = useAuth();
  // Load initial state from localStorage if available to persist context on refresh/navigation
  const [query, setQuery] = useState(() => localStorage.getItem('homepot_ai_query') || '');
  const [response, setResponse] = useState(
    () => localStorage.getItem('homepot_ai_response') || null
  );
  const [trust, setTrust] = useState(() => {
    try {
      const stored = localStorage.getItem('homepot_ai_trust');
      return stored ? JSON.parse(stored) : null;
    } catch {
      return null;
    }
  });
  const [trustExpanded, setTrustExpanded] = useState(false);
  // Selected intent mode; remembered per session (docs/ai-query-routing.md §6.1).
  const [mode, setMode] = useState(() => localStorage.getItem('homepot_ai_mode') || 'auto');
  // How the backend actually resolved the query (routing.resolved) -- drives
  // whether we show the gate/trust UI or a documentation "Knowledge" chip.
  const [routing, setRouting] = useState(null);
  // Real documentation files the backend retrieved to ground a knowledge answer
  // (docs/ai-query-routing.md §8.1). These are actual repo paths, not file
  // names the model invented.
  const [sources, setSources] = useState(() => {
    try {
      const stored = localStorage.getItem('homepot_ai_sources');
      return stored ? JSON.parse(stored) : [];
    } catch {
      return [];
    }
  });
  // Conversation history (short-term memory). Persisted so the workspace can
  // resume a thread; sent to the backend as `history` (last 5 turns).
  const [messages, setMessages] = useState(() => {
    try {
      const stored = localStorage.getItem('homepot_ai_thread');
      return stored ? JSON.parse(stored) : [];
    } catch {
      return [];
    }
  });
  const [loading, setLoading] = useState(false);
  const [replaying, setReplaying] = useState(false);
  const [error, setError] = useState(null);
  // LLM provider state
  const [llmProvider, setLlmProvider] = useState(null);
  const [llmSwitching, setLlmSwitching] = useState(false);

  // Fetch current LLM provider on mount
  useEffect(() => {
    api.ai
      .getProvider()
      .then((res) => {
        if (res?.data) {
          setLlmProvider(res.data);
        }
      })
      .catch(() => {
        // Silently ignore - provider selector is optional
      });
  }, []);
  const [loadingMessage, setLoadingMessage] = useState('Analyzing system metrics...');
  const [slowHint, setSlowHint] = useState(false);
  const [cancelled, setCancelled] = useState(false);
  // Whether the server confirmed the cancel: true only when it had an in-flight
  // query to discard, so the panel never claims something it cannot know.
  const [cancelConfirmed, setCancelConfirmed] = useState(false);
  const [copied, setCopied] = useState(false);
  // Holds the in-flight query's AbortController so Stop/Esc can abandon it.
  const abortRef = useRef(null);
  // The id of the query in flight, so Stop/Esc can name it to the server.
  const queryIdRef = useRef(null);

  const handleGateReplayDone = useCallback(() => {
    setReplaying(false);
  }, []);

  // Abandon the query in flight. Aborting stops this page waiting; telling the
  // server which query to abandon is what makes it discard the answer instead of
  // remembering it. The report is best-effort -- if it fails the page still
  // stops, it just cannot claim the answer was discarded
  // (docs/ai-concurrency.md).
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
      if (res?.data) {
        setLlmProvider(res.data);
      }
    } catch (err) {
      console.error('Failed to switch LLM provider:', err);
    } finally {
      setLlmSwitching(false);
    }
  }, []);

  // Persist query and response to localStorage whenever they change
  useEffect(() => {
    localStorage.setItem('homepot_ai_query', query);
  }, [query]);

  useEffect(() => {
    if (response) {
      localStorage.setItem('homepot_ai_response', response);
    } else {
      localStorage.removeItem('homepot_ai_response');
    }
  }, [response]);

  useEffect(() => {
    if (trust) {
      localStorage.setItem('homepot_ai_trust', JSON.stringify(trust));
    } else {
      localStorage.removeItem('homepot_ai_trust');
    }
  }, [trust]);

  useEffect(() => {
    localStorage.setItem('homepot_ai_mode', mode);
  }, [mode]);

  useEffect(() => {
    if (sources && sources.length) {
      localStorage.setItem('homepot_ai_sources', JSON.stringify(sources));
    } else {
      localStorage.removeItem('homepot_ai_sources');
    }
  }, [sources]);

  useEffect(() => {
    if (messages && messages.length) {
      localStorage.setItem('homepot_ai_thread', JSON.stringify(messages));
    } else {
      localStorage.removeItem('homepot_ai_thread');
    }
  }, [messages]);

  const clearHistory = () => {
    setQuery('');
    setResponse(null);
    setTrust(null);
    setRouting(null);
    setSources([]);
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
    localStorage.removeItem('homepot_ai_thread');
  };

  const handleCopy = () => {
    if (!response) return;
    navigator.clipboard.writeText(response);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

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
      // Knowledge queries skip the gates, so the gate narration would be
      // misleading (docs/ai-query-routing.md §7).
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
      // The model runs on CPU and a cold load can take a couple of minutes;
      // after 90s say so rather than letting the user think it has stalled.
      slowTimer = setTimeout(() => setSlowHint(true), 90000);
      interval = setInterval(() => {
        i = i + 1;
        if (i < messages.length) {
          setLoadingMessage(messages[i]);
        }
      }, 1500); // Change message every 1.5 seconds
    }
    return () => {
      clearInterval(interval);
      clearTimeout(slowTimer);
    };
  }, [loading, mode]);

  // Esc aborts a query that is taking too long, same as the Stop button.
  useEffect(() => {
    if (!loading) return undefined;
    const onKeyDown = (event) => {
      if (event.key === 'Escape') {
        handleCancel();
      }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [loading, handleCancel]);

  const handleAsk = async (e) => {
    e.preventDefault();
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
    // Every query carries an id so Stop/Esc can name exactly which one to
    // abandon server-side (see api.ai.cancel).
    const queryId = newQueryId();
    queryIdRef.current = queryId;

    try {
      const userRole = user?.role || (user?.isAdmin ? 'Admin' : 'Client');
      // `auto` is sent as null so the backend default (heuristics) applies.
      const modeArg = mode === 'auto' ? null : mode;
      // Short-term memory: send the last few turns so the backend can keep
      // the conversation context. Capped to the backend's last-5 limit.
      const historyPayload = messages.slice(-5);
      const result = await api.ai.query(
        query,
        null,
        userRole,
        modeArg,
        controller.signal,
        queryId,
        historyPayload
      );
      // The backend returns { response, timestamp, trust, routing, sources } --
      // trust is the validation envelope's gate-by-gate outcome (see
      // ai/gates/envelope.py), routing reports how the intent was resolved
      // (knowledge vs diagnostic), and sources lists the real doc files a
      // knowledge answer was grounded in.
      setResponse(result.response);
      setTrust(result.trust || null);
      setRouting(result.routing || null);
      setSources(result.sources || []);
      // Commit this turn to the conversation thread (only on success, so
      // cancelled/failed queries do not pollute short-term memory).
      setMessages((prev) => [
        ...prev,
        { role: 'user', content: query },
        {
          role: 'assistant',
          content: result.response,
          trust: result.trust || null,
          routing: result.routing || null,
          sources: result.sources || [],
        },
      ]);
      // Show an animated gate replay before revealing the response,
      // so the technician sees the validation chain in action.
      if (result.trust?.gates?.length) {
        setReplaying(true);
      }
    } catch (err) {
      if (isCancel(err)) {
        // A deliberate Stop/Esc: not a failure, so it does not get an error
        // message. The server discards the abandoned answer (no memory write).
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
  };

  // The backend marks documentation answers with an informational trust (no
  // gates ran), so we surface a "Knowledge" chip instead of the gate UI.
  const isKnowledge = routing?.resolved === 'knowledge' || trust?.trust_mode === 'informational';

  return (
    <Card
      className={`h-full flex flex-col ${isWorkspace ? '' : 'shadow-md'} ${className}`.trim()}
      data-variant={variant}
    >
      <CardHeader className="pb-3 flex flex-row items-center justify-between space-y-0">
        <CardTitle className="flex items-center gap-2 text-lg font-medium">
          <Sparkles className="w-5 h-5 text-purple-600" />
          System Diagnostics AI
          {llmProvider?.healthy === false && (
            <span
              className="inline-block w-2 h-2 rounded-full bg-red-500"
              title="Provider unhealthy"
            />
          )}
        </CardTitle>
        <div className="flex items-center gap-2">
          {!isWorkspace && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onOpenWorkspace}
              className="h-8 px-2 text-xs text-gray-400 hover:text-purple-400"
              title="Open full AI workspace"
            >
              <Maximize2 className="w-4 h-4" />
            </Button>
          )}
          {llmProvider && (
            <div className="flex items-center gap-2">
              <select
                value={llmProvider.current || 'ollama'}
                onChange={(e) => handleSwitchProvider(e.target.value)}
                disabled={llmSwitching}
                className="text-xs bg-slate-800 text-slate-300 border border-slate-700 rounded px-2 py-1 focus:outline-none focus:border-indigo-500"
                title="Switch LLM provider"
              >
                <option value="ollama">Local (Ollama)</option>
                <option value="openai">
                  OpenAI
                  {llmProvider.available?.find((p) => p.name === 'openai')?.has_api_key
                    ? ''
                    : ' (no key)'}
                </option>
                <option value="anthropic">
                  Anthropic
                  {llmProvider.available?.find((p) => p.name === 'anthropic')?.has_api_key
                    ? ''
                    : ' (no key)'}
                </option>
              </select>
              {llmSwitching && <Loader2 className="w-3 h-3 animate-spin text-slate-400" />}
            </div>
          )}
          {(response || query) && (
            <Button
              variant="ghost"
              size="sm"
              onClick={clearHistory}
              className="h-8 w-8 p-0 text-gray-400 hover:text-red-500 transition-colors"
              title="Clear AI Context"
            >
              <Trash2 className="w-4 h-4" />
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent className="flex-1 flex flex-col gap-4 min-h-0">
        {/* Response Area */}
        <div className="flex-1 min-h-0 bg-gray-50 dark:bg-gray-900 rounded-lg p-4 text-sm overflow-y-auto border border-gray-100 dark:border-gray-800">
          {loading ? (
            <div className="flex flex-col items-center justify-center h-full text-gray-500 gap-2 text-center px-4">
              <Loader2 className="w-5 h-5 animate-spin text-purple-600" />
              <span className="text-xs animate-pulse transition-all duration-300">
                {loadingMessage}
              </span>
              {slowHint && (
                <span className="text-[10px] text-gray-400 max-w-[18rem]">
                  Still working — the model runs on CPU, and the first question after a break can
                  take a couple of minutes.
                </span>
              )}
            </div>
          ) : cancelled ? (
            <div className="flex flex-col items-center justify-center h-full gap-2 text-center px-4 text-gray-500">
              <Square className="w-4 h-4" />
              <span className="font-medium">Query cancelled</span>
              <p className="text-xs text-gray-400 max-w-xs">
                {cancelConfirmed
                  ? 'Nothing was saved — the abandoned answer is discarded rather than stored in memory.'
                  : 'Stopped on this page. The answer may have finished server-side before the cancel arrived.'}
              </p>
            </div>
          ) : error ? (
            <div className="flex flex-col items-center justify-center h-full gap-2 text-center px-4 text-red-500">
              <div className="flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span className="font-medium">The assistant couldn&apos;t answer that</span>
              </div>
              <p className="text-xs text-red-400/90 max-w-xs">{error}</p>
            </div>
          ) : replaying ? (
            <GateReplay trust={trust} onDone={handleGateReplayDone} />
          ) : response ? (
            <div className="relative group min-h-full">
              {isKnowledge ? (
                <>
                  <div className="mb-2 inline-flex items-center gap-1.5 rounded-full bg-purple-50 dark:bg-purple-950/30 px-2.5 py-1 text-xs font-medium text-purple-700 dark:text-purple-300">
                    <BookOpen className="w-3.5 h-3.5" />
                    <span>Knowledge</span>
                    <span className="font-normal text-purple-500/80 dark:text-purple-400/70">
                      — answered from documentation
                    </span>
                  </div>
                  {sources.length > 0 && (
                    <div className="mb-2 flex flex-wrap items-center gap-1.5">
                      {sources.map((src) => (
                        <span
                          key={src}
                          title={`Retrieved source: ${src}`}
                          className="inline-flex items-center gap-1 rounded bg-gray-100 dark:bg-gray-800 px-1.5 py-0.5 font-mono text-[11px] text-gray-500 dark:text-gray-400"
                        >
                          <FileText className="w-3 h-3 shrink-0" />
                          {src}
                        </span>
                      ))}
                    </div>
                  )}
                </>
              ) : (
                <TrustBanner
                  trust={trust}
                  expanded={trustExpanded}
                  onToggle={() => setTrustExpanded((v) => !v)}
                />
              )}
              <div className="sticky top-0 float-right z-10">
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6 text-gray-400 hover:text-purple-600 opacity-0 group-hover:opacity-100 transition-opacity hover:bg-transparent bg-white/50 dark:bg-gray-900/50 backdrop-blur-sm rounded-full shadow-sm border border-gray-100 dark:border-gray-800"
                  onClick={handleCopy}
                  title="Copy to clipboard"
                >
                  {copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                </Button>
              </div>
              <div className="prose prose-sm max-w-none text-gray-700 dark:text-gray-300 pr-0">
                <ReactMarkdown>{response}</ReactMarkdown>
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-gray-400 text-center gap-2 px-2">
              <Sparkles className="w-8 h-8 opacity-20" />
              <p className="text-sm italic">
                Ask about system status, anomalies, or maintenance recommendations...
              </p>
              <div className="flex flex-wrap justify-center gap-1.5 mt-2 not-italic">
                {SUGGESTED_PROMPTS.map((p) => (
                  <button
                    key={p}
                    type="button"
                    onClick={() => setQuery(p)}
                    className="text-[11px] px-2.5 py-1 rounded-full border border-gray-200 dark:border-gray-700 text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800"
                  >
                    {p}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Input Area */}
        <div className="flex flex-col gap-2">
          <form onSubmit={handleAsk} className="flex gap-2 items-end">
            {isWorkspace ? (
              <textarea
                spellCheck="true"
                lang="en"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    if (query.trim() && !loading) {
                      handleAsk(e);
                    }
                  }
                }}
                placeholder="Ask about your fleet, devices, or how to do something..."
                rows={2}
                disabled={loading}
                className="flex-1 px-3 py-2 text-sm rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-950 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 transition-all resize-none"
              />
            ) : (
              <input
                type="text"
                spellCheck="true"
                lang="en"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="e.g., How is our system performing today?"
                className="flex-1 px-3 py-2 text-sm rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-950 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 transition-all"
                disabled={loading}
              />
            )}
            <Button
              type={loading ? 'button' : 'submit'}
              onClick={loading ? handleCancel : undefined}
              disabled={!loading && !query.trim()}
              size="icon"
              aria-label={loading ? 'Stop' : 'Send'}
              title={loading ? 'Stop (Esc)' : 'Send'}
              className="bg-purple-600 hover:bg-purple-700 text-white"
            >
              {loading ? <Square className="w-4 h-4" /> : <Send className="w-4 h-4" />}
            </Button>
          </form>

          {/* Mode selector (docs/ai-query-routing.md §6.1). Auto lets the
              backend heuristics decide; the technician can force a path. */}
          <div className="flex items-center gap-2 text-xs">
            <span className="text-gray-500 dark:text-gray-400">Mode:</span>
            <div
              role="group"
              aria-label="AI query mode"
              className="inline-flex rounded-md border border-gray-200 dark:border-gray-700 overflow-hidden"
            >
              {AI_MODES.map((m) => (
                <button
                  key={m.id}
                  type="button"
                  title={m.title}
                  onClick={() => setMode(m.id)}
                  disabled={loading}
                  aria-pressed={mode === m.id}
                  className={`px-2.5 py-1 transition-colors disabled:opacity-50 ${
                    mode === m.id
                      ? 'bg-purple-600 text-white'
                      : 'text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800'
                  }`}
                >
                  {m.label}
                </button>
              ))}
            </div>
          </div>
        </div>
        {isWorkspace && (
          <div className="px-1 pt-1 text-[11px] text-gray-500 dark:text-gray-400 text-center">
            Answers are advisory. Device actions require separate review.
            <span className="ml-2 hidden sm:inline">Enter to send · Shift+Enter for new line</span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
