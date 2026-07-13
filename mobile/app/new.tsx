import { Text, View } from "react-native";
import { colors, fonts } from "../src/theme";

/** Brief wizard — placeholder. The platform agents own this screen. */
export default function NewProject() {
  return (
    <View style={{ flex: 1, backgroundColor: colors.ink, alignItems: "center", justifyContent: "center" }}>
      <Text style={{ fontFamily: fonts.body, color: colors.ivoryDim }}>Brief wizard</Text>
    </View>
  );
}
