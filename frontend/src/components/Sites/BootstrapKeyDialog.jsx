import React, { useState } from 'react';
import { X, KeyRound, Copy, Check, Loader2, AlertTriangle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import api from '@/services/api';

export default function BootstrapKeyDialog({ isOpen, onClose, siteId, siteName }) {
  const [generating, setGenerating] = useState(false);
  const [key, setKey] = useState(null);
  const [error, setError] = useState(null);
  const [copied, setCopied] = useState(false);

  if (!isOpen) return null;

  const reset = () => {
    setGenerating(false);
    setKey(null);
    setError(null);
    setCopied(false);
  };

  const handleClose = () => {
    reset();
    onClose();
  };

  const handleGenerate = async () => {
    setGenerating(true);
    setError(null);
    setCopied(false);
    try {
      const data = await api.sites.generateBootstrapKey(siteId);
      setKey(data?.data?.bootstrap_key || null);
      if (!data?.data?.bootstrap_key) {
        setError('The backend did not return a key. Please try again.');
      }
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to generate bootstrap key.');
    } finally {
      setGenerating(false);
    }
  };

  const handleCopy = async () => {
    if (!key) return;
    try {
      await navigator.clipboard.writeText(key);
      setCopied(true);
    } catch {
      setError('Could not copy to clipboard. Select the key manually.');
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-lg bg-[#141a24] p-6 shadow-lg border border-[#1f2735] animate-in fade-in zoom-in-95 duration-200">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <KeyRound className="h-5 w-5 text-teal-400" />
            Bootstrap Key
          </h2>
          <button
            onClick={handleClose}
            className="text-gray-400 hover:text-white transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <p className="text-gray-300 mb-1">
          Generate a bootstrap key for <span className="font-medium text-white">"{siteName}"</span>.
          A device uses this key to self-enrol into the site from the User App.
        </p>
        <p className="text-sm text-gray-400 mb-4">
          Generating a new key replaces any existing key for this site. The key is shown only once.
        </p>

        {error && (
          <div className="bg-red-500/10 border border-red-500/20 text-red-400 px-4 py-3 rounded-md mb-4 text-sm">
            {error}
          </div>
        )}

        {generating && (
          <div className="flex items-center justify-center gap-2 text-gray-300 py-6">
            <Loader2 className="h-5 w-5 animate-spin" />
            Generating bootstrap key...
          </div>
        )}

        {!generating && key && (
          <div className="mb-4">
            <div className="flex items-center gap-2">
              <code className="flex-1 break-all rounded-md border border-teal-500/30 bg-teal-500/10 px-3 py-2.5 font-mono text-sm text-teal-300 select-all">
                {key}
              </code>
              <Button
                variant="outline"
                onClick={handleCopy}
                className="border-[#1f2735] bg-transparent text-gray-300 hover:bg-[#1f2735] hover:text-white shrink-0"
              >
                {copied ? (
                  <Check className="h-4 w-4 text-teal-400" />
                ) : (
                  <Copy className="h-4 w-4" />
                )}
              </Button>
            </div>
            <p className="mt-2 text-xs text-gray-400 flex items-center gap-1.5">
              <AlertTriangle className="h-3.5 w-3.5 text-yellow-500" />
              Store this key securely — it will not be shown again.
            </p>
          </div>
        )}

        <div className="flex justify-end gap-3">
          {key ? (
            <>
              <Button
                variant="outline"
                onClick={handleGenerate}
                className="border-[#1f2735] bg-transparent text-gray-300 hover:bg-[#1f2735] hover:text-white"
              >
                Regenerate
              </Button>
              <Button
                variant="outline"
                onClick={handleClose}
                className="border-[#1f2735] bg-transparent text-gray-300 hover:bg-[#1f2735] hover:text-white"
              >
                Done
              </Button>
            </>
          ) : (
            <>
              <Button
                variant="outline"
                onClick={handleClose}
                className="border-[#1f2735] bg-transparent text-gray-300 hover:bg-[#1f2735] hover:text-white"
              >
                Cancel
              </Button>
              <Button
                onClick={handleGenerate}
                disabled={generating}
                className="bg-teal-600 hover:bg-teal-700 text-white"
              >
                {generating && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                Generate Bootstrap Key
              </Button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
