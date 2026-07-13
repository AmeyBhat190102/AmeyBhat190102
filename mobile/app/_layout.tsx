import {
  CormorantGaramond_500Medium,
  CormorantGaramond_600SemiBold,
} from "@expo-google-fonts/cormorant-garamond";
import { Inter_400Regular, Inter_500Medium } from "@expo-google-fonts/inter";
import { useFonts } from "expo-font";
import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { View } from "react-native";
import { colors } from "../src/theme";

export default function RootLayout() {
  const [loaded] = useFonts({
    CormorantGaramond_500Medium,
    CormorantGaramond_600SemiBold,
    Inter_400Regular,
    Inter_500Medium,
  });
  if (!loaded) return <View style={{ flex: 1, backgroundColor: colors.ink }} />;

  return (
    <>
      <StatusBar style="light" />
      <Stack
        screenOptions={{
          headerShown: false,
          contentStyle: { backgroundColor: colors.ink },
          animation: "fade",
        }}
      />
    </>
  );
}
