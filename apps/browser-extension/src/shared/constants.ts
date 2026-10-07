export const DEFAULT_BACKEND_HTTP = "http://localhost:8000";
export const DEFAULT_BACKEND_WS = "ws://localhost:8000/api/v1/agent/browser/ws";

export const STORAGE_KEYS = {
  SESSION_DATA: "tv_session_data",
  SETTINGS: "tv_settings",
  PENDING_ACTION: "tv_pending_action",
  OBSERVATION_HISTORY: "tv_obs_history",
};

export const EXTENSION_LIMITS = {
  MAX_VISIBLE_TEXT_LENGTH: 8000,
  MAX_LINKS_TO_EXTRACT: 50,
  MAX_SCROLL_AMOUNT: 1200,
  COMMAND_TIMEOUT_MS: 30000,
  PING_INTERVAL_MS: 25000,
};
