import { ObservationPayload, PageState, PageType } from "../shared/types.js";
import { EXTENSION_LIMITS } from "../shared/constants.js";
import { PermissionsGuard } from "../security/permissions.js";

export class PageReader {
  public static classifyPage(url: string): PageType {
    try {
      const parsed = new URL(url);
      const host = parsed.hostname.toLowerCase();
      const path = parsed.pathname.toLowerCase();

      if (host.includes("instagram.com")) {
        if (path.includes("/p/") || path.includes("/reel/")) {
          return PageType.INSTAGRAM_POST;
        }
        if (path.length > 2 && !path.startsWith("/explore") && !path.startsWith("/direct") && !path.startsWith("/stories")) {
          return PageType.INSTAGRAM_PROFILE;
        }
        return PageType.OTHER;
      }

      if (host.includes("reddit.com")) {
        if (path.includes("/comments/")) {
          return PageType.REDDIT_POST;
        }
        if (path.startsWith("/user/") || path.startsWith("/u/")) {
          return PageType.REDDIT_PROFILE;
        }
        return PageType.OTHER;
      }

      if (host.includes("google.com") || host.includes("bing.com") || host.includes("duckduckgo.com")) {
        return PageType.SEARCH_ENGINE;
      }

      return PageType.PUBLIC_WEBSITE;
    } catch {
      return PageType.OTHER;
    }
  }

  public static getPageState(): PageState {
    const url = window.location.href;
    const title = document.title || "";
    const origin = window.location.origin;
    const pageType = this.classifyPage(url);
    const interactiveElements = document.querySelectorAll("a, button, input, textarea, select");

    return {
      url,
      title,
      origin,
      page_type: pageType,
      is_loading: document.readyState !== "complete",
      visible_text_available: !!(document.body && document.body.innerText.trim().length > 0),
      interactive_elements_count: interactiveElements.length,
      timestamp: new Date().toISOString(),
    };
  }

  public static extractObservation(): ObservationPayload {
    const url = window.location.href;
    const title = document.title || "";
    const origin = window.location.origin;
    const pageType = this.classifyPage(url);

    // Visible text sanitized
    const rawText = document.body ? document.body.innerText : "";
    const visibleText = PermissionsGuard.sanitizeWebText(
      rawText,
      EXTENSION_LIMITS.MAX_VISIBLE_TEXT_LENGTH
    );

    // Headings
    const headingElements = document.querySelectorAll("h1, h2, h3");
    const headings: string[] = [];
    headingElements.forEach((el) => {
      const txt = (el.textContent || "").trim();
      if (txt && !headings.includes(txt) && headings.length < 10) {
        headings.push(txt);
      }
    });

    // Links
    const linkElements = document.querySelectorAll("a[href]");
    const links: string[] = [];
    linkElements.forEach((el) => {
      const href = el.getAttribute("href");
      if (href && (href.startsWith("http://") || href.startsWith("https://"))) {
        if (!links.includes(href) && links.length < EXTENSION_LIMITS.MAX_LINKS_TO_EXTRACT) {
          links.push(href);
        }
      }
    });

    // Handle extraction
    let recipientHandle: string | undefined;
    let profileUrl: string | undefined;

    if (pageType === PageType.INSTAGRAM_PROFILE) {
      const pathParts = window.location.pathname.split("/").filter(Boolean);
      if (pathParts.length > 0) {
        recipientHandle = `@${pathParts[0]}`;
        profileUrl = window.location.href;
      }
    } else if (pageType === PageType.REDDIT_PROFILE) {
      const pathParts = window.location.pathname.split("/").filter(Boolean);
      if (pathParts.length > 1) {
        recipientHandle = `u/${pathParts[1]}`;
        profileUrl = window.location.href;
      }
    }

    // Meta description
    const metaEl = document.querySelector("meta[name='description'], meta[property='og:description']");
    const metaDescription = metaEl ? metaEl.getAttribute("content") || undefined : undefined;

    return {
      url,
      title,
      origin,
      page_type: pageType,
      visible_text: visibleText,
      headings,
      links,
      recipient_handle: recipientHandle,
      profile_url: profileUrl,
      meta_description: metaDescription,
      timestamp: new Date().toISOString(),
    };
  }
}
