# Main application window

## State 3

Technical element map, top to bottom:

- **Title bar:** Floating rounded rectangle; cloudy blue-white acrylic fill, thin gray border, cyan lower glow, soft shadow.
  - Left: app icon and “Transcriber” title.
  - System-dependent minimize, maximize, and close controls.
- **Action toolbar:** “Save as” primary blue button, “Translate” secondary button, “Cancel” secondary button. Rounded rectangle, blue-white acrylic fill.
  - “Save as” button follows the "button-primary-2k.png" style
  - “Translate” follows the `button-primary-2k-green.png` visual style: bright emerald highlights transition smoothly into deeper forest green, with translucent depth, a restrained glossy highlight, white icon and label, and a soft green edge glow.
  - “Cancel” button follws the "button-secondary.png" style
- **File-status row:** Video icon, filename, duration, size, format, and “Complete” status.
- **Section header:** “Transcript playback”, typography control (`Aa`), expand icon.
- **Playback card:** Video thumbnail, play button, elapsed/total time, speed, waveform, and playhead.
- **Transcript area:** Timestamp, speaker badge, editable transcript text, selected-text highlights, overflow menus, and vertical scrollbar.
- **Window shell:** Large rounded outer container with a subtle border and shadow.

You can reference elements by these names—for example: “increase the title-bar corner radius,” “make the acrylic texture stronger,” or “reduce the gap below the title bar.”
