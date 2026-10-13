import { DEFAULT_BACKEND_HTTP } from "../shared/constants.js";

document.addEventListener("DOMContentLoaded", async () => {
  const statusPill = document.getElementById("statusPill")!;
  const pairingSection = document.getElementById("pairingSection")!;
  const sessionSection = document.getElementById("sessionSection")!;
  const pendingOutreachSection = document.getElementById("pendingOutreachSection")!;

  const pairingInput = document.getElementById("pairingInput") as HTMLInputElement;
  const pairBtn = document.getElementById("pairBtn") as HTMLButtonElement;
  const pairError = document.getElementById("pairError")!;

  const sessionIdVal = document.getElementById("sessionIdVal")!;
  const stateVal = document.getElementById("stateVal")!;
  const reconnectBanner = document.getElementById("reconnectBanner")!;
  const reconnectBtn = document.getElementById("reconnectBtn") as HTMLButtonElement;
  const observeBtn = document.getElementById("observeBtn")!;
  const disconnectBtn = document.getElementById("disconnectBtn")!;

  const taskUrlInput = document.getElementById("taskUrlInput") as HTMLInputElement;
  const taskSourceSelect = document.getElementById("taskSourceSelect") as HTMLSelectElement;
  const taskServiceInput = document.getElementById("taskServiceInput") as HTMLInputElement;
  const startTaskBtn = document.getElementById("startTaskBtn") as HTMLButtonElement;
  const startAutoBtn = document.getElementById("startAutoBtn") as HTMLButtonElement | null;
  const stopTaskBtn = document.getElementById("stopTaskBtn") as HTMLButtonElement;
  const taskStatusText = document.getElementById("taskStatusText")!;

  const outreachRecipient = document.getElementById("outreachRecipient")!;
  const outreachChannel = document.getElementById("outreachChannel")!;
  const outreachBody = document.getElementById("outreachBody")!;
  const confirmSendBtn = document.getElementById("confirmSendBtn")!;
  const cancelSendBtn = document.getElementById("cancelSendBtn")!;

  let currentSessionData: any = null;
  let activeJobId: string | null = null;

  // Refresh UI based on background state
  async function refreshStatus() {
    chrome.runtime.sendMessage({ type: "GET_EXTENSION_STATUS" }, (response) => {
      if (!response) return;

      const isConnected = response.is_connected;
      const session = response.session_data;
      const pendingAction = response.pending_action;
      currentSessionData = session;

      if (session) {
        // We have a persisted session: keep pairing prompt HIDDEN
        pairingSection.classList.add("hidden");
        sessionSection.classList.remove("hidden");
        sessionIdVal.textContent = session.session_id.slice(0, 13) + "...";
        stateVal.textContent = response.state || "RUNNING";

        if (response.state === "BLOCKED") {
          stateVal.className = "badge badge-red";
        } else if (response.state === "RUNNING") {
          stateVal.className = "badge badge-green";
        } else {
          stateVal.className = "badge badge-info";
        }

        if (isConnected) {
          statusPill.textContent = "CONNECTED";
          statusPill.className = "status-pill connected";
          reconnectBanner.classList.add("hidden");
        } else {
          statusPill.textContent = "RECONNECTING";
          statusPill.className = "status-pill reconnecting";
          reconnectBanner.classList.remove("hidden");
        }
      } else {
        // No persisted session: show pairing challenge prompt
        statusPill.textContent = "DISCONNECTED";
        statusPill.className = "status-pill disconnected";
        pairingSection.classList.remove("hidden");
        sessionSection.classList.add("hidden");
        reconnectBanner.classList.add("hidden");
      }

      // Check pending outreach action
      if (pendingAction) {
        pendingOutreachSection.classList.remove("hidden");
        outreachRecipient.textContent = pendingAction.recipient || "Unknown";
        outreachChannel.textContent = pendingAction.channel || "INSTAGRAM_DM";
        outreachBody.textContent = pendingAction.body || "";
      } else {
        pendingOutreachSection.classList.add("hidden");
      }
    });
  }

  // Handle pairing button
  pairBtn.addEventListener("click", () => {
    const code = pairingInput.value.trim().toUpperCase();
    if (!code) {
      pairError.textContent = "Please enter pairing code";
      pairError.classList.remove("hidden");
      return;
    }

    pairError.classList.add("hidden");
    pairBtn.textContent = "Connecting...";
    pairBtn.disabled = true;

    chrome.runtime.sendMessage(
      {
        type: "SUBMIT_PAIRING",
        payload: { code, backend_url: DEFAULT_BACKEND_HTTP },
      },
      (res) => {
        pairBtn.textContent = "Connect";
        pairBtn.disabled = false;
        if (res && res.success) {
          pairingInput.value = "";
          refreshStatus();
        } else {
          pairError.textContent = res?.error || "Pairing failed";
          pairError.classList.remove("hidden");
        }
      }
    );
  });

  // Handle reconnect button
  reconnectBtn.addEventListener("click", () => {
    reconnectBtn.textContent = "Connecting...";
    reconnectBtn.disabled = true;
    chrome.runtime.sendMessage({ type: "RECONNECT_GATEWAY" }, (res) => {
      reconnectBtn.textContent = "⚡ Reconnect to Gateway";
      reconnectBtn.disabled = false;
      refreshStatus();
    });
  });

  async function launchProspectingTask(targetUrl?: string, targetService?: string) {
    if (targetUrl && !targetUrl.startsWith("http://") && !targetUrl.startsWith("https://")) {
      taskStatusText.textContent = "⚠️ URL must start with http:// or https://";
      taskStatusText.style.color = "#F87171";
      return;
    }

    if (!currentSessionData) {
      taskStatusText.textContent = "⚠️ No active session found. Connect first.";
      taskStatusText.style.color = "#F87171";
      return;
    }

    const backendUrl = currentSessionData.backend_url || DEFAULT_BACKEND_HTTP;
    const source = taskSourceSelect.value;
    const effectiveQuery = targetUrl || null;
    const effectiveService = targetService || null;

    startTaskBtn.disabled = true;
    if (startAutoBtn) startAutoBtn.disabled = true;
    taskStatusText.textContent = "Submitting task to backend...";
    taskStatusText.style.color = "#93C5FD";

    try {
      const res = await fetch(`${backendUrl}/api/v1/prospecting/jobs?auto_start=true`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${currentSessionData.token}`,
        },
        body: JSON.stringify({
          source,
          query: effectiveQuery,
          target_service: effectiveService,
          max_candidates: 5,
          max_pages: 10,
          max_scrolls: 3,
          session_id: currentSessionData.session_id,
        }),
      });

      if (res.ok) {
        const job = await res.json();
        activeJobId = job.id;
        taskStatusText.textContent = `🚀 Task ${job.id.slice(0, 8)} started in dedicated agent tab`;
        taskStatusText.style.color = "#34D399";
      } else {
        const errData = await res.json().catch(() => ({}));
        let detailMsg = "Failed to start job (" + res.status + ")";
        if (errData.detail) {
          if (Array.isArray(errData.detail)) {
            detailMsg = errData.detail.map((e: any) => `${e.loc ? e.loc.slice(-1)[0] + ': ' : ''}${e.msg}`).join('; ');
          } else if (typeof errData.detail === 'object') {
            detailMsg = JSON.stringify(errData.detail);
          } else {
            detailMsg = String(errData.detail);
          }
        }
        if (res.status === 401) {
          taskStatusText.textContent = `❌ Session unauthorized: ${detailMsg}. Please re-pair extension.`;
          chrome.runtime.sendMessage({ type: "DISCONNECT_SESSION" }, () => refreshStatus());
        } else if (res.status === 403) {
          taskStatusText.textContent = `❌ Forbidden (403): ${detailMsg}`;
        } else {
          taskStatusText.textContent = `❌ ${detailMsg}`;
        }
        taskStatusText.style.color = "#F87171";
      }
    } catch (err: any) {
      taskStatusText.textContent = `❌ Network error: ${err.message}`;
      taskStatusText.style.color = "#F87171";
    } finally {
      startTaskBtn.disabled = false;
      if (startAutoBtn) startAutoBtn.disabled = false;
    }
  }

  // Handle Start Task (with inputs if specified)
  startTaskBtn.addEventListener("click", () => {
    const targetUrl = taskUrlInput.value.trim() || undefined;
    const targetService = taskServiceInput.value.trim() || undefined;
    launchProspectingTask(targetUrl, targetService);
  });

  // Handle Start Autonomous Prospecting (zero inputs)
  if (startAutoBtn) {
    startAutoBtn.addEventListener("click", () => {
      launchProspectingTask(undefined, undefined);
    });
  }

  // Handle Stop Task
  stopTaskBtn.addEventListener("click", async () => {
    stopTaskBtn.disabled = true;
    taskStatusText.textContent = "Stopping task...";
    taskStatusText.style.color = "#FBBF24";

    if (activeJobId && currentSessionData) {
      const backendUrl = currentSessionData.backend_url || DEFAULT_BACKEND_HTTP;
      try {
        await fetch(`${backendUrl}/api/v1/prospecting/jobs/${activeJobId}/cancel`, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${currentSessionData.token}`,
          },
        });
      } catch {}
    }

    // Also trigger stop in session manager
    chrome.runtime.sendMessage({
      type: "TRIGGER_COMMAND",
      command: { type: "STOP", session_id: currentSessionData?.session_id },
    }, () => {});

    taskStatusText.textContent = "Task stopped";
    taskStatusText.style.color = "#9CA3AF";
    stopTaskBtn.disabled = false;
  });

  // Handle observe button
  observeBtn.addEventListener("click", () => {
    observeBtn.textContent = "Observing...";
    chrome.runtime.sendMessage({ type: "TRIGGER_OBSERVATION" }, (res) => {
      observeBtn.textContent = "🔍 Observe Tab";
      if (res && res.success) {
        refreshStatus();
      }
    });
  });

  // Handle disconnect
  disconnectBtn.addEventListener("click", () => {
    chrome.runtime.sendMessage({ type: "DISCONNECT_SESSION" }, () => {
      currentSessionData = null;
      activeJobId = null;
      refreshStatus();
    });
  });

  // Handle send action confirmation
  confirmSendBtn.addEventListener("click", () => {
    chrome.runtime.sendMessage({ type: "CONFIRM_OUTREACH_ACTION", payload: { confirmed: true } }, () => {
      refreshStatus();
    });
  });

  // Handle send action cancel
  cancelSendBtn.addEventListener("click", () => {
    chrome.runtime.sendMessage({ type: "CONFIRM_OUTREACH_ACTION", payload: { confirmed: false } }, () => {
      refreshStatus();
    });
  });

  // Initial fetch and polling
  await refreshStatus();
  setInterval(refreshStatus, 2000);
});
