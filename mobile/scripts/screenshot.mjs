/** Design-review rig: export the app to web, serve it, and screenshot every
 * screen at iPhone and Android viewports. The supervisor agent judges these
 * frames against MOBILE_DESIGN.md.
 *
 *   EXPO_PUBLIC_DESIGN_REVIEW=1 node scripts/screenshot.mjs [outDir]
 *
 * Screens are frozen (animations disabled via reduced motion) so frames are
 * deterministic. Platform is simulated per viewport with the ?platform hint
 * consumed by src/platformHint.ts.
 */

import { execSync, spawn } from "node:child_process";
import { mkdirSync } from "node:fs";
import { chromium } from "playwright";

const OUT = process.argv[2] ?? "screenshots";
const PORT = 8123;

const VIEWPORTS = {
  ios: { width: 390, height: 844, deviceScaleFactor: 3 },      // iPhone 15
  android: { width: 412, height: 915, deviceScaleFactor: 2.6 }, // Pixel 8
};

const ROUTES = [
  ["home", "/"],
  ["new", "/new"],
  ["studio", "/studio/sample"],
  ["theater", "/studio/sample-running"],
];

const EXECUTABLE = process.env.AURA_CHROMIUM
  ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";

async function main() {
  console.log("exporting web build…");
  execSync("npx expo export -p web", {
    stdio: "inherit",
    env: { ...process.env, EXPO_PUBLIC_DESIGN_REVIEW: "1", CI: "1" },
  });

  const server = spawn("npx", ["serve", "dist", "-l", String(PORT), "-s"], {
    stdio: "ignore", detached: false,
  });
  await new Promise((r) => setTimeout(r, 2500));

  mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({ executablePath: EXECUTABLE });
  try {
    for (const [platform, viewport] of Object.entries(VIEWPORTS)) {
      const ctx = await browser.newContext({
        viewport: { width: viewport.width, height: viewport.height },
        deviceScaleFactor: viewport.deviceScaleFactor,
        reducedMotion: "reduce",
        userAgent: platform === "ios"
          ? "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"
          : "Mozilla/5.0 (Linux; Android 14; Pixel 8)",
      });
      const page = await ctx.newPage();
      for (const [name, route] of ROUTES) {
        await page.goto(`http://localhost:${PORT}${route}?platform=${platform}`,
                        { waitUntil: "networkidle" });
        await page.waitForTimeout(1800); // fonts + images settle
        await page.screenshot({ path: `${OUT}/${platform}-${name}.png` });
        console.log(`✓ ${platform}-${name}.png`);
      }
      await ctx.close();
    }
  } finally {
    await browser.close();
    server.kill();
  }
}

main().catch((e) => { console.error(e); process.exit(1); });
