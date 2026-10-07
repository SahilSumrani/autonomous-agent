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
  const observeBtn = document.getElementById("observeBtn")!;
  const disconnectBtn = document.getElementById("disconnectBtn")!;

  const outreachRecipient = document.getElementById("outreachRecipient")!;
  const outreachChannel = document.getElementById("outreachChannel")!;
  const outreachBody = document.getElementById("outreachBody")!;
  const confirmSendBtn = document.getElementById("confirmSendBtn")!;
  const cancelSendBtn = document.getElementById("cancelSendBtn")!;

  // Refresh UI based on background state
  async function refreshStatus() {
    chrome.runtime.sendMessage({ type: "GET_EXTENSION_STATUS" }, (response) => {
      if (!response) return;

      const isConnected = response.is_connected;
      const session = response.session_data;
      const pendingAction = response.pending_action;

      if (isConnected && session) {
        statusPill.textContent = "CONNECTED";
        statusPill.className = "status-pill connected";
        pairingSection.classList.add("hidden");
        sessionSection.classList.remove("hidden");

        sessionIdVal.textContent = session.session_id.slice(0, 13) + "...";
        stateVal.textContent = response.state;
      } else {
        statusPill.textContent = "DISCONNECTED";
        statusPill.className = "status-pill disconnected";
        pairingSection.classList.remove("hidden");
        sessionSection.classList.add("hidden");
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
          refreshStatus();
        } else {
          pairError.textContent = res?.error || "Pairing failed";
          pairError.classList.remove("hidden");
        }
      }
    );
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
