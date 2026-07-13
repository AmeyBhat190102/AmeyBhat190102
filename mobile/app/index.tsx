/** Home — the studio's threshold. A wordmark, one thesis, the work we take
 * on as an editorial list, and a single gold action. No feature grids. */

import { useRouter } from "expo-router";
import { Text, View } from "react-native";
import { DisplayText } from "../src/components/DisplayText";
import { EditorialRow } from "../src/components/EditorialRow";
import { GoldRule } from "../src/components/GoldRule";
import { Label } from "../src/components/Label";
import { PrimaryAction } from "../src/components/PrimaryAction";
import { ScreenShell } from "../src/components/ScreenShell";
import { Wordmark } from "../src/components/Wordmark";
import { ARTIFACTS } from "../src/copy";
import { select } from "../src/platformHint";
import { colors, fonts, spacing } from "../src/theme";

export default function Home() {
  const router = useRouter();

  return (
    <ScreenShell
      footer={<PrimaryAction label="Start a project" onPress={() => router.push("/new")} />}
    >
      <Wordmark />

      <View style={{ marginTop: select({ ios: spacing.xxl, android: spacing.xl }) }}>
        <Label>An AI design studio with standards</Label>
        <DisplayText size="hero" style={{ marginTop: spacing.md }}>
          We don’t generate designs.{"\n"}We translate{" "}
          <DisplayText size="hero" color={colors.goldBright}>
            presence
          </DisplayText>
          .
        </DisplayText>
        <Text
          style={{
            fontFamily: fonts.body,
            fontSize: 14,
            lineHeight: select({ ios: 21, android: 22 }),
            color: colors.ivoryDim,
            marginTop: spacing.lg,
            maxWidth: 320,
          }}
        >
          Twenty years of quiet authority. A family’s occasion. A product’s heft.
          The things that make you unmistakable rarely survive the trip onto a
          card. Our studio of AI specialists exists to carry them across.
        </Text>
        <GoldRule style={{ marginTop: spacing.xl }} />
      </View>

      <View style={{ marginTop: select({ ios: spacing.xxl, android: spacing.xl }) }}>
        <Label style={{ marginBottom: spacing.lg }}>What we make</Label>
        {ARTIFACTS.map((a, i) => (
          <EditorialRow
            key={a.key}
            index={i}
            name={a.name}
            reason={a.reason}
            onPress={() => router.push("/new")}
          />
        ))}
      </View>

      <Text
        style={{
          fontFamily: fonts.display,
          fontSize: 16,
          color: colors.ivoryDim,
          marginTop: spacing.xxl,
        }}
      >
        Designs that carry who you are.
      </Text>
    </ScreenShell>
  );
}
