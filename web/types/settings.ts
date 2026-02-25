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
}

// ============ 默认值 ============

/**
 * 默认设置
 */
export const DEFAULT_SETTINGS: Settings = {
  apiBaseUrl: "http://localhost:8000/api/v1",
  theme: "system",
  userId: "web-user",
};
