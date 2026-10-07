# Browser Security & Isolation Architecture

## Zero-Exfiltration Boundary
The TechVerse Chrome extension runs under an explicit zero-trust model regarding local browser data.

### Absolute Prohibitions
1. **No Cookie Scraping**: Manifest V3 explicitly omits the `cookies` permission. No cookies are read, extracted, or transmitted to the backend.
2. **No Credential Harvesting**: The extension never reads input fields marked as `password`, form authentication tokens, or localStorage authorization tokens.
3. **No Arbitrary Code Execution**: The backend communicates exclusively via typed JSON command definitions. No `eval()`, `new Function()`, or remote script injections are permitted in the content scripts.
4. **No CAPTCHA / Bot Bypass**: When Cloudflare, reCAPTCHA, Instagram challenge, or Reddit rate limits appear, the extension immediately shifts into `BLOCKED` or `WAITING_FOR_USER` status and stops.
5. **No Stealth Automation**: The extension does not randomize browser fingerprints, mask WebGL, spoof headers, or run evasive proxies.

## SSRF & Origin Policies
All navigation and page access requests are validated by `OriginPolicy` (extension side) and `validate_and_sanitize_target_url` (backend side):
- **Forbidden Hostnames**: `localhost`, `127.0.0.1`, `::1`
- **Forbidden IP Ranges**: `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`
- **Forbidden Cloud Metadata**: `169.254.169.254`
- **Forbidden Schemes**: `chrome://`, `chrome-extension://`, `file://`, `about:`, `data:`, `javascript:`
- Only valid public `http://` and `https://` URLs are permitted.

## Pairing & Short-Lived Tokens
- User generates a pairing challenge code (`TV-XXXX-XXXX`) from the authenticated dashboard.
- Pairing codes are single-use, cryptographically random, expire in 5 minutes, and are tied to a specific `organization_id`.
- The extension exchanges the code for a short-lived `tv_sess_*` token.
- No long-lived credentials or user passwords reside in extension storage.
- Revocation can be initiated immediately via `POST /api/v1/agent/browser/revoke`.

## Multi-Tenant Isolation
All browser sessions and command requests are strictly scoped by `organization_id`. An organization cannot inspect or send commands to browser sessions registered to a differing tenant.
