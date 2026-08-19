/** The aura reading — the visual constitution the crew obeys. A single
 * gold-edged passage, never a boxed card. */

import { Text, View } from "react-native";
import { select } from "../platformHint";
import { Project } from "../sample";
import { colors, fonts, spacing } from "../theme";
import { DisplayText } from "./DisplayText";
import { Label } from "./Label";

export function AuraCard({ aura }: { aura: NonNullable<Project["package"]>["aura"] }) {
  const swatches = [...aura.palette.primary_hex, ...aura.palette.accent_hex];
  return (
    <View
      style={{
        borderLeftWidth: 1,
        borderLeftColor: colors.gold,
        paddingLeft: spacing.lg,
        paddingVertical: spacing.xs,
      }}
    >
      <Label>Aura reading</Label>
      <DisplayText size="line" style={{ marginTop: spacing.sm }}>
        {aura.archetype}
      </DisplayText>
      <Text
        style={{
          fontFamily: fonts.body,
          fontSize: 13,
          lineHeight: select({ ios: 20, android: 21 }),
          color: colors.ivoryDim,
          marginTop: spacing.sm,
        }}
      >
        {aura.adjectives.join(" · ")}
      </Text>
      <View style={{ flexDirection: "row", gap: spacing.sm, marginTop: spacing.md }}>
        {swatches.map((hex) => (
          <View
            key={hex}
            style={{
              width: 18,
              height: 18,
              borderRadius: 9,
              backgroundColor: hex,
              borderWidth: 1,
              borderColor: colors.hairline,
            }}
          />
        ))}
      </View>
    </View>
  );
}
