import React, { useEffect, useRef, useState } from 'react';
import {
  ArrowDown,
  ArrowUp,
  Check,
  Copy,
  Loader2,
  Sparkles,
  Square,
  SquarePen,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useAIConversation } from '@/hooks/useAIConversation';
import ProposalCard from './ProposalCard';
import './AskAIWidget.css';

function CopyButton({ text, label = 'Copy response' }) {
  const [status, setStatus] = useState('');
  const timeoutRef = useRef(null);
  useEffect(() => () => clearTimeout(timeoutRef.current), []);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setStatus('Copied');
    } catch {
      setStatus('Copy unavailable');
    }
    clearTimeout(timeoutRef.current);
    timeoutRef.current = setTimeout(() => setStatus(''), 2000);
  };
  return (
    <button type="button" className="ai-text-action" onClick={copy} aria-label={label}>
      {status === 'Copied' ? <Check aria-hidden="true" /> : <Copy aria-hidden="true" />}
      <span role="status">{status || 'Copy'}</span>
    </button>
  );
}

const markdownComponents = {
  pre({ children }) {
    const text = React.Children.toArray(children)
      .map((child) => child.props?.children || '')
      .join('');
    return (
      <div className="ai-code-block">
        <CopyButton text={text.replace(/\n$/, '')} label="Copy code" />
        <pre>{children}</pre>
      </div>
    );
  },
  table({ children }) {
    return (
      <div className="ai-table-scroll">
        <table>{children}</table>
      </div>
    );
  },
};

function MessageDetails({ message }) {
  const trust = message.trust;
  const sources = message.sources || [];
  const activity = message.activity || [];
  if (!trust && !sources.length && !activity.length) return null;
  return (
    <details className="ai-details">
      <summary>Details</summary>
      <div className="ai-details-body">
        {sources.length > 0 && (
          <div>
            <p>Evidence</p>
            <ul>
              {sources.map((source) => (
                <li key={source}>
                  <code>{source}</code>
                </li>
              ))}
            </ul>
          </div>
        )}
        {trust && trust.trust_mode !== 'informational' && (
          <div>
            <p className="ai-validation-label">{trust.trust_mode_label}</p>
            {trust.trust_score != null && (
              <p>Validation trust: {Math.round(trust.trust_score * 100)}%</p>
            )}
            {(trust.gates || []).map((gate, index) => (
              <p key={`${gate.gate_id}-${index}`}>
                Gate {gate.gate_id} ({gate.name}): {gate.status}.{' '}
                {(gate.checks || []).map((check) => check.message).join(' ') || gate.error}
              </p>
            ))}
            {!trust.actionable && <p>Advisory only. Device actions require separate review.</p>}
          </div>
        )}
        {activity.length > 0 && (
          <ul>
            {activity.map((event, index) => (
              <li key={event.id || index}>{event.type}</li>
            ))}
          </ul>
        )}
      </div>
    </details>
  );
}

function ConversationMessage({ message }) {
  const assistant = message.role === 'assistant';
  const resolved =
    message.routing?.resolved ||
    (message.trust?.trust_mode === 'informational' ? 'knowledge' : null);
  return (
    <article
      className={`ai-turn ${assistant ? 'ai-assistant-turn' : 'ai-user-turn'}`}
      aria-label={assistant ? 'HOMEPOT AI response' : 'Your message'}
    >
      <div className="ai-speaker">{assistant ? 'HOMEPOT AI' : 'You'}</div>
      <div className="ai-markdown">
        <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
          {message.content}
        </ReactMarkdown>
      </div>
      {assistant && (
        <>
          <div className="ai-message-meta">
            {resolved && <span className="capitalize">{resolved}</span>}
            {message.provider && (
              <span>
                {message.provider}
                {message.model ? ` / ${message.model}` : ''}
              </span>
            )}
            {message.elapsedMs != null && <span>{Math.round(message.elapsedMs / 1000)} s</span>}
            <CopyButton text={message.content} />
          </div>
          <MessageDetails message={message} />
          {message.proposal && <ProposalCard proposal={message.proposal} />}
        </>
      )}
    </article>
  );
}

export default function AskAIWidget({ variant = 'compact', className = '' }) {
  const c = useAIConversation(variant);
  const scrollRef = useRef(null);
  const inputRef = useRef(null);
  const stickToBottomRef = useRef(true);
  const [showLatest, setShowLatest] = useState(false);
  // Both variants render the same thread; sizing comes entirely from the parent.
  // The response fallback also preserves pre-session browser storage on upgrade.
  const messages = c.messages.length
    ? c.messages
    : c.response
      ? [
          {
            role: 'assistant',
            content: c.response,
            trust: c.trust,
            routing: c.routing,
            sources: c.sources,
            proposal: c.proposal,
          },
        ]
      : [];
  const jumpToLatest = () => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
    stickToBottomRef.current = true;
    setShowLatest(false);
  };
  useEffect(() => {
    const el = scrollRef.current;
    if (el && stickToBottomRef.current) el.scrollTop = el.scrollHeight;
  }, [c.messages, c.loading, c.response, c.error, c.loadingMessage]);
  useEffect(() => {
    const input = inputRef.current;
    if (!input) return;
    input.style.height = 'auto';
    input.style.height = `${Math.min(96, Math.max(42, input.scrollHeight))}px`;
  }, [c.query]);
  const newConversation = () => {
    c.clearHistory();
    stickToBottomRef.current = true;
    setShowLatest(false);
    inputRef.current?.focus();
  };

  return (
    <section
      className={`ai-assistant ${className}`.trim()}
      data-variant={variant}
      aria-label="HOMEPOT AI assistant"
    >
      <header className="ai-header">
        <h2>
          <Sparkles aria-hidden="true" />
          HOMEPOT AI
        </h2>
        <div className="ai-header-actions">
          {c.llmProvider && (
            <span
              className={`ai-provider-status ${c.llmProvider.healthy === false ? 'is-unhealthy' : ''}`}
              title={`${c.llmProvider.current}${c.llmProvider.model ? ` / ${c.llmProvider.model}` : ''}`}
            >
              {c.llmProvider.healthy === false
                ? 'Provider unavailable'
                : c.llmProvider.healthy === true
                  ? 'Connected'
                  : 'Status unknown'}
            </span>
          )}
          <button
            type="button"
            className="ai-icon-action"
            onClick={newConversation}
            disabled={c.loading}
            aria-label="New conversation"
            title="New conversation (keeps prior transcripts)"
          >
            <SquarePen aria-hidden="true" />
          </button>
        </div>
      </header>
      <div className="ai-conversation-wrap">
        <div
          ref={scrollRef}
          className="ai-conversation"
          role="region"
          aria-label="Conversation"
          onScroll={() => {
            const el = scrollRef.current;
            const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
            stickToBottomRef.current = nearBottom;
            setShowLatest(!nearBottom);
          }}
        >
          {messages.length === 0 && !c.loading && !c.error && !c.cancelled && (
            <div className="ai-empty-state">
              <Sparkles aria-hidden="true" />
              <p>Ask about system status, anomalies, or how to perform a task.</p>
              <div className="ai-suggestions">
                {c.suggestedPrompts.map((prompt) => (
                  <button
                    type="button"
                    key={prompt}
                    onClick={() => {
                      c.setQuery(prompt);
                      inputRef.current?.focus();
                    }}
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          )}
          {messages.map((message, index) => (
            <ConversationMessage key={index} message={message} />
          ))}
          {c.loading && (
            <div className="ai-active-run">
              <div className="ai-user-turn">
                <div className="ai-speaker">You</div>
                <p>{c.query}</p>
              </div>
              <div className="ai-progress" role="status">
                <Loader2 className="animate-spin" aria-hidden="true" />
                <span>{c.loadingMessage}</span>
              </div>
              {c.slowHint && (
                <p className="ai-inline-note">
                  Still working. You can stop this response at any time.
                </p>
              )}
            </div>
          )}
          {c.error && (
            <div className="ai-inline-error" role="alert">
              <p>The assistant couldn&apos;t answer that</p>
              <p>{c.error}</p>
            </div>
          )}
          {c.cancelled && (
            <div className="ai-inline-note" role="status">
              <p>Query cancelled</p>
              <p>
                {c.cancelConfirmed
                  ? 'Nothing was saved. The abandoned answer is discarded rather than stored in memory.'
                  : 'Stopped on this page. The answer may have finished server-side before the cancel arrived.'}
              </p>
            </div>
          )}
        </div>
        {showLatest && (
          <button type="button" className="ai-jump-latest" onClick={jumpToLatest}>
            <ArrowDown aria-hidden="true" />
            Latest
          </button>
        )}
      </div>
      <form className="ai-composer" onSubmit={c.handleAsk}>
        <textarea
          ref={inputRef}
          aria-label="Message HOMEPOT AI"
          spellCheck="true"
          lang="en"
          value={c.query}
          onChange={(e) => c.setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (
              e.key === 'Enter' &&
              !e.shiftKey &&
              !e.nativeEvent.isComposing &&
              e.keyCode !== 229
            ) {
              e.preventDefault();
              if (c.query.trim() && !c.loading) c.handleAsk(e);
            }
          }}
          placeholder="Ask a question or continue…"
          rows={2}
          disabled={c.loading}
        />
        <div className="ai-composer-controls">
          <select
            aria-label="AI query mode"
            value={c.mode}
            onChange={(e) => c.setMode(e.target.value)}
            disabled={c.loading}
          >
            {c.aiModes.map((mode) => (
              <option key={mode.id} value={mode.id}>
                {mode.label}
              </option>
            ))}
          </select>
          {c.llmProvider &&
            (c.isAdmin ? (
              <select
                aria-label="Switch LLM provider"
                title="Switch LLM provider (admin only)"
                value={c.llmProvider.current || 'ollama'}
                onChange={(e) => c.handleSwitchProvider(e.target.value)}
                disabled={c.loading || c.llmSwitching}
              >
                <option value="ollama">Ollama</option>
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
            ) : (
              <span className="ai-provider-readonly" title="LLM provider (read-only)">
                {c.llmProvider.current || 'ollama'}
              </span>
            ))}
          {c.llmSwitching && (
            <Loader2 className="ai-switching animate-spin" aria-label="Switching provider" />
          )}
          <button
            type={c.loading ? 'button' : 'submit'}
            onClick={c.loading ? c.handleCancel : undefined}
            className="ai-send"
            disabled={!c.loading && (!c.query.trim() || c.llmSwitching)}
            aria-label={c.loading ? 'Stop' : 'Send'}
            title={c.loading ? 'Stop (Esc)' : 'Send'}
          >
            {c.loading ? <Square aria-hidden="true" /> : <ArrowUp aria-hidden="true" />}
          </button>
        </div>
        <div className="ai-composer-note">
          <span>Device actions require review.</span>
          <span className="ai-keyboard-hint">Enter ↵ · Shift+Enter new line</span>
        </div>
      </form>
    </section>
  );
}
