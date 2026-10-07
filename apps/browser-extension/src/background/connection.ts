import { EXTENSION_LIMITS } from "../shared/constants.js";
import { encodeMessageFrame } from "../shared/protocol.js";
import { ExtensionSessionState, PairingSessionData } from "../shared/types.js";
import { SessionManager } from "./session_manager.js";

export class GatewayConnection {
  private static ws: WebSocket | null = null;
  private static pingInterval: any = null;
  private static reconnectAttempts = 0;
  private static maxReconnectAttempts = 5;
  private static onCommandCallback: ((command: any) => void) | null = null;

  public static setCommandCallback(callback: (command: any) => void): void {
    this.onCommandCallback = callback;
  }

  public static isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }

  public static async connect(): Promise<boolean> {
    const sessionData = await SessionManager.getSessionData();
    if (!sessionData) {
      SessionManager.setState(ExtensionSessionState.DISCONNECTED);
      return false;
    }

    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return true;
    }

    return new Promise((resolve) => {
      try {
        const httpBase = sessionData.backend_url.replace(/\/$/, "");
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

        this.ws.onclose = () => {
          this.stopHeartbeat();
          this.ws = null;
          SessionManager.setState(ExtensionSessionState.DISCONNECTED);
          this.scheduleReconnect();
          resolve(false);
        };

        this.ws.onerror = (err) => {
          console.error("Gateway WebSocket error:", err);
          this.ws?.close();
        };
      } catch (err) {
        console.error("Failed to establish WebSocket connection:", err);
        SessionManager.setState(ExtensionSessionState.DISCONNECTED);
        resolve(false);
      }
    });
  }

  public static disconnect(): void {
    this.stopHeartbeat();
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    SessionManager.setState(ExtensionSessionState.DISCONNECTED);
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
    if (this.reconnectAttempts >= this.maxReconnectAttempts) return;
    this.reconnectAttempts++;
    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 15000);
    setTimeout(() => {
      this.connect();
    }, delay);
  }
}
