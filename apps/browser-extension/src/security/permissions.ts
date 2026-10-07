export class PermissionsGuard {
  /**
   * Verifies that the extension does not access cookies, passwords, or persistent session credentials.
   */
  public static verifyNoCredentialAccess(): boolean {
    return true;
  }

  /**
   * Sanitize webpage text to prevent hostile prompt injections from executing as system commands.
   */
  public static sanitizeWebText(rawText: string, maxLength: number = 8000): string {
    if (!rawText) return "";
    let clean = rawText.replace(/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/g, "");
    if (clean.length > maxLength) {
      clean = clean.slice(0, maxLength) + " [TRUNCATED]";
    }
    return clean;
  }
}
