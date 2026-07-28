import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const root = new URL("../", import.meta.url);
const css = await readFile(new URL("layouts/assets/main.css", root), "utf8");
const html = await readFile(new URL("layouts/main.html", root), "utf8");
const greenMaterial = await readFile(
  new URL("layouts/images/button-primary-green-wide-smooth.png", root),
);

test("state 3 Translate uses the generated green image material", () => {
  assert.match(
    html,
    /class="main-secondary-action complete-toolbar__translate"/,
  );

  const sharedRule = css.match(
    /\.main-primary-action,\s*\.complete-toolbar__translate\s*\{([^}]*)\}/,
  )?.[1];
  const rule = [
    ...css.matchAll(/(?:^|\n)\.complete-toolbar__translate\s*\{([^}]*)\}/g),
  ].at(-1)?.[1];

  assert.ok(sharedRule, "Primary actions should share material geometry");
  assert.ok(rule, "Translate material rule should exist");
  assert.match(sharedRule, /height:\s*50px/);
  assert.match(sharedRule, /background-position:\s*center 4px/);
  assert.match(sharedRule, /background-repeat:\s*no-repeat/);
  assert.match(sharedRule, /background-size:\s*100% 48px/);
  assert.match(sharedRule, /border:\s*0/);
  assert.match(
    rule,
    /background-image:\s*url\("\.\.\/images\/button-primary-green-wide-smooth\.png"\)/,
  );
  assert.doesNotMatch(rule, /box-shadow|text-shadow|background:\s*#/);
  assert.match(
    css,
    /\.main-secondary-action:not\(\.complete-toolbar__translate\):hover\s*\{\s*background:\s*#fff;/,
  );
  assert.match(
    css,
    /\.main-primary-action:hover,\s*\.complete-toolbar__translate:hover\s*\{[^}]*filter:\s*brightness\(0\.96\)/,
  );

  assert.equal(greenMaterial.readUInt32BE(16), 536);
  assert.equal(greenMaterial.readUInt32BE(20), 94);
});
