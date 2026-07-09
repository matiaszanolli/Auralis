# Auralis UI/UX Redesign — Status Note

> **2026-07-08 correction**: This file originally pointed to five companion planning documents (`DESIGN_DOCUMENTATION_INDEX.md`, `AURALIS_DESIGN_SUMMARY.md`, `AURALIS_REDESIGN_IMPLEMENTATION_ROADMAP.md`, `AURALIS_DESIGN_SYSTEM_COMPLETE.md`, `QUICK_REFERENCE_DESIGNER.md`) that do not exist anywhere in this repository — every link below 404s. Whether they were local-only files that never got committed, or were removed at some point, is not knowable from the repo alone.
>
> The good news: the redesign they describe largely **did ship**. The two signature colors this doc calls out — Soft Violet (`#7366F0`) and Electric Aqua (`#47D6FF`) — are live today in `auralis-web/frontend/src/design-system/tokens/colors.ts` and `tokens/surfaces.ts`. For the current, real design system, see:
>
> - `auralis-web/frontend/src/design-system/` — the actual token source of truth (colors, spacing, typography, effects, surfaces — see the `tokens/` subdirectory)
> - [docs/guides/UI_DESIGN_GUIDELINES.md](../guides/UI_DESIGN_GUIDELINES.md) — component conventions (note: also has some stale specifics as of 2026-07-08's docs audit; verify import paths against actual code)
> - `FIGMA_TOKENS_EXPORT.json` (repo root) — the one file from this redesign's original file list that does still exist
>
> The rest of this file is kept below for historical color/scheme context only — do not follow its "Next Steps" as an active plan, and do not click the document links, they don't resolve.

---

## Original vision (historical reference)

**Premium, professional audio player** with a soft, deep, elegant feel; audio-first visualization; premium plugin (FabFilter/Ozone-style) aesthetics; Tidal-level polish.

**Key colors**: Soft Violet `#7366F0` (professional, not neon), Electric Aqua `#47D6FF` (energy for audio-reactive elements), Deep Navy `#0D111A` (premium, calming background) — all confirmed present in the current token files referenced above.

**Key visual elements**: glass effects on floating panels, elevation hierarchy instead of harsh borders, audio-reactive glows, soft ambient shadows, large album covers, an animated spectrum visualizer, JetBrains Mono for numerics, ~200ms transitions.

Five screens were targeted for this treatment: Player Bar Dock, Album Grid, Album Detail, Artist Screen, Enhancement Panel. Check the current frontend (`auralis-web/frontend/src/components/`) against `design-system/tokens/` to see how much of this actually landed for any given screen — this file cannot tell you that on its own anymore.
