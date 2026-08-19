# AURA Studio — mobile

The studio in your hand: Expo (React Native) app for **iOS and Android** from one codebase, speaking the exact design language of the website — dark gallery, ivory type, gold as foil, editorial and type-led. Four screens: the threshold (home), the brief wizard, the agent theater, and the gallery reveal.

Built by a supervised multi-agent loop: an iOS agent and an Android agent iterated the screens independently while a design-supervisor agent reviewed rendered frames each round against [`MOBILE_DESIGN.md`](MOBILE_DESIGN.md) — approving only when every frame scored ≥ 8 on palette discipline, type voice, whitespace, platform rhythm, anti-AI-tells, and copy voice. Approval landed in round 2.

## Run it

```bash
cd mobile && npm install

# On a device/simulator (engine reachable at EXPO_PUBLIC_ENGINE_URL):
EXPO_PUBLIC_ENGINE_URL=http://<your-host>:8800 npx expo start

# Ship builds via EAS:
#   npx eas build -p ios / -p android
```

No engine running? Screens fall back to a bundled sample project, and `EXPO_PUBLIC_DESIGN_REVIEW=1` forces that mode everywhere.

## Design review rig

```bash
npm run typecheck                         # tsc --noEmit
EXPO_PUBLIC_DESIGN_REVIEW=1 npm run screenshots
```

Exports the app to web, serves it, and captures every screen at iPhone 15 (390×844@3x) and Pixel 8 (412×915@2.6x) into `screenshots/` — the frames the supervisor judges. The `?platform=` hint (see `src/platformHint.ts`) makes each platform's branches render in the browser exactly as on device.

## How platform voice works

One brand, two rhythms. **All** platform branching goes through `src/platformHint.ts` (`select()` / `platformOS()`) — never `Platform.OS` in UI code:

- **iOS**: larger/tighter display type (40/1.08, −0.3 tracking), pressed-opacity feedback, `‹ Back` chevron+label, haptics on pick/confirm, keyboard-avoiding padding.
- **Android**: 36/1.16/0 display type, ivory ripple (10%) via `src/ripple.ts`, bare `←` back affordance, hardware-back steps the wizard, 48dp touch targets, gesture-nav footer air.

## Layout

```
app/                 expo-router routes: index (threshold), new (wizard),
                     studio/[id] (theater ⇄ gallery)
src/theme.ts         tokens — the single source of the design language
src/components/      ScreenShell, DisplayText, Label, GoldRule, EditorialRow,
                     PrimaryAction, QuietBack, Field, AuraCard, CrewList,
                     GalleryPiece, Wordmark
src/api.ts           engine client + design-review/sample fallback
src/sample.ts        sample project (real engine data shapes)
src/platformHint.ts  platform resolution (device + review rig)
scripts/screenshot.mjs  the review rig
MOBILE_DESIGN.md     the standard the supervisor enforces
```

Checkout/payments open in the web app for now (`/checkout/[id]`); native IAP-free purchase flow is a roadmap item alongside push notifications ("your gallery is hung") and the share-able aura mirror card.
