/**
 * 聊天消息相关类型定义
 */

// ============ 消息类型 ============

/**
 * 消息角色类型
 */
export type MessageRole = "user" | "assistant" | "system";

/**
 * 消息类型（用于区分不同类型的消息展示）
 */
export type MessageType = "text" | "thinking" | "tool_call";

/**
 * 工具调用状态
 */
export type ToolCallStatus = 'pending' | 'running' | 'completed' | 'error';

/**
 * 工具调用
 */
export interface ToolCall {
  /** 工具调用唯一标识 */
  id: string;
  /** 工具名称 */
  name: string;
  /** 调用状态 */
  status: ToolCallStatus;
}

/**
 * 聊天消息
 */
export interface Message {
  /** 消息唯一标识 */
  id: string;
  /** 消息角色 */
  role: MessageRole;
  /** 消息内容 */
  content: string;
  /** 时间戳 (Unix timestamp, milliseconds) */
  timestamp: number;
  /** 是否正在加载中 */
  isStreaming?: boolean;
  /** 工具调用列表 */
  toolCalls?: ToolCall[];
  /** 消息类型（用于特殊展示） */
  type?: MessageType;
  /** 思考详情（type=thinking 时使用） */
  thinkingData?: {
    thought: string;
    action?: string;
    actionInput?: unknown;
  };
  /** 工具调用详情（type=tool_call 时使用） */
  toolData?: {
    tool: string;
    output?: string;
  };
}
