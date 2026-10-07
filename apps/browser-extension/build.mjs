import * as esbuild from "esbuild";
import * as fs from "fs";
import * as path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const distDir = path.join(__dirname, "dist");

async function build() {
  console.log("⚡ Building TechVerse AI Chrome Extension...");

  // Ensure directories
  fs.mkdirSync(path.join(distDir, "background"), { recursive: true });
  fs.mkdirSync(path.join(distDir, "content"), { recursive: true });
  fs.mkdirSync(path.join(distDir, "popup"), { recursive: true });

  // 1. Background Service Worker (ES Module)
  await esbuild.build({
    entryPoints: [path.join(__dirname, "src/background/service_worker.ts")],
    outfile: path.join(distDir, "background/service_worker.js"),
    bundle: true,
    format: "esm",
    target: "chrome115",
    sourcemap: false,
    minify: false,
  });
  console.log("✓ Built background/service_worker.js");

  // 2. Content Script (IIFE for isolated page execution)
  await esbuild.build({
    entryPoints: [path.join(__dirname, "src/content/content_script.ts")],
    outfile: path.join(distDir, "content/content_script.js"),
    bundle: true,
    format: "iife",
    target: "chrome115",
    sourcemap: false,
    minify: false,
  });
  console.log("✓ Built content/content_script.js");

  // 3. Popup UI Script
  await esbuild.build({
    entryPoints: [path.join(__dirname, "src/popup/popup.ts")],
    outfile: path.join(distDir, "popup/popup.js"),
    bundle: true,
    format: "esm",
    target: "chrome115",
    sourcemap: false,
    minify: false,
  });
  console.log("✓ Built popup/popup.js");

  // 4. Copy static assets
  fs.copyFileSync(
    path.join(__dirname, "src/popup/popup.html"),
    path.join(distDir, "popup/popup.html")
  );
  fs.copyFileSync(
    path.join(__dirname, "src/popup/popup.css"),
    path.join(distDir, "popup/popup.css")
  );
  console.log("✓ Copied popup HTML & CSS");

  // 5. Generate and validate dist/manifest.json from source manifest
  const sourceManifestPath = path.join(__dirname, "manifest.json");
  const rawManifest = fs.readFileSync(sourceManifestPath, "utf-8");
  const manifest = JSON.parse(rawManifest);

  // Normalize relative paths to be relative to dist root (strip leading "dist/")
  const normalizePath = (p) => (typeof p === "string" ? p.replace(/^\.?\/?dist\//, "") : p);

  if (manifest.background?.service_worker) {
    manifest.background.service_worker = normalizePath(manifest.background.service_worker);
  }
  if (Array.isArray(manifest.content_scripts)) {
    for (const cs of manifest.content_scripts) {
      if (Array.isArray(cs.js)) {
        cs.js = cs.js.map(normalizePath);
      }
      if (Array.isArray(cs.css)) {
        cs.css = cs.css.map(normalizePath);
      }
    }
  }
  if (manifest.action?.default_popup) {
    manifest.action.default_popup = normalizePath(manifest.action.default_popup);
  }

  // Validate that all referenced files exist in dist
  const referencedFiles = [
    manifest.background?.service_worker,
    ...(manifest.content_scripts?.flatMap((cs) => cs.js || []) || []),
    ...(manifest.content_scripts?.flatMap((cs) => cs.css || []) || []),
    manifest.action?.default_popup,
  ].filter(Boolean);

  for (const relFile of referencedFiles) {
    const fullPath = path.join(distDir, relFile);
    if (!fs.existsSync(fullPath)) {
      throw new Error(`Manifest references file not found in dist: ${relFile}`);
    }
  }

  const distManifestPath = path.join(distDir, "manifest.json");
  fs.writeFileSync(distManifestPath, JSON.stringify(manifest, null, 2) + "\n", "utf-8");
  console.log("✓ Generated dist/manifest.json");

  console.log("🎉 Extension build successful! Ready to unpack in Chrome.");
}

build().catch((err) => {
  console.error("Build failed:", err);
  process.exit(1);
});
