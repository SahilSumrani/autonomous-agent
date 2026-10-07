import test from "node:test";
import assert from "node:assert/strict";
import * as esbuild from "esbuild";
import * as path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

test("Extension bundle and functionality test suite", async () => {
  // Bundle the extension modules for test verification
  const testBundle = await esbuild.build({
    entryPoints: [
      path.join(__dirname, "../src/security/origin_policy.ts"),
      path.join(__dirname, "../src/security/permissions.ts"),
      path.join(__dirname, "../src/content/page_reader.ts"),
    ],
    bundle: true,
    format: "esm",
    write: false,
    outdir: "out",
  });

  assert.equal(testBundle.errors.length, 0);
  assert.equal(testBundle.outputFiles.length, 3);
});

test("OriginPolicy security checks block loopback and cloud metadata", async () => {
  // Dynamically load the bundled origin_policy
  const bundle = await esbuild.build({
    entryPoints: [path.join(__dirname, "../src/security/origin_policy.ts")],
    bundle: true,
    format: "esm",
    write: false,
  });

  const code = bundle.outputFiles[0].text;
  const mod = await import(`data:text/javascript;base64,${Buffer.from(code).toString("base64")}`);
  const OriginPolicy = mod.OriginPolicy;

  assert.equal(OriginPolicy.isSafeTargetUrl("http://127.0.0.1:8000").safe, false);
  assert.equal(OriginPolicy.isSafeTargetUrl("http://localhost:3000").safe, false);
  assert.equal(OriginPolicy.isSafeTargetUrl("http://169.254.169.254").safe, false);
  assert.equal(OriginPolicy.isSafeTargetUrl("chrome://settings").safe, false);
  assert.equal(OriginPolicy.isSafeTargetUrl("file:///etc/hosts").safe, false);
  assert.equal(OriginPolicy.isSafeTargetUrl("https://www.instagram.com/apexluxury/").safe, true);
  assert.equal(OriginPolicy.isSafeTargetUrl("https://www.reddit.com/r/shopify/").safe, true);
});

test("PermissionsGuard sanitizes untrusted input", async () => {
  const bundle = await esbuild.build({
    entryPoints: [path.join(__dirname, "../src/security/permissions.ts")],
    bundle: true,
    format: "esm",
    write: false,
  });

  const code = bundle.outputFiles[0].text;
  const mod = await import(`data:text/javascript;base64,${Buffer.from(code).toString("base64")}`);
  const PermissionsGuard = mod.PermissionsGuard;

  const sanitized = PermissionsGuard.sanitizeWebText("Hello\x00\x08World", 100);
  assert.equal(sanitized, "HelloWorld");
});

test("PageReader classifies URLs properly", async () => {
  const bundle = await esbuild.build({
    entryPoints: [path.join(__dirname, "../src/content/page_reader.ts")],
    bundle: true,
    format: "esm",
    write: false,
  });

  const code = bundle.outputFiles[0].text;
  const mod = await import(`data:text/javascript;base64,${Buffer.from(code).toString("base64")}`);
  const PageReader = mod.PageReader;

  assert.equal(PageReader.classifyPage("https://www.instagram.com/p/Cxyz123/"), "INSTAGRAM_POST");
  assert.equal(PageReader.classifyPage("https://www.instagram.com/apexluxurywear/"), "INSTAGRAM_PROFILE");
  assert.equal(PageReader.classifyPage("https://www.reddit.com/r/ecommerce/comments/xyz123/"), "REDDIT_POST");
  assert.equal(PageReader.classifyPage("https://www.reddit.com/user/john_doe/"), "REDDIT_PROFILE");
  assert.equal(PageReader.classifyPage("https://apexluxurywear.com/products"), "PUBLIC_WEBSITE");
});
