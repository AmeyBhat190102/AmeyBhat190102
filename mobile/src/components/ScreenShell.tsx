/** The room every screen lives in: ink walls, editorial margins, and an
 * optional action bar pinned above the home indicator (iOS rhythm — the
 * Android agent may move it into a bottom bar of its own). */

import { ReactNode } from "react";
import { ScrollView, View, ViewStyle } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { select } from "../platformHint";
import { colors, spacing } from "../theme";

export function ScreenShell({
  children,
  footer,
  scroll = true,
  contentStyle,
}: {
  children: ReactNode;
  /** Pinned below the scroll area — the single gold action lives here. */
  footer?: ReactNode;
  scroll?: boolean;
  contentStyle?: ViewStyle;
}) {
  const insets = useSafeAreaInsets();
  const padTop = insets.top + select({ ios: spacing.md, android: spacing.md });
  const padBottom = footer ? spacing.lg : Math.max(insets.bottom, spacing.xl);

  const body = (
    <View
      style={[
        {
          paddingTop: padTop,
          paddingHorizontal: spacing.lg,
          paddingBottom: padBottom,
        },
        contentStyle,
      ]}
    >
      {children}
    </View>
  );

  return (
    <View style={{ flex: 1, backgroundColor: colors.ink }}>
      {scroll ? (
        <ScrollView
          style={{ flex: 1 }}
          contentInsetAdjustmentBehavior="never"
          showsVerticalScrollIndicator={false}
        >
          {body}
        </ScrollView>
      ) : (
        <View style={{ flex: 1 }}>{body}</View>
      )}
      {footer ? (
        <View
          style={{
            paddingHorizontal: spacing.lg,
            paddingTop: spacing.md,
            // iOS: clear the home indicator. Android: gesture-nav insets run
            // tighter than the iOS indicator, so give the gold bar a little
            // air above the navigation area rather than sitting flush on it.
            paddingBottom: select({
              ios: Math.max(insets.bottom, spacing.lg),
              android: Math.max(insets.bottom + spacing.sm, spacing.lg),
            }),
            borderTopWidth: 1,
            borderTopColor: colors.hairline,
            backgroundColor: colors.ink,
          }}
        >
          {footer}
        </View>
      ) : null}
    </View>
  );
}
