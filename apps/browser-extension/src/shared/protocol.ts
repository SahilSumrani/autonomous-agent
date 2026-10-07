import {
  BrowserCommand,
  BrowserCommandResult,
  CommandExecutionStatus,
  ExtensionSessionState,
  ObservationPayload,
  PageState,
} from "./types.js";

export function createSuccessResult(
  command: BrowserCommand,
  result: Record<string, any> = {},
  durationMs: number = 0
): BrowserCommandResult {
  return {
    command_id: command.command_id,
    session_id: command.session_id,
    success: true,
    status: CommandExecutionStatus.SUCCESS,
    result,
    duration_ms: durationMs,
    timestamp: new Date().toISOString(),
    correlation_id: command.correlation_id,
  };
}

export function createFailureResult(
  command: BrowserCommand,
  error: string,
  status: CommandExecutionStatus = CommandExecutionStatus.FAILED,
  durationMs: number = 0
): BrowserCommandResult {
  return {
    command_id: command.command_id,
    session_id: command.session_id,
    success: false,
    status,
    result: {},
    error,
    duration_ms: durationMs,
    timestamp: new Date().toISOString(),
    correlation_id: command.correlation_id,
  };
}

export function encodeMessageFrame(frameType: string, payload: any): string {
  return JSON.stringify({
    frame_type: frameType,
    payload,
  });
}
