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

  const rule = css.match(/\.complete-toolbar__translate\s*\{([^}]*)\}/)?.[1];

  assert.ok(rule, "Translate material rule should exist");
  assert.match(rule, /height:\s*50px/);
  assert.match(
    rule,
    /background-image:\s*url\("\.\.\/images\/button-primary-green-wide-smooth\.png"\)/,
  );
  assert.match(rule, /background-position:\s*center 4px/);
  assert.match(rule, /background-repeat:\s*no-repeat/);
  assert.match(rule, /background-size:\s*100% 48px/);
  assert.match(rule, /border:\s*0/);
  assert.doesNotMatch(rule, /box-shadow|text-shadow|background:\s*#/);

  assert.equal(greenMaterial.readUInt32BE(16), 536);
  assert.equal(greenMaterial.readUInt32BE(20), 94);
});
