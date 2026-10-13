import { AgentControlState, OverlayStatus } from "../shared/types.js";
import { STORAGE_KEYS } from "../shared/constants.js";

/**
 * AI Browser Control Visual Overlay
 * Provides a glowing halo and real-time agent status badge
 * completely non-blocking (pointer-events: none) and style-isolated (Shadow DOM).
 */
export class AgentOverlay {
  private static hostElement: HTMLElement | null = null;
  private static shadowRoot: ShadowRoot | null = null;
  private static haloElement: HTMLElement | null = null;
  private static badgeElement: HTMLElement | null = null;
  private static dotElement: HTMLElement | null = null;
  private static textElement: HTMLElement | null = null;
  private static tagElement: HTMLElement | null = null;
  private static fadeTimeout: any = null;

  private static currentState: AgentControlState = {
    active: false,
    status: "NORMAL",
    action_text: "",
    updated_at: Date.now(),
  };

  /**
   * Initialize overlay root inside the document
   */
  public static init(): void {
    if (this.hostElement) return;

    // Attach to documentElement to avoid polluting document.body
    const targetParent = document.documentElement || document.body;
    if (!targetParent) return;

    this.hostElement = document.createElement("div");
    this.hostElement.id = "tv-ai-browser-control-host";
    this.hostElement.setAttribute("aria-hidden", "true");
    this.hostElement.style.cssText = "all: initial; pointer-events: none !important; position: static;";

    this.shadowRoot = this.hostElement.attachShadow({ mode: "open" });

    // Inject styles and markup
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          all: initial;
          pointer-events: none !important;
          user-select: none !important;
        }

        .tv-overlay-container {
          position: fixed;
          inset: 0;
          width: 100vw;
          height: 100vh;
          pointer-events: none !important;
          z-index: 2147483647;
          overflow: hidden;
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
          transition: opacity 0.4s ease, visibility 0.4s ease;
          opacity: 0;
          visibility: hidden;
        }

        .tv-overlay-container.tv-visible {
          opacity: 1;
          visibility: visible;
        }

        /* Halo edge glow */
        .tv-halo {
          position: absolute;
          inset: 0;
          pointer-events: none !important;
          box-sizing: border-box;
          transition: box-shadow 0.4s ease, border-color 0.4s ease, opacity 0.4s ease;
        }

        /* RUNNING State: Blue/Purple Glowing Halo */
        .tv-halo.status-RUNNING {
          border: 2.5px solid rgba(139, 92, 246, 0.7);
          box-shadow: inset 0 0 30px 8px rgba(99, 102, 241, 0.5), inset 0 0 65px 16px rgba(168, 85, 247, 0.3);
          animation: tvHaloPulseRunning 2.8s infinite ease-in-out;
        }

        @keyframes tvHaloPulseRunning {
          0%, 100% {
            box-shadow: inset 0 0 24px 6px rgba(99, 102, 241, 0.42), inset 0 0 50px 12px rgba(168, 85, 247, 0.25);
            border-color: rgba(139, 92, 246, 0.6);
          }
          50% {
            box-shadow: inset 0 0 38px 10px rgba(99, 102, 241, 0.7), inset 0 0 80px 22px rgba(168, 85, 247, 0.45);
            border-color: rgba(168, 85, 247, 0.95);
          }
        }

        /* PAUSED State: Amber/Yellow Subtle Glow */
        .tv-halo.status-PAUSED {
          border: 2.5px solid rgba(245, 158, 11, 0.75);
          box-shadow: inset 0 0 28px 7px rgba(245, 158, 11, 0.5), inset 0 0 60px 14px rgba(251, 191, 36, 0.3);
          animation: tvHaloPulsePaused 3.2s infinite ease-in-out;
        }

        @keyframes tvHaloPulsePaused {
          0%, 100% {
            box-shadow: inset 0 0 22px 5px rgba(245, 158, 11, 0.4), inset 0 0 45px 10px rgba(251, 191, 36, 0.2);
            border-color: rgba(245, 158, 11, 0.6);
          }
          50% {
            box-shadow: inset 0 0 34px 9px rgba(245, 158, 11, 0.68), inset 0 0 72px 18px rgba(251, 191, 36, 0.42);
            border-color: rgba(245, 158, 11, 0.95);
          }
        }

        /* WAITING FOR APPROVAL State: Purple/Amber Glow */
        .tv-halo.status-WAITING_FOR_APPROVAL {
          border: 2.5px solid rgba(168, 85, 247, 0.85);
          box-shadow: inset 0 0 32px 9px rgba(168, 85, 247, 0.6), inset 0 0 68px 18px rgba(245, 158, 11, 0.4);
          animation: tvHaloPulseApproval 2.2s infinite ease-in-out;
        }

        @keyframes tvHaloPulseApproval {
          0%, 100% {
            box-shadow: inset 0 0 26px 7px rgba(168, 85, 247, 0.5), inset 0 0 54px 14px rgba(245, 158, 11, 0.3);
            border-color: rgba(168, 85, 247, 0.7);
          }
          50% {
            box-shadow: inset 0 0 42px 12px rgba(168, 85, 247, 0.78), inset 0 0 85px 24px rgba(245, 158, 11, 0.52);
            border-color: rgba(245, 158, 11, 0.95);
          }
        }

        /* BLOCKED State: Red Glow */
        .tv-halo.status-BLOCKED {
          border: 2.5px solid rgba(239, 68, 68, 0.85);
          box-shadow: inset 0 0 35px 11px rgba(239, 68, 68, 0.65), inset 0 0 75px 22px rgba(220, 38, 38, 0.42);
          animation: tvHaloPulseBlocked 1.8s infinite ease-in-out;
        }

        /* ERROR State: Red/Amber Alert Glow */
        .tv-halo.status-ERROR {
          border: 2.5px solid rgba(239, 68, 68, 0.85);
          box-shadow: inset 0 0 35px 11px rgba(239, 68, 68, 0.65), inset 0 0 75px 22px rgba(245, 158, 11, 0.4);
          animation: tvHaloPulseBlocked 2.0s infinite ease-in-out;
        }

        @keyframes tvHaloPulseBlocked {
          0%, 100% {
            box-shadow: inset 0 0 28px 8px rgba(239, 68, 68, 0.55), inset 0 0 60px 16px rgba(220, 38, 38, 0.35);
            border-color: rgba(239, 68, 68, 0.75);
          }
          50% {
            box-shadow: inset 0 0 45px 14px rgba(239, 68, 68, 0.82), inset 0 0 95px 28px rgba(220, 38, 38, 0.55);
            border-color: rgba(239, 68, 68, 1);
          }
        }

        /* Floating Status Badge */
        .tv-badge-wrapper {
          position: absolute;
          top: 16px;
          left: 50%;
          transform: translateX(-50%);
          pointer-events: none !important;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .tv-status-badge {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 7px 18px 7px 14px;
          background: rgba(15, 23, 42, 0.88);
          backdrop-filter: blur(14px);
          -webkit-backdrop-filter: blur(14px);
          border: 1px solid rgba(255, 255, 255, 0.16);
          border-radius: 9999px;
          color: #ffffff;
          font-size: 12.5px;
          font-weight: 500;
          letter-spacing: 0.2px;
          box-shadow: 0 10px 28px -4px rgba(0, 0, 0, 0.5), 0 0 18px rgba(99, 102, 241, 0.3);
          transition: border-color 0.3s ease, box-shadow 0.3s ease;
        }

        /* Mode Tag */
        .tv-tag {
          font-size: 10px;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.6px;
          padding: 2.5px 7px;
          border-radius: 4px;
          background: rgba(99, 102, 241, 0.25);
          color: #c7d2fe;
          border: 1px solid rgba(129, 140, 248, 0.3);
          white-space: nowrap;
        }

        /* Pulsing Dot */
        .tv-dot-container {
          position: relative;
          width: 9px;
          height: 9px;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .tv-dot {
          width: 9px;
          height: 9px;
          border-radius: 50%;
          background: #818cf8;
          transition: background-color 0.3s ease;
        }

        .tv-dot-ping {
          position: absolute;
          inset: -2px;
          border-radius: 50%;
          background: #818cf8;
          opacity: 0.75;
          animation: tvPing 1.8s cubic-bezier(0, 0, 0.2, 1) infinite;
        }

        @keyframes tvPing {
          75%, 100% {
            transform: scale(2.2);
            opacity: 0;
          }
        }

        /* Status colors for dot and tag */
        .status-PAUSED .tv-dot,
        .status-PAUSED .tv-dot-ping {
          background: #fbbf24;
        }
        .status-PAUSED .tv-tag {
          background: rgba(245, 158, 11, 0.25);
          color: #fde68a;
          border-color: rgba(245, 158, 11, 0.35);
        }

        .status-WAITING_FOR_APPROVAL .tv-dot,
        .status-WAITING_FOR_APPROVAL .tv-dot-ping {
          background: #c084fc;
        }
        .status-WAITING_FOR_APPROVAL .tv-tag {
          background: rgba(168, 85, 247, 0.25);
          color: #e9d5ff;
          border-color: rgba(168, 85, 247, 0.35);
        }

        .status-BLOCKED .tv-dot,
        .status-BLOCKED .tv-dot-ping {
          background: #f87171;
        }
        .status-BLOCKED .tv-tag {
          background: rgba(239, 68, 68, 0.25);
          color: #fecaca;
          border-color: rgba(239, 68, 68, 0.35);
        }

        .status-ERROR .tv-dot,
        .status-ERROR .tv-dot-ping {
          background: #f87171;
        }
        .status-ERROR .tv-tag {
          background: rgba(239, 68, 68, 0.25);
          color: #fecaca;
          border-color: rgba(239, 68, 68, 0.35);
        }

        .status-COMPLETED .tv-dot,
        .status-COMPLETED .tv-dot-ping {
          background: #34d399;
        }
        .status-COMPLETED .tv-tag {
          background: rgba(16, 185, 129, 0.25);
          color: #a7f3d0;
          border-color: rgba(16, 185, 129, 0.35);
        }

        .tv-action-text {
          white-space: nowrap;
          color: #f1f5f9;
        }
      </style>

      <div class="tv-overlay-container" id="tv-container">
        <div class="tv-halo" id="tv-halo"></div>
        <div class="tv-badge-wrapper">
          <div class="tv-status-badge" id="tv-badge">
            <span class="tv-tag" id="tv-tag">AGENT ACTIVE</span>
            <div class="tv-dot-container">
              <span class="tv-dot-ping" id="tv-dot-ping"></span>
              <span class="tv-dot" id="tv-dot"></span>
            </div>
            <span class="tv-action-text" id="tv-text">AI Agent • Active</span>
          </div>
        </div>
      </div>
    `;

    targetParent.appendChild(this.hostElement);

    this.haloElement = this.shadowRoot.getElementById("tv-halo");
    this.badgeElement = this.shadowRoot.getElementById("tv-badge");
    this.dotElement = this.shadowRoot.getElementById("tv-dot");
    this.textElement = this.shadowRoot.getElementById("tv-text");
    this.tagElement = this.shadowRoot.getElementById("tv-tag");

    // Load initial state from storage
    this.loadStateFromStorage();
  }

  /**
   * Load stored agent control state
   */
  public static async loadStateFromStorage(): Promise<void> {
    try {
      const data = await chrome.storage.local.get(STORAGE_KEYS.AGENT_CONTROL_STATE);
      const stored = data[STORAGE_KEYS.AGENT_CONTROL_STATE];
      if (stored) {
        this.updateState(stored);
      }
    } catch {
      // Storage access may fail if extension reloaded
    }
  }

  /**
   * Update visual overlay elements according to current state
   */
  public static updateState(state: Partial<AgentControlState>): void {
    if (!this.hostElement || !this.shadowRoot) {
      this.init();
    }
    if (!this.shadowRoot) return;

    this.currentState = {
      ...this.currentState,
      ...state,
      updated_at: Date.now(),
    };

    const container = this.shadowRoot.getElementById("tv-container");
    const halo = this.haloElement;
    const textEl = this.textElement;
    const tagEl = this.tagElement;
    const badgeEl = this.badgeElement;

    if (!container || !halo || !textEl || !tagEl || !badgeEl) return;

    if (this.fadeTimeout) {
      clearTimeout(this.fadeTimeout);
      this.fadeTimeout = null;
    }

    const { active, status, action_text, reason } = this.currentState;

    if (!active || status === "NORMAL" || status === "COMPLETED" || status === "DISCONNECTED") {
      container.className = "tv-overlay-container";
      return;
    }

    // Active state: show glow & badge
    container.className = "tv-overlay-container tv-visible";
    halo.className = `tv-halo status-${status}`;
    badgeEl.className = `tv-status-badge status-${status}`;

    // Tag text
    switch (status) {
      case "RUNNING":
        tagEl.textContent = "AGENT ACTIVE";
        break;
      case "PAUSED":
        tagEl.textContent = "AGENT PAUSED";
        break;
      case "WAITING_FOR_APPROVAL":
        tagEl.textContent = "APPROVAL NEEDED";
        break;
      case "BLOCKED":
        tagEl.textContent = "AGENT BLOCKED";
        break;
      case "ERROR":
        tagEl.textContent = "AGENT ERROR";
        break;
      default:
        tagEl.textContent = "AGENT ACTIVE";
        break;
    }

    // Status action text
    if (reason && status === "BLOCKED") {
      textEl.textContent = `AI Agent • Blocked: ${reason}`;
    } else {
      textEl.textContent = action_text || "AI Agent • Controlling browser";
    }
  }

  /**
   * Hide and cleanup overlay
   */
  public static hide(): void {
    this.updateState({ active: false, status: "NORMAL" });
  }
}
