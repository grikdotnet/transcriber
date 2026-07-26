import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const htmlPath = new URL("../layouts/main.html", import.meta.url);
const cssPath = new URL("../layouts/assets/main.css", import.meta.url);

const [html, css] = await Promise.all([
  readFile(htmlPath, "utf8"),
  readFile(cssPath, "utf8"),
]);

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

test("state controls use one fixed-height floating material menu at the top", () => {
  assert.match(
    css,
    /\.setup-toolbar,\s*\.complete-toolbar\s*\{[^}]*\bposition:\s*absolute;[^}]*\bright:\s*16px;[^}]*\btop:\s*16px;[^}]*\bleft:\s*16px;[^}]*\bheight:\s*72px;[^}]*\bborder-radius:\s*20px;/s,
  );
  assert.match(
    css,
    /\.main-state-view\s*\{[^}]*\bpadding-top:\s*104px;/s,
  );
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
    html,
    /<button class="main-control main-control--file"[^>]*aria-label="Open file"/,
  );
  assert.match(
    html,
    /<button class="main-primary-action"[^>]*aria-label="Transcribe"/,
  );
});
