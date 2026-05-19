# Global Aesthetics Dashboard Design Review

Figma FigJam: https://www.figma.com/board/j7gGJ3pgj8Ridt9eTZ2Znd?utm_source=codex&utm_content=edit_in_figjam&oai_id=&request_id=d20caa74-2430-4a2f-aedc-deabbc8d86a2

## Immediate Changes Applied

- Restored the page hierarchy: headline and analytical judgment now come before the map.
- Moved all KPI cards into the first screen before the map.
- Converted the world map from a full-bleed page takeover into a contained analysis module.
- Separated navigation roles: top navigation is track entry, left rail is page navigation, map controls are scoped to the map.
- Added track-level insight copy to each primary track card.
- Reduced map visual dominance by muting map tiles and moving controls inside the map module.
- Restored left-rail anchor scrolling after map rendering changes.

## P0 Findings

1. First-screen hierarchy must answer "what is this dashboard saying?" before asking the user to explore.
   The current fix moves KPI cards and analytical cues forward. Next pass should compress the hero further if the first viewport still feels too editorial.

2. The map should be a spatial evidence view, not the product shell.
   Keep it bounded at roughly 420-560 px on desktop. On mobile, show filters and stats before expecting map interaction.

3. KPI cards need scanning priority but not decorative weight.
   Keep them compact, use consistent number sizing, and avoid large decorative glows inside dense dashboard modules.

4. Section anchors must stay stable after async map/chart rendering.
   Any future layout change that alters map height should be checked with direct hash links such as `#segments`, `#analysis`, and `#evidence-status`.

## P1 Findings

1. Build a small Figma component system:
   KPI card, section header, left rail item, map module, track group card, heat tile, evidence notice, tooltip, and empty state.

2. Define component states:
   Default, hover, focus, active, loading, empty, filtered, disabled, and dense mode.

3. Tighten bilingual typography:
   Chinese should carry the primary business reading. English should be secondary, smaller, and never equal-weight in dense cards.

4. Simplify heat-card semantics:
   Keep the color scale, but reduce the "data wall" feeling with fewer visible tiles, clearer grouping, and tooltips for long evidence details.

5. Reduce chart novelty where it competes with comprehension:
   Bar lists, small multiples, and ranked tables should beat clever encodings when the user needs to compare quickly.

## P2 Findings

1. Add a design QA checklist to the project:
   Desktop screenshot, mobile screenshot, hash navigation, console errors, horizontal overflow, text truncation, contrast, and keyboard focus.

2. Unify radius and density:
   Most dashboard modules should stay at 8 px radius. Reserve larger radii for modals or intentional emphasis.

3. Create semantic color tokens:
   `evidence`, `market`, `geography`, `risk`, `growth`, `neutral`, and `inactive`. Avoid coloring by decoration only.

4. Improve evidence storytelling:
   Each evidence module should state whether it is confirmed, pending review, official source, market signal, or derived analysis.

5. Mobile-specific map behavior:
   Avoid burying content under a tall map. Consider a compact map preview with an expand action if the map remains interaction-heavy.

## Next Recommended Pass

1. Shrink the hero another 10-15% if the map entry still feels too low on 1280x720 screens.
2. Convert the top six track cards into a reusable Figma/component pattern.
3. Add a mobile screenshot QA pass at 390 px and 430 px widths.
4. Rework the segment heat tiles into "top 6 visible + expand" if vertical height remains heavy.
5. Add a project-level `DESIGN_QA_CHECKLIST.md` once the visual direction stabilizes.
