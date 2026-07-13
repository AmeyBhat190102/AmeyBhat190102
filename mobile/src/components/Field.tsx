/** A form field the studio's way: small-caps label above, ivory type on a
 * hairline underline. No filled boxes, no grey blocks. */

import { Text, TextInput, View } from "react-native";
import { select } from "../platformHint";
import { colors, fonts, spacing } from "../theme";
import { Label } from "./Label";

export function Field({
  label,
  value,
  onChangeText,
  placeholder,
  hint,
  multiline = false,
}: {
  label: string;
  value: string;
  onChangeText: (v: string) => void;
  placeholder?: string;
  hint?: string;
  multiline?: boolean;
}) {
  return (
    <View>
      <Label>{label}</Label>
      <TextInput
        value={value}
        onChangeText={onChangeText}
        placeholder={placeholder}
        placeholderTextColor={`${colors.ivoryDim}66`}
        multiline={multiline}
        keyboardAppearance="dark"
        cursorColor={colors.gold}
        selectionColor={colors.gold}
        style={{
          fontFamily: fonts.body,
          fontSize: 16,
          lineHeight: select({ ios: 24, android: 25 }),
          color: colors.ivoryBright,
          paddingTop: spacing.sm,
          paddingBottom: spacing.sm + 2,
          paddingHorizontal: 0,
          minHeight: multiline ? 132 : undefined,
          textAlignVertical: multiline ? "top" : "auto",
          borderBottomWidth: 1,
          borderBottomColor: colors.hairline,
        }}
      />
      {hint ? (
        <Text
          style={{
            fontFamily: fonts.body,
            fontSize: 12,
            lineHeight: 18,
            color: colors.ivoryDim,
            opacity: 0.8,
            marginTop: spacing.sm,
          }}
        >
          {hint}
        </Text>
      ) : null}
    </View>
  );
}
