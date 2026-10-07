import { OriginPolicy } from "../security/origin_policy.js";
import {
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

export class CommandRouter {
  public static async executeCommand(command: BrowserCommand): Promise<void> {
    const startTime = performance.now();

    try {
      // 1. Session control commands
      if (command.type === BrowserCommandType.PAUSE) {
        SessionManager.setState(ExtensionSessionState.PAUSED);
        const result = createSuccessResult(command, { status: "PAUSED" }, performance.now() - startTime);
        GatewayConnection.sendFrame("RESULT", result);
        return;
      }

      if (command.type === BrowserCommandType.RESUME) {
        SessionManager.setState(ExtensionSessionState.RUNNING);
        const result = createSuccessResult(command, { status: "RUNNING" }, performance.now() - startTime);
        GatewayConnection.sendFrame("RESULT", result);
        return;
      }

      if (command.type === BrowserCommandType.STOP) {
        SessionManager.setState(ExtensionSessionState.STOPPED);
        const result = createSuccessResult(command, { status: "STOPPED" }, performance.now() - startTime);
        GatewayConnection.sendFrame("RESULT", result);
        return;
      }

      // 2. Navigation commands
      if (command.type === BrowserCommandType.OPEN_PAGE) {
        const targetUrl = command.payload.url;
        const safetyCheck = OriginPolicy.isSafeTargetUrl(targetUrl);
        if (!safetyCheck.safe) {
          const result = createFailureResult(
            command,
            safetyCheck.reason || "Blocked by origin policy",
            CommandExecutionStatus.BLOCKED,
            performance.now() - startTime
          );
          GatewayConnection.sendFrame("RESULT", result);
          return;
        }

        const [activeTab] = await chrome.tabs.query({ active: true, currentWindow: true });
        if (activeTab && activeTab.id) {
          await chrome.tabs.update(activeTab.id, { url: targetUrl });
        } else {
          await chrome.tabs.create({ url: targetUrl });
        }

        const result = createSuccessResult(command, { opened_url: targetUrl }, performance.now() - startTime);
        GatewayConnection.sendFrame("RESULT", result);
        return;
      }

      // 3. History navigation
      if (command.type === BrowserCommandType.NAVIGATE) {
        const direction = command.payload.direction || "reload";
        const [activeTab] = await chrome.tabs.query({ active: true, currentWindow: true });
        if (!activeTab || !activeTab.id) {
          const result = createFailureResult(command, "No active browser tab found", CommandExecutionStatus.FAILED);
          GatewayConnection.sendFrame("RESULT", result);
          return;
        }

        if (direction === "back") await chrome.tabs.goBack(activeTab.id);
        else if (direction === "forward") await chrome.tabs.goForward(activeTab.id);
        else await chrome.tabs.reload(activeTab.id);

        const result = createSuccessResult(command, { direction }, performance.now() - startTime);
        GatewayConnection.sendFrame("RESULT", result);
        return;
      }

      // 4. Outreach execution with human confirmation
      if (command.type === BrowserCommandType.EXECUTE_APPROVED_OUTREACH) {
        await this.handleOutreachExecution(command, startTime);
        return;
      }

      // 5. Content Script commands
      const [activeTab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!activeTab || !activeTab.id) {
        const result = createFailureResult(command, "No active tab found", CommandExecutionStatus.FAILED);
        GatewayConnection.sendFrame("RESULT", result);
        return;
      }

      chrome.tabs.sendMessage(
        activeTab.id,
        { command_type: command.type, payload: command.payload },
        (response) => {
          const duration = performance.now() - startTime;
          if (chrome.runtime.lastError) {
            const errorMsg = chrome.runtime.lastError.message || "Could not communicate with page content script";
            const failResult = createFailureResult(command, errorMsg, CommandExecutionStatus.FAILED, duration);
            GatewayConnection.sendFrame("RESULT", failResult);
            return;
          }

          if (response && response.success) {
            const successResult = createSuccessResult(command, response.result || response, duration);
            GatewayConnection.sendFrame("RESULT", successResult);
          } else {
            const status = response?.status === "BLOCKED" ? CommandExecutionStatus.BLOCKED : CommandExecutionStatus.FAILED;
            const failResult = createFailureResult(command, response?.error || "Content command failed", status, duration);
            GatewayConnection.sendFrame("RESULT", failResult);
          }
        }
      );
    } catch (err: any) {
      const duration = performance.now() - startTime;
      const failResult = createFailureResult(command, err.message || "Command routing error", CommandExecutionStatus.FAILED, duration);
      GatewayConnection.sendFrame("RESULT", failResult);
    }
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

    // Prompt user via extension badge
    chrome.action.setBadgeText({ text: "CONFIRM" });
    chrome.action.setBadgeBackgroundColor({ color: "#2563EB" });

    // In automated testing or immediate execution mode:
    // If confirmation flag is preset, confirm directly
    if (payload.auto_confirm === true) {
      await chrome.storage.local.remove(STORAGE_KEYS.PENDING_ACTION);
      chrome.action.setBadgeText({ text: "" });
      SessionManager.setState(ExtensionSessionState.RUNNING);

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
