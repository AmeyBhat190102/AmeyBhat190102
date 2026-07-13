/** The studio's aura, as mobile design tokens — the same language the
 * website speaks (web/src/app/globals.css): dark gallery, ivory type, one
 * gold accent used like foil. Platform code must draw ONLY from here. */

import { Platform } from "react-native";

export const colors = {
  ink: "#14100c",        // the room — warm near-black, never pure black
  inkSoft: "#1d1812",
  inkRaised: "#262019",
  ivory: "#e8ddc8",      // body type
  ivoryBright: "#f2ead6", // display type
  ivoryDim: "#cbbfa4",
  gold: "#b08d4f",       // the single accent — sparingly, like foil
  goldBright: "#d4af6a",
  crimson: "#8d3b2e",    // errors and kill verdicts only
  hairline: "rgba(203,191,164,0.16)",
} as const;

export const fonts = {
  display: "CormorantGaramond_500Medium",
  displaySemi: "CormorantGaramond_600SemiBold",
  body: "Inter_400Regular",
  bodyMedium: "Inter_500Medium",
} as const;

/** Label style: small caps feel via uppercase + wide tracking (the web's
 * `uppercase tracking-[0.35em]`). */
export const label = {
  fontFamily: fonts.bodyMedium,
  fontSize: 10,
  letterSpacing: 3.2,
  textTransform: "uppercase" as const,
  color: colors.gold,
};

export const spacing = { xs: 6, sm: 10, md: 16, lg: 24, xl: 36, xxl: 56 } as const;

export const radius = { sm: 4, md: 6 } as const;

/** Platform voice: identical brand, native rhythm. */
export const platform = Platform.select({
  ios: { pressedOpacity: 0.6, headerBlur: true },
  default: { pressedOpacity: 0.8, headerBlur: false },
});
