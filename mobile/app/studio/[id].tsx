import { useLocalSearchParams } from "expo-router";
import { Text, View } from "react-native";
import { colors, fonts } from "../../src/theme";

/** Studio: theater while running, gallery when done — placeholder.
 * The platform agents own this screen. */
export default function Studio() {
  const { id } = useLocalSearchParams<{ id: string }>();
  return (
    <View style={{ flex: 1, backgroundColor: colors.ink, alignItems: "center", justifyContent: "center" }}>
      <Text style={{ fontFamily: fonts.body, color: colors.ivoryDim }}>Project {id}</Text>
    </View>
  );
}
