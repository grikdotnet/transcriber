import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { inflateSync } from "node:zlib";

const root = new URL("../", import.meta.url);
const css = await readFile(new URL("layouts/assets/main.css", root), "utf8");
const html = await readFile(new URL("layouts/main.html", root), "utf8");
const greenMaterial = await readFile(
  new URL("layouts/images/button-primary-green-wide-smooth.png", root),
);
const blueMaterial = await readFile(
  new URL("layouts/images/button-primary-wide-smooth.png", root),
);

const pngColorType = (material) => material[25];
const digest = (data) => createHash("sha256").update(data).digest("hex");

const pngAlpha = (material) => {
  const width = material.readUInt32BE(16);
  const height = material.readUInt32BE(20);
  const stride = width * 4;
  const chunks = [];

  for (let offset = 8; offset < material.length; ) {
    const length = material.readUInt32BE(offset);
    if (material.toString("ascii", offset + 4, offset + 8) === "IDAT") {
      chunks.push(material.subarray(offset + 8, offset + 8 + length));
    }
    offset += length + 12;
  }

  const packed = inflateSync(Buffer.concat(chunks));
  const pixels = Buffer.alloc(stride * height);
  const alpha = Buffer.alloc(width * height);

  for (let y = 0; y < height; y += 1) {
    const filter = packed[y * (stride + 1)];
    const row = packed.subarray(y * (stride + 1) + 1, (y + 1) * (stride + 1));
    for (let x = 0; x < stride; x += 1) {
      const left = x >= 4 ? pixels[y * stride + x - 4] : 0;
      const up = y > 0 ? pixels[(y - 1) * stride + x] : 0;
      const upperLeft =
        y > 0 && x >= 4 ? pixels[(y - 1) * stride + x - 4] : 0;
      const predictor = {
        0: 0,
        1: left,
        2: up,
        3: Math.floor((left + up) / 2),
        4: (() => {
          const p = left + up - upperLeft;
          const distances = [
            Math.abs(p - left),
            Math.abs(p - up),
            Math.abs(p - upperLeft),
          ];
          return [left, up, upperLeft][distances.indexOf(Math.min(...distances))];
        })(),
      }[filter];
      pixels[y * stride + x] = (row[x] + predictor) & 255;
    }
    for (let x = 0; x < width; x += 1) {
      alpha[y * width + x] = pixels[y * stride + x * 4 + 3];
    }
  }

  return alpha;
};

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
  assert.equal(
    greenMaterial.readUInt32BE(16),
    blueMaterial.readUInt32BE(16),
    "Green and blue materials should have the same width",
  );
  assert.equal(
    greenMaterial.readUInt32BE(20),
    blueMaterial.readUInt32BE(20),
    "Green and blue materials should have the same height",
  );
  assert.equal(
    pngColorType(greenMaterial),
    pngColorType(blueMaterial),
    "Green and blue materials should use the same RGBA color type",
  );
  assert.equal(
    digest(pngAlpha(greenMaterial)),
    digest(pngAlpha(blueMaterial)),
    "Green material should preserve the blue material's shadow transparency",
  );
});
