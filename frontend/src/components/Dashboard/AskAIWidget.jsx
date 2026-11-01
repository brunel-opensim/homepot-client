import React, { useState, useEffect, useRef } from 'react';
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
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { useAIConversation, AI_MODES } from '@/hooks/useAIConversation';
import ProposalCard from '@/components/Dashboard/ProposalCard';

// Visual treatment per backend trust mode (ai/gates/base.py Mode instances).
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
const TRUST_MODE_STYLES_LOCAL = TRUST_MODE_STYLES;

function TrustBanner({ trust, expanded, onToggle }) {
  if (!trust) return null;
  const style = TRUST_MODE_STYLES_LOCAL[trust.trust_mode] || TRUST_MODE_STYLES_LOCAL.mode_1;
  const Icon = style.icon;
  const scorePct = Math.round((trust.trust_score ?? 0) * 100);
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
          className={`w-3.5 h-3.5 text-gray-400 transition-transform shrink-0 ${expanded ? 'rotate-180' : ''}`}
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
        <span>Replaying validation gate chain...</span>
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

export default function AskAIWidget({ variant = 'compact', className = '' }) {
  const c = useAIConversation(variant);
  const scrollRef = useRef(null);
  const stickToBottomRef = useRef(true);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const onScroll = () => {
      const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
      stickToBottomRef.current = nearBottom;
    };
    el.addEventListener('scroll', onScroll);
    return () => el.removeEventListener('scroll', onScroll);
  }, []);

  useEffect(() => {
    const el = scrollRef.current;
    if (el && stickToBottomRef.current) {
      el.scrollTop = el.scrollHeight;
    }
  }, [c.messages, c.loading, c.response, c.error]);
  const { isWorkspace } = c;

  const isAdmin = c.isAdmin;

  return (
    <Card
      className={`h-full flex flex-col ${isWorkspace ? 'bg-[#0c1423] border-[#2a3548] rounded-xl overflow-hidden' : 'shadow-md'} ${className}`.trim()}
      data-variant={variant}
    >
      <CardHeader
        className={`pb-3 flex flex-row items-center justify-between space-y-0 ${isWorkspace ? 'border-b border-[#243044] px-5 py-3' : ''}`.trim()}
      >
        <CardTitle className="flex items-center gap-2 text-lg font-medium">
          <Sparkles className="w-5 h-5 text-purple-600" />
          System Diagnostics AI
          {c.llmProvider?.healthy === false && (
            <span
              className="inline-block w-2 h-2 rounded-full bg-red-500"
              title="Provider unhealthy"
            />
          )}
        </CardTitle>
        <div className="flex items-center gap-2">
          {c.llmProvider &&
            (isAdmin ? (
              <div className="flex items-center gap-2">
                <select
                  value={c.llmProvider.current || 'ollama'}
                  onChange={(e) => c.handleSwitchProvider(e.target.value)}
                  disabled={c.llmSwitching}
                  className="text-xs bg-slate-800 text-slate-300 border border-slate-700 rounded px-2 py-1 focus:outline-none focus:border-indigo-500"
                  title="Switch LLM provider (admin only)"
                  aria-label="Switch LLM provider"
                >
                  <option value="ollama">Local (Ollama)</option>
                  <option value="openai">
                    OpenAI
                    {c.llmProvider.available?.find((p) => p.name === 'openai')?.has_api_key
                      ? ''
                      : ' (no key)'}
                  </option>
                  <option value="anthropic">
                    Anthropic
                    {c.llmProvider.available?.find((p) => p.name === 'anthropic')?.has_api_key
                      ? ''
                      : ' (no key)'}
                  </option>
                </select>
                {c.llmSwitching && <Loader2 className="w-3 h-3 animate-spin text-slate-400" />}
              </div>
            ) : (
              <span className="text-xs text-slate-400" title="LLM provider (read-only)">
                {c.llmProvider.current || 'ollama'}
                {c.llmProvider.model ? ` · ${c.llmProvider.model}` : ''}
              </span>
            ))}
          {(c.response || c.query) && (
            <Button
              variant="ghost"
              size="sm"
              onClick={c.clearHistory}
              className="h-8 w-8 p-0 text-gray-400 hover:text-red-500 transition-colors"
              title="New conversation (keeps prior transcripts)"
              aria-label="New conversation"
            >
              <Trash2 className="w-4 h-4" />
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent className="flex-1 flex flex-col gap-4 min-h-0">
        {/* Response Area */}
        <div
          ref={scrollRef}
          className={`flex-1 min-h-0 text-sm overflow-y-auto ${isWorkspace ? 'px-6 py-6 bg-[#0c1423]' : 'bg-gray-50 dark:bg-gray-900 rounded-lg p-4 border border-gray-100 dark:border-gray-800'}`}
          aria-live="polite"
        >
          {isWorkspace ? (
            <>
              {c.messages.length === 0 && !c.loading && !c.error && !c.cancelled ? (
                <div className="flex flex-col items-center justify-center h-full text-gray-400 text-center gap-3 px-4">
                  <Sparkles className="w-10 h-10 opacity-20" />
                  <p className="text-sm font-medium text-gray-300">
                    Ask about your fleet, devices, or how to do something.
                  </p>
                  <div className="flex flex-wrap justify-center gap-2 mt-2">
                    {c.suggestedPrompts.map((p) => (
                      <button
                        key={p}
                        type="button"
                        onClick={() => c.setQuery(p)}
                        className="text-xs px-3 py-1.5 rounded-full border border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800"
                      >
                        {p}
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="space-y-4">
                  {c.messages.map((m, idx) => (
                    <div
                      key={idx}
                      className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
                    >
                      <div
                        className={`max-w-[85%] rounded-lg px-3 py-2 ${m.role === 'user' ? (isWorkspace ? 'border-l-2 border-[#7864b2] bg-[#131e30] text-[#e4eaf4] pl-3' : 'bg-purple-600 text-white') : 'bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-200 border border-gray-100 dark:border-gray-700'}`}
                      >
                        {isWorkspace && (
                          <div
                            className={`text-xs mb-1 font-medium ${m.role === 'user' ? 'text-[#9baac1]' : 'text-[#bda8ec]'}`}
                          >
                            {m.role === 'user' ? 'You' : 'HOMEPOT AI'}
                          </div>
                        )}
                        {m.role === 'assistant' &&
                          (m.routing?.resolved === 'knowledge' ||
                            m.trust?.trust_mode === 'informational') && (
                            <div className="mb-2 inline-flex items-center gap-1.5 rounded-full bg-purple-50 dark:bg-purple-950/30 px-2.5 py-1 text-xs font-medium text-purple-700 dark:text-purple-300">
                              <BookOpen className="w-3.5 h-3.5" />
                              <span>Knowledge</span>
                            </div>
                          )}
                        {m.role === 'assistant' &&
                          m.routing?.resolved === 'diagnostic' &&
                          m.trust?.trust_mode !== 'informational' && (
                            <div className="mb-2 inline-flex items-center gap-1.5 rounded-full bg-indigo-50 dark:bg-indigo-950/30 px-2.5 py-1 text-xs font-medium text-indigo-700 dark:text-indigo-300">
                              <ShieldAlert className="w-3.5 h-3.5" />
                              <span>Diagnostic</span>
                            </div>
                          )}
                        <div className="prose prose-sm max-w-none text-gray-700 dark:text-gray-200">
                          <ReactMarkdown>{m.content}</ReactMarkdown>
                        </div>
                        {m.role === 'assistant' && (
                          <div className="mt-2 flex items-center gap-2 text-[11px] text-gray-400 dark:text-gray-500 flex-wrap">
                            {m.routing?.resolved && (
                              <span className="capitalize">{m.routing.resolved}</span>
                            )}
                            {m.provider && (
                              <span>
                                · {m.provider}
                                {m.model ? ` / ${m.model}` : ''}
                              </span>
                            )}
                            {m.elapsedMs != null && (
                              <span>· {Math.round(m.elapsedMs / 1000)} s</span>
                            )}
                          </div>
                        )}
                        {m.role === 'assistant' && (m.trust || (m.sources && m.sources.length)) && (
                          <details className="mt-2 text-xs text-gray-500 dark:text-gray-400">
                            <summary className="cursor-pointer select-none py-1 hover:text-gray-700 dark:hover:text-gray-200">
                              Details
                            </summary>
                            <div className="pl-3 border-l border-gray-200 dark:border-gray-700 mt-2 space-y-2">
                              {m.sources && m.sources.length > 0 && (
                                <div className="flex flex-wrap items-center gap-1.5">
                                  <span className="font-medium text-gray-600 dark:text-gray-300">
                                    Evidence:
                                  </span>
                                  {m.sources.map((src) => (
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
                              {m.trust && m.trust.trust_mode !== 'informational' && (
                                <TrustBanner
                                  trust={m.trust}
                                  expanded={c.trustExpanded}
                                  onToggle={() => c.setTrustExpanded((v) => !v)}
                                />
                              )}
                            </div>
                          </details>
                        )}
                        {m.role === 'assistant' && m.proposal && (
                          <ProposalCard proposal={m.proposal} />
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
              {c.loading && (
                <div className="flex flex-col items-center justify-center py-4 text-gray-500 gap-2 text-center px-4">
                  <Loader2 className="w-5 h-5 animate-spin text-purple-600" />
                  <span className="text-xs animate-pulse transition-all duration-300">
                    {c.loadingMessage}
                  </span>
                  {c.slowHint && (
                    <span className="text-[10px] text-gray-400 max-w-[18rem]">
                      Still working — the model runs on CPU, and the first question after a break
                      can take a couple of minutes.
                    </span>
                  )}
                </div>
              )}
              {c.error && (
                <div className="flex flex-col items-center justify-center py-4 gap-2 text-center px-4 text-red-500">
                  <div className="flex items-center gap-2">
                    <AlertCircle className="w-4 h-4 shrink-0" />
                    <span className="font-medium">The assistant couldn&apos;t answer that</span>
                  </div>
                  <p className="text-xs text-red-400/90 max-w-xs">{c.error}</p>
                </div>
              )}
              {c.cancelled && (
                <div className="flex flex-col items-center justify-center py-4 gap-2 text-center px-4 text-gray-500">
                  <Square className="w-4 h-4" />
                  <span className="font-medium">Query cancelled</span>
                  <p className="text-xs text-gray-400 max-w-xs">
                    {c.cancelConfirmed
                      ? 'Nothing was saved — the abandoned answer is discarded rather than stored in memory.'
                      : 'Stopped on this page. The answer may have finished server-side before the cancel arrived.'}
                  </p>
                </div>
              )}
            </>
          ) : c.loading ? (
            <div className="flex flex-col items-center justify-center h-full text-gray-500 gap-2 text-center px-4">
              <Loader2 className="w-5 h-5 animate-spin text-purple-600" />
              <span className="text-xs animate-pulse transition-all duration-300">
                {c.loadingMessage}
              </span>
              {c.slowHint && (
                <span className="text-[10px] text-gray-400 max-w-[18rem]">
                  Still working — the model runs on CPU, and the first question after a break can
                  take a couple of minutes.
                </span>
              )}
            </div>
          ) : c.cancelled ? (
            <div className="flex flex-col items-center justify-center h-full gap-2 text-center px-4 text-gray-500">
              <Square className="w-4 h-4" />
              <span className="font-medium">Query cancelled</span>
              <p className="text-xs text-gray-400 max-w-xs">
                {c.cancelConfirmed
                  ? 'Nothing was saved — the abandoned answer is discarded rather than stored in memory.'
                  : 'Stopped on this page. The answer may have finished server-side before the cancel arrived.'}
              </p>
            </div>
          ) : c.error ? (
            <div className="flex flex-col items-center justify-center h-full gap-2 text-center px-4 text-red-500">
              <div className="flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span className="font-medium">The assistant couldn&apos;t answer that</span>
              </div>
              <p className="text-xs text-red-400/90 max-w-xs">{c.error}</p>
            </div>
          ) : c.replaying ? (
            <GateReplay trust={c.trust} onDone={c.handleGateReplayDone} />
          ) : c.response ? (
            <div className="relative group min-h-full">
              {c.isKnowledge ? (
                <>
                  <div className="mb-2 inline-flex items-center gap-1.5 rounded-full bg-purple-50 dark:bg-purple-950/30 px-2.5 py-1 text-xs font-medium text-purple-700 dark:text-purple-300">
                    <BookOpen className="w-3.5 h-3.5" />
                    <span>Knowledge</span>
                    <span className="font-normal text-purple-500/80 dark:text-purple-400/70">
                      — answered from documentation
                    </span>
                  </div>
                </>
              ) : (
                <>
                  {c.routing?.resolved === 'diagnostic' && (
                    <div className="mb-2 inline-flex items-center gap-1.5 rounded-full bg-indigo-50 dark:bg-indigo-950/30 px-2.5 py-1 text-xs font-medium text-indigo-700 dark:text-indigo-300">
                      <ShieldAlert className="w-3.5 h-3.5" />
                      <span>Diagnostic</span>
                      <span className="font-normal text-indigo-500/80 dark:text-indigo-400/70">
                        — validated through gates
                      </span>
                    </div>
                  )}
                </>
              )}
              <div className="sticky top-0 float-right z-10">
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6 text-gray-400 hover:text-purple-600 opacity-0 group-hover:opacity-100 transition-opacity hover:bg-transparent bg-white/50 dark:bg-gray-900/50 backdrop-blur-sm rounded-full shadow-sm border border-gray-100 dark:border-gray-800"
                  onClick={c.handleCopy}
                  title="Copy to clipboard"
                >
                  {c.copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                </Button>
              </div>
              <div className="prose prose-sm max-w-none text-gray-700 dark:text-gray-300 pr-0">
                <ReactMarkdown>{c.response}</ReactMarkdown>
              </div>
              <div className="mt-2 flex items-center gap-2 text-[11px] text-gray-400 dark:text-gray-500 flex-wrap">
                {c.routing?.resolved && <span className="capitalize">{c.routing.resolved}</span>}
                {c.llmProvider?.current && (
                  <span>
                    · {c.llmProvider.current}
                    {c.llmProvider.model ? ` / ${c.llmProvider.model}` : ''}
                  </span>
                )}
              </div>
              {(c.trust || (c.sources && c.sources.length)) && (
                <details className="mt-2 text-xs text-gray-500 dark:text-gray-400">
                  <summary className="cursor-pointer select-none py-1 hover:text-gray-700 dark:hover:text-gray-200">
                    Details
                  </summary>
                  <div className="pl-3 border-l border-gray-200 dark:border-gray-700 mt-2 space-y-2">
                    {c.sources && c.sources.length > 0 && (
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span className="font-medium text-gray-600 dark:text-gray-300">
                          Evidence:
                        </span>
                        {c.sources.map((src) => (
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
                    {c.trust && c.trust.trust_mode !== 'informational' && (
                      <TrustBanner
                        trust={c.trust}
                        expanded={c.trustExpanded}
                        onToggle={() => c.setTrustExpanded((v) => !v)}
                      />
                    )}
                  </div>
                </details>
              )}
              {c.proposal && <ProposalCard proposal={c.proposal} />}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-gray-400 italic text-center gap-2">
              <Sparkles className="w-8 h-8 opacity-20" />
              <p>Ask about system status, anomalies, or maintenance recommendations...</p>
              <div className="flex flex-wrap justify-center gap-1.5 mt-2 not-italic">
                {c.suggestedPrompts.map((p) => (
                  <button
                    key={p}
                    type="button"
                    onClick={() => c.setQuery(p)}
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
        <div
          className={`flex flex-col gap-2 ${isWorkspace ? 'mx-3 mb-3 p-3 bg-[#141f32] border border-[#35415a] rounded-xl' : ''}`.trim()}
        >
          <form onSubmit={c.handleAsk} className="flex gap-2 items-end">
            {isWorkspace ? (
              <textarea
                spellCheck="true"
                lang="en"
                value={c.query}
                onChange={(e) => c.setQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    if (c.query.trim() && !c.loading) c.handleAsk(e);
                  }
                }}
                placeholder="Ask about your fleet, devices, or how to do something..."
                rows={2}
                disabled={c.loading}
                className="flex-1 px-3 py-2 text-sm rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-950 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 transition-all resize-none"
              />
            ) : (
              <input
                type="text"
                spellCheck="true"
                lang="en"
                value={c.query}
                onChange={(e) => c.setQuery(e.target.value)}
                placeholder="e.g., How is our system performing today?"
                className="flex-1 px-3 py-2 text-sm rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-950 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 transition-all"
                disabled={c.loading}
              />
            )}
            <Button
              type={c.loading ? 'button' : 'submit'}
              onClick={c.loading ? c.handleCancel : undefined}
              disabled={!c.loading && !c.query.trim()}
              size="icon"
              aria-label={c.loading ? 'Stop' : 'Send'}
              title={c.loading ? 'Stop (Esc)' : 'Send'}
              className="bg-purple-600 hover:bg-purple-700 text-white"
            >
              {c.loading ? <Square className="w-4 h-4" /> : <Send className="w-4 h-4" />}
            </Button>
          </form>

          {/* Mode selector */}
          <div className="flex items-center gap-2 text-xs">
            <span className="text-gray-500 dark:text-gray-400">Mode:</span>
            <div
              role="group"
              aria-label="AI query mode"
              className="inline-flex rounded-md border border-gray-200 dark:border-gray-700 overflow-hidden"
            >
              {c.aiModes.map((m) => (
                <button
                  key={m.id}
                  type="button"
                  title={m.title}
                  onClick={() => c.setMode(m.id)}
                  disabled={c.loading}
                  aria-pressed={c.mode === m.id}
                  className={`px-2.5 py-1 transition-colors disabled:opacity-50 ${c.mode === m.id ? 'bg-purple-600 text-white' : 'text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800'}`}
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
