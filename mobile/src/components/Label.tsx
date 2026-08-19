/** The small-caps voice — uppercase, wide tracking, usually gold foil. */

import { StyleProp, Text, TextStyle } from "react-native";
import { colors, label } from "../theme";

export function Label({
  children,
  color = colors.gold,
  style,
}: {
  children: React.ReactNode;
  color?: string;
  style?: StyleProp<TextStyle>;
}) {
  return <Text style={[label, { color }, style]}>{children}</Text>;
}
