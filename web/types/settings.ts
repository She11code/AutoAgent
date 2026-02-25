/**
 * 设置类型定义
 */

// ============ 设置类型 ============

/**
 * 主题类型
 */
export type Theme = "light" | "dark" | "system";

/**
 * 应用设置
 */
export interface Settings {
  /** API 基础 URL */
  apiBaseUrl: string;
  /** 主题设置 */
  theme: Theme;
  /** 用户ID */
  userId: string;
  /** 是否显示工具调用详情 */
  showToolDetails?: boolean;
  /** 消息字体大小 */
  fontSize?: "small" | "medium" | "large";
  /** 是否启用流式输出 */
  enableStreaming?: boolean;
  /** 请求超时时间 (毫秒) */
  requestTimeout?: number;
}

// ============ 默认值 ============

/**
 * 默认设置
 */
export const DEFAULT_SETTINGS: Settings = {
  apiBaseUrl: "http://localhost:8000/api/v1",
  theme: "system",
  userId: "web-user",
  showToolDetails: true,
  fontSize: "medium",
  enableStreaming: true,
  requestTimeout: 60000,
};

// ============ 本地存储键 ============

/**
 * 本地存储键名
 */
export const STORAGE_KEYS = {
  SETTINGS: "auto-agent-settings",
  SESSIONS: "auto-agent-sessions",
  CURRENT_SESSION: "auto-agent-current-session",
} as const;
