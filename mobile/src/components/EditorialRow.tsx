/** An editorial list row — a name in display type, a reason beneath, a
 * hairline above. The home threshold and the wizard's artifact step both
 * read from these. Never a card. */

import { Pressable, Text, View } from "react-native";
import { tapPick } from "../haptics";
import { select } from "../platformHint";
import { ripple } from "../ripple";
import { colors, fonts, label, spacing } from "../theme";
import { DisplayText } from "./DisplayText";
import { Hairline } from "./GoldRule";

export function EditorialRow({
  index,
  name,
  reason,
  selected = false,
  onPress,
}: {
  index: number;
  name: string;
  reason: string;
  selected?: boolean;
  onPress?: () => void;
}) {
  // iOS speaks in pressed-opacity; Android answers with an ivory ripple.
  const pressedOpacity = select({ ios: 0.55, android: 1 });
  return (
    <View>
      <Hairline />
      <Pressable
        onPress={
          onPress
            ? () => {
                tapPick();
                onPress();
              }
            : undefined
        }
        disabled={!onPress}
        android_ripple={ripple()}
        style={({ pressed }) => ({
          paddingVertical: select({ ios: spacing.lg, android: spacing.lg }),
          flexDirection: "row",
          opacity: pressed ? pressedOpacity : 1,
        })}
      >
        <Text
          style={[
            label,
            {
              color: selected ? colors.goldBright : colors.gold,
              width: 34,
              marginTop: select({ ios: 8, android: 7 }),
            },
          ]}
        >
          {String(index + 1).padStart(2, "0")}
        </Text>
        <View style={{ flex: 1 }}>
          <DisplayText size="name" color={selected ? colors.goldBright : colors.ivoryBright}>
            {name}
          </DisplayText>
          <Text
            style={{
              fontFamily: fonts.body,
              fontSize: 13,
              lineHeight: 19,
              color: colors.ivoryDim,
              marginTop: spacing.xs,
            }}
          >
            {reason}
          </Text>
        </View>
        {selected ? (
          <Text style={[label, { color: colors.goldBright, marginTop: select({ ios: 8, android: 7 }) }]}>
            chosen
          </Text>
        ) : null}
      </Pressable>
    </View>
  );
}
