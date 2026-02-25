/**
 * API 类型定义
 *
 * 与后端 FastAPI 模型对应的 TypeScript 类型
 * Base URL: http://localhost:8000/api/v1
 */

// ========== 聊天相关 ==========

export interface ChatRequest {
  message: string;
  session_id?: string;
  user_id?: string;
}

export interface ChatResponse {
  response: string;
  session_id: string;
}

// ========== 会话相关 ==========

export interface SessionInfo {
  session_id: string;
  user_id: string;
  title: string | null;
  created_at: number;
  updated_at: number;
}

export interface SessionListResponse {
  sessions: SessionInfo[];
}

export interface SessionCreateRequest {
  user_id: string;
  title?: string;
  initial_message?: string;
}

export interface SessionCreateResponse {
  session_id: string;
  title: string;
}

export interface DeleteResponse {
  status: string;
  session_id: string;
}

// ========== 健康检查 ==========

export interface HealthResponse {
  status: string;
}

// ========== 历史消息 ==========

export interface MessageItem {
  role: 'user' | 'assistant';
  content: string;
  timestamp?: number;
}

export interface HistoryResponse {
  session_id: string;
  messages: MessageItem[];
}

// ========== 流式事件类型 ==========

/**
 * 流式事件类型
 */
export type StreamEventType =
  | 'node_start'
  | 'node_end'
  | 'supervisor_route'
  | 'thinking'
  | 'tool_call'
  | 'plan_step'
  | 'message'
  | 'done'
  | 'error';

/**
 * 流式 SSE 事件
 */
export interface StreamEvent {
  type: StreamEventType;
  node?: string;
  agent?: string;
  updates?: StreamUpdates;
  thought?: string;
  action?: string;
  action_input?: unknown;
  observation?: string;
  tool?: string;
  tool_output?: string;
  steps?: PlanStep[];
  routed_agent?: string;
  task?: string;
  content?: string;
  done?: boolean;
  final_answer?: string;
  message?: string;
}

/**
 * 节点更新信息
 */
export interface StreamUpdates {
  task_context?: {
    react_status?: string;
    active_agent?: string;
    plan_status?: string;
    current_task?: string;
    react_current_step?: number;
    react_max_steps?: number;
    react_final_answer?: string;
    last_iteration?: {
      thought?: string;
      action?: string;
      action_input?: unknown;
      observation?: string;
    };
    plan_steps?: PlanStep[];
  };
  messages?: Array<{
    type: string;
    content: string;
    name?: string;
  }>;
}

/**
 * 计划步骤
 */
export interface PlanStep {
  step_id: number;
  description?: string;
  task?: string;
  status?: string;
}
