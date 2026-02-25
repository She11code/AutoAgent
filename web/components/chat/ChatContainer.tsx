'use client';

import * as React from 'react';
import { ScrollArea } from '@/components/ui';
import { MessageItem } from './MessageItem';
import { MessageInput } from './MessageInput';
import type { Message } from '@/types/chat';

interface ChatContainerProps {
  messages: Message[];
  isStreaming: boolean;
  onSendMessage: (content: string) => void;
  currentSessionTitle?: string;
}

export function ChatContainer({
  messages,
  isStreaming,
  onSendMessage,
  currentSessionTitle,
}: ChatContainerProps) {
  const scrollRef = React.useRef<HTMLDivElement>(null);

  // 自动滚动到底部
  React.useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  return (
    <div className="flex flex-col h-full">
      {/* Messages Area */}
      <ScrollArea ref={scrollRef} className="flex-1">
        {messages.length === 0 && !isStreaming ? (
          <div className="flex flex-col items-center justify-center h-full text-gray-500 dark:text-gray-400">
            <div className="text-center">
              <h3 className="text-lg font-medium mb-2">
                {currentSessionTitle || '开始新对话'}
              </h3>
              <p className="text-sm">输入消息开始与 Auto-Agent 对话</p>
            </div>
          </div>
        ) : (
          <div className="max-w-4xl mx-auto">
            {messages.map((message) => (
              <MessageItem key={message.id} message={message} />
            ))}
          </div>
        )}
      </ScrollArea>

      {/* Input Area */}
      <MessageInput onSend={onSendMessage} disabled={isStreaming} />
    </div>
  );
}
