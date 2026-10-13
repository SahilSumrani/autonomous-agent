import { BrowserCommandType } from "../shared/types.js";
import { STORAGE_KEYS } from "../shared/constants.js";
import { PageReader } from "./page_reader.js";
import { PageActions } from "./page_actions.js";
import { SafetyGuard } from "./safety_guard.js";
import { DomObserver } from "./dom_observer.js";
import { AgentOverlay } from "./agent_overlay.js";

// Initialize AI Browser Control Overlay
AgentOverlay.init();

// Listen for cross-session agent control state changes
chrome.storage.onChanged.addListener((changes, areaName) => {
  if (areaName === "local" && changes[STORAGE_KEYS.AGENT_CONTROL_STATE]) {
    const newState = changes[STORAGE_KEYS.AGENT_CONTROL_STATE].newValue;
    if (newState) {
      AgentOverlay.updateState(newState);
    } else {
      AgentOverlay.hide();
    }
  }
});

// Check safety when script initializes
function reportSafetyState() {
  const safety = SafetyGuard.inspectPageSafety();
  if (safety.isBlocked) {
    AgentOverlay.updateState({
      active: true,
      status: "BLOCKED",
      action_text: `AI Agent • Blocked: ${safety.reason}`,
      reason: safety.reason,
    });

    chrome.runtime.sendMessage({
      type: "SECURITY_ALERT",
      payload: {
        url: window.location.href,
        challenge_type: safety.challengeType,
        reason: safety.reason,
      },
    });
  }
}

// Watch navigation changes
DomObserver.startObserving((newUrl) => {
  reportSafetyState();
  AgentOverlay.loadStateFromStorage();
  const pageState = PageReader.getPageState();
  chrome.runtime.sendMessage({
    type: "PAGE_STATE_CHANGED",
    payload: pageState,
  });
});

// Run initial check
reportSafetyState();

// Message listener from background worker
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  const { command_type, payload } = request;

  // Handle overlay state updates directly
  if (command_type === "SET_OVERLAY_STATE") {
    AgentOverlay.updateState(payload || {});
    sendResponse({ success: true });
    return false;
  }

  // Run safety check before any command
  const safety = SafetyGuard.inspectPageSafety();
  if (safety.isBlocked && command_type !== "CHECK_SAFETY") {
    AgentOverlay.updateState({
      active: true,
      status: "BLOCKED",
      action_text: `AI Agent • Blocked: ${safety.reason}`,
      reason: safety.reason,
    });

    sendResponse({
      success: false,
      status: "BLOCKED",
      error: `Action blocked: ${safety.reason}`,
      challenge_type: safety.challengeType,
    });
    return true;
  }

  (async () => {
    try {
      switch (command_type) {
        case BrowserCommandType.GET_PAGE_STATE: {
          const state = PageReader.getPageState();
          sendResponse({ success: true, result: state });
          break;
        }

        case BrowserCommandType.READ_PAGE:
        case BrowserCommandType.EXTRACT_VISIBLE_CONTENT: {
          AgentOverlay.updateState({
            active: true,
            status: "RUNNING",
            action_text: "AI Agent • Reading page",
          });
          const obs = PageReader.extractObservation();
          sendResponse({ success: true, result: obs });
          break;
        }

        case BrowserCommandType.EXTRACT_LINKS: {
          AgentOverlay.updateState({
            active: true,
            status: "RUNNING",
            action_text: "AI Agent • Extracting links",
          });
          const obs = PageReader.extractObservation();
          sendResponse({ success: true, result: { links: obs.links } });
          break;
        }

        case BrowserCommandType.FIND_TEXT: {
          AgentOverlay.updateState({
            active: true,
            status: "RUNNING",
            action_text: "AI Agent • Researching",
          });
          const query = (payload.query || "").toLowerCase();
          const bodyText = (document.body?.innerText || "").toLowerCase();
          const found = bodyText.includes(query);
          sendResponse({ success: true, result: { found, query } });
          break;
        }

        case BrowserCommandType.CLICK: {
          AgentOverlay.updateState({
            active: true,
            status: "RUNNING",
            action_text: "AI Agent • Interacting",
          });
          const clickSelector = payload.selector || (payload.target?.selector_type === "selector" ? payload.target.value : undefined);
          const clickText = payload.text || (payload.target?.selector_type === "text" ? payload.target.value : undefined);
          const clickRes = await PageActions.safeClick({
            selector: clickSelector,
            text: clickText,
          });
          sendResponse({
            success: clickRes.success,
            status: clickRes.success ? "SUCCESS" : "FAILED",
            error: clickRes.error,
          });
          break;
        }

        case BrowserCommandType.TYPE_TEXT: {
          AgentOverlay.updateState({
            active: true,
            status: "RUNNING",
            action_text: "AI Agent • Entering search query",
          });
          const typeRes = await PageActions.safeTypeText({
            selector: payload.selector,
            text: payload.text || "",
            clearFirst: payload.clear_first !== false,
          });
          sendResponse({
            success: typeRes.success,
            status: typeRes.success ? "SUCCESS" : "FAILED",
            result: typeRes,
            error: typeRes.error,
          });
          break;
        }

        case BrowserCommandType.PRESS_KEY: {
          AgentOverlay.updateState({
            active: true,
            status: "RUNNING",
            action_text: "AI Agent • Submitting search",
          });
          const keyRes = await PageActions.safePressKey({
            key: payload.key || "Enter",
            selector: payload.selector,
          });
          sendResponse({
            success: keyRes.success,
            status: keyRes.success ? "SUCCESS" : "FAILED",
            result: keyRes,
            error: keyRes.error,
          });
          break;
        }

        case BrowserCommandType.FIND_SEARCH_INPUT: {
          const discoveryRes = PageActions.findSearchInput();
          sendResponse({
            success: true,
            result: discoveryRes,
          });
          break;
        }

        case BrowserCommandType.SCROLL: {
          AgentOverlay.updateState({
            active: true,
            status: "RUNNING",
            action_text: "AI Agent • Scrolling",
          });
          const scrollDistance = payload.amount || payload.distance || 500;
          const scrollRes = PageActions.safeScroll(payload.direction || "down", scrollDistance);
          sendResponse({ success: true, result: scrollRes });
          break;
        }

        case "CHECK_SAFETY": {
          sendResponse({ success: true, result: safety });
          break;
        }

        default: {
          sendResponse({ success: false, error: `Unhandled content command: ${command_type}` });
          break;
        }
      }
    } catch (err: any) {
      sendResponse({ success: false, error: err.message || "Content script execution error" });
    }
  })();

  return true; // Keep channel open for async response
});
