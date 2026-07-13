/** The quiet way back — a chevron and a word, top-left, never a button.
 * On Android it mirrors system back (hardware/gesture back does the same
 * thing) and answers touch with a borderless ivory halo, the native voice
 * for small quiet affordances. Extra hitSlop lifts the target past 48dp. */

import { Pressable, Text } from "react-native";
import { select } from "../platformHint";
import { rippleBorderless } from "../ripple";
import { colors, fonts, spacing } from "../theme";

export function QuietBack({ label, onPress }: { label: string; onPress: () => void }) {
  const pressedOpacity = select({ ios: 0.5, android: 1 });
  return (
    <Pressable
      onPress={onPress}
      hitSlop={select({ ios: 12, android: 16 })}
      android_ripple={rippleBorderless()}
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
