import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const htmlPath = new URL("../layouts/main.html", import.meta.url);
const cssPath = new URL("../layouts/assets/main.css", import.meta.url);

const [html, css] = await Promise.all([
  readFile(htmlPath, "utf8"),
  readFile(cssPath, "utf8"),
]);

function ruleBody(selector) {
  const escapedSelector = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return css.match(new RegExp(`${escapedSelector}\\s*\\{([^}]*)\\}`))?.[1];
}

test("the app shell directly contains the identity and fluid content", () => {
  assert.match(
    html,
    /<main class="main-window"[^>]*>\s*<div class="app-identity"[\s\S]*?<\/div>\s*<div class="main-window__content"/,
  );
  assert.doesNotMatch(html, /main-prototype-canvas|main-titlebar/);
});

test("the title keeps its icon without the cloudy header artwork", () => {
  assert.match(
    html,
    /<div class="app-identity"[^>]*>\s*<img class="app-icon"[^>]*jjinni-header-full\.jpeg[^>]*>\s*<span id="main-window-title">Transcriber<\/span>/,
  );
  assert.doesNotMatch(html + css, /header-cloudy-(?:background|edge)/);
});

test("the identity row is compact and visually transparent", () => {
  const identityRule = css.match(/\.app-identity\s*\{([^}]*)\}/)?.[1];
  assert.ok(identityRule, "missing .app-identity rule");
  assert.match(identityRule, /\bheight:\s*40px;/);
  assert.match(identityRule, /\bflex:\s*0 0 40px;/);
  assert.doesNotMatch(identityRule, /\bbackground(?:-color)?:|\bborder(?:-bottom)?:/);
});

test("the app and main area fill the available window", () => {
  assert.match(
    css,
    /\.main-window\s*\{[^}]*\bdisplay:\s*flex;[^}]*\bflex-direction:\s*column;[^}]*\bwidth:\s*100%;[^}]*\bheight:\s*100%;/s,
  );
  assert.match(
    css,
    /\.main-window__content\s*\{[^}]*\bmin-height:\s*0;[^}]*\bflex:\s*1;/s,
  );
});

test("state controls use one compact menu directly below the title", () => {
  assert.match(
    css,
    /\.setup-toolbar,\s*\.complete-toolbar\s*\{[^}]*\bposition:\s*absolute;[^}]*\bright:\s*16px;[^}]*\btop:\s*0;[^}]*\bleft:\s*16px;[^}]*\bheight:\s*53px;/s,
  );
  assert.match(
    css,
    /\.main-state-view\s*\{[^}]*\bpadding-top:\s*69px;/s,
  );
});

test("state toolbars are transparent and each setup control owns its surface", () => {
  const toolbarRule = css.match(
    /\.setup-toolbar,\s*\.complete-toolbar\s*\{([^}]*)\}/,
  )?.[1];
  const controlSurfaceRule = css.match(
    /\.main-field select,\s*\.main-control,\s*\.speaker-control\s*\{([^}]*)\}/,
  )?.[1];

  assert.ok(toolbarRule, "missing shared state toolbar rule");
  assert.match(toolbarRule, /\bbackground:\s*transparent;/);
  assert.match(toolbarRule, /\bborder:\s*0;/);
  assert.match(toolbarRule, /\bbox-shadow:\s*none;/);
  assert.match(toolbarRule, /\bbackdrop-filter:\s*none;/);

  assert.ok(controlSurfaceRule, "missing shared setup control surface rule");
  assert.match(controlSurfaceRule, /\bbackground:\s*rgba\(/);
  assert.match(controlSurfaceRule, /\bborder:\s*1px solid /);
  assert.match(controlSurfaceRule, /\bborder-radius:\s*14px;/);
});

test("language and speaker fields share the same fixed control height", () => {
  const sharedControlRule = css.match(
    /\.main-field select,\s*\.main-control,\s*\.speaker-control,\s*\.main-primary-action,\s*\.main-secondary-action\s*\{([^}]*)\}/,
  )?.[1];

  assert.ok(sharedControlRule, "missing shared control sizing rule");
  assert.match(sharedControlRule, /\bheight:\s*38px;/);
  assert.match(sharedControlRule, /\bflex:\s*0 0 38px;/);
  assert.doesNotMatch(
    css,
    /\.speaker-control\s*\{[^}]*\bflex:\s*1;/,
    "speaker-specific styles must not override the shared control height",
  );
});

test("file status uses an inset liquid-glass card", () => {
  const fileStatusRule = ruleBody(".file-status-row");

  assert.ok(fileStatusRule, "missing .file-status-row rule");
  assert.match(fileStatusRule, /\bmargin:\s*0 16px;/);
  assert.match(fileStatusRule, /\bbackground:\s*rgba\(/);
  assert.match(fileStatusRule, /\bborder:\s*1px solid /);
  assert.match(fileStatusRule, /\bborder-radius:\s*16px;/);
  assert.match(fileStatusRule, /\bbox-shadow:/);
  assert.match(fileStatusRule, /\bbackdrop-filter:\s*blur\(/);
});

test("the optimized stylesheet has no custom properties", () => {
  assert.doesNotMatch(css, /--[\w-]+\s*:|var\(/);
});

test("compact windows keep every dock action visible", () => {
  assert.match(
    css,
    /@media \(max-width: 480px\)[\s\S]*?\.main-control span,[\s\S]*?display:\s*none;/,
  );
  assert.match(
    css,
    /@media \(max-width: 480px\)[\s\S]*?\.main-control,[\s\S]*?min-width:\s*44px;/,
  );
  assert.match(
    css,
    /@media \(max-width: 480px\)[\s\S]*?\.setup-toolbar,\s*\.complete-toolbar\s*\{[^}]*\btop:\s*0;/,
  );
  assert.match(
    html,
    /<button class="main-control main-control--file"[^>]*aria-label="Open file"/,
  );
  assert.match(
    html,
    /<button class="main-primary-action"[^>]*aria-label="Transcribe"/,
  );
});
