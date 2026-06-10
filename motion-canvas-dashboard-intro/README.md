# Motion Canvas Dashboard Intro

This is an independent Motion Canvas experiment for a full introduction video
of the v3 global aesthetics dashboard. The current scene follows the real v3
visual language: warm editorial background, dark left navigation, serif Chinese
headlines, burgundy accents, and normalized metric cards.

It is separate from the existing Remotion demos:

- `../video-demo`
- `../video-demo-globe`

## Preview

```powershell
cd E:\shared\Documents\data\global_aesthetics_dashboard\motion-canvas-dashboard-intro
npm install
npm start
```

Open the local Motion Canvas editor, then press play.

## Main Files

- `src/scenes/dashboardIntro.tsx` - the current full-dashboard intro prototype.
- `src/project.ts` - registers the Motion Canvas scene.
- `vite.config.ts` - enables Motion Canvas preview.

## Suggested Storyline

1. Opening: show the dashboard-like overview page.
2. Global scale: highlight the core metric cards.
3. Route map: explain how the audience should read the dashboard.
4. Evidence chain: show why the dashboard is trustworthy.
5. Brand close: explain the finished video direction.

## How This Differs From Remotion

Remotion is strongest when we want to record the real dashboard interaction and
edit it into a video.

Motion Canvas is better when we want a cleaner explainer: rebuild the story as
animated charts, labels, flows, and selected screenshots.

For a finished version, capture several stills from `web/v3` and import them
with Motion Canvas `Img` components, then animate callouts and narration over
those stills. After the picture is locked, add `@motion-canvas/ffmpeg` back if
you want direct MP4 export from the editor; until then, keeping the preview
project lean is more reliable on Windows.
