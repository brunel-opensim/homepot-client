import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Sparkles, Send, Loader2, AlertCircle } from 'lucide-react';
import api from '@/services/api';

export default function AskAIWidget() {
  const [query, setQuery] = useState('');
  const [response, setResponse] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleAsk = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setError(null);
    setResponse(null);

    try {
      const result = await api.ai.query(query);
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
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-lg font-medium">
          <Sparkles className="w-5 h-5 text-purple-600" />
          Ask AI Assistant
        </CardTitle>
      </CardHeader>
      <CardContent className="flex-1 flex flex-col gap-4">
        {/* Response Area */}
        <div className="flex-1 min-h-[150px] bg-gray-50 dark:bg-gray-900 rounded-lg p-4 text-sm overflow-y-auto border border-gray-100 dark:border-gray-800">
          {loading ? (
            <div className="flex flex-col items-center justify-center h-full text-gray-500 gap-2">
              <Loader2 className="w-5 h-5 animate-spin text-purple-600" />
              <span className="text-xs">Analyzing system metrics...</span>
            </div>
          ) : error ? (
            <div className="flex items-center text-red-500 gap-2 h-full justify-center">
              <AlertCircle className="w-4 h-4" />
              {error}
            </div>
          ) : response ? (
            <div className="prose prose-sm max-w-none text-gray-700 dark:text-gray-300 whitespace-pre-wrap">
              {response}
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
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="e.g., Why is the kitchen camera failing?"
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
