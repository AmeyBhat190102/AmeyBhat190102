/** The brief wizard — one question per screen, three steps in one route:
 * the artifact, the presence, the hard facts. Progress is a thin gold line,
 * and the last word is "Open the studio". */

import { useRouter } from "expo-router";
import { useEffect, useState } from "react";
import { BackHandler, KeyboardAvoidingView, Text, View } from "react-native";
import { createProject } from "../src/api";
import { DisplayText } from "../src/components/DisplayText";
import { EditorialRow } from "../src/components/EditorialRow";
import { Field } from "../src/components/Field";
import { Label } from "../src/components/Label";
import { PrimaryAction } from "../src/components/PrimaryAction";
import { QuietBack } from "../src/components/QuietBack";
import { ScreenShell } from "../src/components/ScreenShell";
import { ARTIFACTS } from "../src/copy";
import { platformOS, select } from "../src/platformHint";
import { colors, fonts, spacing } from "../src/theme";

const STEPS = ["The artifact", "The presence", "The hard facts"] as const;

export default function NewProject() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [artifact, setArtifact] = useState<string | null>(null);
  const [presence, setPresence] = useState("");
  const [name, setName] = useState("");
  const [line, setLine] = useState("");
  const [details, setDetails] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Android: hardware/gesture back walks the wizard back a step; only from
  // the first step does it leave the flow (fall through to the Stack pop).
  useEffect(() => {
    if (platformOS() !== "android") return;
    const sub = BackHandler.addEventListener("hardwareBackPress", () => {
      if (step > 0) {
        setStep((s) => s - 1);
        return true;
      }
      return false;
    });
    return () => sub.remove();
  }, [step]);

  const chosen = ARTIFACTS.find((a) => a.key === artifact);
  const canContinue =
    step === 0 ? artifact !== null :
    step === 1 ? presence.trim().length > 0 :
    name.trim().length > 0 && !busy;

  async function openStudio() {
    setBusy(true);
    setError(null);
    const brief = [
      `Artifact: ${chosen?.name ?? "Visiting cards"}.`,
      `Who this is for: ${presence.trim()}`,
      `Name, exactly as it must appear: ${name.trim()}.`,
      line.trim() ? `Line beneath the name: ${line.trim()}.` : "",
      details.trim() ? `Details to typeset: ${details.trim()}` : "",
    ].filter(Boolean).join("\n");
    try {
      const project = await createProject(brief);
      router.push(`/studio/${project.project_id}`);
    } catch {
      setError("The studio couldn’t be reached. Your brief is safe — try again.");
    } finally {
      setBusy(false);
    }
  }

  const footer = (
    <View>
      {error ? (
        <Text
          style={{
            fontFamily: fonts.body,
            fontSize: 13,
            lineHeight: 19,
            color: colors.crimson,
            marginBottom: spacing.md,
          }}
        >
          {error}
        </Text>
      ) : null}
      <PrimaryAction
        label={step < 2 ? "Continue" : busy ? "Opening the studio…" : "Open the studio"}
        disabled={!canContinue}
        onPress={() => (step < 2 ? setStep(step + 1) : void openStudio())}
      />
    </View>
  );

  return (
    <KeyboardAvoidingView
      style={{ flex: 1 }}
      behavior={platformOS() === "ios" ? "padding" : undefined}
    >
      <ScreenShell footer={footer}>
        <QuietBack
          label={step === 0 ? "Studio" : "Back"}
          onPress={() => (step === 0 ? router.back() : setStep(step - 1))}
        />

        {/* Progress: a thin gold line, never dots. */}
        <View style={{ height: 1, backgroundColor: colors.hairline }}>
          <View
            style={{
              height: 1,
              width: `${((step + 1) / STEPS.length) * 100}%`,
              backgroundColor: colors.gold,
            }}
          />
        </View>

        <View style={{ marginTop: select({ ios: spacing.xl, android: spacing.xl }) }}>
          <Label>
            {String(step + 1).padStart(2, "0")} of {String(STEPS.length).padStart(2, "0")} — {STEPS[step]}
          </Label>

          {step === 0 && (
            <>
              <DisplayText size="hero" style={{ marginTop: spacing.md }}>
                What are we making?
              </DisplayText>
              <Text style={helper}>
                Choose the piece. The producer casts the crew around this decision.
              </Text>
              <View style={{ marginTop: spacing.xl }}>
                {ARTIFACTS.map((a, i) => (
                  <EditorialRow
                    key={a.key}
                    index={i}
                    name={a.name}
                    reason={a.reason}
                    selected={artifact === a.key}
                    onPress={() => setArtifact(a.key)}
                  />
                ))}
              </View>
            </>
          )}

          {step === 1 && (
            <>
              <DisplayText size="hero" style={{ marginTop: spacing.md }}>
                Who is this for?
              </DisplayText>
              <Text style={helper}>
                Presence, not preferences. Write the way you’d introduce them to
                someone who matters — what they carry into a room, not what
                colours they like.
              </Text>
              <View style={{ marginTop: spacing.xl }}>
                <Field
                  label="The reading"
                  value={presence}
                  onChangeText={setPresence}
                  multiline
                  placeholder="Two decades of constitutional practice. A handshake: brief, firm, remembered."
                  hint="The aura agent studies every word of this."
                />
              </View>
            </>
          )}

          {step === 2 && (
            <>
              <DisplayText size="hero" style={{ marginTop: spacing.md }}>
                The hard facts.
              </DisplayText>
              <Text style={helper}>
                Exactly what must be typeset, spelled the way it should appear.
                The layout engine sets these at true physical size — image models
                never touch your letters.
              </Text>
              <View style={{ marginTop: spacing.xl, gap: spacing.xl }}>
                <Field
                  label="The name"
                  value={name}
                  onChangeText={setName}
                  placeholder="Adv. Meera Krishnan"
                />
                <Field
                  label="The line beneath"
                  value={line}
                  onChangeText={setLine}
                  placeholder="Senior Advocate · Constitutional Law"
                />
                <Field
                  label="Details to carry"
                  value={details}
                  onChangeText={setDetails}
                  multiline
                  placeholder="Chambers, telephone, the date that matters…"
                  hint="Phone, address, dates — whatever the piece must hold."
                />
              </View>
            </>
          )}
        </View>
      </ScreenShell>
    </KeyboardAvoidingView>
  );
}

const helper = {
  fontFamily: fonts.body,
  fontSize: 14,
  lineHeight: 21,
  color: colors.ivoryDim,
  marginTop: spacing.lg,
  maxWidth: 320,
} as const;
