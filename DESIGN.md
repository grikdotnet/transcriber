---
version: alpha
name: Cloud White
description: Airy native-desktop model-management UI with cloudy white glass, pale-blue service panes, cyan refraction, and restrained electric-blue actions.
colors:
  primary: "#086CF7"
  primary-hover: "#0065D8"
  primary-pressed: "#0059D9"
  primary-disabled: "#AABFE8"
  primary-edge: "#00C7FA"
  on-primary: "#FFFFFF"
  neutral: "#FAFAFC"
  window-surface: "#F5F9FDF2"
  header-surface: "#E8ECF1E8"
  header-highlight: "#FFFFFFCC"
  menu-surface: "#F0F3F9F2"
  content-surface: "#FAFAFCF5"
  control-surface: "#F7FAFDF0"
  on-surface: "#151922"
  on-surface-muted: "#56627A"
  on-surface-subtle: "#6B7487"
  outline: "#C9D3E1"
  outline-subtle: "#E2E6EC"
  wave-core: "#82E9FA"
  wave-glow: "#C7F7FF"
  progress-track: "#DEE2E8"
  status-active: "#0D8AF9"
  focus-ring: "#007CFC"
  error: "#C33232"
typography:
  window-title:
    fontFamily: "Segoe UI Variable Text, Segoe UI, SF Pro Text, system-ui, sans-serif"
    fontSize: 12px
    fontWeight: 400
    lineHeight: 1.4
    letterSpacing: 0px
  heading-md:
    fontFamily: "Segoe UI Variable Text, Segoe UI, SF Pro Text, system-ui, sans-serif"
    fontSize: 16px
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: 0px
  body-md:
    fontFamily: "Segoe UI Variable Text, Segoe UI, SF Pro Text, system-ui, sans-serif"
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.45
    letterSpacing: 0px
  body-sm:
    fontFamily: "Segoe UI Variable Text, Segoe UI, SF Pro Text, system-ui, sans-serif"
    fontSize: 13px
    fontWeight: 400
    lineHeight: 1.4
    letterSpacing: 0px
  label-sm:
    fontFamily: "Segoe UI Variable Text, Segoe UI, SF Pro Text, system-ui, sans-serif"
    fontSize: 13px
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: 0px
  button-md:
    fontFamily: "Segoe UI Variable Text, Segoe UI, SF Pro Text, system-ui, sans-serif"
    fontSize: 15px
    fontWeight: 500
    lineHeight: 1.3
    letterSpacing: 0px
  metric-lg:
    fontFamily: "Segoe UI Variable Display, Segoe UI Variable Text, Segoe UI, system-ui, sans-serif"
    fontSize: 27px
    fontWeight: 500
    lineHeight: 1.2
    letterSpacing: 0px
rounded:
  xs: 4px
  sm: 8px
  md: 10px
  lg: 18px
  window: 18px
  full: 9999px
spacing:
  xxs: 4px
  xs: 8px
  sm: 12px
  md: 16px
  lg: 24px
  xl: 32px
  shell-inset: 5px
  panel-inset: 18px
  content-inset: 30px
  panel-gap: 4px
components:
  external-canvas:
    backgroundColor: "{colors.neutral}"
  window-shell:
    backgroundColor: "{colors.window-surface}"
    textColor: "{colors.on-surface}"
    typography: "{typography.body-md}"
    rounded: "{rounded.window}"
    padding: "{spacing.shell-inset}"
  window-header:
    backgroundColor: "{colors.header-surface}"
    textColor: "{colors.on-surface}"
    typography: "{typography.window-title}"
    rounded: "{rounded.window}"
    padding: "{spacing.md}"
    height: 53px
  header-cloud-highlight:
    backgroundColor: "{colors.header-highlight}"
    rounded: "{rounded.full}"
    size: 32px
  header-separator-wave:
    backgroundColor: "{colors.wave-core}"
    rounded: "{rounded.full}"
    height: 1px
  header-separator-glow:
    backgroundColor: "{colors.wave-glow}"
    rounded: "{rounded.full}"
    height: 5px
  language-panel:
    backgroundColor: "{colors.menu-surface}"
    textColor: "{colors.on-surface}"
    typography: "{typography.body-md}"
    rounded: "{rounded.lg}"
    padding: "{spacing.panel-inset}"
    width: 190px
  content-panel:
    backgroundColor: "{colors.content-surface}"
    textColor: "{colors.on-surface}"
    typography: "{typography.body-md}"
    rounded: "{rounded.lg}"
    padding: "{spacing.content-inset}"
  search-input:
    backgroundColor: "{colors.control-surface}"
    textColor: "{colors.on-surface-muted}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.sm}"
    padding: "{spacing.sm}"
    height: 40px
  language-row:
    backgroundColor: "{colors.menu-surface}"
    textColor: "{colors.on-surface}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.md}"
    padding: "{spacing.sm}"
    height: 44px
  language-row-selected:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.label-sm}"
    rounded: "{rounded.md}"
    padding: "{spacing.sm}"
    height: 47px
  subtle-divider:
    backgroundColor: "{colors.outline-subtle}"
    height: 1px
  panel-outline:
    backgroundColor: "{colors.outline}"
    height: 1px
  helper-text:
    backgroundColor: "{colors.content-surface}"
    textColor: "{colors.on-surface-subtle}"
    typography: "{typography.body-md}"
  metadata-label:
    backgroundColor: "{colors.content-surface}"
    textColor: "{colors.on-surface-muted}"
    typography: "{typography.body-sm}"
  metadata-value:
    backgroundColor: "{colors.content-surface}"
    textColor: "{colors.on-surface}"
    typography: "{typography.label-sm}"
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.button-md}"
    rounded: "{rounded.md}"
    padding: "{spacing.md}"
    height: 46px
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
    textColor: "{colors.on-primary}"
    typography: "{typography.button-md}"
    rounded: "{rounded.md}"
    padding: "{spacing.md}"
    height: 46px
  button-primary-active:
    backgroundColor: "{colors.primary-pressed}"
    textColor: "{colors.on-primary}"
    typography: "{typography.button-md}"
    rounded: "{rounded.md}"
    padding: "{spacing.md}"
    height: 46px
  button-primary-disabled:
    backgroundColor: "{colors.primary-disabled}"
    textColor: "{colors.on-surface}"
    typography: "{typography.button-md}"
    rounded: "{rounded.md}"
    padding: "{spacing.md}"
    height: 46px
  button-secondary:
    backgroundColor: "{colors.content-surface}"
    textColor: "{colors.primary-pressed}"
    typography: "{typography.button-md}"
    rounded: "{rounded.sm}"
    padding: "{spacing.md}"
    height: 46px
  progress-track:
    backgroundColor: "{colors.progress-track}"
    rounded: "{rounded.full}"
    height: 8px
  progress-fill:
    backgroundColor: "{colors.primary-edge}"
    rounded: "{rounded.full}"
    height: 8px
  status-active:
    backgroundColor: "{colors.status-active}"
    rounded: "{rounded.full}"
    size: 8px
  focus-indicator:
    backgroundColor: "{colors.focus-ring}"
    rounded: "{rounded.md}"
    height: 2px
  status-error:
    backgroundColor: "{colors.content-surface}"
    textColor: "{colors.error}"
    typography: "{typography.body-sm}"
  window-footer-termination:
    backgroundColor: "{colors.window-surface}"
    rounded: "{rounded.window}"
    padding: "{spacing.shell-inset}"
    height: 28px
---

# Cloud White Design System

## Overview

Cloud White is a light native-desktop design language for local model management and other focused utility workflows. Its personality is calm, airy, precise, and slightly tactile: cloudy white acrylic builds depth, pale blue distinguishes services and navigation, and electric blue marks selection, progress, focus, and the one primary action.

The source of truth is [DESIGN-CLOUD-WHITE.png](design/DESIGN-CLOUD-WHITE.png), a `1672 × 941px` raster composition with three model-download states. Measurements in this document are source-pixel approximations, normally within `±2px`; the flattened image cannot reveal exact blur kernels, font files, opacity, or vector paths.

This file uses the Google Labs [DESIGN.md alpha format](https://github.com/google-labs-code/design.md/blob/main/docs/spec.md): frontmatter tokens are normative, while the prose explains composition and material behavior. The filename `DESOGN.md` preserves the requested deliverable name even though `DESIGN.md` is the upstream discovery convention.

The system has five architectural layers:

1. **Evidence:** source image, measured coordinates, lossless reference crops, and explicitly declared source-pixel derivations.
2. **Foundations:** color, typography, spacing, radius, and material constants.
3. **Materials:** cloudy header glass, pale-blue menu glass, white content glass, refraction edges, and shadows.
4. **Components:** shell, header, menu controls, metadata rows, buttons, status, progress, and footer action zone.
5. **Compositions and state:** a stable split-view shell whose operational pane changes between Select, Ready, and Downloading.

The hierarchy is `WindowShell → Header + HeaderSeparator + Body + FooterTermination`; `Body → ServiceMenu + VerticalSeparator + OperationalArea`; `OperationalArea → StateContent + ActionDock`. `FooterTermination` is the shared lower edge of the shell, while `ActionDock` is ordinary layout inside the operational pane. Tokens must flow downward through this hierarchy. A state may replace operational content and action treatment, but it must not restyle or move the shared shell.

Cloud White is deliberately cool white and blue/cyan. Reserve red only for genuine error messaging through `error`; do not introduce warm accent families into the base theme.

## Colors

The palette is cool and almost neutral. Surfaces are deliberately close in value; boundaries come from translucency, curved edges, and soft blue-gray strokes rather than from strong fills.

- **Primary (`#086CF7`):** Selected language, Download action, focus emphasis, and active progress base.
- **Primary edge (`#00C7FA`):** Cyan liquid-glass highlight, refracted button rim, and the bright end of progress fill. It is not body-text color.
- **Neutral (`#FAFAFC`):** External canvas. Keep it untextured and free of colored auras.
- **Header surface (`#E8ECF1E8`):** Stabilized fallback beneath cloudy translucent layers.
- **Menu surface (`#F0F3F9F2`):** Pale-blue service/navigation plane.
- **Content surface (`#FAFAFCF5`):** Near-white operational plane with only very faint cool clouding.
- **On-surface (`#151922`):** Headings, values, labels, and native controls.
- **Muted text (`#56627A`) and subtle text (`#6B7487`):** Metadata labels, helper copy, and secondary information.
- **Outlines:** `#C9D3E1` for component boundaries and `#E2E6EC` for internal dividers.
- **Wave:** `#82E9FA` core inside a `#C7F7FF` haze. The wave is a material refraction, not an accent stripe.
- **Progress track (`#DEE2E8`):** Quiet cool-gray track behind a blue-to-cyan fill.

Raster sampling varies by point because glass and cloud effects are composited. Typical observed averages are about `#E8ECF1` in the header, `#F0F3F9` in the menu, `#FAFAFC` in the content panel, and `#136DFB` across the primary-button interior. Use the tokens above for implementation instead of chasing individual raster pixels.

For transparency fallbacks, keep the same RGB family but use opaque surfaces. Text must maintain WCAG AA contrast against the stabilized surface immediately beneath it; do not calculate contrast against the desktop wallpaper.

## Typography

Use native system UI typography. The raster most closely resembles Segoe UI Variable; the fallback stack deliberately supports macOS without importing a web font. Exact font identity is not provable from the source image.

- **Window title:** `12px / 1.4`, regular. Keep it visually subordinate to pane headings.
- **Pane heading:** `16px / 1.4`, semibold. Sentence case only.
- **Body and helper copy:** default `14px`; `13px` may be used for compact metadata when the platform renders it clearly.
- **Labels and values:** labels use regular muted text; compact values use medium weight and near-black.
- **Buttons:** `15px`, medium, centered. Never uppercase.
- **Progress metric:** `27px`, medium. Use the large metric only for a live percentage or similarly dominant operation value.

Do not use condensed, serif, monospace, novelty, or display fonts. Allow model names and localized language labels to wrap or elide with an accessible full-name affordance; never shrink below `13px` to make text fit.

## Layout

### Reference geometry

The middle window is the primary geometry reference because it cleanly shows the ready state.

| Region | Approximate source bounds | Implementation rule |
| --- | --- | --- |
| Window shell | `515 × 698px` at `(577,106)` | Treat the reference as a compact design sample. Recommended minimum usable application viewport is `760 × 600px`; scale the content pane, not type or controls. |
| Cloudy header | `506 × 53px` at `(582,106)` | Fixed `52–53px` visual height; app identity leading and native controls trailing. |
| Header wave | band at `y=148–163px` | `1px` luminous core with `3–5px` haze and no layout height of its own. |
| Service/menu pane | `190 × 637px` at `(582,160)` | About `36–37%` of this compact sample; use `224px` at normal `760px+` app widths and allow up to `288px`. |
| Vertical separator | `11 × 637px` evidence crop at `(769,160)` | Perceived separator is a `3–5px` trough formed by two curved panel edges, not a hard rule. |
| Operational pane | `310 × 637px` at `(777,160)` | Flexible remainder; `30px` horizontal content inset in detail states. |
| Operational action dock | `310 × 100px` at `(777,697)` | Bottom-anchored layout region inside the operational pane. It is not the window footer. |
| Window footer termination | full shell width at `y≈776–804px` | Shared lower edge showing both pane bottoms, central trough, outer frame, lower radii, and shadow; no controls or semantic footer content. |

The source windows vary slightly in width (`531px`, `515px`, and `526px`) because the reference is a composed raster. Treat those differences as image-generation variance, not state-dependent layout. A real application must use one invariant shell geometry for all three states.

### Stable split view

- Outer shell inset: `5px` around header and inner panes.
- Header-to-body transition: visually continuous; the wave overlays the boundary.
- Panel gap: `4px` perceived trough, allowed range `4–8px` at larger sizes.
- Menu inset: `18px` leading and trailing.
- Operational inset: `30px` leading and trailing for metadata; empty content may use a wider optical center.
- Search and Auto detect controls: `40px` high.
- Language rows: minimum `44px` high, about `8–14px` between visual rows; the selected liquid capsule is `47px` including its face, with shadow outside the layout box.
- Flags: roughly `24 × 18px`, natural aspect ratio, `2–3px` radius. Do not stretch flags to a square.
- Metadata rows: approximately `55px` high with a `1px` divider. Labels align left and short values align right.
- Progress track: `8px` high and full available content width.
- Bottom actions: `46px` control height with about `22–25px` horizontal inset from the operational panel edge. They belong to the action dock and must not be represented as footer artwork.

At less than `760px` usable width, replace the persistent menu with a temporary sheet or navigation drawer. Do not compress controls, collapse label/value separation, or stack nested cards. At 200% zoom, preserve reading order and allow metadata values to move below their labels.

## Elevation & Depth

Depth is produced by layered light, not by opaque cards. Use opaque fallback colors first, then enhance them where the platform supports backdrop blur.

**Window shell.** Use a neutral outline near `1px #C9D3E1`, a top-edge white highlight at roughly 55–70% opacity, and a restrained shadow close to `0 5px 14px rgba(55,75,100,.14)`. A larger production window may use `0 12px 28px rgba(55,75,100,.12)` while keeping the canvas clean.

**Cloudy header.** Start with `header-surface`. Apply approximately `backdrop-filter: blur(28px) saturate(115%)`. Add two or three oversized, heavily blurred radial pools: white at 35–55% opacity, ice blue at 12–20%, and blue-gray at 8–14%. Their edges must be invisible. Keep a stabilized translucent underlay behind title text and controls so moving wallpaper never compromises legibility.

**Inner panes.** Use `blur(20–24px)` with less cloud contrast than the header. The menu is visibly cooler/bluer than the operational pane. Each pane gets a faint `1px` blue-gray outline plus a subtle white inner top edge.

**Selected row and primary action.** Use a vertical gradient from approximately `#0082FD` at the top through `#086CF7` to `#0056FA` at the bottom. Add a cyan-white inset top highlight, a `1px` bright blue boundary, and a shadow near `0 6px 10px rgba(0,70,190,.28)`. Keep the glow within about `8px` of the control.

**Header wave.** Draw a `1px` core with a `3–5px` blurred duplicate below it. Fade opacity to zero over the outer 10–15% of the width. Use a shallow irregular curve with only `2–3px` peak-to-trough displacement; it should read as light refracting through glass, not as an illustration.

For Reduce Transparency, remove backdrop filters and cloud pools, use opaque surface tokens, and retain outlines and hierarchy. For Reduce Motion, remove traveling highlights, shimmer, and animated wave distortion. Download progress may update its fill width without decorative sweeping motion.

## Shapes

The shape language uses continuous soft corners:

- Window shell and inset panels: `18px`.
- Header: `18px` top corners, with a soft lower transition rather than a hard rectangular bar.
- Search, Auto detect, buttons: `8–10px`.
- Selected language row: `10px`.
- Status dot and progress track: full pills.
- Flags: `2–3px` only.

Do not use square cards, sharp separators, full-pill buttons, or thick outlines. The vertical separator is negative space between two rounded panes. The action dock follows the operational panel’s layout; the window footer is only the shared lower termination of both panes and the outer shell.

## Components

### Window shell and cloudy header

The shell owns outer outline, shadow, window radius, and platform backdrop integration. The header owns app icon, “Model downloads” title, drag region, and native minimize/maximize/close controls. Keep platform controls neutral; do not recolor them blue.

The header is shared across all states and must not react to menu selection or progress. App identity is vertically centered. Keep at least `8px` clear space around each native control and preserve the platform’s expected hit areas.

Reference artifact: [cloudy header with source context](design/artifacts/cloud-white/window-header-cloudy.png). It intentionally includes neutral canvas above and beside the left window plus a narrow body transition below; this surrounding contrast makes the translucent cloudy fill visible in white image viewers. The header component itself remains `52–53px` high.

### Header separator wave

The wave is an overlay at the header’s lower inner edge. It must not consume body layout space, interrupt focus outlines, or become a semantic separator. Mark it decorative for assistive technology.

Use one shallow continuous path. The blue/cyan intensity is strongest from the leading quarter through the center and fades near both ends. Avoid a repeated sine pattern, thick blue stroke, equal brightness across the width, or vertical movement over `3px`.

Reference artifact: [blue wave evidence crop](design/artifacts/cloud-white/header-separator-blue-wave.png).

### Service/menu area

The pale-blue menu stays visible while the operational pane changes state. Its order is: pane heading, Search, Auto detect, then language rows. Search filters the visible languages without changing the current selection. Auto detect is a service choice, not a language.

Resting language rows are visually flat over the pane. Hover uses a slight white lift; pressed lowers luminance. Selected uses the primary liquid capsule, white label, visible checkmark, and the written language name in addition to its flag. Focus uses a `2px` `focus-ring` outline with no layout shift. The whole row is interactive and at least `44 × 44px`.

Reference artifact: [service/menu panel](design/artifacts/cloud-white/service-menu-area.png).

### Main operational area

The operational pane is the only state-changing region. Keep its heading at the same top position in all states. Its primary content modes are:

1. **Select language / empty.** Heading “Download a model,” one-line helper copy, a centered cloud-download icon, and a two-line instruction. Do not show a disabled Download button; absence of an action is the clearer state.
2. **Ready / not installed.** Heading identifies the selected language. Show model name, size, supported languages, RAM/VRAM, license, and status in a flat definition list. Anchor Download in the footer action zone.
3. **Downloading.** Keep model identity and metadata. Replace the compact status value with status label, dominant percentage, transferred/total size, remaining time, and progress track. Replace Download with the outlined Cancel action without moving the footer.

Reference artifact: [main operational-area material](design/artifacts/cloud-white/main-operational-area.png). This intentionally uses a content-free lower portion of the pane so the artifact documents only surface, outlines, and lower radii. State composition is defined by the prose above, not by duplicate screenshots.

### Vertical menu separator

The separator is a relationship between the two panes, not an independent dark line. Form it with the menu’s trailing outline, the operational pane’s leading outline, and a narrow light trough. Keep both panel radii visible at the top and bottom.

Reference artifact: [vertical separator evidence crop](design/artifacts/cloud-white/vertical-menu-separator.png).

### Metadata rows

Use a semantic definition list. Labels align leading and use muted text; short values align trailing and use `on-surface`. Long model names wrap to two lines before truncating. Dividers begin and end at the content inset, never at the panel edge.

Status must remain textual. “Not installed,” “Downloading,” “Installed,” “Update available,” and “Failed” must not be represented by color alone. Keep the visible model identity during every state change.

### Primary Download button

Download or Update is the only filled primary action in the pane. The control is `46px` high and spans the footer’s available width. Hover sharpens to the accessible `primary-hover`; pressed uses `primary-pressed`, shifts down `1px`, and contracts the shadow. Focus adds a `2px` external ring. Disabled uses `primary-disabled`, removes glow, switches to dark text, and must still meet readable text contrast.

Reference artifact: [primary treatment](design/artifacts/cloud-white/button-primary.png). It uses the selected “English” menu control because that source element shows the intended cyan-to-blue edge contrast most clearly. The source columns containing the flag are removed and the two remaining lossless segments are joined, so no pixels are synthesized, blurred, interpolated, scaled, or lossily encoded. The resulting sample is intentionally narrower than the source control. Reuse only its material treatment; the checkmark, label, width, and menu-selection semantics do not prescribe the consuming action.

### Secondary Cancel button

Cancel uses a translucent content-surface fill, darker blue text, and a `1–1.5px` blue outline. It must stay visually quieter than Download but remain clearly actionable. Hover adds a pale-blue surface tint; pressed lowers the surface. Do not use red: cancelling a download is reversible interruption, not destructive data loss.

Reference artifact: [secondary button](design/artifacts/cloud-white/button-secondary.png). The crop is a visual treatment sample; its visible source label does not prescribe the consuming screen’s action.

### Progress and status

Pair the active dot with the word “Downloading.” Present percentage as the dominant metric, followed by transferred/total size and remaining time. The track is determinate and `8px` high, with a blue-to-cyan fill and no continuous shimmer.

The percentage text is authoritative. Announce progress to assistive technology at meaningful intervals such as every 5–10%, not on every rendered frame. On completion, replace the live region with a concise installed confirmation. On failure, retain model metadata, show a short inline error, and offer Retry as the sole filled primary action.

### Operational action dock

The bottom `~100px` inside the operational panel is an action dock, not a footer. It inherits the operational surface, has no top divider, and pins its single action to a consistent vertical baseline. The empty state has no dock control; Ready contains Download; Downloading contains Cancel. Other screens in this family may use this area for one primary action or a primary/secondary pair, but avoid three-button rows.

### Window footer termination

The footer artifact is the full-width lower termination of the application window. It spans the service pane, central trough, operational pane, outer frame, and both lower corners. It contains no button, label, navigation, or independent footer surface. Its job is to document how the glass panes meet the shell and how the outer shadow falls onto the neutral canvas.

Footer geometry is state-invariant, so the artifact set contains one shared footer rather than state-specific duplicates.

Reference artifact: [window footer](design/artifacts/cloud-white/footer.png).

### Artifact scope

Artifacts represent reusable visual elements only. Do not create or retain full workflow-state screenshots, state-specific main-pane crops, state-specific footer crops, or filenames tied to application actions. The three source states remain useful evidence for the prose specification, but they are intentionally absent from the artifact set.

### Reference artifacts and provenance

Artifacts are source evidence samples for inspection, not nine-slice production textures. Pure crops are lossless; the primary treatment joins two declared lossless source segments after omitting the flag columns. Coordinates, dimensions, derivations, reuse guidance, and source SHA-256 are recorded in [manifest.json](design/artifacts/cloud-white/manifest.json). Regenerate them with `design/generate_cloud_white_artifacts.sh`.

The [component contact sheet](design/artifacts/cloud-white/contact-sheet.png) collects every evidence artifact for visual QA. Every retained primary-treatment pixel is source-exact; rebuild interfaces from tokens and component guidance so they can resize, localize, focus, and animate correctly.

## Do's and Don'ts

- Do keep the external canvas quiet, neutral, and free of colored background effects.
- Do use cloudy material most strongly in the header and more quietly in inner panes.
- Do keep the menu pale blue and the operational pane nearly white.
- Do reserve saturated blue/cyan for selection, focus, primary action, status, and progress.
- Do preserve the same shell geometry while operational content changes state.
- Do use written language names, checkmarks, status text, and numeric progress so color and flags are never the only signals.
- Do keep interactive targets at least `40 × 40px`, preferably `44 × 44px`, with visible keyboard focus.
- Do target WCAG AA against stabilized fallback surfaces and verify the final implementation at 200% zoom, high contrast, reduced transparency, and reduced motion.
- Do keep keyboard order logical: Search, Auto detect, language rows, then operational action.
- Don't add red, purple, green, or warm accent families to Cloud White; keep the base palette cool white, blue-gray, blue, and cyan.
- Don't use a thick straight header divider; the wave must remain a thin fading refraction.
- Don't draw a hard vertical rule between menu and content; preserve the luminous curved trough.
- Don't stretch, tile, ship, or use the PNG crops as production component backgrounds.
- Don't introduce nested cards, global navigation, account chrome, history panels, or unrelated dashboard furniture.
- Don't hide model identity during download, rely on an indeterminate spinner, or make Cancel a filled destructive action.
- Don't claim accessibility compliance from the reference image alone; semantics, focus, contrast, live regions, reflow, and platform behavior require implementation testing.
