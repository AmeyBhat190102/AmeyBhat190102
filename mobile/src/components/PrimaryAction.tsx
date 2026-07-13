/** The one gold action a screen is allowed — a full-width bar, foil on ink.
 * On iOS it sits pinned above the home indicator (place it in
 * ScreenShell's footer). */

import { Pressable, Text } from "react-native";
import { tapConfirm } from "../haptics";
import { select } from "../platformHint";
import { colors, fonts, radius, spacing } from "../theme";

export function PrimaryAction({
  label,
  onPress,
  disabled = false,
}: {
  label: string;
  onPress: () => void;
  disabled?: boolean;
}) {
  const pressedOpacity = select({ ios: 0.6, android: 0.8 });
  return (
    <Pressable
      onPress={() => {
        tapConfirm();
        onPress();
      }}
      disabled={disabled}
      style={({ pressed }) => ({
        backgroundColor: colors.gold,
        borderRadius: radius.sm,
        paddingVertical: select({ ios: spacing.md, android: spacing.md }),
        alignItems: "center",
        opacity: disabled ? 0.35 : pressed ? pressedOpacity : 1,
      })}
    >
      <Text
        style={{
          fontFamily: fonts.bodyMedium,
          fontSize: 14,
          letterSpacing: 0.8,
          color: colors.ink,
        }}
      >
        {label}
      </Text>
    </Pressable>
  );
}
