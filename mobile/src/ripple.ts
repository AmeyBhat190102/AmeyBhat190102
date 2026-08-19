/** Android's touch voice: an ivory ripple at 10% — light catching the ink,
 * never Material grey. iOS keeps pressed-opacity; the guard goes through
 * platformHint's select() so the review rig stays honest. */

import type { PressableAndroidRippleConfig } from "react-native";
import { select } from "./platformHint";

/** Ivory (#e8ddc8) at 10% — matches theme ivory, kept literal because
 * android_ripple needs an rgba string. */
const IVORY_10 = "rgba(232,221,200,0.10)";

/** Bounded ripple for rows, bars, and bordered buttons. `undefined` on iOS
 * so the prop is a no-op there. */
export function ripple(): PressableAndroidRippleConfig | undefined {
  return select<PressableAndroidRippleConfig | undefined>({
    ios: undefined,
    android: { color: IVORY_10 },
  });
}

/** Borderless ripple for small quiet affordances (the back chevron) — the
 * Android-native halo, still ivory. */
export function rippleBorderless(): PressableAndroidRippleConfig | undefined {
  return select<PressableAndroidRippleConfig | undefined>({
    ios: undefined,
    android: { color: IVORY_10, borderless: true },
  });
}
