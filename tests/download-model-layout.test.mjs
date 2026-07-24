import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const htmlPath = new URL("../layouts/download-model.html", import.meta.url);
const cssPath = new URL("../layouts/assets/styles.css", import.meta.url);

const [html, css] = await Promise.all([
  readFile(htmlPath, "utf8"),
  readFile(cssPath, "utf8"),
]);

test("the app shell directly contains the menu and main area", () => {
  assert.match(
    html,
    /<main class="app-window"[^>]*>\s*<aside class="language-panel"[\s\S]*?<\/aside>\s*<section class="content-panel"[\s\S]*?<\/section>\s*<\/main>/,
  );
  assert.doesNotMatch(html, /prototype-canvas|window-body/);
});

test("the app shell fills the available window with flexbox", () => {
  assert.match(
    css,
    /\.app-window\s*\{[^}]*\bdisplay:\s*flex;[^}]*\bwidth:\s*100%;[^}]*\bheight:\s*100%;/s,
  );
});

test("the menu is fixed width and the main area is fluid", () => {
  assert.match(
    css,
    /\.language-panel\s*\{[^}]*\bflex:\s*0 0 \d+px;/s,
  );
  assert.match(
    css,
    /\.content-panel\s*\{[^}]*\bflex:\s*1;/s,
  );
});

test("the stylesheet has no custom properties", () => {
  assert.doesNotMatch(css, /--[\w-]+\s*:|var\(/);
});

test("the main content uses all available space", () => {
  assert.doesNotMatch(css, /max-width:\s*680px/);
  assert.match(
    css,
    /\.language-panel,\s*\.content-panel\s*\{[^}]*\bmin-height:\s*0;/s,
  );
  assert.match(css, /\.empty-state\s*\{[^}]*\bmin-height:\s*0;/s);
});
