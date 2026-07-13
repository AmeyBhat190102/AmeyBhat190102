/** The crew, as a call sheet: role, assignment, and status in small caps.
 * Running work pulses gold, softly — frozen in design review so frames are
 * deterministic. */

import { useEffect, useRef } from "react";
import { Animated, Text, View } from "react-native";
import { DESIGN_REVIEW } from "../api";
import { ROLE_LABELS, STATUS_LABELS } from "../copy";
import { select } from "../platformHint";
import { TaskInfo } from "../sample";
import { colors, fonts, label, spacing } from "../theme";
import { Hairline } from "./GoldRule";

const STATUS_COLOR: Record<TaskInfo["status"], string> = {
  pending: colors.ivoryDim,
  running: colors.goldBright,
  succeeded: colors.ivory,
  failed: colors.crimson,
  skipped: colors.ivoryDim,
  budget_denied: colors.ivoryDim,
};

export function CrewList({ tasks }: { tasks: TaskInfo[] }) {
  return (
    <View>
      {tasks.map((t) => (
        <CrewRow key={t.task_id} task={t} />
      ))}
      <Hairline />
    </View>
  );
}

function CrewRow({ task }: { task: TaskInfo }) {
  const running = task.status === "running";
  const dimmed = task.status === "pending" || task.status === "skipped" || task.status === "budget_denied";
  const pulse = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    if (!running || DESIGN_REVIEW) return;
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, { toValue: 0.55, duration: 1100, useNativeDriver: true }),
        Animated.timing(pulse, { toValue: 1, duration: 1100, useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [running, pulse]);

  return (
    <View>
      <Hairline />
      <Animated.View
        style={{
          paddingVertical: select({ ios: spacing.md, android: spacing.md }),
          opacity: running ? pulse : dimmed ? 0.45 : 1,
        }}
      >
        <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "baseline" }}>
          <Text style={[label, { color: running ? colors.goldBright : colors.gold }]}>
            {ROLE_LABELS[task.role_key] ?? task.role_key.replace(/_/g, " ")}
          </Text>
          <Text style={[label, { color: STATUS_COLOR[task.status] }]}>
            {STATUS_LABELS[task.status] ?? task.status}
          </Text>
        </View>
        <Text
          style={{
            fontFamily: fonts.body,
            fontSize: 14,
            lineHeight: 20,
            color: running ? colors.ivoryBright : colors.ivory,
            marginTop: spacing.sm,
          }}
        >
          {task.title}
        </Text>
      </Animated.View>
    </View>
  );
}
