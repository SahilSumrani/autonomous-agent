import { EXTENSION_LIMITS } from "../shared/constants.js";

export interface ClickTargetSpec {
  selector?: string;
  text?: string;
}

export interface TypeTargetSpec {
  selector?: string;
  text: string;
  clearFirst?: boolean;
}

export interface KeyPressSpec {
  key: string;
  selector?: string;
}

export interface SearchInputDiscoveryResult {
  found: boolean;
  selector?: string;
  placeholder?: string;
  input_type?: string;
  name?: string;
}

export class PageActions {
  private static cursorElement: HTMLElement | null = null;

  /**
   * Render or animate a visible virtual cursor dot on the page to indicate
   * real-time agent intent and point of interaction.
   */
  public static showVirtualCursor(x: number, y: number, actionName: string = "agent-click"): void {
    try {
      if (!this.cursorElement) {
        const cursor = document.createElement("div");
        cursor.id = "techverse-agent-cursor";
        cursor.style.position = "fixed";
        cursor.style.width = "20px";
        cursor.style.height = "20px";
        cursor.style.borderRadius = "50%";
        cursor.style.background = "radial-gradient(circle, #38bdf8 0%, #2563eb 70%)";
        cursor.style.border = "2px solid #ffffff";
        cursor.style.boxShadow = "0 0 12px rgba(56, 189, 248, 0.9)";
        cursor.style.pointerEvents = "none";
        cursor.style.zIndex = "2147483647";
        cursor.style.transition = "transform 0.25s cubic-bezier(0.2, 0.8, 0.2, 1), opacity 0.3s ease";
        cursor.style.transform = `translate3d(${x - 10}px, ${y - 10}px, 0)`;
        document.body.appendChild(cursor);
        this.cursorElement = cursor;
      } else {
        this.cursorElement.style.opacity = "1";
        this.cursorElement.style.transform = `translate3d(${x - 10}px, ${y - 10}px, 0)`;
      }

      // Add click ripple animation
      const ripple = document.createElement("div");
      ripple.style.position = "fixed";
      ripple.style.left = `${x - 15}px`;
      ripple.style.top = `${y - 15}px`;
      ripple.style.width = "30px";
      ripple.style.height = "30px";
      ripple.style.borderRadius = "50%";
      ripple.style.border = "2px solid #60a5fa";
      ripple.style.pointerEvents = "none";
      ripple.style.zIndex = "2147483646";
      ripple.style.animation = "techverse-ripple 0.6s ease-out forwards";
      document.body.appendChild(ripple);

      // Add keyframes if not present
      if (!document.getElementById("techverse-cursor-styles")) {
        const style = document.createElement("style");
        style.id = "techverse-cursor-styles";
        style.textContent = `
          @keyframes techverse-ripple {
            0% { transform: scale(0.5); opacity: 1; }
            100% { transform: scale(2.2); opacity: 0; }
          }
        `;
        document.head.appendChild(style);
      }

      setTimeout(() => {
        try {
          ripple.remove();
        } catch {}
      }, 700);

      // Fade cursor slightly after idle
      setTimeout(() => {
        if (this.cursorElement) {
          this.cursorElement.style.opacity = "0.7";
        }
      }, 1500);
    } catch {}
  }

  /**
   * Locate the primary search input on current page using standard heuristics.
   */
  public static findSearchInput(): SearchInputDiscoveryResult {
    const searchSelectors = [
      'input[type="search"]',
      'input[name="q"]',
      'input[name="query"]',
      'input[name="search"]',
      'input[name="search_query"]',
      'input[placeholder*="search" i]',
      'input[placeholder*="find" i]',
      'input[aria-label*="search" i]',
      'textarea[placeholder*="search" i]',
      '[role="searchbox"]',
      '[role="search"] input[type="text"]',
      'form[action*="search" i] input[type="text"]',
      'form input[type="text"]',
    ];

    for (const sel of searchSelectors) {
      try {
        const elements = document.querySelectorAll<HTMLInputElement | HTMLTextAreaElement>(sel);
        for (const el of Array.from(elements)) {
          const rect = el.getBoundingClientRect();
          const style = window.getComputedStyle(el);
          const isVisible =
            style.display !== "none" &&
            style.visibility !== "hidden" &&
            style.opacity !== "0" &&
            rect.width > 20 &&
            rect.height > 15;

          const isEnabled = !el.disabled && !el.readOnly;

          if (isVisible && isEnabled) {
            return {
              found: true,
              selector: sel,
              placeholder: el.placeholder || undefined,
              input_type: el.type,
              name: el.name || undefined,
            };
          }
        }
      } catch {}
    }

    return { found: false };
  }

  /**
   * Safely clicks a target element based on structured selector or visible text.
   */
  public static async safeClick(spec: ClickTargetSpec): Promise<{ success: boolean; error?: string }> {
    let targetEl: HTMLElement | null = null;

    if (spec.selector) {
      try {
        targetEl = document.querySelector(spec.selector);
      } catch (e: any) {
        return { success: false, error: `Invalid CSS selector: ${spec.selector}` };
      }
    } else if (spec.text) {
      const targetText = spec.text.trim().toLowerCase();
      const candidates = document.querySelectorAll<HTMLElement>("a, button, span, [role='button'], input[type='submit']");
      for (const el of Array.from(candidates)) {
        const textContent = (el.innerText || el.textContent || "").trim().toLowerCase();
        if (textContent === targetText || (textContent.includes(targetText) && textContent.length < 50)) {
          targetEl = el;
          break;
        }
      }
    }

    if (!targetEl) {
      return { success: false, error: "Target element not found on page" };
    }

    const rect = targetEl.getBoundingClientRect();
    const style = window.getComputedStyle(targetEl);

    if (style.display === "none" || style.visibility === "hidden" || style.opacity === "0") {
      return { success: false, error: "Target element is hidden from view" };
    }

    targetEl.scrollIntoView({ behavior: "smooth", block: "center" });

    // Show visible cursor movement to target center
    const freshRect = targetEl.getBoundingClientRect();
    this.showVirtualCursor(freshRect.left + freshRect.width / 2, freshRect.top + freshRect.height / 2, "click");

    const originalOutline = targetEl.style.outline;
    targetEl.style.outline = "2px solid #2563EB";
    setTimeout(() => {
      if (targetEl) targetEl.style.outline = originalOutline;
    }, 600);

    try {
      targetEl.click();
      return { success: true };
    } catch (err: any) {
      return { success: false, error: `Click execution failed: ${err.message}` };
    }
  }

  /**
   * Safely types text into a discovered or designated search/form input.
   * Dispatches synthetic events so modern reactive UI frameworks detect the change.
   */
  public static async safeTypeText(spec: TypeTargetSpec): Promise<{ success: boolean; error?: string; typed_text?: string }> {
    let targetEl: HTMLInputElement | HTMLTextAreaElement | null = null;

    if (spec.selector && spec.selector !== "auto") {
      try {
        targetEl = document.querySelector(spec.selector);
      } catch (e: any) {
        return { success: false, error: `Invalid selector: ${spec.selector}` };
      }
    }

    if (!targetEl) {
      const discovery = this.findSearchInput();
      if (discovery.found && discovery.selector) {
        targetEl = document.querySelector(discovery.selector);
      }
    }

    if (!targetEl) {
      return { success: false, error: "SEARCH_INPUT_NOT_FOUND" };
    }

    const rect = targetEl.getBoundingClientRect();
    const style = window.getComputedStyle(targetEl);

    if (style.display === "none" || style.visibility === "hidden" || style.opacity === "0") {
      return { success: false, error: "Search input is hidden from view" };
    }

    targetEl.scrollIntoView({ behavior: "smooth", block: "center" });

    const freshRect = targetEl.getBoundingClientRect();
    this.showVirtualCursor(freshRect.left + freshRect.width / 2, freshRect.top + freshRect.height / 2, "type");

    try {
      targetEl.focus();

      if (spec.clearFirst !== false) {
        targetEl.value = "";
      }

      // Handle React / Vue prototype value setter
      const prototype = Object.getPrototypeOf(targetEl);
      const descriptor =
        Object.getOwnPropertyDescriptor(prototype, "value") ||
        Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value");

      if (descriptor && descriptor.set) {
        descriptor.set.call(targetEl, spec.text);
      } else {
        targetEl.value = spec.text;
      }

      targetEl.dispatchEvent(new Event("input", { bubbles: true, cancelable: true }));
      targetEl.dispatchEvent(new Event("change", { bubbles: true, cancelable: true }));

      const originalOutline = targetEl.style.outline;
      targetEl.style.outline = "2px solid #38bdf8";
      setTimeout(() => {
        if (targetEl) targetEl.style.outline = originalOutline;
      }, 700);

      return { success: true, typed_text: spec.text };
    } catch (err: any) {
      return { success: false, error: `Type execution failed: ${err.message}` };
    }
  }

  /**
   * Safely dispatches a key event (e.g. Enter to submit search).
   */
  public static async safePressKey(spec: KeyPressSpec): Promise<{ success: boolean; error?: string; key?: string }> {
    let targetEl: HTMLElement | null = null;

    if (spec.selector) {
      try {
        targetEl = document.querySelector(spec.selector);
      } catch {}
    }

    if (!targetEl) {
      targetEl = (document.activeElement as HTMLElement) || document.body;
    }

    try {
      const key = spec.key || "Enter";
      const keyCode = key === "Enter" ? 13 : 0;

      const keyboardEvents = ["keydown", "keypress", "keyup"];
      for (const eventName of keyboardEvents) {
        const ev = new KeyboardEvent(eventName, {
          key: key,
          code: key === "Enter" ? "Enter" : key,
          keyCode: keyCode,
          which: keyCode,
          bubbles: true,
          cancelable: true,
        });
        targetEl.dispatchEvent(ev);
      }

      // If Enter key pressed on a form input, trigger form submit or search button click
      if (key === "Enter") {
        const form = targetEl.closest("form");
        if (form) {
          const submitBtn = form.querySelector<HTMLElement>('button[type="submit"], input[type="submit"], [role="button"]');
          if (submitBtn) {
            submitBtn.click();
          } else {
            form.requestSubmit ? form.requestSubmit() : form.submit();
          }
        }
      }

      return { success: true, key };
    } catch (err: any) {
      return { success: false, error: `Press key failed: ${err.message}` };
    }
  }

  /**
   * Safely scrolls the active page with bounded parameters.
   */
  public static safeScroll(direction: "up" | "down", amount: number = 500): { success: boolean; scrolled_px: number } {
    const boundedAmount = Math.min(Math.max(amount, 50), EXTENSION_LIMITS.MAX_SCROLL_AMOUNT);
    const delta = direction === "up" ? -boundedAmount : boundedAmount;

    // 1. Scroll window
    try {
      window.scrollBy({
        top: delta,
        left: 0,
        behavior: "smooth",
      });
    } catch {}

    // 2. Scroll document scrolling element
    try {
      if (document.scrollingElement) {
        if (typeof (document.scrollingElement as any).scrollBy === "function") {
          (document.scrollingElement as any).scrollBy({ top: delta, left: 0, behavior: "smooth" });
        } else {
          document.scrollingElement.scrollTop += delta;
        }
      }
    } catch {}

    // 3. Scroll all internal overflow containers (Threads, Twitter, Reddit feeds)
    const scrollableSelectors = [
      "main",
      "[role='main']",
      "[role='feed']",
      "[data-pressable-container]",
      "div[style*='overflow']",
      "div[class*='scroll']",
      "section",
    ];
    try {
      const candidates = document.querySelectorAll<HTMLElement>(scrollableSelectors.join(", "));
      for (const el of Array.from(candidates)) {
        try {
          const style = window.getComputedStyle(el);
          const canScroll =
            style.overflowY === "auto" ||
            style.overflowY === "scroll" ||
            style.overflow === "auto" ||
            style.overflow === "scroll";
          if (canScroll && el.scrollHeight > el.clientHeight) {
            if (typeof el.scrollBy === "function") {
              el.scrollBy({ top: delta, left: 0, behavior: "smooth" });
            } else {
              el.scrollTop += delta;
            }
          }
        } catch {}
      }
    } catch {}

    // 4. Dispatch synthetic wheel event so infinite list virtualization listeners trigger
    try {
      const wheelEv = new WheelEvent("wheel", {
        deltaY: delta,
        bubbles: true,
        cancelable: true,
      });
      window.dispatchEvent(wheelEv);
      document.dispatchEvent(wheelEv);
    } catch {}

    return { success: true, scrolled_px: delta };
  }
}
