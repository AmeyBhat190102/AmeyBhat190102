/** The studio: the agent theater while the crew works, the gallery reveal
 * when the lights come up. Route id "sample-running" shows the sample
 * project mid-run so the theater can be reviewed. */

import { useLocalSearchParams, useRouter } from "expo-router";
import { useEffect, useState } from "react";
import { Text, View } from "react-native";
import { getProject } from "../../src/api";
import { AuraCard } from "../../src/components/AuraCard";
import { CrewList } from "../../src/components/CrewList";
import { DisplayText } from "../../src/components/DisplayText";
import { GalleryPiece } from "../../src/components/GalleryPiece";
import { GoldRule } from "../../src/components/GoldRule";
import { Label } from "../../src/components/Label";
import { PrimaryAction } from "../../src/components/PrimaryAction";
import { QuietBack } from "../../src/components/QuietBack";
import { ScreenShell } from "../../src/components/ScreenShell";
import { Project, TaskInfo } from "../../src/sample";
import { select } from "../../src/platformHint";
import { colors, fonts, spacing } from "../../src/theme";

export default function Studio() {
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const routeId = id ?? "sample";
  // "sample-running" reviews the theater: same sample data, mid-run.
  const forceRunning = routeId === "sample-running";
  const fetchId = forceRunning ? "sample" : routeId;

  const [project, setProject] = useState<Project | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    async function load() {
      try {
        const p = await getProject(fetchId);
        if (!alive) return;
        setProject(forceRunning ? { ...p, status: "running" } : p);
        // The theater keeps watch until the lights come up.
        if (!forceRunning && p.status !== "done" && p.status !== "failed") {
          timer = setTimeout(load, 4000);
        }
      } catch {
        if (alive) setFailed(true);
      }
    }
    void load();
    return () => {
      alive = false;
      if (timer) clearTimeout(timer);
    };
  }, [fetchId, forceRunning]);

  const back = (
    <QuietBack
      label="Studio"
      onPress={() => (router.canGoBack() ? router.back() : router.replace("/"))}
    />
  );

  if (failed) {
    return (
      <ScreenShell>
        {back}
        <Label color={colors.crimson}>Unreachable</Label>
        <DisplayText size="title" style={{ marginTop: spacing.md }}>
          The studio door didn’t open.
        </DisplayText>
        <Text style={quiet}>
          We couldn’t reach this project. Check the connection and walk back in.
        </Text>
      </ScreenShell>
    );
  }

  if (!project) {
    return (
      <ScreenShell scroll={false} contentStyle={{ flex: 1, justifyContent: "center" }}>
        <Label>One moment</Label>
        <DisplayText size="title" style={{ marginTop: spacing.md }}>
          The studio lights are on…
        </DisplayText>
      </ScreenShell>
    );
  }

  return project.status === "done" && project.package ? (
    <Gallery project={project} back={back} />
  ) : (
    <Theater project={project} back={back} />
  );
}

/* ————— The theater: the crew at work ————— */

function Theater({ project, back }: { project: Project; back: React.ReactNode }) {
  return (
    <ScreenShell>
      {back}
      <Label>The agent theater</Label>
      <DisplayText size="hero" style={{ marginTop: spacing.md }}>
        The studio is working.
      </DisplayText>
      <Text style={quiet}>
        The producer has cast a crew for your brief alone. Specialists work in
        parallel; the critic stands at the door.
      </Text>

      {project.package?.aura ? (
        <View style={{ marginTop: select({ ios: spacing.xl, android: spacing.xl }) }}>
          <AuraCard aura={project.package.aura} />
        </View>
      ) : null}

      <View style={{ marginTop: select({ ios: spacing.xxl, android: spacing.xl }) }}>
        <Label style={{ marginBottom: spacing.lg }}>The crew</Label>
        <CrewList tasks={project.tasks} />
      </View>

      <View style={{ marginTop: select({ ios: spacing.xxl, android: spacing.xl }) }}>
        <Label style={{ marginBottom: spacing.lg }}>From the floor</Label>
        {narration(project).map((n, i) => (
          <View key={i} style={{ flexDirection: "row", marginBottom: spacing.md }}>
            <Label style={{ width: 78, marginTop: 3 }}>{n.tag}</Label>
            <Text
              style={{
                flex: 1,
                fontFamily: fonts.body,
                fontSize: 14,
                lineHeight: select({ ios: 21, android: 22 }),
                color: colors.ivory,
              }}
            >
              {n.text}
            </Text>
          </View>
        ))}
      </View>
    </ScreenShell>
  );
}

function narration(project: Project): { tag: string; text: string }[] {
  const lines: { tag: string; text: string }[] = [];
  if (project.package?.aura) {
    lines.push({ tag: "Aura", text: project.package.aura.archetype });
  }
  if (project.tasks.length > 0) {
    lines.push({
      tag: "Producer",
      text: `Crew cast — ${project.tasks.length} assignments for this brief.`,
    });
  }
  for (const t of project.tasks) {
    if (t.status === "succeeded") {
      lines.push({ tag: "Studio", text: `${t.title} has developed.` });
    } else if (t.status === "running") {
      lines.push({ tag: "Studio", text: `${t.title} is on the easel.` });
    } else if (t.status === "failed") {
      lines.push({ tag: "Critic", text: `${t.title} was killed. The crew moves on.` });
    }
  }
  if (project.tasks.some((t: TaskInfo) => t.status === "running")) {
    lines.push({ tag: "Critic", text: "Standing by. Weak work goes back with notes." });
  }
  return lines;
}

/* ————— The gallery: the reveal ————— */

function Gallery({ project, back }: { project: Project; back: React.ReactNode }) {
  const [picked, setPicked] = useState<string | null>(null);
  const pkg = project.package!;
  const rationaleBy = Object.fromEntries(pkg.rationales.map((r) => [r.candidate_id, r]));

  return (
    <ScreenShell
      footer={
        !project.paid ? (
          <PrimaryAction
            label="Unlock this project"
            onPress={() => {
              /* checkout arrives with payment integration */
            }}
          />
        ) : undefined
      }
    >
      {back}
      <Label>Your gallery</Label>
      <DisplayText size="hero" style={{ marginTop: spacing.md }}>
        {pkg.selected.length} designs.{"\n"}One is unmistakably you.
      </DisplayText>
      <Text style={quiet}>{pkg.aura.essence_statement}</Text>
      <GoldRule style={{ marginTop: spacing.xl }} />

      <View style={{ marginTop: select({ ios: spacing.xxl, android: spacing.xl }), gap: spacing.xxl }}>
        {pkg.selected.map((c) => (
          <GalleryPiece
            key={c.candidate_id}
            projectId={project.project_id}
            piece={c}
            rationale={rationaleBy[c.candidate_id]}
            picked={picked === c.candidate_id}
            onPick={() => setPicked(c.candidate_id)}
          />
        ))}
      </View>

      {pkg.rejected_count > 0 ? (
        <Text
          style={{
            fontFamily: fonts.body,
            fontSize: 12,
            lineHeight: 18,
            color: colors.ivoryDim,
            opacity: 0.7,
            marginTop: spacing.xxl,
          }}
        >
          {pkg.rejected_count === 1
            ? "One direction didn’t survive the critic."
            : `${pkg.rejected_count} directions didn’t survive the critic.`}
        </Text>
      ) : null}

      {!project.paid ? (
        <View style={{ marginTop: spacing.xl }}>
          <GoldRule />
          <DisplayText size="title" style={{ marginTop: spacing.xl }}>
            Take it home.
          </DisplayText>
          <Text style={quiet}>
            Print-ready PDFs at true physical dimensions, full-resolution files,
            and the design source — yours forever, revisable on request.
          </Text>
        </View>
      ) : null}
    </ScreenShell>
  );
}

const quiet = {
  fontFamily: fonts.body,
  fontSize: 14,
  lineHeight: 21,
  color: colors.ivoryDim,
  marginTop: spacing.lg,
  maxWidth: 330,
} as const;
