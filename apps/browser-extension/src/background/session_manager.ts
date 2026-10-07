import { ExtensionSessionState, PairingSessionData } from "../shared/types.js";
import { DEFAULT_BACKEND_HTTP, STORAGE_KEYS } from "../shared/constants.js";

export class SessionManager {
  private static currentState: ExtensionSessionState = ExtensionSessionState.DISCONNECTED;

  public static getState(): ExtensionSessionState {
    return this.currentState;
  }

  public static setState(state: ExtensionSessionState): void {
    this.currentState = state;
  }

  public static async getSessionData(): Promise<PairingSessionData | null> {
    const data = await chrome.storage.local.get(STORAGE_KEYS.SESSION_DATA);
    return data[STORAGE_KEYS.SESSION_DATA] || null;
  }

  public static async setSessionData(data: PairingSessionData): Promise<void> {
    await chrome.storage.local.set({ [STORAGE_KEYS.SESSION_DATA]: data });
    this.setState(ExtensionSessionState.AUTHORIZED);
  }

  public static async clearSessionData(): Promise<void> {
    await chrome.storage.local.remove([STORAGE_KEYS.SESSION_DATA, STORAGE_KEYS.PENDING_ACTION]);
    this.setState(ExtensionSessionState.DISCONNECTED);
  }

  /**
   * Submit pairing challenge code to FastAPI backend and store session credentials.
   */
  public static async pairWithBackend(
    pairingCode: string,
    backendHttpUrl: string = DEFAULT_BACKEND_HTTP
  ): Promise<{ success: boolean; error?: string; sessionData?: PairingSessionData }> {
    try {
      this.setState(ExtensionSessionState.CONNECTING);
      const url = `${backendHttpUrl.replace(/\/$/, "")}/api/v1/agent/browser/pair`;
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          pairing_code: pairingCode.trim().toUpperCase(),
          browser_id: `chrome-ext-${chrome.runtime.id}`,
          client_version: "2.0.0",
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        this.setState(ExtensionSessionState.DISCONNECTED);
        return {
          success: false,
          error: errorData.detail || `Pairing failed with status ${response.status}`,
        };
      }

      const res = await response.json();
      const sessionData: PairingSessionData = {
        session_id: res.session_id,
        token: res.token,
        organization_id: res.organization_id,
        expires_at: res.expires_at,
        backend_url: backendHttpUrl,
      };

      await this.setSessionData(sessionData);
      return { success: true, sessionData };
    } catch (err: any) {
      this.setState(ExtensionSessionState.DISCONNECTED);
      return { success: false, error: err.message || "Network error pairing with backend" };
    }
  }
}
