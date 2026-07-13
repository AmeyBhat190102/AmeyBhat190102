/** Haptics, iOS only — the quiet tick of a well-made drawer. Android gets
 * ripple feedback instead (owned by the Android agent), so these are no-ops
 * there. All guards go through platformHint so the review rig stays honest. */

import * as Haptics from "expo-haptics";
import { Platform } from "react-native";
import { platformOS } from "./platformHint";

function onIOS(): boolean {
  // Real device only — the web review rig should never invoke native haptics.
  return Platform.OS === "ios" && platformOS() === "ios";
}

/** A selection changed — picking an artifact row, choosing a design. */
export function tapPick(): void {
  if (onIOS()) void Haptics.selectionAsync().catch(() => {});
}

/** A commitment — the primary action, "This is the one". */
export function tapConfirm(): void {
  if (onIOS()) void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium).catch(() => {});
}
