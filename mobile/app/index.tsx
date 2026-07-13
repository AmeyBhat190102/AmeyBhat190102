import { Text, View } from "react-native";
import { colors, fonts } from "../src/theme";

/** Home — placeholder. The platform agents own this screen. */
export default function Home() {
  return (
    <View style={{ flex: 1, backgroundColor: colors.ink, alignItems: "center", justifyContent: "center" }}>
      <Text style={{ fontFamily: fonts.display, fontSize: 28, color: colors.ivoryBright }}>
        AURA <Text style={{ color: colors.gold }}>Studio</Text>
      </Text>
    </View>
  );
}
