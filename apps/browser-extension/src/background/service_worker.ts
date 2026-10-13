import { CommandRouter } from "./command_router.js";
import { GatewayConnection } from "./connection.js";
import { SessionManager } from "./session_manager.js";
import { STORAGE_KEYS } from "../shared/constants.js";
import { CommandExecutionStatus, ExtensionSessionState } from "../shared/types.js";

// Initialize command routing
GatewayConnection.setCommandCallback(async (command) => {
  await CommandRouter.executeCommand(command);
});

// Expose on globalThis for diagnostics & inspection
(globalThis as any).SessionManager = SessionManager;
(globalThis as any).GatewayConnection = GatewayConnection;
(globalThis as any).CommandRouter = CommandRouter;

// Auto-connect on startup if session credentials exist
chrome.runtime.onStartup.addListener(async () => {
  const session = await SessionManager.getSessionData();
  if (session) {
    await GatewayConnection.connect();
  }
});

// Also try connect on install/load
(async () => {
  const session = await SessionManager.getSessionData();
  if (session) {
    await GatewayConnection.connect();
  }
})();

// Listen for tab URL updates
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === "complete" && tab.url && GatewayConnection.isConnected()) {
    // Request fresh page state from content script
    chrome.tabs.sendMessage(tabId, { command_type: "GET_PAGE_STATE" }, (response) => {
      if (!chrome.runtime.lastError && response?.success) {
        GatewayConnection.sendFrame("PAGE_STATE", response.result);
      }
    });
  }
});

// Listen for tab closure to clean up dedicated agent tab
chrome.tabs.onRemoved.addListener((tabId) => {
  if (tabId === CommandRouter.getDedicatedTabId()) {
    CommandRouter.setDedicatedTabId(null);
  }
});

// Runtime message listener (from content script or popup)
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  const { type, payload } = message;

  (async () => {
    switch (type) {
      case "PAGE_STATE_CHANGED": {
        if (GatewayConnection.isConnected()) {
          GatewayConnection.sendFrame("PAGE_STATE", payload);
        }
        sendResponse({ received: true });
        break;
      }

      case "SECURITY_ALERT": {
        if (GatewayConnection.isConnected()) {
          GatewayConnection.sendFrame("SECURITY_ALERT", payload);
        }
        SessionManager.setState(ExtensionSessionState.BLOCKED);
        await CommandRouter.setControlState({
          active: true,
          status: "BLOCKED",
          action_text: `AI Agent • Blocked: ${payload.reason || payload.challenge_type}`,
          reason: payload.reason,
        });
        sendResponse({ received: true });
        break;
      }

      case "SUBMIT_PAIRING": {
        const result = await SessionManager.pairWithBackend(payload.code, payload.backend_url);
        if (result.success) {
          await GatewayConnection.connect();
        }
        sendResponse(result);
        break;
      }

      case "DISCONNECT_SESSION": {
        GatewayConnection.disconnect();
        await SessionManager.clearSessionData();
        await CommandRouter.setControlState({ active: false, status: "NORMAL" });
        sendResponse({ success: true });
        break;
      }

      case "RECONNECT_GATEWAY": {
        const session = await SessionManager.getSessionData();
        if (session) {
          await GatewayConnection.connect();
          sendResponse({ success: true, is_connected: GatewayConnection.isConnected() });
        } else {
          sendResponse({ success: false, error: "No active session to reconnect" });
        }
        break;
      }

      case "GET_EXTENSION_STATUS": {
        const sessionData = await SessionManager.getSessionData();
        const pending = await chrome.storage.local.get(STORAGE_KEYS.PENDING_ACTION);
        sendResponse({
          state: SessionManager.getState(),
          is_connected: GatewayConnection.isConnected(),
          session_data: sessionData,
          pending_action: pending[STORAGE_KEYS.PENDING_ACTION] || null,
        });
        break;
      }

      case "CONFIRM_OUTREACH_ACTION": {
        const pendingData = await chrome.storage.local.get(STORAGE_KEYS.PENDING_ACTION);
        const action = pendingData[STORAGE_KEYS.PENDING_ACTION];
        if (!action) {
          sendResponse({ success: false, error: "No pending action found" });
          return;
        }

        await chrome.storage.local.remove(STORAGE_KEYS.PENDING_ACTION);
        chrome.action.setBadgeText({ text: "" });

        if (payload.confirmed === true) {
          SessionManager.setState(ExtensionSessionState.RUNNING);
          GatewayConnection.sendFrame("RESULT", {
            command_id: action.command_id,
            success: true,
            status: CommandExecutionStatus.SUCCESS,
            result: {
              draft_id: action.draft_id,
              recipient: action.recipient,
              channel: action.channel,
              confirmed_by_user: true,
            },
            duration_ms: 0,
            timestamp: new Date().toISOString(),
          });
          sendResponse({ success: true, status: "SENT" });
        } else {
          SessionManager.setState(ExtensionSessionState.RUNNING);
          GatewayConnection.sendFrame("RESULT", {
            command_id: action.command_id,
            success: false,
            status: CommandExecutionStatus.CANCELLED,
            error: "User cancelled outreach in extension popup",
            duration_ms: 0,
            timestamp: new Date().toISOString(),
          });
          sendResponse({ success: true, status: "CANCELLED" });
        }
        break;
      }

      case "TRIGGER_OBSERVATION": {
        const [activeTab] = await chrome.tabs.query({ active: true, currentWindow: true });
        if (activeTab && activeTab.id) {
          chrome.tabs.sendMessage(activeTab.id, { command_type: "READ_PAGE" }, (response) => {
            if (!chrome.runtime.lastError && response?.success) {
              if (GatewayConnection.isConnected()) {
                GatewayConnection.sendFrame("OBSERVATION", response.result);
              }
              sendResponse({ success: true, observation: response.result });
            } else {
              sendResponse({ success: false, error: "Could not read page" });
            }
          });
        } else {
          sendResponse({ success: false, error: "No active tab" });
        }
        break;
      }

      default:
        sendResponse({ success: false, error: "Unknown message type" });
        break;
    }
  })();

  return true; // Keep async response open
});
