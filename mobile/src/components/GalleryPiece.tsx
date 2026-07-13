/** One piece on the gallery wall: the work full-bleed, then the reading —
 * risk in small caps, the direction's name in display type, the rationale
 * beneath, and the quiet claim button that fills gold when it's the one. */

import { Image, Pressable, Text, useWindowDimensions, View } from "react-native";
import { fileUrl } from "../api";
import { RISK_LABELS } from "../copy";
import { tapConfirm } from "../haptics";
import { select } from "../platformHint";
import { ripple } from "../ripple";
import { SAMPLE_CARD, SelectedCandidate } from "../sample";
import { colors, fonts, radius, spacing } from "../theme";
import { DisplayText } from "./DisplayText";
import { Label } from "./Label";

/** The engine's card renders are 1050×960. Height is set explicitly (not
 * via aspectRatio style) because react-native-web lets a static asset's
 * intrinsic height win over the CSS aspect-ratio. */
const CARD_ASPECT = 1050 / 960;

export function GalleryPiece({
  projectId,
  piece,
  rationale,
  picked,
  onPick,
}: {
  projectId: string;
  piece: SelectedCandidate;
  rationale?: { headline: string; body: string };
  picked: boolean;
  onPick: () => void;
}) {
  // iOS: pressed-opacity. Android: ivory ripple, 48dp claim button.
  const pressedOpacity = select({ ios: 0.6, android: 1 });
  // GalleryPiece hangs inside ScreenShell's editorial margins.
  const { width: windowWidth } = useWindowDimensions();
  const imageWidth = windowWidth - spacing.lg * 2;
  return (
    <View>
      {piece.preview_artifact_ids.map((artifactId) => (
        <Image
          key={artifactId}
          source={
            artifactId === "sample"
              ? SAMPLE_CARD
              : { uri: fileUrl(projectId, artifactId) }
          }
          resizeMode="cover"
          accessibilityLabel={piece.direction.name}
          style={{
            width: imageWidth,
            height: Math.round(imageWidth / CARD_ASPECT),
            borderRadius: radius.sm,
            backgroundColor: colors.inkSoft,
          }}
        />
      ))}

      <View style={{ marginTop: spacing.lg }}>
        <Label>{RISK_LABELS[piece.direction.risk_level] ?? piece.direction.risk_level}</Label>
        <DisplayText size="title" style={{ marginTop: spacing.sm }}>
          {piece.direction.name}
        </DisplayText>
        {rationale ? (
          <>
            <Text
              style={{
                fontFamily: fonts.body,
                fontSize: 16,
                lineHeight: select({ ios: 23, android: 24 }),
                color: colors.ivory,
                marginTop: spacing.md,
              }}
            >
              {rationale.headline}
            </Text>
            <Text
              style={{
                fontFamily: fonts.body,
                fontSize: 13,
                lineHeight: select({ ios: 20, android: 21 }),
                color: colors.ivoryDim,
                marginTop: spacing.sm,
              }}
            >
              {rationale.body}
            </Text>
          </>
        ) : null}
        <Text
          style={{
            fontFamily: fonts.body,
            fontSize: 12,
            lineHeight: 18,
            color: colors.ivoryDim,
            opacity: 0.7,
            marginTop: spacing.md,
          }}
        >
          {piece.direction.thesis}
        </Text>

        <Pressable
          onPress={() => {
            tapConfirm();
            onPick();
          }}
          android_ripple={ripple()}
          style={({ pressed }) => ({
            alignSelf: "flex-start",
            marginTop: spacing.lg,
            paddingVertical: spacing.sm + 2,
            paddingHorizontal: spacing.lg,
            minHeight: select<number | undefined>({ ios: undefined, android: 48 }),
            justifyContent: "center",
            borderRadius: radius.sm,
            borderWidth: 1,
            borderColor: picked ? colors.gold : colors.hairline,
            backgroundColor: picked ? colors.gold : "transparent",
            // Clip the ripple to the quiet button's corners on Android.
            overflow: select<"visible" | "hidden">({ ios: "visible", android: "hidden" }),
            opacity: pressed ? pressedOpacity : 1,
          })}
        >
          <Text
            style={{
              fontFamily: fonts.bodyMedium,
              fontSize: 13,
              letterSpacing: 0.4,
              color: picked ? colors.ink : colors.ivory,
            }}
          >
            {picked ? "Your choice" : "This is the one"}
          </Text>
        </Pressable>
      </View>
    </View>
  );
}
