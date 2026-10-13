export class OriginPolicy {
  private static readonly BLOCKED_HOSTS = new Set([
    "localhost",
    "127.0.0.1",
    "::1",
    "0.0.0.0",
    "169.254.169.254",
  ]);

  private static readonly BLOCKED_PROTOCOLS = new Set([
    "chrome:",
    "chrome-extension:",
    "edge:",
    "file:",
    "about:",
    "data:",
    "blob:",
    "javascript:",
  ]);

  /**
   * Validate whether a target URL is safe for navigation by the browser agent.
   * Prohibits internal browser schemes and loopback/private hosts.
   */
  public static isSafeTargetUrl(rawUrl: string): { safe: boolean; reason?: string } {
    if (!rawUrl || typeof rawUrl !== "string") {
      return { safe: false, reason: "Empty or invalid URL" };
    }

    try {
      const parsed = new URL(rawUrl);

      if (this.BLOCKED_PROTOCOLS.has(parsed.protocol.toLowerCase())) {
        return { safe: false, reason: `Blocked protocol: ${parsed.protocol}` };
      }

      if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
        return { safe: false, reason: `Unsupported protocol: ${parsed.protocol}` };
      }

      if (parsed.username || parsed.password) {
        return { safe: false, reason: "Credentials in URL are prohibited" };
      }

      const hostname = parsed.hostname.toLowerCase();

      if (this.BLOCKED_HOSTS.has(hostname)) {
        return { safe: false, reason: `Prohibited local/loopback host: ${hostname}` };
      }

      // Check IPv4 private address ranges: 10.x.x.x, 192.168.x.x, 172.16-31.x.x
      if (this.isPrivateIpv4(hostname)) {
        return { safe: false, reason: `Private IPv4 address blocked: ${hostname}` };
      }

      return { safe: true };
    } catch {
      return { safe: false, reason: "Malformed URL syntax" };
    }
  }

  private static isPrivateIpv4(host: string): boolean {
    const parts = host.split(".").map(Number);
    if (parts.length !== 4 || parts.some((p) => isNaN(p) || p < 0 || p > 255)) {
      return false;
    }
    // 10.0.0.0/8
    if (parts[0] === 10) return true;
    // 172.16.0.0/12
    if (parts[0] === 172 && parts[1] >= 16 && parts[1] <= 31) return true;
    // 192.168.0.0/16
    if (parts[0] === 192 && parts[1] === 168) return true;
    // 169.254.0.0/16 (link-local / cloud metadata)
    if (parts[0] === 169 && parts[1] === 254) return true;
    return false;
  }
}
