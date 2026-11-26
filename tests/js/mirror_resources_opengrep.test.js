"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const MirrorResources = require("../../web/lib/mirror_resources.js");

test("constant tokenizer retains quoted >, comments and unexecuted script contents", () => {
  const text = [
    '<!-- <img src="ignore.png"> -->',
    '<base href="https://example.test/assets/">',
    '<script src="boot.js">const fake = "<img src=\\"fake.png\\">";</script>',
    '<img data-src="image.png">',
    '<a href="readme.html?x=1>2">Read</a>'
  ].join("");
  const observed = MirrorResources.discover(text, "text/html", "https://example.test/");
  const names = observed.resources.map((item) => item.url);
  assert.ok(names.includes("https://example.test/assets/boot.js"));
  assert.ok(names.includes("https://example.test/assets/image.png"));
  assert.ok(names.some((url) => url.startsWith("https://example.test/assets/readme.html?")));
  assert.ok(names.every((url) => !/fake|ignore/.test(url)));
  assert.ok(observed.unsupported.includes("script_generated_content_not_evaluated"));
});

test("style content remains discoverable after tokenizer parser compatibility rewrite", () => {
  const text = '<style>body{background:url("hero.png")}</style>';
  const observed = MirrorResources.discover(text, "text/html", "https://example.test/page");
  assert.deepEqual(observed.resources, [{url:"https://example.test/hero.png",kind:"asset"}]);
});
