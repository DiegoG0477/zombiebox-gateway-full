import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { test } from "node:test";
import { saveSpotifyMode, spotifyModeConfig } from "./configure-spotify-mode.mjs";

const legacy = `device_name: Zombie Box Spotify
credentials:
  type: device_auth
zeroconf_enabled: false
audio_backend: pipe
`;

test("existing code mode can switch to local pairing without losing account state", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "zombie-spotify-mode-"));
  try {
    const dir = path.join(root, "spotify-state");
    fs.mkdirSync(dir);
    const config = path.join(dir, "config.yml");
    const state = path.join(dir, "state.json");
    fs.writeFileSync(config, legacy);
    fs.writeFileSync(state, '{"credentials":{"data":"private-test-value"}}');
    saveSpotifyMode(root, "zeroconf", process.getuid(), process.getgid());
    const local = fs.readFileSync(config, "utf8");
    assert.match(
      local,
      /credentials:\n  type: zeroconf\n  zeroconf:\n    persist_credentials: true/,
    );
    assert.match(local, /zeroconf_enabled: true/);
    assert.match(local, /zeroconf_port: 3679/);
    assert.equal(fs.statSync(config).mode & 0o777, 0o600);
    saveSpotifyMode(root, "device_auth", process.getuid(), process.getgid());
    const code = fs.readFileSync(config, "utf8");
    assert.match(code, /  type: device_auth/);
    assert.match(code, /zeroconf_enabled: false/);
    assert.equal(fs.readFileSync(state, "utf8"), '{"credentials":{"data":"private-test-value"}}');
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});

test("unsupported Spotify config is preserved instead of rewritten", () => {
  assert.throws(() => spotifyModeConfig("credentials:\n  type: spotify_token\n", "zeroconf"));
  assert.throws(() => spotifyModeConfig(legacy, "bad-mode"));
});

test("LAN interface allowlist is written atomically and retained when omitted later", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "zombie-spotify-interface-"));
  try {
    const dir = path.join(root, "spotify-state");
    fs.mkdirSync(dir);
    const config = path.join(dir, "config.yml");
    const account = path.join(dir, "state.json");
    fs.writeFileSync(config, legacy);
    fs.writeFileSync(account, '{"credentials":{"data":"preserved"}}');
    saveSpotifyMode(root, "zeroconf", process.getuid(), process.getgid(), ["wlp1s0", "enp0s31f6"]);
    const selected = fs.readFileSync(config, "utf8");
    assert.match(selected, /zeroconf_interfaces_to_advertise:\n  - wlp1s0\n  - enp0s31f6\n/);
    assert.equal(fs.statSync(config).mode & 0o777, 0o600);
    saveSpotifyMode(root, "device_auth", process.getuid(), process.getgid());
    assert.match(fs.readFileSync(config, "utf8"), /  - wlp1s0\n  - enp0s31f6\n/);
    saveSpotifyMode(root, "zeroconf", process.getuid(), process.getgid(), ["--all-interfaces"]);
    assert.doesNotMatch(fs.readFileSync(config, "utf8"), /zeroconf_interfaces_to_advertise/);
    assert.equal(fs.readFileSync(account, "utf8"), '{"credentials":{"data":"preserved"}}');
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});

test("invalid or unsupported interface settings leave the file unchanged", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "zombie-spotify-interface-invalid-"));
  try {
    const dir = path.join(root, "spotify-state");
    fs.mkdirSync(dir);
    const config = path.join(dir, "config.yml");
    fs.writeFileSync(config, legacy);
    for (const names of [["lo"], ["wlp1s0", "wlp1s0"], ["wlp1s0:\nmalicious"]]) {
      assert.throws(() =>
        saveSpotifyMode(root, "zeroconf", process.getuid(), process.getgid(), names),
      );
      assert.equal(fs.readFileSync(config, "utf8"), legacy);
    }
    assert.throws(() =>
      saveSpotifyMode(root, "device_auth", process.getuid(), process.getgid(), ["wlp1s0"]),
    );
    assert.equal(fs.readFileSync(config, "utf8"), legacy);
    fs.writeFileSync(config, legacy + "zeroconf_interfaces_to_advertise: [custom]\n");
    assert.throws(() =>
      saveSpotifyMode(root, "zeroconf", process.getuid(), process.getgid(), ["wlp1s0"]),
    );
    assert.match(fs.readFileSync(config, "utf8"), /\[custom\]/);
    fs.writeFileSync(
      config,
      legacy + "zeroconf_interfaces_to_advertise: []\nzeroconf_interfaces_to_advertise: []\n",
    );
    assert.throws(() =>
      saveSpotifyMode(root, "zeroconf", process.getuid(), process.getgid(), ["wlp1s0"]),
    );
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});
