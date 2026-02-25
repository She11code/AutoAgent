'use client';

import * as React from 'react';
import { Plus, MessageSquare, Trash2, Settings } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button, ScrollArea } from '@/components/ui';
import type { SessionInfo } from '@/types/api';

interface SidebarProps {
  sessions: SessionInfo[];
  currentSessionId: string | null;
  onSelectSession: (id: string) => void;
  onCreateSession: () => void;
  onDeleteSession: (id: string) => void;
  onOpenSettings: () => void;
  isLoading?: boolean;
}

export function Sidebar({
  sessions,
  currentSessionId,
  onSelectSession,
  onCreateSession,
  onDeleteSession,
  onOpenSettings,
  isLoading,
}: SidebarProps) {
  const [deleteConfirm, setDeleteConfirm] = React.useState<string | null>(null);

  const formatDate = (timestamp: number) => {
    const date = new Date(timestamp * 1000);
    const now = new Date();
    const diffDays = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24));

    if (diffDays === 0) {
      return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
    } else if (diffDays === 1) {
      return '昨天';
    } else if (diffDays < 7) {
      return `${diffDays} 天前`;
    } else {
      return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
    }
  };

  return (
    <div className="flex flex-col h-full bg-sidebar-light dark:bg-sidebar-dark border-r border-border-light dark:border-border-dark">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-border-light dark:border-border-dark">
        <h1 className="text-lg font-semibold">Auto-Agent</h1>
        <Button variant="ghost" size="icon" onClick={onOpenSettings}>
          <Settings className="h-4 w-4" />
        </Button>
      </div>

      {/* New Session Button */}
      <div className="p-3">
        <Button
          onClick={onCreateSession}
          className="w-full justify-start gap-2"
          disabled={isLoading}
        >
          <Plus className="h-4 w-4" />
          新建对话
        </Button>
      </div>

      {/* Session List */}
      <ScrollArea className="flex-1 px-2">
        {sessions.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-32 text-muted-light dark:text-muted-dark text-sm">
            <MessageSquare className="h-8 w-8 mb-2 opacity-50" />
            <span>暂无对话</span>
          </div>
        ) : (
          <div className="space-y-1 pb-4">
            {sessions.map((session) => (
              <div
                key={session.session_id}
                className={cn(
                  'group flex items-center gap-2 px-3 py-2 rounded-md cursor-pointer transition-colors',
                  currentSessionId === session.session_id
                    ? 'bg-primary/10 text-primary'
                    : 'hover:bg-gray-100 dark:hover:bg-gray-800'
                )}
                onClick={() => onSelectSession(session.session_id)}
              >
                <MessageSquare className="h-4 w-4 shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">
                    {session.title || '新对话'}
                  </p>
                  <p className="text-xs text-muted-light dark:text-muted-dark">
                    {formatDate(session.updated_at)}
                  </p>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  className={cn(
                    'h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity',
                    deleteConfirm === session.session_id && 'opacity-100 text-red-500'
                  )}
                  onClick={(e) => {
                    e.stopPropagation();
                    if (deleteConfirm === session.session_id) {
                      onDeleteSession(session.session_id);
                      setDeleteConfirm(null);
                    } else {
                      setDeleteConfirm(session.session_id);
                      setTimeout(() => setDeleteConfirm(null), 3000);
                    }
                  }}
                >
                  <Trash2 className="h-3 w-3" />
                </Button>
              </div>
            ))}
          </div>
        )}
      </ScrollArea>
    </div>
  );
}
