export interface SafetyCheckResult {
  isBlocked: boolean;
  challengeType?: "CAPTCHA" | "SECURITY_CHECK" | "RATE_LIMIT" | "LOGIN_REQUIRED" | "PRIVATE_ACCOUNT";
  reason?: string;
}

export class SafetyGuard {
  /**
   * Detects if the current DOM presents a CAPTCHA, bot challenge, security wall, or rate limit.
   */
  public static inspectPageSafety(): SafetyCheckResult {
    const docText = (document.body?.innerText || "").slice(0, 5000).toLowerCase();

    // 1. CAPTCHA Elements
    const captchaElements = document.querySelectorAll(
      ".g-recaptcha, .h-captcha, #cf-turnstile, iframe[src*='captcha'], iframe[src*='recaptcha'], iframe[src*='turnstile']"
    );
    if (captchaElements.length > 0) {
      return {
        isBlocked: true,
        challengeType: "CAPTCHA",
        reason: "Active CAPTCHA challenge detected on page",
      };
    }

    // 2. Security Check strings
    if (
      docText.includes("verify you are human") ||
      docText.includes("security check") ||
      docText.includes("suspicious activity") ||
      docText.includes("unusual traffic from your computer network")
    ) {
      return {
        isBlocked: true,
        challengeType: "SECURITY_CHECK",
        reason: "Security check or automated traffic challenge presented",
      };
    }

    // 3. Rate Limit strings
    if (
      docText.includes("rate limit exceeded") ||
      docText.includes("too many requests") ||
      docText.includes("try again later") && docText.includes("limit")
    ) {
      return {
        isBlocked: true,
        challengeType: "RATE_LIMIT",
        reason: "Platform rate limit encountered",
      };
    }

    // 4. Private account on Instagram
    if (
      docText.includes("this account is private") &&
      (window.location.hostname.includes("instagram.com") || window.location.hostname.includes("threads.net"))
    ) {
      return {
        isBlocked: true,
        challengeType: "PRIVATE_ACCOUNT",
        reason: "Target profile is private and cannot be researched",
      };
    }

    return { isBlocked: false };
  }
}
