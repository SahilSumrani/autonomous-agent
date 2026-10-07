import { BrowserCommandType } from "../shared/types.js";
import { PageReader } from "./page_reader.js";
import { PageActions } from "./page_actions.js";
import { SafetyGuard } from "./safety_guard.js";
import { DomObserver } from "./dom_observer.js";

// Check safety when script initializes
function reportSafetyState() {
  const safety = SafetyGuard.inspectPageSafety();
  if (safety.isBlocked) {
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

  // Run safety check before any command
  const safety = SafetyGuard.inspectPageSafety();
  if (safety.isBlocked && command_type !== "CHECK_SAFETY") {
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
          const obs = PageReader.extractObservation();
          sendResponse({ success: true, result: obs });
          break;
        }

        case BrowserCommandType.EXTRACT_LINKS: {
          const obs = PageReader.extractObservation();
          sendResponse({ success: true, result: { links: obs.links } });
          break;
        }

        case BrowserCommandType.FIND_TEXT: {
          const query = (payload.query || "").toLowerCase();
          const bodyText = (document.body?.innerText || "").toLowerCase();
          const found = bodyText.includes(query);
          sendResponse({ success: true, result: { found, query } });
          break;
        }

        case BrowserCommandType.CLICK: {
          const clickRes = await PageActions.safeClick({
            selector: payload.selector,
            text: payload.text,
          });
          sendResponse({
            success: clickRes.success,
            status: clickRes.success ? "SUCCESS" : "FAILED",
            error: clickRes.error,
          });
          break;
        }

        case BrowserCommandType.SCROLL: {
          const scrollRes = PageActions.safeScroll(payload.direction || "down", payload.amount || 500);
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
