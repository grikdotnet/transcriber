---
version: alpha
name: Ink Bronze Fluid Glass
description: Dark native desktop model-download UI with deep ink acrylic surfaces and restrained bronze interaction accents.
colors:
  primary: "#9F4219"
  primary-hover: "#B34D1E"
  primary-pressed: "#7C310E"
  primary-edge: "#E7904B"
  on-primary: "#FFF8EE"
  neutral: "#F7F9FC"
  window-surface: "#111724F2"
  header-surface: "#151D2CEB"
  sidebar-surface: "#1A2230F0"
  content-surface: "#111B2BF2"
  control-surface: "#202B3AE0"
  control-hover: "#2A3545F0"
  on-surface: "#F4F5F7"
  on-surface-muted: "#AAB1BE"
  on-surface-subtle: "#8F98A7"
  outline: "#465161"
  outline-subtle: "#303B4A"
  progress-track: "#334052"
  status-active: "#E06E2E"
  brand-blue: "#3CA6FF"
typography:
  window-title:
    fontFamily: "SF Pro Text, Segoe UI Variable, Segoe UI, system-ui, sans-serif"
    fontSize: 14px
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: 0px
  heading-lg:
    fontFamily: "SF Pro Text, Segoe UI Variable, Segoe UI, system-ui, sans-serif"
    fontSize: 22px
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: 0px
  heading-md:
    fontFamily: "SF Pro Text, Segoe UI Variable, Segoe UI, system-ui, sans-serif"
    fontSize: 16px
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: 0px
  body-md:
    fontFamily: "SF Pro Text, Segoe UI Variable, Segoe UI, system-ui, sans-serif"
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.45
    letterSpacing: 0px
  label-md:
    fontFamily: "SF Pro Text, Segoe UI Variable, Segoe UI, system-ui, sans-serif"
    fontSize: 13px
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: 0px
  metric-lg:
    fontFamily: "SF Pro Text, Segoe UI Variable, Segoe UI, system-ui, sans-serif"
    fontSize: 26px
    fontWeight: 600
    lineHeight: 1.25
    letterSpacing: 0px
rounded:
  xs: 4px
  sm: 8px
  md: 10px
  lg: 16px
  xl: 20px
  window: 22px
  full: 9999px
spacing:
  xxs: 4px
  xs: 8px
  sm: 12px
  md: 16px
  lg: 24px
  xl: 32px
  window-inset: 16px
  content-inset: 28px
components:
  external-canvas:
    backgroundColor: "{colors.neutral}"
  subtle-divider:
    backgroundColor: "{colors.outline-subtle}"
    height: 1px
  helper-text:
    backgroundColor: "{colors.content-surface}"
    textColor: "{colors.on-surface-subtle}"
    typography: "{typography.body-md}"
  window-shell:
    backgroundColor: "{colors.window-surface}"
    textColor: "{colors.on-surface}"
    typography: "{typography.body-md}"
    rounded: "{rounded.window}"
    padding: "{spacing.window-inset}"
  window-header:
    backgroundColor: "{colors.header-surface}"
    textColor: "{colors.on-surface}"
    typography: "{typography.window-title}"
    rounded: "{rounded.lg}"
    padding: "{spacing.md}"
    height: 48px
  language-panel:
    backgroundColor: "{colors.sidebar-surface}"
    textColor: "{colors.on-surface}"
    typography: "{typography.body-md}"
    rounded: "{rounded.lg}"
    padding: "{spacing.md}"
    width: 224px
  content-panel:
    backgroundColor: "{colors.content-surface}"
    textColor: "{colors.on-surface}"
    typography: "{typography.body-md}"
    rounded: "{rounded.lg}"
    padding: "{spacing.content-inset}"
  search-input:
    backgroundColor: "{colors.control-surface}"
    textColor: "{colors.on-surface-muted}"
    typography: "{typography.body-md}"
    rounded: "{rounded.sm}"
    padding: "{spacing.sm}"
    height: 40px
  search-input-hover:
    backgroundColor: "{colors.control-hover}"
    textColor: "{colors.on-surface}"
    typography: "{typography.body-md}"
    rounded: "{rounded.sm}"
    padding: "{spacing.sm}"
    height: 40px
  language-row-selected:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.label-md}"
    rounded: "{rounded.md}"
    padding: "{spacing.sm}"
    height: 44px
  language-row-selected-hover:
    backgroundColor: "{colors.primary-hover}"
    textColor: "{colors.on-primary}"
    typography: "{typography.label-md}"
    rounded: "{rounded.md}"
    padding: "{spacing.sm}"
    height: 44px
  language-row-selected-active:
    backgroundColor: "{colors.primary-pressed}"
    textColor: "{colors.on-primary}"
    typography: "{typography.label-md}"
    rounded: "{rounded.md}"
    padding: "{spacing.sm}"
    height: 44px
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.body-md}"
    rounded: "{rounded.sm}"
    padding: "{spacing.md}"
    height: 46px
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
    textColor: "{colors.on-primary}"
    typography: "{typography.body-md}"
    rounded: "{rounded.sm}"
    padding: "{spacing.md}"
    height: 46px
  button-primary-active:
    backgroundColor: "{colors.primary-pressed}"
    textColor: "{colors.on-primary}"
    typography: "{typography.body-md}"
    rounded: "{rounded.sm}"
    padding: "{spacing.md}"
    height: 46px
  button-secondary:
    backgroundColor: "{colors.content-surface}"
    textColor: "{colors.primary-edge}"
    typography: "{typography.body-md}"
    rounded: "{rounded.sm}"
    padding: "{spacing.md}"
    height: 46px
  metadata-label:
    backgroundColor: "{colors.content-surface}"
    textColor: "{colors.on-surface-muted}"
    typography: "{typography.label-md}"
    rounded: "{rounded.xs}"
    padding: "{spacing.xs}"
  metadata-value:
    backgroundColor: "{colors.content-surface}"
    textColor: "{colors.on-surface}"
    typography: "{typography.body-md}"
    rounded: "{rounded.xs}"
    padding: "{spacing.xs}"
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
  brand-mark:
    backgroundColor: "{colors.header-surface}"
    textColor: "{colors.brand-blue}"
    typography: "{typography.window-title}"
    rounded: "{rounded.full}"
    size: 28px
---

## Overview

Ink Bronze Fluid Glass is the dark companion theme for the local ASR model downloader. Deep ink-blue acrylic provides the structure; polished bronze marks selection, focus, progress, and the primary action. The balance is navy first and bronze second. It must never become an all-brown, sepia, or gaming-style interface.

The workflow retains three stable states: language selection, model information, and download progress. The language pane remains visible while the content pane advances, so the user never loses context.

The external canvas is invariant. Keep the area around application windows exactly `neutral` (`#F7F9FC`) without a dark page background, tint, gradient, vignette, texture, or colored aura.

## Colors

- **Primary (`#9F4219`):** Deep bronze used for the selected language and primary action. It supports readable ivory text.
- **Primary edge (`#E7904B`):** Polished copper highlight for inner refraction, progress fill, focus ring, and secondary action text. Never use it as small text on a light background.
- **Window and content surfaces:** Deep ink blue, never pure black. Sidebar and header are slightly lighter translucent layers.
- **On-surface (`#F4F5F7`):** Main text. Muted cool-gray tokens preserve hierarchy without shifting the interface toward brown.
- **Brand blue (`#3CA6FF`):** Reserved for the small app mark. It does not compete with bronze interaction states.
- **Neutral (`#F7F9FC`):** Fixed external canvas shared with the light theme.

Ink and navy should occupy at least 85% of visible theme color. Bronze is reserved for interaction and progress.

## Typography

Use native system typography: San Francisco on macOS, Segoe UI Variable on Windows, then system fallbacks. Headings use compact semibold weight; labels and metadata remain 13–14px. The 26px metric is exclusive to download percentage.

Do not use condensed, serif, monospace, novelty, or uppercase display styles. Warm ivory is used only where a bronze surface requires it; ordinary copy stays cool white or muted slate.

## Layout

Use the same geometry as the light theme so theme switching never moves controls. The stable desktop split view uses a `224px` language pane and a flexible content pane. The language pane may grow to `288px` at large widths and should remain about 28–32% of the window. Minimum usable content size is `760 × 600px`.

- Outer inset: `16px`.
- Header height: `48px`.
- Panel gap: `4–8px`.
- Language panel padding: `16px`.
- Content padding: `28px`.
- Search and Auto detect controls: `40px` high.
- Language rows: `44px` high with `8px` gaps.
- Flag assets: `22 × 16px`, natural aspect ratio, `2–3px` corner radius.
- Metadata rows: at least `56px`, label left and value right.
- Bottom actions: `46px` high and aligned to the content pane bottom.

Center the empty-state icon and message inside the content pane. Keep the split view down to `760px`; below that threshold the language pane may become a temporary sheet instead of compressing metadata or introducing stacked cards.

## Elevation & Depth

Use a layered acrylic material over opaque dark fallbacks. The outer window may use approximately `blur(32px) saturate(115%)`; inner panes use `20–24px` blur. Add a 1px top-edge highlight at roughly 8% white opacity and a neutral outer outline around 20% opacity.

Use a neutral-dark window shadow around `0 12px 28px rgba(3,8,14,.28)` plus `0 2px 6px rgba(3,8,14,.34)`. No colored shadow may spill onto the external canvas.

The header may carry one thin, fading bronze refraction along part of its inner lower edge. It is a material glint, not a thick divider. The selected row and primary button use restrained bronze depth: a soft dark shadow, a faint copper outline, and an inset warm highlight. Other controls remain nearly flat.

For Reduce Transparency, replace blur with opaque `window-surface`, `sidebar-surface`, and `content-surface` equivalents. Do not remove separation or lower text contrast.

## Shapes

Use `22px` for the window, `16–20px` for inset acrylic panes and header, `8–10px` for controls, and full pills only for progress and status dots. The dark theme must keep the same softened continuous geometry as the light theme.

Avoid hard column dividers and square panels. Separate panes with spacing, tonal contrast, a subtle outline, and curved boundaries.

## Components

**Window header.** Use inset rounded ink acrylic. App icon and title sit leading; native window controls stay neutral and trailing. The small app mark may use brand blue. Do not recolor native controls bronze.

**Search.** Use a dark translucent control with a leading icon and muted placeholder. Hover raises surface luminance slightly. Focus uses a 2px copper ring with no layout shift.

**Language list.** Auto detect uses a globe icon. Explicit languages use real rectangular flags plus written labels. Resting rows are transparent; hover uses `control-hover`. Selected uses a deep bronze liquid capsule, ivory text, checkmark, copper inner highlight, and soft shadow. Accessibility state and checkmark must carry selection in addition to color.

**Model metadata.** Use a flat definition list with subtle dividers, cool-muted labels, and high-contrast values. Values align right where short. Long names wrap. Always show model name, size, supported languages, RAM/VRAM, license, and installed/update state.

**Primary action.** Download or Update is the only filled bronze action. Hover uses `primary-hover`; pressed uses `primary-pressed`, drops 1px, and contracts its shadow. Disabled uses a neutral dark control surface, at least 45% text opacity, and no glow.

**Progress.** Keep language and model identity visible. Show status text, a dominant percentage, transferred/total size, remaining time, and an 8px determinate track. Use copper fill with a subtle top highlight. Replace Download with an outlined copper Cancel action, never a filled destructive red.

**State mapping.** Not installed shows Download. Installed shows a quiet completion state. Update available changes the action label to Update. Downloading shows progress and Cancel. Failure keeps model data visible, shows concise inline error text, and offers Retry as the sole primary action.

All targets are at least `40 × 40px`, preferably `44px`. Keyboard order is Search, Auto detect, languages, then action. Announce progress at meaningful intervals. Respect reduced motion by removing shimmer and sweeping highlights.

## Do's and Don'ts

- Do keep the external canvas exactly `#F7F9FC`.
- Do keep at least 85% of the theme in deep ink and cool navy.
- Do reserve bronze for selection, focus, primary action, and active progress.
- Do use subtle acrylic depth, curved boundaries, and readable cool-white text.
- Do preserve identical geometry across light and dark themes.
- Do meet WCAG AA and maintain visible keyboard focus.
- Don't turn entire panes brown or apply a sepia filter.
- Don't add purple, teal, or mismatched bright-blue interaction accents.
- Don't use sharp bars, thick copper borders, wood/leather textures, or steampunk cues.
- Don't change or darken the canvas surrounding the windows.
- Don't rely on flags or color alone for language and status meaning.
- Don't add nested cards, global navigation, history, account, or unrelated controls.
