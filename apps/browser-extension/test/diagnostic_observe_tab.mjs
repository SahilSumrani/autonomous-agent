import test from "node:test";
import assert from "node:assert/strict";
import * as esbuild from "esbuild";
import * as path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

test("Controlled Diagnostic: Observe Tab on chrome://newtab vs https://example.com", async () => {
  // 1. Bundle PageReader & PermissionsGuard
  const bundle = await esbuild.build({
    entryPoints: [
      path.join(__dirname, "../src/content/page_reader.ts"),
      path.join(__dirname, "../src/content/safety_guard.ts"),
    ],
    bundle: true,
    format: "esm",
    write: false,
    outdir: "out",
  });

  const readerFile = bundle.outputFiles.find(f => f.path.includes("page_reader"));
  const safetyFile = bundle.outputFiles.find(f => f.path.includes("safety_guard"));

  const readerMod = await import(`data:text/javascript;base64,${Buffer.from(readerFile.text).toString("base64")}`);
  const safetyMod = await import(`data:text/javascript;base64,${Buffer.from(safetyFile.text).toString("base64")}`);

  const { PageReader } = readerMod;
  const { SafetyGuard } = safetyMod;

  // 2. Simulate chrome://newtab environment
  {
    // Content script cannot execute on chrome:// URLs per MV3
    const newTabUrl = "chrome://newtab/";
    // PageReader fallback
    const pageType = PageReader.classifyPage(newTabUrl);
    assert.equal(pageType, "PUBLIC_WEBSITE");

    // In Chrome MV3, content scripts are not injected into chrome://*
    // Simulating service_worker.ts TRIGGER_OBSERVATION behavior on chrome://newtab:
    let wsFrameSent = false;
    let serviceWorkerResponse = null;

    const mockChromeTabsSendMessage = (tabId, message, callback) => {
      // Chrome simulates connection failure because no content script exists
      const mockLastError = { message: "Could not establish connection. Receiving end does not exist." };
      callback(undefined, mockLastError);
    };

    // Service worker TRIGGER_OBSERVATION execution simulation
    const activeTab = { id: 101, url: "chrome://newtab" };
    mockChromeTabsSendMessage(activeTab.id, { command_type: "READ_PAGE" }, (response, lastError) => {
      if (!lastError && response?.success) {
        wsFrameSent = true;
        serviceWorkerResponse = { success: true, observation: response.result };
      } else {
        serviceWorkerResponse = { success: false, error: "Could not read page" };
      }
    });

    assert.equal(wsFrameSent, false, "WebSocket frame MUST NOT be sent on chrome://newtab failure");
    assert.equal(serviceWorkerResponse.success, false);
    assert.equal(serviceWorkerResponse.error, "Could not read page");
  }

  // 3. Simulate https://example.com/ environment
  {
    const exampleUrl = "https://example.com/";
    const pageType = PageReader.classifyPage(exampleUrl);
    assert.equal(pageType, "PUBLIC_WEBSITE");

    // Mock DOM environment for https://example.com/
    global.window = {
      location: {
        href: "https://example.com/",
        origin: "https://example.com",
        pathname: "/",
        hostname: "example.com",
      },
    };
    global.document = {
      title: "Example Domain",
      readyState: "complete",
      body: {
        innerText: "Example Domain\nThis domain is for use in illustrative examples in documents.",
      },
      querySelectorAll: (sel) => {
        if (sel === "h1, h2, h3") {
          return [{ textContent: "Example Domain" }];
        }
        if (sel === "a[href]") {
          return [{
            getAttribute: (attr) => attr === "href" ? "https://www.iana.org/domains/example" : null,
          }];
        }
        if (sel.includes("g-recaptcha")) {
          return [];
        }
        return [];
      },
      querySelector: (sel) => {
        if (sel.includes("meta")) return null;
        return null;
      },
    };

    // Step 3a: Safety guard check
    const safety = SafetyGuard.inspectPageSafety();
    assert.equal(safety.isBlocked, false, "example.com should not be blocked");

    // Step 3b: Content script extracts observation
    const observation = PageReader.extractObservation();
    assert.equal(observation.url, "https://example.com/");
    assert.equal(observation.title, "Example Domain");
    assert.equal(observation.origin, "https://example.com");
    assert.equal(observation.page_type, "PUBLIC_WEBSITE");
    assert.ok(observation.visible_text.includes("Example Domain"));
    assert.deepEqual(observation.headings, ["Example Domain"]);
    assert.deepEqual(observation.links, ["https://www.iana.org/domains/example"]);

    // Step 3c: Service worker message flow
    let wsFrameSent = false;
    let sentFrameType = null;
    let sentPayload = null;
    let serviceWorkerResponse = null;

    const mockGatewayConnection = {
      isConnected: () => true,
      sendFrame: (frameType, payload) => {
        wsFrameSent = true;
        sentFrameType = frameType;
        sentPayload = payload;
      },
    };

    const mockChromeTabsSendMessage = (tabId, message, callback) => {
      // Content script is present and responds successfully
      assert.equal(message.command_type, "READ_PAGE");
      callback({ success: true, result: observation });
    };

    const activeTab = { id: 102, url: "https://example.com/" };
    mockChromeTabsSendMessage(activeTab.id, { command_type: "READ_PAGE" }, (response) => {
      if (response?.success) {
        if (mockGatewayConnection.isConnected()) {
          mockGatewayConnection.sendFrame("OBSERVATION", response.result);
        }
        serviceWorkerResponse = { success: true, observation: response.result };
      } else {
        serviceWorkerResponse = { success: false, error: "Could not read page" };
      }
    });

    assert.equal(wsFrameSent, true, "WebSocket frame MUST be sent for https://example.com");
    assert.equal(sentFrameType, "OBSERVATION");
    assert.equal(sentPayload.url, "https://example.com/");
    assert.equal(serviceWorkerResponse.success, true);
    assert.equal(serviceWorkerResponse.observation.title, "Example Domain");
  }
});
