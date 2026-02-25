'use client';

import * as React from 'react';
import { User, Bot, Brain, Wrench } from 'lucide-react';
import { Avatar, AvatarFallback } from '@/components/ui';
import { MarkdownRenderer } from '@/lib/utils/markdown';
import { cn } from '@/lib/utils';
import type { Message } from '@/types/chat';

interface MessageItemProps {
  message: Message;
}

export function MessageItem({ message }: MessageItemProps) {
  const isUser = message.role === 'user';
  const isStreaming = message.isStreaming;
  const messageType = message.type || 'text';

  // 思考消息样式
  if (messageType === 'thinking') {
    return (
      <div className="flex gap-3 px-4 py-2 bg-blue-50/50 dark:bg-blue-900/10">
        <div className="w-8 h-8 shrink-0 flex items-center justify-center">
          <div className="w-6 h-6 rounded-full bg-blue-100 dark:bg-blue-800 flex items-center justify-center">
            <Brain className="h-3 w-3 text-blue-500" />
          </div>
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-xs text-blue-600 dark:text-blue-400 font-medium mb-1">
            思考中
          </div>
          <div className="text-sm text-gray-600 dark:text-gray-300">
            {message.thinkingData?.thought || message.content}
          </div>
          {message.thinkingData?.action && (
            <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">
              行动: {message.thinkingData.action}
            </div>
          )}
        </div>
      </div>
    );
  }

  // 工具调用消息样式
  if (messageType === 'tool_call') {
    return (
      <div className="flex gap-3 px-4 py-2 bg-yellow-50/50 dark:bg-yellow-900/10">
        <div className="w-8 h-8 shrink-0 flex items-center justify-center">
          <div className="w-6 h-6 rounded-full bg-yellow-100 dark:bg-yellow-800 flex items-center justify-center">
            <Wrench className="h-3 w-3 text-yellow-600" />
          </div>
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-xs text-yellow-600 dark:text-yellow-400 font-medium mb-1">
            工具调用
          </div>
          <code className="text-sm px-2 py-0.5 bg-gray-100 dark:bg-gray-800 rounded">
            {message.toolData?.tool || 'unknown'}
          </code>
          {message.toolData?.output && (
            <pre className="mt-2 text-xs text-gray-600 dark:text-gray-400 bg-gray-100 dark:bg-gray-800 rounded p-2 overflow-x-auto max-h-24">
              {message.toolData.output.length > 300
                ? message.toolData.output.slice(0, 300) + '...'
                : message.toolData.output}
            </pre>
          )}
        </div>
      </div>
    );
  }

  // 普通消息样式
  return (
    <div
      className={cn(
        'flex gap-3 px-4 py-3',
        isUser ? 'bg-transparent' : 'bg-gray-50 dark:bg-gray-900/50'
      )}
    >
      <Avatar className="h-8 w-8 shrink-0">
        <AvatarFallback
          className={
            isUser
              ? 'bg-primary text-white'
              : 'bg-gray-200 dark:bg-gray-700'
          }
        >
          {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
        </AvatarFallback>
      </Avatar>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-sm font-medium">
            {isUser ? '你' : 'Auto-Agent'}
          </span>
          {message.timestamp && (
            <span className="text-xs text-muted-light dark:text-muted-dark">
              {new Date(message.timestamp).toLocaleTimeString('zh-CN', {
                hour: '2-digit',
                minute: '2-digit',
              })}
            </span>
          )}
        </div>

        <div className="prose prose-sm dark:prose-invert max-w-none">
          {isStreaming && !message.content ? (
            <div className="flex items-center gap-1">
              <div className="w-2 h-2 bg-primary rounded-full animate-bounce [animation-delay:-0.3s]" />
              <div className="w-2 h-2 bg-primary rounded-full animate-bounce [animation-delay:-0.15s]" />
              <div className="w-2 h-2 bg-primary rounded-full animate-bounce" />
            </div>
          ) : (
            <MarkdownRenderer content={message.content} />
          )}
        </div>

        {/* Tool Calls Display */}
        {message.toolCalls && message.toolCalls.length > 0 && (
          <div className="mt-2 space-y-1">
            {message.toolCalls.map((tool) => (
              <div
                key={tool.id}
                className="flex items-center gap-2 text-xs text-muted-light dark:text-muted-dark bg-gray-100 dark:bg-gray-800 rounded px-2 py-1"
              >
                <span className="font-mono">{tool.name}</span>
                {tool.status === 'running' && (
                  <span className="text-primary">running...</span>
                )}
                {tool.status === 'completed' && (
                  <span className="text-green-500">done</span>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
