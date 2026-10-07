export enum BrowserCommandType {
  OPEN_PAGE = "OPEN_PAGE",
  NAVIGATE = "NAVIGATE",
  READ_PAGE = "READ_PAGE",
  FIND_TEXT = "FIND_TEXT",
  SCROLL = "SCROLL",
  CLICK = "CLICK",
  EXTRACT_VISIBLE_CONTENT = "EXTRACT_VISIBLE_CONTENT",
  EXTRACT_LINKS = "EXTRACT_LINKS",
  GET_PAGE_STATE = "GET_PAGE_STATE",
  REQUEST_USER_APPROVAL = "REQUEST_USER_APPROVAL",
  PAUSE = "PAUSE",
  RESUME = "RESUME",
  STOP = "STOP",
  EXECUTE_APPROVED_OUTREACH = "EXECUTE_APPROVED_OUTREACH",
}

export enum CommandExecutionStatus {
  SUCCESS = "SUCCESS",
  FAILED = "FAILED",
  BLOCKED = "BLOCKED",
  WAITING_FOR_USER = "WAITING_FOR_USER",
  EXPIRED = "EXPIRED",
  CANCELLED = "CANCELLED",
  DELIVERY_UNKNOWN = "DELIVERY_UNKNOWN",
}

export enum ExtensionSessionState {
  DISCONNECTED = "DISCONNECTED",
  CONNECTING = "CONNECTING",
  CONNECTED = "CONNECTED",
  AUTHORIZED = "AUTHORIZED",
  RUNNING = "RUNNING",
  PAUSED = "PAUSED",
  WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL",
  BLOCKED = "BLOCKED",
  STOPPED = "STOPPED",
  ERROR = "ERROR",
}

export enum PageType {
  INSTAGRAM_POST = "INSTAGRAM_POST",
  INSTAGRAM_PROFILE = "INSTAGRAM_PROFILE",
  REDDIT_POST = "REDDIT_POST",
  REDDIT_PROFILE = "REDDIT_PROFILE",
  PUBLIC_WEBSITE = "PUBLIC_WEBSITE",
  SEARCH_ENGINE = "SEARCH_ENGINE",
  OTHER = "OTHER",
  BLOCKED_PAGE = "BLOCKED_PAGE",
}

export interface BrowserCommand {
  command_id: string;
  session_id: string;
  type: BrowserCommandType;
  payload: Record<string, any>;
  issued_at: string;
  expires_at?: string;
  correlation_id: string;
}

export interface BrowserCommandResult {
  command_id: string;
  session_id: string;
  success: boolean;
  status: CommandExecutionStatus;
  result: Record<string, any>;
  error?: string;
  duration_ms: number;
  timestamp: string;
  correlation_id: string;
}

export interface PageState {
  url: string;
  title?: string;
  origin?: string;
  page_type: PageType;
  is_loading: boolean;
  visible_text_available: boolean;
  interactive_elements_count: number;
  timestamp: string;
}

export interface ObservationPayload {
  url: string;
  title?: string;
  origin?: string;
  page_type: PageType;
  visible_text: string;
  headings: string[];
  links: string[];
  recipient_handle?: string;
  profile_url?: string;
  meta_description?: string;
  timestamp: string;
}

export interface ApprovedOutreachPayload {
  draft_id: string;
  lead_id: string;
  channel: string;
  recipient: string;
  subject?: string;
  body: string;
  cta_text?: string;
  approval_id?: string;
  expected_profile_or_domain?: string;
}

export interface PairingSessionData {
  session_id: string;
  token: string;
  organization_id: string;
  expires_at: string;
  backend_url: string;
}
