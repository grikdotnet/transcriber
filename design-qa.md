# Design QA — state 3 Translate material

Source visual truth: `/Users/gri/.codex/worktrees/1ed5/transcriber/design/artifacts/cloud-white/button-primary-green-2k.png`

Implementation screenshots:

- Full view: `/tmp/qa-main-translate-green-complete.jpg`
- Focused button region: `/tmp/qa-main-translate-green-focus.jpg`

Viewport: 1280 × 720 CSS px, device scale factor 1.

Pixels and normalization:

- Source: 2152 × 731 px.
- Generated text-free material: 536 × 94 px, fitted to the same 180 × 50 CSS px slot as Save as.
- Full implementation capture: 1280 × 720 px.
- Focused implementation capture: 200 × 70 px.
- The reference and focused render were compared together at their native densities; geometry was judged from the browser's computed CSS measurements.

State: complete (`?state=complete`).

## Findings

No actionable P0, P1, or P2 differences remain.

- Fonts and typography: the live Translate label and globe icon remain crisp, centered, and readable over the image material.
- Spacing and layout rhythm: Translate and Save as both measure 180 × 50 px and share the same y-position.
- Colors and visual tokens: the generated image preserves the reference's bright green upper highlight, darker lower transition, inner neon rim, and dark outer edge.
- Image quality and asset fidelity: the new raster is text-free, sharp at its rendered size, and replaces the former CSS-painted approximation.
- Copy and content: the visible action remains “Translate”; no source-image “English” label or checkmark is present.

Full-view comparison evidence: the complete toolbar remains aligned, the green action has the same footprint as Save as, and surrounding content does not shift.

Focused comparison evidence: the source and focused render were opened together. The material transition, rim structure, and glossy highlight are preserved; only the source-specific text/checkmark were intentionally replaced by the live Translate content.

Primary interaction/state checks: complete state loaded successfully; Translate and Save as were measured in the rendered page.

Browser console errors: none.

## Comparison history

Initial implementation pass: no actionable P0/P1/P2 mismatch was found, so no visual correction loop was required.

## Follow-up Polish

None required for this scoped change.

final result: passed
