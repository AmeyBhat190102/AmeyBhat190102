# MOBILE_DESIGN.md — the standard the supervisor enforces

The AURA Studio mobile app must speak the exact design language of the website (`web/WEBSITE.md`, `web/src/app/globals.css`): **a dark gallery you walk through, not an app you operate.** The stop condition for the build loop: frames are indistinguishable in voice from the website, and could not be mistaken for a template or an "AI-made" layout.

## Non-negotiables (supervisor rejects on sight)

1. **Palette discipline.** Only tokens from `src/theme.ts`. Ink `#14100c` rooms — never pure black, never grey cards on black. Gold is *foil*: one accent per view region, used for labels, rules, and the single primary action. Crimson only for errors.
2. **Type carries the design.** Cormorant Garamond for display (screen titles, artifact names, numbers that matter), Inter for UI. Labels are uppercase, 10px, letterSpacing ≥ 3 — the web's small-caps voice. No default system font anywhere.
3. **Whitespace is the status signal.** Generous vertical rhythm (`spacing.xl+` between sections). If a screen feels dense, it's wrong.
4. **Hairline gold rules** (1px, gradient or 16% ivory) as dividers — never boxed cards with visible borders on all four sides, never elevation shadows on containers.
5. **The anti-"AI-made" test.** Reject anything that pattern-matches generic app UI: centered-everything hero + three feature cards, emoji as icons, pill buttons with heavy rounding (radius > 6), gradient buttons, glassmorphism, drop-shadowed cards, placeholder-grey blocks, lorem copy. Copy must sound like the studio ("The studio is working", "This is the one") — never "Get Started Now!".

## Platform voice (identical brand, native rhythm)

All platform branching goes through `src/platformHint.ts: platformOS()/select()` — never `Platform.OS` directly (the review rig depends on it).

- **iOS agent owns:** iOS reading rhythm — larger display sizes, tighter line heights; back affordance top-left as a quiet chevron + label; primary actions as full-width gold bars pinned above the home indicator; scroll feels editorial (large title that condenses is welcome). Haptics (`expo-haptics`) on pick/confirm.
- **Android agent owns:** Material-adjacent behaviors without Material's look — ripple feedback (`android_ripple`, ivory at 10%), slightly smaller display type, left-aligned headers, system back handled; primary action may sit as a bottom bar (not a FAB — no FABs, ever).

## The four screens

1. **Home** — the studio's threshold. Wordmark, one line of thesis, artifact types as an editorial list (name + one-line *reason*, hairline-ruled), single gold action: "Start a project". A quiet footer line. No feature grids.
2. **New (brief wizard)** — one question per screen feel: artifact choice as full-width editorial rows, then presence textarea, then hard facts. Progress as a thin gold line, not dots. Ends with "Open the studio".
3. **Studio (running)** — the agent theater, mobile-sized: aura card (archetype + palette swatches) at top once read; the crew as a vertical list (role, assignment, status in small caps); narration lines beneath. Running items pulse gold subtly.
4. **Studio (done → gallery)** — the reveal: full-bleed card preview images, one per viewport-height section; risk label in small caps, direction name in display type, rationale beneath; "This is the one" as a hairline-bordered quiet button that fills gold when picked; unlock bar at the end.

Sample data for all states comes from `src/sample.ts` (design-review mode renders it automatically).

## Review loop protocol

- Frames are produced by `npm run screenshots` at iPhone 15 (390×844@3x) and Pixel 8 (412×915@2.6x) — three routes each.
- The supervisor scores each frame 0–10 on: palette discipline, type voice, whitespace, platform rhythm, anti-AI-tells, copy voice. **Approve only when every frame ≥ 8 and no non-negotiable is violated.**
- Supervisor feedback must be actionable per platform ("Android home: header is centered — left-align; ripple missing on artifact rows"), and agents address every note or argue why not.
