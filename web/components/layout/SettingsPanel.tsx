'use client';

import * as React from 'react';
import { X } from 'lucide-react';
import { Button, Input } from '@/components/ui';
import { useSettingsStore } from '@/lib/stores';
import type { Theme } from '@/types/settings';

interface SettingsPanelProps {
  open: boolean;
  onClose: () => void;
}

export function SettingsPanel({ open, onClose }: SettingsPanelProps) {
  const { apiBaseUrl, setApiBaseUrl, theme, setTheme, userId, setUserId, reset } =
    useSettingsStore();
  const [localApiUrl, setLocalApiUrl] = React.useState(apiBaseUrl);
  const [localUserId, setLocalUserId] = React.useState(userId);

  React.useEffect(() => {
    setLocalApiUrl(apiBaseUrl);
    setLocalUserId(userId);
  }, [apiBaseUrl, userId]);

  const handleSave = () => {
    setApiBaseUrl(localApiUrl);
    setUserId(localUserId);
    onClose();
  };

  const handleReset = () => {
    reset();
    setLocalApiUrl('http://localhost:8000/api/v1');
    setLocalUserId('web-user');
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose} />

      {/* Panel */}
      <div className="relative z-50 bg-white dark:bg-gray-900 rounded-lg shadow-lg w-full max-w-md mx-4">
        <div className="flex items-center justify-between p-4 border-b border-border-light dark:border-border-dark">
          <h2 className="text-lg font-semibold">设置</h2>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="p-4 space-y-4">
          {/* API URL */}
          <div className="space-y-2">
            <label className="text-sm font-medium">API 地址</label>
            <Input
              value={localApiUrl}
              onChange={(e) => setLocalApiUrl(e.target.value)}
              placeholder="http://localhost:8000/api/v1"
            />
            <p className="text-xs text-muted-light dark:text-muted-dark">
              后端 API 服务地址
            </p>
          </div>

          {/* User ID */}
          <div className="space-y-2">
            <label className="text-sm font-medium">用户 ID</label>
            <Input
              value={localUserId}
              onChange={(e) => setLocalUserId(e.target.value)}
              placeholder="web-user"
            />
            <p className="text-xs text-muted-light dark:text-muted-dark">
              用于区分不同用户的会话
            </p>
          </div>

          {/* Theme */}
          <div className="space-y-2">
            <label className="text-sm font-medium">主题</label>
            <div className="flex gap-2">
              {(['light', 'dark', 'system'] as Theme[]).map((t) => (
                <Button
                  key={t}
                  variant={theme === t ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setTheme(t)}
                >
                  {t === 'light' ? '浅色' : t === 'dark' ? '深色' : '系统'}
                </Button>
              ))}
            </div>
          </div>
        </div>

        <div className="flex justify-end gap-2 p-4 border-t border-border-light dark:border-border-dark">
          <Button variant="outline" onClick={handleReset}>
            重置
          </Button>
          <Button onClick={handleSave}>保存</Button>
        </div>
      </div>
    </div>
  );
}
