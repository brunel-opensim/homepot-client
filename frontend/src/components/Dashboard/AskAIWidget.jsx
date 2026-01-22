import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Sparkles, Send, Loader2, AlertCircle, Trash2, Copy, Check } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import api from '@/services/api';
import { useAuth } from '@/hooks/useAuth';

export default function AskAIWidget() {
  const { user } = useAuth();
  // Load initial state from localStorage if available to persist context on refresh/navigation
  const [query, setQuery] = useState(() => localStorage.getItem('homepot_ai_query') || '');
  const [response, setResponse] = useState(
    () => localStorage.getItem('homepot_ai_response') || null
  );
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

  const clearHistory = () => {
    setQuery('');
    setResponse(null);
    setError(null);
    localStorage.removeItem('homepot_ai_query');
    localStorage.removeItem('homepot_ai_response');
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

    try {
      const userRole = user?.role || (user?.isAdmin ? 'Admin' : 'Client');
      const result = await api.ai.query(query, null, userRole);
      // The backend returns { response: "..." }
      setResponse(result.response);
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
