import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { test } from "node:test";
import { providerPatch, saveProvider } from "./configure-provider.mjs";

test("IPTV accepts a private imported M3U, never an arbitrary host file", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "zombie-config-"));
  try {
    fs.mkdirSync(path.join(root, "media"));
    fs.writeFileSync(path.join(root, "media", "channels.m3u"), "#EXTM3U\n");
    assert.deepEqual(
      providerPatch("iptv", { source: "file", filename: "channels.m3u" }, {}, root),
      {
        enabled: true,
        playlistPath: "/media/channels.m3u",
      },
    );
    assert.throws(() => providerPatch("iptv", { source: "file", filename: "../secret" }, {}, root));
    fs.symlinkSync(path.join(root, "media", "channels.m3u"), path.join(root, "media", "alias.m3u"));
    assert.throws(() => providerPatch("iptv", { source: "file", filename: "alias.m3u" }, {}, root));
    const oversized = path.join(root, "media", "oversized.m3u");
    fs.writeFileSync(oversized, "#EXTM3U\n");
    fs.truncateSync(oversized, 8 * 1024 * 1024 + 1);
    assert.throws(() =>
      providerPatch("iptv", { source: "file", filename: "oversized.m3u" }, {}, root),
    );
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});

test("Stremio setup requires the catalog selected from the addon manifest", () => {
  assert.throws(
    () => providerPatch("stremio", { url: "https://addon.example.org/manifest.json" }),
    /catalog ID is required/,
  );
  assert.deepEqual(
    providerPatch("stremio", {
      url: "https://addon.example.org/manifest.json",
      catalogId: "top",
      mediaType: "series",
    }),
    {
      enabled: true,
      url: "https://addon.example.org/manifest.json",
      catalogId: "top",
      mediaType: "series",
    },
  );
  assert.deepEqual(
    providerPatch(
      "stremio",
      {},
      {
        enabled: false,
        url: "https://addon.example.org/manifest.json",
        catalogId: "top",
        mediaType: "series",
      },
    ),
    {
      enabled: true,
      url: "https://addon.example.org/manifest.json",
      catalogId: "top",
      mediaType: "series",
    },
  );
});

test("Plex update preserves unrelated worker secrets and writes mode 0600", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "zombie-config-"));
  try {
    fs.mkdirSync(path.join(root, "gateway"));
    const file = path.join(root, "gateway", "providers.json");
    fs.writeFileSync(file, JSON.stringify({ youtube: { enabled: true, token: "worker-secret" } }));
    saveProvider(
      root,
      "plex",
      { url: "https://plex.example.org", token: "provider-secret" },
      process.getuid(),
      process.getgid(),
    );
    const result = JSON.parse(fs.readFileSync(file, "utf8"));
    assert.deepEqual(result.youtube, { enabled: true, token: "worker-secret" });
    assert.deepEqual(result.plex, {
      enabled: true,
      url: "https://plex.example.org",
      token: "provider-secret",
    });
    assert.equal(fs.statSync(file).mode & 0o777, 0o600);
    assert.throws(() => providerPatch("stremio", { url: "file:///etc/passwd" }));
    assert.throws(() =>
      providerPatch("plex", { url: "https://name:pass@example.org", token: "x" }),
    );
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});

test("Malformed private configuration does not disclose secret contents", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "zombie-config-"));
  try {
    fs.mkdirSync(path.join(root, "gateway"));
    const file = path.join(root, "gateway", "providers.json");
    const malformed = '{"plex":{"token":"private-test-token"},oops}';
    fs.writeFileSync(file, malformed);
    assert.throws(
      () =>
        saveProvider(
          root,
          "iptv",
          { source: "url", url: "https://example.org/list.m3u" },
          process.getuid(),
          process.getgid(),
        ),
      (error) => error.message === "Invalid providers.json; existing settings were preserved",
    );
    assert.equal(fs.readFileSync(file, "utf8"), malformed);
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});
