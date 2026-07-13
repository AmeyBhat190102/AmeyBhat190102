/** AURA Studio — the wordmark, exactly as the website sets it. */

import { Text } from "react-native";
import { colors, fonts } from "../theme";

export function Wordmark({ size = 21 }: { size?: number }) {
  return (
    <Text
      style={{
        fontFamily: fonts.display,
        fontSize: size,
        letterSpacing: 1.5,
        color: colors.ivoryBright,
      }}
    >
      AURA <Text style={{ color: colors.gold }}>Studio</Text>
    </Text>
  );
}
