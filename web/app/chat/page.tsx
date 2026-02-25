'use client';

import * as React from 'react';
import { Sidebar, Header, SettingsPanel } from '@/components/layout';
import { ChatContainer } from '@/components/chat';
import { useChatStore, useSessionStore, useSettingsStore } from '@/lib/stores';
import { chatApi, sessionApi } from '@/lib/api';
import type { Message } from '@/types/chat';

export default function ChatPage() {
  const [settingsOpen, setSettingsOpen] = React.useState(false);

  // AbortController for canceling stream requests
  const abortControllerRef = React.useRef<AbortController | null>(null);

  // Cleanup on unmount
  React.useEffect(() => {
    return () => {
      abortControllerRef.current?.abort();
    };
  }, []);

  // Stores
  const {
    messages,
    isStreaming,
    addMessage,
    setStreaming,
    clearMessages,
    updateLastMessageDone,
    setMessages,
    setLoadingHistory,
    handleStreamEvent,
  } = useChatStore();

  const {
    sessions,
    currentSessionId,
    setSessions,
    addSession,
    removeSession,
    setCurrentSession,
    setLoading,
    setError,
  } = useSessionStore();

  const { userId } = useSettingsStore();

  // Stable callback for loading sessions
  const loadSessions = React.useCallback(async () => {
    setLoading(true);
    try {
      const response = await sessionApi.list(userId);
      setSessions(response.sessions);
    } catch (error) {
      setError((error as Error).message);
    } finally {
      setLoading(false);
    }
  }, [userId, setSessions, setLoading, setError]);

  // Stable callback for loading history
  const loadHistory = React.useCallback(async (sessionId: string) => {
    setLoadingHistory(true);
    try {
      const response = await sessionApi.getHistory(sessionId);
      // 转换为前端Message格式
      const historyMessages: Message[] = response.messages.map((msg, index) => ({
        id: `${msg.role}-${index}-${Date.now()}`,
        role: msg.role,
        content: msg.content,
        timestamp: msg.timestamp || Date.now(),
      }));
      setMessages(historyMessages);
    } catch (error) {
      console.error('Failed to load history:', error);
      clearMessages();
    }
  }, [setLoadingHistory, setMessages, clearMessages]);

  // Load sessions on mount
  React.useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  // 切换会话时加载历史消息
  React.useEffect(() => {
    if (currentSessionId) {
      loadHistory(currentSessionId);
    } else {
      clearMessages();
    }
  }, [currentSessionId, loadHistory, clearMessages]);

  const handleCreateSession = async () => {
    try {
      const response = await sessionApi.create({
        user_id: userId,
      });
      addSession({
        session_id: response.session_id,
        user_id: userId,
        title: response.title,
        created_at: Date.now() / 1000,
        updated_at: Date.now() / 1000,
      });
      setCurrentSession(response.session_id);
    } catch (error) {
      console.error('Failed to create session:', error);
    }
  };

  const handleSelectSession = (sessionId: string) => {
    setCurrentSession(sessionId);
  };

  const handleDeleteSession = async (sessionId: string) => {
    try {
      await sessionApi.delete(sessionId);
      removeSession(sessionId);
    } catch (error) {
      console.error('Failed to delete session:', error);
    }
  };

  const handleSendMessage = async (content: string) => {
    if (!content.trim() || isStreaming) return;

    // 取消之前的请求（如果有）
    abortControllerRef.current?.abort();
    abortControllerRef.current = new AbortController();
    const signal = abortControllerRef.current.signal;

    // 如果没有当前会话，先创建一个
    let sessionId = currentSessionId;
    if (!sessionId) {
      try {
        const response = await sessionApi.create({
          user_id: userId,
        });
        sessionId = response.session_id;
        addSession({
          session_id: sessionId,
          user_id: userId,
          title: content.slice(0, 20) + (content.length > 20 ? '...' : ''),
          created_at: Date.now() / 1000,
          updated_at: Date.now() / 1000,
        });
        setCurrentSession(sessionId);
      } catch (error) {
        console.error('Failed to create session:', error);
        return;
      }
    }

    // 添加用户消息
    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content,
      timestamp: Date.now(),
    };
    addMessage(userMessage);

    // 显示加载状态
    setStreaming(true);

    // 添加一个空的 AI 消息占位符
    addMessage({
      id: `ai-${Date.now()}`,
      role: 'assistant',
      content: '',
      timestamp: Date.now(),
      isStreaming: true,
    });

    try {
      // 使用流式 API，传递 AbortSignal
      for await (const event of chatApi.chatStream(
        {
          message: content,
          session_id: sessionId,
          user_id: userId,
        },
        signal
      )) {
        // 处理流式事件
        handleStreamEvent(event);
      }
    } catch (error) {
      // 如果是取消导致的错误，不显示错误消息
      if (error instanceof Error && error.name === 'AbortError') {
        console.log('Chat stream aborted');
        return;
      }
      console.error('Chat stream error:', error);
      updateLastMessageDone(`错误: ${(error as Error).message}`);
      setStreaming(false);
    }
    // 注意：不需要 finally setStreaming(false)，
    // 因为 done 事件会在 handleStreamEvent 中处理
  };

  const currentSession = sessions.find((s) => s.session_id === currentSessionId);

  return (
    <div className="flex h-screen bg-[#FDFDF7] dark:bg-[#09090B]">
      {/* Sidebar */}
      <div className="w-64 shrink-0">
        <Sidebar
          sessions={sessions}
          currentSessionId={currentSessionId}
          onSelectSession={handleSelectSession}
          onCreateSession={handleCreateSession}
          onDeleteSession={handleDeleteSession}
          onOpenSettings={() => setSettingsOpen(true)}
        />
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0">
        <Header title={currentSession?.title || undefined} />

        <main className="flex-1 overflow-hidden">
          <ChatContainer
            messages={messages}
            isStreaming={isStreaming}
            onSendMessage={handleSendMessage}
            currentSessionTitle={currentSession?.title || undefined}
          />
        </main>
      </div>

      {/* Settings Panel */}
      <SettingsPanel open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  );
}
