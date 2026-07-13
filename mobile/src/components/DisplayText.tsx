/** Cormorant display type — the voice that carries every screen.
 * iOS reads larger and tighter; Android values are placeholders close to
 * iOS, for the Android agent to refine. */

import { StyleProp, Text, TextStyle } from "react-native";
import { select } from "../platformHint";
import { colors, fonts } from "../theme";

type Size = "hero" | "title" | "name" | "line";

const SIZES: Record<Size, { ios: number; android: number }> = {
  hero: { ios: 40, android: 37 },   // the screen's one big statement
  title: { ios: 30, android: 28 },  // section / question headings
  name: { ios: 26, android: 24 },   // artifact and direction names
  line: { ios: 20, android: 19 },   // display-voice body lines
};

export function DisplayText({
  children,
  size = "title",
  semi = false,
  color = colors.ivoryBright,
  style,
}: {
  children: React.ReactNode;
  size?: Size;
  semi?: boolean;
  color?: string;
  style?: StyleProp<TextStyle>;
}) {
  const fontSize = select(SIZES[size]);
  const lineHeight = Math.round(fontSize * select({ ios: 1.08, android: 1.14 }));
  return (
    <Text
      style={[
        {
          fontFamily: semi ? fonts.displaySemi : fonts.display,
          fontSize,
          lineHeight,
          letterSpacing: select({ ios: -0.3, android: 0 }),
          color,
        },
        style,
      ]}
    >
      {children}
    </Text>
  );
}
