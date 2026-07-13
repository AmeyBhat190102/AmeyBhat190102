/** The quiet way back — a chevron and a word, top-left, never a button.
 * iOS voice; Android placeholder stays close (system back is the Android
 * agent's concern). */

import { Pressable, Text } from "react-native";
import { select } from "../platformHint";
import { colors, fonts, spacing } from "../theme";

export function QuietBack({ label, onPress }: { label: string; onPress: () => void }) {
  const pressedOpacity = select({ ios: 0.5, android: 0.7 });
  return (
    <Pressable
      onPress={onPress}
      hitSlop={12}
      style={({ pressed }) => ({
        flexDirection: "row",
        alignItems: "center",
        alignSelf: "flex-start",
        opacity: pressed ? pressedOpacity : 1,
        marginBottom: spacing.xl,
      })}
    >
      <Text
        style={{
          fontFamily: fonts.body,
          fontSize: select({ ios: 20, android: 18 }),
          lineHeight: 20,
          color: colors.gold,
          marginRight: spacing.xs,
          marginTop: select({ ios: -2, android: -1 }),
        }}
      >
        {"‹"}
      </Text>
      <Text style={{ fontFamily: fonts.body, fontSize: 14, color: colors.ivoryDim }}>
        {label}
      </Text>
    </Pressable>
  );
}
