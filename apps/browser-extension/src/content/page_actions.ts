import { EXTENSION_LIMITS } from "../shared/constants.js";

export interface ClickTargetSpec {
  selector?: string;
  text?: string;
}

export class PageActions {
  /**
   * Safely clicks a target element based on structured selector or visible text.
   * Prohibits arbitrary code execution or eval().
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

    // Check visibility and dimensions
    const rect = targetEl.getBoundingClientRect();
    const style = window.getComputedStyle(targetEl);

    if (style.display === "none" || style.visibility === "hidden" || style.opacity === "0") {
      return { success: false, error: "Target element is hidden from view" };
    }

    // Scroll into view if needed
    targetEl.scrollIntoView({ behavior: "smooth", block: "center" });

    // Brief highlight animation for user feedback
    const originalOutline = targetEl.style.outline;
    targetEl.style.outline = "2px solid #2563EB";
    setTimeout(() => {
      if (targetEl) targetEl.style.outline = originalOutline;
    }, 600);

    // Dispatch click safely
    try {
      targetEl.click();
      return { success: true };
    } catch (err: any) {
      return { success: false, error: `Click execution failed: ${err.message}` };
    }
  }

  /**
   * Safely scrolls the active page with bounded parameters.
   */
  public static safeScroll(direction: "up" | "down", amount: number = 500): { success: boolean; scrolled_px: number } {
    const boundedAmount = Math.min(Math.max(amount, 50), EXTENSION_LIMITS.MAX_SCROLL_AMOUNT);
    const delta = direction === "up" ? -boundedAmount : boundedAmount;

    window.scrollBy({
      top: delta,
      left: 0,
      behavior: "smooth",
    });

    return { success: true, scrolled_px: delta };
  }
}
