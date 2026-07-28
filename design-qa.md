# Design QA — state 3 Translate alignment and hover

Source visual truth:

- User annotation on the complete-state toolbar at `http://127.0.0.1:4174/layouts/main.html?state=complete`.
- Save as is the geometry reference.
- Green material source: `/Users/gri/.codex/worktrees/1ed5/transcriber/design/artifacts/cloud-white/button-primary-green-2k.png`.

Implementation screenshots:

- Full view: `/tmp/qa-main-translate-aligned-593x643.jpg`.
- Focused toolbar: `/tmp/qa-main-translate-toolbar-593x90.jpg`.

Viewport: 593 × 643 CSS px, device scale factor 1.

Pixels and normalization:

- Green source: 2152 × 731 px.
- Green text-free material: 536 × 94 px with normalized internal padding.
- Full implementation capture: 593 × 643 px.
- Focused toolbar capture: 570 × 90 px.
- Source material and the focused implementation were opened together. Save as and Translate were also judged side by side in the same focused capture.

State: complete (`?state=complete`).

## Findings

No actionable P0, P1, or P2 differences remain.

- Fonts and typography: both live labels and icons remain centered and crisp.
- Spacing and layout rhythm: Save as is `170.328 × 50` CSS px at `y = 41.5`; Translate is `170.336 × 50` CSS px at the same `y = 41.5`.
- Colors and visual tokens: the green material remains intact and preserves its glossy transition.
- Image quality and asset fidelity: the green raster retains the source material while its internal padding now matches the visual footprint of the blue action.
- Copy and content: Save as, Translate, and Cancel remain unchanged.
- Interaction state: the generic secondary-button hover rule explicitly excludes Translate. Translate hover keeps its background image and changes only brightness.

Full-view comparison evidence: the toolbar and downstream content retain their positions, with no overflow or wrapping at the annotated viewport.

Focused comparison evidence: Save as and Translate have matching top and bottom alignment in the 570 × 90 toolbar crop.

Primary interaction/state checks: complete state loaded; both buttons were measured; hover CSS was inspected in the rendered page.

Browser console errors: none.

## Comparison history

Earlier P2 findings:

- Translate’s visible green material extended lower than Save as despite equal element boxes.
- The generic `.main-secondary-action:hover` shorthand removed Translate’s background image.

Fixes:

- Normalized the green raster’s internal padding against the blue material asset.
- Consolidated shared primary geometry into one CSS rule.
- Excluded Translate from the generic secondary hover and retained only a brightness change for its hover state.

Post-fix evidence:

- Both elements are 50 CSS px high and share `y = 41.5`.
- Rendered CSS retains the green background image and no longer applies the image-clearing hover shorthand to Translate.

## Follow-up Polish

None required for this scoped change.

final result: passed
