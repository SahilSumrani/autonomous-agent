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

      if (host.includes("threads.net") || host.includes("threads.com")) {
        if (path.includes("/post/") || path.includes("/t/")) {
          return PageType.THREADS_POST;
        }
        if (path.startsWith("/@") || (path.length > 2 && !path.startsWith("/search") && !path.startsWith("/explore"))) {
          return PageType.THREADS_PROFILE;
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

  public static cleanSocialPostText(rawText: string, author?: string): string {
    if (!rawText) return "";
    let t = rawText.trim();
    if (author) {
      const h = author.replace(/^@/, "").trim();
      if (h) {
        const authorRegex = new RegExp(`^Follow\\s*${h}\\s*(?:\\d{1,2}/\\d{1,2}/\\d{2,4}|\\d+[mhdws]|yesterday|just now)?\\s*(?:More)?\\s*`, "i");
        t = t.replace(authorRegex, "");
      }
    }
    // Generic Follow prefix
    t = t.replace(/^Follow\s*[a-zA-Z0-9_\.]*?(?:(?:\d{1,2}\/\d{1,2}\/\d{2,4})|(?:\d+[mhdws])|yesterday|just now)\s*(?:More)?\s*/i, "");
    t = t.replace(/^Follow\s+[a-zA-Z0-9_\.]+\s*/i, "");
    t = t.replace(/^Follow\s*/i, "");

    // Inline system noise
    t = t.replace(/\b(Audio is muted|Audio unavailable|Log in to like|Log in)\b/gi, "");

    // Trailing action buttons: Like, Reply, Repost, Share with counts
    t = t.replace(/(?:\s*[1-9]\d{0,1}\/[1-9]\d{0,1}\s*)?(?:\s*(?:Like|Reply|Repost|Share)\s*\d*)+$/i, "");
    t = t.replace(/\s*[1-9]\d{0,1}\/[1-9]\d{0,1}$/, "");
    t = t.replace(/\s*More$/i, "");
    return t.trim();
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
    } else if (pageType === PageType.THREADS_PROFILE) {
      const pathParts = window.location.pathname.split("/").filter(Boolean);
      if (pathParts.length > 0 && pathParts[0].startsWith("@")) {
        recipientHandle = pathParts[0];
        profileUrl = window.location.href;
      }
    }

    // Extract individual content units (Threads, Reddit, social posts)
    const contentUnits: Array<{ author?: string; text: string; url?: string; links?: string[]; timestamp?: string }> = [];
    try {
      // 1. Articles and Threads cards
      const articles = document.querySelectorAll("article, [data-pressable-container], div[role='article'], div[data-testid*='post'], div[role='feed'] > div, [data-pressable-container='true']");
      articles.forEach((art) => {
        const rawText = (art.textContent || "").trim();
        if (rawText.length > 15) {
          // Author extraction from link or text header
          let author: string | undefined;
          const authorEl = art.querySelector("a[href*='/@'], a[href^='/@'], a[role='link'][href*='@']");
          if (authorEl) {
            const authorHref = authorEl.getAttribute("href") || "";
            const m = authorHref.match(/@([a-zA-Z0-9_\.]+)/);
            if (m) {
              author = `@${m[1]}`;
            } else {
              const cleanTxt = (authorEl.textContent || "").trim().replace(/^@/, "");
              if (cleanTxt && /^[a-zA-Z0-9_\.]+$/.test(cleanTxt)) {
                author = `@${cleanTxt}`;
              }
            }
          }

          // Timestamp extraction
          const timeEl = art.querySelector("time, [aria-label*='ago'], [aria-label*='hour'], [aria-label*='minute']");
          let timestamp = timeEl ? (timeEl.getAttribute("datetime") || timeEl.getAttribute("aria-label") || timeEl.textContent?.trim() || undefined) : undefined;
          if (!timestamp) {
            const timeMatch = rawText.match(/\b(\d+[mhdws]|yesterday|just now)\b/i);
            if (timeMatch) timestamp = timeMatch[1];
          }

          if (!author) {
            const headerMatch = rawText.match(/^([a-zA-Z0-9_\.]{3,30})(?:\s*>\s*[^0-9\n]+\s*)?(\d+[mhdws]|yesterday|just now)/i);
            if (headerMatch) {
              author = `@${headerMatch[1]}`;
              if (!timestamp) timestamp = headerMatch[2];
            }
          }

          const postLinkEl = art.querySelector("a[href*='/post/'], a[href*='/t/']");
          let postUrl: string | undefined;
          if (postLinkEl) {
            const rawHref = postLinkEl.getAttribute("href") || "";
            postUrl = rawHref.startsWith("http") ? rawHref : `${origin}${rawHref.startsWith("/") ? "" : "/"}${rawHref}`;
          }

          const artLinks: string[] = [];
          art.querySelectorAll("a[href]").forEach((l) => {
            const h = l.getAttribute("href");
            if (h && (h.startsWith("http://") || h.startsWith("https://"))) {
              artLinks.push(h);
            }
          });

          // Clean scraped UI artifacts (Follow, Like, Reply, Repost, Share, Audio notices)
          const text = this.cleanSocialPostText(rawText, author);
          if (text.length >= 15) {
            if (!contentUnits.some((c) => (postUrl && c.url === postUrl) || (author && c.author === author && c.text === text))) {
              contentUnits.push({
                author,
                text,
                url: postUrl,
                links: artLinks,
                timestamp,
              });
            }
          }
        }
      });

      // 2. Reddit posts (shreddit-post, Post containers, comments)
      const redditPosts = document.querySelectorAll("shreddit-post, [data-testid='post-container'], div.Post");
      redditPosts.forEach((postEl) => {
        const rawAuthor = postEl.getAttribute("author") ||
          postEl.querySelector("a[href*='/user/'], a[href*='/u/'], [data-testid='post_author_link']")?.textContent?.trim();
        let author: string | undefined;
        if (rawAuthor) {
          const cleanAuth = rawAuthor.replace(/^u\//, "").trim();
          author = `u/${cleanAuth}`;
        }

        const permalink = postEl.getAttribute("permalink") ||
          postEl.getAttribute("content-href") ||
          postEl.querySelector("a[href*='/comments/']")?.getAttribute("href");
        let postUrl: string | undefined;
        if (permalink) {
          postUrl = permalink.startsWith("http") ? permalink : `https://www.reddit.com${permalink.startsWith("/") ? "" : "/"}${permalink}`;
        }

        const titleText = postEl.getAttribute("post-title") ||
          postEl.querySelector("h1, h2, [slot='title'], a[data-click-id='body']")?.textContent?.trim() || "";
        const bodyText = postEl.querySelector("[slot='text-body'], div[data-click-id='text_body'], .RichTextJSON-root, p")?.textContent?.trim() || "";
        const fullText = `${titleText ? titleText + ". " : ""}${bodyText}`.trim() || (postEl.textContent || "").trim();

        if (fullText.length > 20) {
          const postLinks: string[] = [];
          postEl.querySelectorAll("a[href]").forEach((l) => {
            const h = l.getAttribute("href");
            if (h && (h.startsWith("http://") || h.startsWith("https://")) && !h.includes("reddit.com/r/")) {
              postLinks.push(h);
            }
          });

          // Only add if not already captured
          if (!contentUnits.some((c) => (postUrl && c.url === postUrl) || (author && c.author === author && c.text === fullText))) {
            contentUnits.push({
              author,
              text: fullText,
              url: postUrl,
              links: postLinks,
            });
          }
        }
      });

      // 3. Fallback: Parse visible text blocks directly for Threads feeds if structured DOM was minimized
      if (contentUnits.length === 0 && (url.includes("threads") || visibleText.includes("threads") || visibleText.length > 50)) {
        const threadRegex = /(?:^|\n)([a-zA-Z0-9_\.]{3,30})\s*(?:>\s*[^0-9\n]+\s*)?(\d+[mhdws]|yesterday|just now)\n+([\s\S]+?)(?=\n+[a-zA-Z0-9_\.]{3,30}(?:\s*>\s*[^0-9\n]+\s*)?\s+(?:\d+[mhdws]|yesterday|just now)|\Z)/gi;
        let match: RegExpExecArray | null;
        while ((match = threadRegex.exec(visibleText)) !== null) {
          const auth = `@${match[1]}`;
          const tstamp = match[2];
          const postBody = match[3].trim();
          if (postBody.length > 15) {
            contentUnits.push({
              author: auth,
              text: postBody,
              timestamp: tstamp,
              url: `${origin}/${auth}`,
            });
          }
        }
      }
    } catch {
      // DOM extraction failsafe
    }

    // Meta description
    const metaEl = document.querySelector("meta[name='description'], meta[property='og:description']");
    const metaDescription = metaEl ? metaEl.getAttribute("content") || undefined : undefined;

    let maxContainerHeight = 0;
    let maxContainerScrollY = 0;
    try {
      const scrollContainers = document.querySelectorAll<HTMLElement>("main, [role='main'], [role='feed'], div[style*='overflow']");
      scrollContainers.forEach((c) => {
        if (c.scrollHeight > maxContainerHeight) {
          maxContainerHeight = c.scrollHeight;
          maxContainerScrollY = c.scrollTop;
        }
      });
    } catch {}

    const docHeight = Math.max(
      document.documentElement ? document.documentElement.scrollHeight : 0,
      document.body ? document.body.scrollHeight : 0,
      maxContainerHeight
    );
    const scrollY = Math.max(window.scrollY || window.pageYOffset || 0, maxContainerScrollY);

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
      content_units: contentUnits.length > 0 ? contentUnits : undefined,
      document_height: docHeight,
      scroll_y: scrollY,
      timestamp: new Date().toISOString(),
    };
  }
}
