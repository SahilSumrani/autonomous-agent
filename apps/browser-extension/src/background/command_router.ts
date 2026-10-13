import { OriginPolicy } from "../security/origin_policy.js";
import {
  AgentControlState,
  BrowserCommand,
  BrowserCommandResult,
  BrowserCommandType,
  CommandExecutionStatus,
  ExtensionSessionState,
} from "../shared/types.js";
import { createFailureResult, createSuccessResult } from "../shared/protocol.js";
import { STORAGE_KEYS } from "../shared/constants.js";
import { GatewayConnection } from "./connection.js";
import { SessionManager } from "./session_manager.js";

export interface AgentJobLock {
  sessionId: string;
  jobId?: string;
  lockedAt: number;
}

export class CommandRouter {
  private static dedicatedAgentTabId: number | null = null;
  private static activeJobLock: AgentJobLock | null = null;

  public static getDedicatedTabId(): number | null {
    return this.dedicatedAgentTabId;
  }

  public static setDedicatedTabId(tabId: number | null): void {
    this.dedicatedAgentTabId = tabId;
    if (tabId) {
      chrome.storage.local.set({ [STORAGE_KEYS.DEDICATED_AGENT_TAB_ID]: tabId }).catch(() => {});
    } else {
      chrome.storage.local.remove(STORAGE_KEYS.DEDICATED_AGENT_TAB_ID).catch(() => {});
    }
  }

  public static getActiveJobLock(): AgentJobLock | null {
    return this.activeJobLock;
  }

  public static releaseJobLock(): void {
    this.activeJobLock = null;
  }

  /**
   * Dedicated agent target tab resolver.
   * NEVER falls back to user's active or existing personal tabs.
   */
  public static async resolveTargetTab(requestedTabId?: number): Promise<chrome.tabs.Tab | undefined> {
    if (requestedTabId) {
      try {
        const tab = await chrome.tabs.get(requestedTabId);
        if (tab && tab.id) {
          this.setDedicatedTabId(tab.id);
          return tab;
        }
      } catch {}
    }

    if (!this.dedicatedAgentTabId) {
      try {
        const stored = await chrome.storage.local.get(STORAGE_KEYS.DEDICATED_AGENT_TAB_ID);
        const storedId = stored[STORAGE_KEYS.DEDICATED_AGENT_TAB_ID];
        if (storedId && typeof storedId === "number") {
          this.dedicatedAgentTabId = storedId;
        }
      } catch {}
    }

    if (this.dedicatedAgentTabId) {
      try {
        const tab = await chrome.tabs.get(this.dedicatedAgentTabId);
        if (tab && tab.id) {
          return tab;
        }
      } catch {
        this.setDedicatedTabId(null);
      }
    }

    // Do NOT hijack user's active or open personal tabs
    return undefined;
  }

  /**
   * Check and acquire or renew per-session/job lock.
   */
  public static checkJobLock(sessionId: string, jobId?: string): { allowed: boolean; reason?: string } {
    const now = Date.now();
    const LOCK_TIMEOUT_MS = 15 * 60 * 1000; // 15 mins expiry for orphan jobs

    if (this.activeJobLock) {
      const isExpired = now - this.activeJobLock.lockedAt > LOCK_TIMEOUT_MS;
      const isSameSession = this.activeJobLock.sessionId === sessionId;
      const isSameJob = !this.activeJobLock.jobId || !jobId || this.activeJobLock.jobId === jobId;

      if (!isExpired && (!isSameSession || !isSameJob)) {
        return {
          allowed: false,
          reason: `Browser extension session is locked to active job (${this.activeJobLock.jobId || this.activeJobLock.sessionId}). Concurrent jobs cannot control the browser.`,
        };
      }
    }

    // Acquire or refresh lock
    this.activeJobLock = {
      sessionId,
      jobId,
      lockedAt: now,
    };
    return { allowed: true };
  }

  /**
   * Broadcast and persist real-time AI Agent Control visual state
   */
  public static async setControlState(state: Partial<AgentControlState>, tabId?: number): Promise<void> {
    const fullState: AgentControlState = {
      active: state.active ?? true,
      status: state.status ?? "RUNNING",
      action_text: state.action_text ?? "AI Agent • Active",
      reason: state.reason,
      updated_at: Date.now(),
    };

    // 1. Persist to storage so any newly loaded or reloaded tab picks it up immediately
    await chrome.storage.local.set({
      [STORAGE_KEYS.AGENT_CONTROL_STATE]: fullState,
    });

    // 2. Proactively dispatch direct message to target tab or dedicated agent tab
    try {
      const targetId = tabId || this.dedicatedAgentTabId;
      if (targetId) {
        chrome.tabs.sendMessage(targetId, { command_type: "SET_OVERLAY_STATE", payload: fullState }, () => {
          if (chrome.runtime.lastError) {
            // Tab may not have injected content script yet
          }
        });
      }
    } catch {
      // Ignore delivery errors
    }
  }

  public static async executeCommand(command: BrowserCommand): Promise<void> {
    const startTime = performance.now();

    try {
      // 1. Session control commands
      if (command.type === BrowserCommandType.PAUSE) {
        SessionManager.setState(ExtensionSessionState.PAUSED);
        await this.setControlState({
          active: true,
          status: "PAUSED",
          action_text: "AI Agent • Paused",
        });
        const result = createSuccessResult(command, { status: "PAUSED" }, performance.now() - startTime);
        GatewayConnection.sendFrame("RESULT", result);
        return;
      }

      if (command.type === BrowserCommandType.RESUME) {
        SessionManager.setState(ExtensionSessionState.RUNNING);
        await this.setControlState({
          active: true,
          status: "RUNNING",
          action_text: "AI Agent • Resuming",
        });
        const result = createSuccessResult(command, { status: "RUNNING" }, performance.now() - startTime);
        GatewayConnection.sendFrame("RESULT", result);
        return;
      }

      if (command.type === BrowserCommandType.STOP) {
        this.releaseJobLock();
        SessionManager.setState(ExtensionSessionState.STOPPED);
        await this.setControlState({
          active: false,
          status: "COMPLETED",
          action_text: "AI Agent • Task Completed",
        });
        const result = createSuccessResult(command, { status: "STOPPED" }, performance.now() - startTime);
        GatewayConnection.sendFrame("RESULT", result);
        return;
      }

      // Check per-session/job lock to prevent concurrent jobs from stomping
      const incomingJobId = command.payload?.job_id;
      const lockCheck = this.checkJobLock(command.session_id, incomingJobId);
      if (!lockCheck.allowed) {
        const result = createFailureResult(
          command,
          lockCheck.reason || "Browser locked to another active job",
          CommandExecutionStatus.BLOCKED,
          performance.now() - startTime
        );
        GatewayConnection.sendFrame("RESULT", result);
        return;
      }

      // 2. Navigation commands: NAVIGATE and OPEN_PAGE
      const isNavigateCmd = command.type === BrowserCommandType.NAVIGATE;
      const isOpenPageCmd = command.type === BrowserCommandType.OPEN_PAGE;
      const targetUrl = command.payload.target_url || command.payload.url;

      if ((isNavigateCmd || isOpenPageCmd) && targetUrl) {
        // Validate URL security and SSRF rules
        const safetyCheck = OriginPolicy.isSafeTargetUrl(targetUrl);
        if (!safetyCheck.safe) {
          await this.setControlState({
            active: true,
            status: "BLOCKED",
            action_text: `AI Agent • Blocked: ${safetyCheck.reason}`,
            reason: safetyCheck.reason,
          });
          const result = createFailureResult(
            command,
            safetyCheck.reason || "Blocked by origin policy",
            CommandExecutionStatus.BLOCKED,
            performance.now() - startTime
          );
          GatewayConnection.sendFrame("RESULT", result);
          return;
        }

        // Dedicated Tab Isolation:
        // NEVER navigate a user's normal tab. Only navigate the dedicated agent tab,
        // or create a new dedicated agent tab if one doesn't exist yet.
        const existingAgentTab = await this.resolveTargetTab(command.payload.tab_id);
        let targetTabId = existingAgentTab?.id;

        if (targetTabId) {
          // Dedicated tab already exists: navigate it
          this.setDedicatedTabId(targetTabId);
          await this.setControlState(
            {
              active: true,
              status: "RUNNING",
              action_text: "AI Agent • Navigating",
            },
            targetTabId
          );
          const loadPromise = this.waitForTabComplete(targetTabId, 15000, targetUrl);
          await chrome.tabs.update(targetTabId, { url: targetUrl });
          await loadPromise;
        } else {
          // Open a new dedicated agent tab
          const createdTab = await chrome.tabs.create({ url: targetUrl, active: true });
          targetTabId = createdTab.id;
          this.setDedicatedTabId(targetTabId || null);
          if (targetTabId) {
            await this.setControlState(
              {
                active: true,
                status: "RUNNING",
                action_text: "AI Agent • Navigating",
              },
              targetTabId
            );
            await this.waitForTabComplete(targetTabId, 15000, targetUrl);
          }
        }

        // Settle delay for content script initialization
        await new Promise((r) => setTimeout(r, 400));

        // Update status for inspection/reading
        await this.setControlState(
          {
            active: true,
            status: "RUNNING",
            action_text: "AI Agent • Reading page",
          },
          targetTabId
        );

        const duration = performance.now() - startTime;
        const result = createSuccessResult(
          command,
          {
            opened_url: targetUrl,
            target_url: targetUrl,
            tab_id: targetTabId,
            status: "complete",
          },
          duration
        );
        GatewayConnection.sendFrame("RESULT", result);
        return;
      }

      // History navigation (direction: back / forward / reload)
      if (isNavigateCmd && !targetUrl && command.payload.direction) {
        const direction = command.payload.direction;
        const activeTab = await this.resolveTargetTab(command.payload.tab_id);
        if (!activeTab || !activeTab.id) {
          const result = createFailureResult(command, "No active browser tab found", CommandExecutionStatus.FAILED);
          GatewayConnection.sendFrame("RESULT", result);
          return;
        }

        await this.setControlState({
          active: true,
          status: "RUNNING",
          action_text: `AI Agent • Navigating (${direction})`,
        }, activeTab.id);

        if (direction === "back") await chrome.tabs.goBack(activeTab.id);
        else if (direction === "forward") await chrome.tabs.goForward(activeTab.id);
        else await chrome.tabs.reload(activeTab.id);

        const result = createSuccessResult(command, { direction }, performance.now() - startTime);
        GatewayConnection.sendFrame("RESULT", result);
        return;
      }

      // 3. Outreach execution with human confirmation
      if (command.type === BrowserCommandType.EXECUTE_APPROVED_OUTREACH) {
        await this.handleOutreachExecution(command, startTime);
        return;
      }

      // 4. Content Script commands (READ_PAGE, SCROLL, CLICK, FIND_TEXT, etc.)
      const targetTab = await this.resolveTargetTab(command.payload.tab_id);
      if (!targetTab || !targetTab.id) {
        const result = createFailureResult(command, "No active browser tab found", CommandExecutionStatus.FAILED);
        GatewayConnection.sendFrame("RESULT", result);
        return;
      }
      const activeTabId = targetTab.id;
      this.setDedicatedTabId(activeTabId);

      // Update control overlay action text according to active command
      let actionText = "AI Agent • Working";
      if (command.type === BrowserCommandType.READ_PAGE || command.type === BrowserCommandType.EXTRACT_VISIBLE_CONTENT) {
        actionText = "AI Agent • Reading page";
      } else if (command.type === BrowserCommandType.SCROLL) {
        actionText = "AI Agent • Scrolling";
      } else if (command.type === BrowserCommandType.CLICK) {
        actionText = "AI Agent • Interacting";
      } else if (command.type === BrowserCommandType.TYPE_TEXT) {
        actionText = "AI Agent • Typing query";
      } else if (command.type === BrowserCommandType.PRESS_KEY) {
        actionText = "AI Agent • Submitting";
      } else if (command.type === BrowserCommandType.FIND_TEXT || command.type === BrowserCommandType.FIND_SEARCH_INPUT) {
        actionText = "AI Agent • Searching";
      }

      await this.setControlState(
        {
          active: true,
          status: "RUNNING",
          action_text: actionText,
        },
        activeTabId
      );

      const sendToContentScriptWithRetry = (retriesLeft = 5, delayMs = 350): void => {
        chrome.tabs.sendMessage(
          activeTabId,
          { command_type: command.type, payload: command.payload },
          async (response) => {
            const duration = performance.now() - startTime;
            if (chrome.runtime.lastError) {
              const errorMsg = chrome.runtime.lastError.message || "Could not communicate with page content script";
              if (
                retriesLeft > 0 &&
                (errorMsg.includes("Receiving end does not exist") ||
                  errorMsg.includes("Could not establish connection") ||
                  errorMsg.includes("Extension context invalidated"))
              ) {
                setTimeout(() => sendToContentScriptWithRetry(retriesLeft - 1, Math.round(delayMs * 1.5)), delayMs);
                return;
              }
              const failResult = createFailureResult(command, errorMsg, CommandExecutionStatus.FAILED, duration);
              GatewayConnection.sendFrame("RESULT", failResult);
              return;
            }

            if (response && response.success) {
              const successResult = createSuccessResult(command, response.result || response, duration);
              GatewayConnection.sendFrame("RESULT", successResult);
            } else {
              const status = response?.status === "BLOCKED" ? CommandExecutionStatus.BLOCKED : CommandExecutionStatus.FAILED;
              if (status === CommandExecutionStatus.BLOCKED) {
                await this.setControlState(
                  {
                    active: true,
                    status: "BLOCKED",
                    action_text: `AI Agent • Blocked: ${response?.error || "Security barrier"}`,
                    reason: response?.error || "Security barrier",
                  },
                  activeTabId
                );
              }
              const failResult = createFailureResult(command, response?.error || "Content command failed", status, duration);
              GatewayConnection.sendFrame("RESULT", failResult);
            }
          }
        );
      };

      sendToContentScriptWithRetry(5, 350);
    } catch (err: any) {
      const duration = performance.now() - startTime;
      const failResult = createFailureResult(command, err.message || "Command routing error", CommandExecutionStatus.FAILED, duration);
      GatewayConnection.sendFrame("RESULT", failResult);
    }
  }

  /**
   * Helper to wait for a tab to finish loading the expected URL
   */
  private static waitForTabComplete(tabId: number, timeoutMs: number, expectedUrl?: string): Promise<void> {
    return new Promise((resolve) => {
      let settled = false;
      const timer = setTimeout(() => {
        if (!settled) {
          settled = true;
          chrome.tabs.onUpdated.removeListener(listener);
          resolve();
        }
      }, timeoutMs);

      function isUrlMatch(currentUrl?: string): boolean {
        if (!expectedUrl || !currentUrl) return true;
        try {
          const expected = new URL(expectedUrl);
          const current = new URL(currentUrl);
          return expected.origin === current.origin && current.pathname.startsWith(expected.pathname);
        } catch {
          return currentUrl.includes(expectedUrl) || expectedUrl.includes(currentUrl);
        }
      }

      function listener(updatedId: number, changeInfo: chrome.tabs.TabChangeInfo, tab: chrome.tabs.Tab) {
        if (updatedId === tabId && changeInfo.status === "complete") {
          if (!expectedUrl || isUrlMatch(tab.url)) {
            if (!settled) {
              settled = true;
              clearTimeout(timer);
              chrome.tabs.onUpdated.removeListener(listener);
              setTimeout(resolve, 400);
            }
          }
        }
      }

      chrome.tabs.onUpdated.addListener(listener);

      // Check current state only if URL already matches the expected target URL
      chrome.tabs.get(tabId).then((tab) => {
        if (!settled && tab && tab.status === "complete" && isUrlMatch(tab.url)) {
          setTimeout(() => {
            if (!settled) {
              settled = true;
              clearTimeout(timer);
              chrome.tabs.onUpdated.removeListener(listener);
              resolve();
            }
          }, 400);
        }
      }).catch(() => {});
    });
  }

  private static async handleOutreachExecution(command: BrowserCommand, startTime: number): Promise<void> {
    const payload = command.payload;
    const [activeTab] = await chrome.tabs.query({ active: true, currentWindow: true });

    // Store pending outreach action for popup confirmation
    await chrome.storage.local.set({
      [STORAGE_KEYS.PENDING_ACTION]: {
        command_id: command.command_id,
        draft_id: payload.draft_id,
        channel: payload.channel,
        recipient: payload.recipient,
        subject: payload.subject,
        body: payload.body,
        cta_text: payload.cta_text,
        approval_id: payload.approval_id,
        received_at: new Date().toISOString(),
      },
    });

    SessionManager.setState(ExtensionSessionState.WAITING_FOR_APPROVAL);
    await this.setControlState(
      {
        active: true,
        status: "WAITING_FOR_APPROVAL",
        action_text: "AI Agent • Waiting for approval",
      },
      activeTab?.id
    );

    // Prompt user via extension badge
    chrome.action.setBadgeText({ text: "CONFIRM" });
    chrome.action.setBadgeBackgroundColor({ color: "#2563EB" });

    // In automated testing or immediate execution mode:
    if (payload.auto_confirm === true) {
      await chrome.storage.local.remove(STORAGE_KEYS.PENDING_ACTION);
      chrome.action.setBadgeText({ text: "" });
      SessionManager.setState(ExtensionSessionState.RUNNING);
      await this.setControlState(
        {
          active: true,
          status: "RUNNING",
          action_text: "AI Agent • Outreach Approved",
        },
        activeTab?.id
      );

      const successResult = createSuccessResult(
        command,
        {
          draft_id: payload.draft_id,
          recipient: payload.recipient,
          channel: payload.channel,
          executed: true,
        },
        performance.now() - startTime
      );
      GatewayConnection.sendFrame("RESULT", successResult);
    }
  }
}
