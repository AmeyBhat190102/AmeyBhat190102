/** Hairline rules — the gallery's only architecture. Never a boxed card. */

import { DimensionValue, View, ViewStyle } from "react-native";
import { colors } from "../theme";

export function GoldRule({
  width = 56,
  center = false,
  style,
}: {
  width?: DimensionValue;
  center?: boolean;
  style?: ViewStyle;
}) {
  return (
    <View
      style={[
        {
          width,
          height: 1,
          backgroundColor: colors.gold,
          opacity: 0.55,
          alignSelf: center ? "center" : "flex-start",
        },
        style,
      ]}
    />
  );
}

/** Ivory hairline at 16% — the divider between editorial rows. */
export function Hairline({ style }: { style?: ViewStyle }) {
  return <View style={[{ height: 1, backgroundColor: colors.hairline }, style]} />;
}
