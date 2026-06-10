# Global Aesthetics Dashboard Video Demo

This folder is an independent video production workspace for the dashboard demo.
It does not modify the dashboard data model or source UI.

## Output

- Final MP4: `..\output\global-aesthetics-map-demo-16x9.mp4`
- Captions: `public\assets\captions\global-aesthetics-map-demo.srt`
- Recorded browser source: `public\assets\recordings\dashboard-interaction.webm`
- Generated stereo instrumental bed: `public\assets\audio\generated-ambient-bed.wav`

## Build

Keep the dashboard server running at:

```text
http://127.0.0.1:8790/index.html
```

Then run:

```powershell
npm install
npm run build
```

The build runs preflight checks, records the real dashboard interaction,
generates the local royalty-free instrumental bed, exports captions, renders
the final MP4, and validates the finished file.

## Preview

```powershell
npm run studio
```

The Remotion composition ID is `GlobalAestheticsDemo`.

## Rendering Notes

The Remotion composition in `src\GlobalAestheticsDemo.tsx` is frame-driven:
camera scale and movement are derived from `useCurrentFrame()`, `interpolate()`,
and `spring()`.

The current final MP4 does not burn subtitles into the pixels. Captions are kept
as sidecar SRT files so the player displays only one small subtitle layer and so
the copy can be rewritten without rerendering the picture.

The current default build uses the FFmpeg finalizer (`npm run render:ffmpeg`)
for the final MP4 because the Windows Remotion compositor native package was
not available in this local environment. The finalizer trims the loading blank
from the recording, adds timeline-based camera movement, and encodes the final
picture without hard subtitles.
