import { EXTENSION_LIMITS } from "../shared/constants.js";
import { encodeMessageFrame } from "../shared/protocol.js";
import { ExtensionSessionState, PairingSessionData } from "../shared/types.js";
import { SessionManager } from "./session_manager.js";
import { CommandRouter } from "./command_router.js";

export class GatewayConnection {
  private static ws: WebSocket | null = null;
  private static pingInterval: any = null;
  private static reconnectTimer: any = null;
  private static reconnectAttempts = 0;
  private static onCommandCallback: ((command: any) => void) | null = null;

  public static setCommandCallback(callback: (command: any) => void): void {
    this.onCommandCallback = callback;
  }

  public static isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }

  public static getReconnectAttempts(): number {
    return this.reconnectAttempts;
  }

  public static async connect(forceReconnect: boolean = false): Promise<boolean> {
    const sessionData = await SessionManager.getSessionData();
    if (!sessionData) {
      SessionManager.setState(ExtensionSessionState.DISCONNECTED);
      return false;
    }

    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      if (!forceReconnect) {
        return true;
      }
      this.disconnect();
    }

    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    return new Promise((resolve) => {
      try {
        let httpBase = (sessionData.backend_url || "http://127.0.0.1:8000").replace(/\/$/, "");
        // Normalize localhost:8000 to 127.0.0.1:8000 on Windows to avoid IPv6 [::1] connection refused
        if (httpBase.includes("localhost:8000")) {
          httpBase = httpBase.replace("localhost:8000", "127.0.0.1:8000");
        }
        const wsBase = httpBase.replace(/^http:/, "ws:").replace(/^https:/, "wss:");
        const wsUrl = `${wsBase}/api/v1/agent/browser/ws?token=${encodeURIComponent(sessionData.token)}`;

        SessionManager.setState(ExtensionSessionState.CONNECTING);
        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
          this.reconnectAttempts = 0;
          SessionManager.setState(ExtensionSessionState.CONNECTED);
          this.startHeartbeat();
          resolve(true);
        };

        this.ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            this.handleIncomingFrame(data);
          } catch (e) {
            console.error("Error parsing WebSocket frame:", e);
          }
        };

        this.ws.onclose = (event) => {
          this.stopHeartbeat();
          this.ws = null;
          SessionManager.setState(ExtensionSessionState.DISCONNECTED);
          CommandRouter.setControlState({ active: false, status: "DISCONNECTED", action_text: "" }).catch(() => {});
          
          if (event.code === 4003) {
            // Explicit revocation by backend: clear session so user can re-pair cleanly
            console.warn("Session token revoked by backend (code 4003). Clearing session credentials.");
            SessionManager.clearSessionData();
          } else {
            // Transient network disconnect or server restart: schedule automatic reconnect
            this.scheduleReconnect();
          }
          resolve(false);
        };

        this.ws.onerror = (err) => {
          console.error("Gateway WebSocket error:", err);
          CommandRouter.setControlState({ active: false, status: "DISCONNECTED", action_text: "" }).catch(() => {});
          this.ws?.close();
        };
      } catch (err) {
        console.error("Failed to establish WebSocket connection:", err);
        SessionManager.setState(ExtensionSessionState.DISCONNECTED);
        CommandRouter.setControlState({ active: false, status: "DISCONNECTED", action_text: "" }).catch(() => {});
        this.scheduleReconnect();
        resolve(false);
      }
    });
  }

  public static disconnect(): void {
    this.stopHeartbeat();
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    SessionManager.setState(ExtensionSessionState.DISCONNECTED);
    CommandRouter.setControlState({ active: false, status: "DISCONNECTED", action_text: "" }).catch(() => {});
  }

  public static sendFrame(frameType: string, payload: any): boolean {
    if (!this.isConnected()) return false;
    try {
      this.ws!.send(encodeMessageFrame(frameType, payload));
      return true;
    } catch (e) {
      console.error("Failed to send WebSocket frame:", e);
      return false;
    }
  }

  private static handleIncomingFrame(data: any): void {
    const frameType = data.frame_type;
    if (frameType === "COMMAND" && data.command) {
      if (this.onCommandCallback) {
        this.onCommandCallback(data.command);
      }
    } else if (frameType === "CONNECTED_ACK") {
      SessionManager.setState(ExtensionSessionState.CONNECTED);
    }
  }

  private static startHeartbeat(): void {
    this.stopHeartbeat();
    this.pingInterval = setInterval(() => {
      if (this.isConnected()) {
        this.sendFrame("PING", { timestamp: new Date().toISOString() });
      }
    }, EXTENSION_LIMITS.PING_INTERVAL_MS);
  }

  private static stopHeartbeat(): void {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }

  private static scheduleReconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
    }
    this.reconnectAttempts++;
    // Exponential backoff: 1s, 2s, 4s, 8s, up to 15s max. Continues retrying while sessionData exists.
    const delay = Math.min(1000 * Math.pow(1.5, Math.min(this.reconnectAttempts, 8)), 15000);
    this.reconnectTimer = setTimeout(async () => {
      const sessionData = await SessionManager.getSessionData();
      if (sessionData && !this.isConnected()) {
        this.connect();
      }
    }, delay);
  }
}
