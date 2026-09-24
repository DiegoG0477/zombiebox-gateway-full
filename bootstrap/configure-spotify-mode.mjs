import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const MODES = new Set(["zeroconf", "device_auth"]);
const INTERFACE = /^[A-Za-z][A-Za-z0-9_.-]{0,14}$/;

function interfaceSelection(mode, names) {
  if (names.length === 0) return null; // Preserve an existing allowlist.
  if (mode !== "zeroconf") throw new Error("Network interfaces apply only to zeroconf mode");
  if (names.length === 1 && names[0] === "--all-interfaces") return [];
  if (
    names.length > 4 ||
    new Set(names).size !== names.length ||
    names.some((name) => !INTERFACE.test(name) || name === "lo")
  )
    throw new Error("Specify one to four distinct LAN interface names");
  return names;
}

function setInterfaces(lines, names) {
  const key = "zeroconf_interfaces_to_advertise:";
  if (lines.filter((line) => line.startsWith(key)).length > 1)
    throw new Error("Duplicate Spotify interface settings; existing file preserved");
  const start = lines.findIndex((line) => line === key || line === `${key} []`);
  if (start >= 0) {
    let end = start + 1;
    if (lines[start] === key) {
      while (end < lines.length && /^\s/.test(lines[end])) {
        if (!/^  - [A-Za-z][A-Za-z0-9_.-]{0,14}$/.test(lines[end]))
          throw new Error("Unsupported Spotify interface settings; existing file preserved");
        end++;
      }
    }
    lines.splice(start, end - start);
  } else if (lines.some((line) => line.startsWith(key))) {
    throw new Error("Unsupported Spotify interface settings; existing file preserved");
  }
  if (names.length > 0) {
    const backend = lines.findIndex((line) => line.startsWith("zeroconf_backend:"));
    lines.splice(backend + 1, 0, key, ...names.map((name) => `  - ${name}`));
  }
}

export function spotifyModeConfig(previous, mode, interfaceNames = []) {
  if (!MODES.has(mode)) throw new Error("Choose zeroconf or device_auth");
  const interfaces = interfaceSelection(mode, interfaceNames);
  if (previous.length > 64 * 1024 || /\0/.test(previous))
    throw new Error("Invalid Spotify configuration; preserved for operator review");
  const lines = previous.split("\n");
  const credentials = lines.indexOf("credentials:");
  if (credentials < 0 || !/^  type: (zeroconf|device_auth)$/.test(lines[credentials + 1] || ""))
    throw new Error("Unsupported Spotify credential settings; existing file preserved");
  lines[credentials + 1] = `  type: ${mode}`;
  if (!lines.includes("  zeroconf:")) {
    lines.splice(credentials + 2, 0, "  zeroconf:", "    persist_credentials: true");
  } else {
    const persist = lines.findIndex((line) => /^    persist_credentials: (true|false)$/.test(line));
    if (persist < 0)
      throw new Error("Unsupported Spotify Zeroconf settings; existing file preserved");
    lines[persist] = "    persist_credentials: true";
  }
  const enabled = lines.findIndex((line) => /^zeroconf_enabled: (true|false)$/.test(line));
  if (enabled < 0)
    throw new Error("Unsupported Spotify discovery settings; existing file preserved");
  lines[enabled] = `zeroconf_enabled: ${mode === "zeroconf"}`;
  for (const [name, value] of [
    ["zeroconf_port", "3679"],
    ["zeroconf_backend", "builtin"],
  ]) {
    const index = lines.findIndex((line) => line.startsWith(`${name}:`));
    if (index < 0) lines.splice(enabled + 1, 0, `${name}: ${value}`);
    else lines[index] = `${name}: ${value}`;
  }
  if (interfaces !== null) setInterfaces(lines, interfaces);
  return lines.join("\n");
}

export function saveSpotifyMode(seedRoot, mode, uid, gid, interfaceNames = []) {
  if (![uid, gid].every((value) => Number.isSafeInteger(value) && value > 0))
    throw new Error("Invalid service identity");
  const directory = path.join(seedRoot, "spotify-state");
  const file = path.join(directory, "config.yml");
  const stat = fs.lstatSync(file);
  if (!stat.isFile() || stat.size > 64 * 1024)
    throw new Error("Invalid Spotify configuration; existing file preserved");
  const current = fs.readFileSync(file, "utf8");
  const next = spotifyModeConfig(current, mode, interfaceNames);
  if (next === current) return;
  const temporary = path.join(directory, `.spotify-${crypto.randomUUID()}.tmp`);
  let fd;
  try {
    fd = fs.openSync(temporary, "wx", 0o600);
    fs.writeFileSync(fd, next);
    fs.fchownSync(fd, uid, gid);
    fs.fsyncSync(fd);
    fs.closeSync(fd);
    fd = undefined;
    fs.renameSync(temporary, file);
    const dirFD = fs.openSync(directory, "r");
    try {
      fs.fsyncSync(dirFD);
    } finally {
      fs.closeSync(dirFD);
    }
  } finally {
    if (fd !== undefined) fs.closeSync(fd);
    if (fs.existsSync(temporary)) fs.unlinkSync(temporary);
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    const [mode, ...interfaceNames] = process.argv.slice(2);
    if (!MODES.has(mode))
      throw new Error(
        "Usage: configure-spotify-mode.mjs {zeroconf [LAN-interface ...|--all-interfaces]|device_auth}",
      );
    saveSpotifyMode(
      process.env.ZOMBIE_SEED_ROOT || "/seed",
      mode,
      Number(process.env.ZOMBIE_UID || 1000),
      Number(process.env.ZOMBIE_GID || 1000),
      interfaceNames,
    );
    process.stdout.write(`Spotify mode set to ${mode}. Restart the Spotify service.\n`);
  } catch (error) {
    process.stderr.write(`Spotify mode unchanged: ${error.message}\n`);
    process.exitCode = 1;
  }
}
