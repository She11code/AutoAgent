'use client';

import * as React from 'react';
import { Sun, Moon, Monitor } from 'lucide-react';
import { Button } from '@/components/ui';
import { useSettingsStore } from '@/lib/stores';
import type { Theme } from '@/types/settings';

interface HeaderProps {
  title?: string;
}

export function Header({ title }: HeaderProps) {
  const { theme, setTheme } = useSettingsStore();
  const [mounted, setMounted] = React.useState(false);

  React.useEffect(() => {
    setMounted(true);
  }, []);

  const cycleTheme = () => {
    const themes: Theme[] = ['light', 'dark', 'system'];
    const currentIndex = themes.indexOf(theme);
    const nextIndex = (currentIndex + 1) % themes.length;
    setTheme(themes[nextIndex]);
  };

  const getThemeIcon = () => {
    if (!mounted) return <Monitor className="h-4 w-4" />;
    switch (theme) {
      case 'light':
        return <Sun className="h-4 w-4" />;
      case 'dark':
        return <Moon className="h-4 w-4" />;
      default:
        return <Monitor className="h-4 w-4" />;
    }
  };

  return (
    <header className="flex items-center justify-between h-14 px-4 border-b border-border-light dark:border-border-dark bg-background-light dark:bg-background-dark">
      <h2 className="text-base font-medium truncate max-w-md">
        {title || 'Auto-Agent'}
      </h2>
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon" onClick={cycleTheme} title={`当前主题: ${theme}`}>
          {getThemeIcon()}
        </Button>
      </div>
    </header>
  );
}
