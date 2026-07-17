import React, { useState, useEffect } from 'react';
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
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import api from '@/services/api';
import { useAuth } from '@/hooks/useAuth';

// Visual treatment per backend trust mode (ai/gates/base.py Mode instances).
// Falls back to the "mode_1" (status-only / least trusted) styling for any
// mode id we don't explicitly recognize, so a future Gate D mode degrades
// safely instead of rendering unstyled.
const TRUST_MODE_STYLES = {
  grounded: {
    icon: ShieldCheck,
    text: 'text-green-700 dark:text-green-400',
    bg: 'bg-green-50 dark:bg-green-950/30',
    border: 'border-green-200 dark:border-green-900',
    chipPass: 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-400',
  },
  mode_3: {
    icon: ShieldAlert,
    text: 'text-amber-700 dark:text-amber-400',
    bg: 'bg-amber-50 dark:bg-amber-950/30',
    border: 'border-amber-200 dark:border-amber-900',
    chipPass: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-400',
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

export default function AskAIWidget() {
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
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [loadingMessage, setLoadingMessage] = useState('Analyzing system metrics...');
  const [copied, setCopied] = useState(false);

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

  const clearHistory = () => {
    setQuery('');
    setResponse(null);
    setTrust(null);
    setTrustExpanded(false);
    setError(null);
    localStorage.removeItem('homepot_ai_query');
    localStorage.removeItem('homepot_ai_response');
    localStorage.removeItem('homepot_ai_trust');
  };

  const handleCopy = () => {
    if (!response) return;
    navigator.clipboard.writeText(response);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  useEffect(() => {
    let interval;
    if (loading) {
      const messages = [
        'Reviewing conversation history...',
        'Accessing long-term memory & vector store...',
        'Scanning active sites & devices...',
        'Analyzing push notification metrics...',
        'Checking for system anomalies...',
        'Synthesizing insights...',
      ];
      let i = 0;
      setLoadingMessage(messages[0]);
      interval = setInterval(() => {
        i = i + 1;
        if (i < messages.length) {
          setLoadingMessage(messages[i]);
        }
      }, 1500); // Change message every 1.5 seconds
    }
    return () => clearInterval(interval);
  }, [loading]);

  const handleAsk = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setError(null);
    setResponse(null);
    setTrust(null);
    setTrustExpanded(false);

    try {
      const userRole = user?.role || (user?.isAdmin ? 'Admin' : 'Client');
      const result = await api.ai.query(query, null, userRole);
      // The backend returns { response, timestamp, trust } -- trust is the
      // validation envelope's gate-by-gate outcome (see ai/gates/envelope.py).
      setResponse(result.response);
      setTrust(result.trust || null);
    } catch (err) {
      console.error('AI Query failed:', err);
      setError('Failed to get a response. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card className="h-full flex flex-col shadow-md">
      <CardHeader className="pb-3 flex flex-row items-center justify-between space-y-0">
        <CardTitle className="flex items-center gap-2 text-lg font-medium">
          <Sparkles className="w-5 h-5 text-purple-600" />
          System Diagnostics AI
        </CardTitle>
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
      </CardHeader>
      <CardContent className="flex-1 flex flex-col gap-4 min-h-0">
        {/* Response Area */}
        <div className="flex-1 min-h-0 bg-gray-50 dark:bg-gray-900 rounded-lg p-4 text-sm overflow-y-auto border border-gray-100 dark:border-gray-800">
          {loading ? (
            <div className="flex flex-col items-center justify-center h-full text-gray-500 gap-2">
              <Loader2 className="w-5 h-5 animate-spin text-purple-600" />
              <span className="text-xs animate-pulse transition-all duration-300">
                {loadingMessage}
              </span>
            </div>
          ) : error ? (
            <div className="flex items-center text-red-500 gap-2 h-full justify-center">
              <AlertCircle className="w-4 h-4" />
              {error}
            </div>
          ) : response ? (
            <div className="relative group min-h-full">
              <TrustBanner
                trust={trust}
                expanded={trustExpanded}
                onToggle={() => setTrustExpanded((v) => !v)}
              />
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
            <div className="flex flex-col items-center justify-center h-full text-gray-400 italic text-center gap-2">
              <Sparkles className="w-8 h-8 opacity-20" />
              <p>Ask about system status, anomalies, or maintenance recommendations...</p>
            </div>
          )}
        </div>

        {/* Input Area */}
        <form onSubmit={handleAsk} className="flex gap-2">
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
          <Button
            type="submit"
            disabled={loading || !query.trim()}
            size="icon"
            className="bg-purple-600 hover:bg-purple-700 text-white"
          >
            <Send className="w-4 h-4" />
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
