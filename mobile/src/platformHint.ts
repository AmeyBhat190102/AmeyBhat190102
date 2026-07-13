/** Platform resolution that also works in the web-based design-review rig.
 *
 * On device this is just React Native's Platform.OS. In the browser rig,
 * `?platform=ios|android` overrides it so the iOS and Android agents' work
 * can be reviewed separately from one web export. All platform branching in
 * app code must go through `platformOS()` (never Platform.OS directly) so
 * review frames match device behavior. */

import { Platform } from "react-native";

export type MobileOS = "ios" | "android";

export function platformOS(): MobileOS {
  if (Platform.OS === "ios" || Platform.OS === "android") return Platform.OS;
  if (typeof window !== "undefined") {
    const q = new URLSearchParams(window.location.search).get("platform");
    if (q === "ios" || q === "android") return q;
    // persists across client-side navigations
    const stored = window.sessionStorage?.getItem("aura-platform");
    if (stored === "ios" || stored === "android") return stored;
  }
  return "ios";
}

export function rememberPlatformHint(): void {
  if (typeof window === "undefined") return;
  const q = new URLSearchParams(window.location.search).get("platform");
  if (q === "ios" || q === "android") {
    window.sessionStorage?.setItem("aura-platform", q);
  }
}

export function select<T>(options: { ios: T; android: T }): T {
  return options[platformOS()];
}
