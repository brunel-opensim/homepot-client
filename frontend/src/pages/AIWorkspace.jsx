import React from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import AskAIWidget from '@/components/Dashboard/AskAIWidget';

export default function AIWorkspace() {
  const navigate = useNavigate();

  return (
    <div className="h-full flex flex-col bg-black text-gray-200 p-2 gap-2 overflow-hidden">
      <div className="shrink-0 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-purple-600" />
          <h1 className="text-lg font-semibold text-white">AI Workspace</h1>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => navigate('/dashboard')}
          className="text-gray-400 hover:text-white"
        >
          <ArrowLeft className="w-4 h-4 mr-1" />
          Back to Dashboard
        </Button>
      </div>
      <div className="flex-1 min-h-0">
        <AskAIWidget variant="workspace" />
      </div>
    </div>
  );
}
