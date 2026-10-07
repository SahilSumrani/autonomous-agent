export class DomObserver {
  private static lastUrl: string = window.location.href;
  private static callback: ((url: string) => void) | null = null;

  public static startObserving(onUrlChange: (url: string) => void): void {
    this.callback = onUrlChange;
    this.lastUrl = window.location.href;

    // Observe popstate
    window.addEventListener("popstate", () => this.checkUrlChange());

    // Intercept pushState & replaceState
    const originalPushState = history.pushState;
    history.pushState = (...args: any[]) => {
      originalPushState.apply(history, args as any);
      this.checkUrlChange();
    };

    const originalReplaceState = history.replaceState;
    history.replaceState = (...args: any[]) => {
      originalReplaceState.apply(history, args as any);
      this.checkUrlChange();
    };

    // Periodic check for client-side navigation (e.g. Next.js / Instagram SPA)
    setInterval(() => this.checkUrlChange(), 1500);
  }

  private static checkUrlChange(): void {
    const currentUrl = window.location.href;
    if (currentUrl !== this.lastUrl) {
      this.lastUrl = currentUrl;
      if (this.callback) {
        this.callback(currentUrl);
      }
    }
  }
}
