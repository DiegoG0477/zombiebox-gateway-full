import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const SUPPORTED = new Set(["iptv", "plex", "jellyfin", "stremio"]);

function validatedURL(value) {
  if (value.length > 4096 || /[\u0000-\u001f\u007f]/.test(value))
    throw new Error("Invalid HTTP(S) address");
  let parsed;
  try {
    parsed = new URL(value);
  } catch {
    throw new Error("Invalid HTTP(S) address");
  }
  if (
    !["http:", "https:"].includes(parsed.protocol) ||
    !parsed.hostname ||
    parsed.username ||
    parsed.password
  )
    throw new Error("Only HTTP(S) addresses without embedded credentials are accepted");
  return value;
}

function validatedText(value, limit) {
  if (!value || value.length > limit || /[\u0000-\u001f\u007f]/.test(value))
    throw new Error("Invalid value");
  return value;
}

function validatedPlaylist(name, seedRoot) {
  if (!/^[a-zA-Z0-9_.-]{1,120}$/.test(name) || name === "." || name === "..")
    throw new Error("Use a simple M3U filename from the private media volume");
  const file = path.join(seedRoot, "media", name);
  const stat = fs.lstatSync(file);
  // The gateway reads at most 8 MiB; do not accept a file it cannot use.
  if (!stat.isFile() || stat.size < 1 || stat.size > 8 * 1024 * 1024)
    throw new Error("Invalid M3U file in the private media volume");
  return "/media/" + name;
}

export function providerPatch(provider, answers, previous = {}, seedRoot = "/seed") {
  if (!SUPPORTED.has(provider)) throw new Error("Unsupported provider");
  if (!previous || typeof previous !== "object" || Array.isArray(previous))
    throw new Error("Invalid existing provider entry; preserved for operator review");
  const next = { ...previous, enabled: true };
  if (provider === "iptv") {
    if (answers.source === "url") {
      next.url = validatedURL(answers.url);
      delete next.playlistPath;
    } else if (answers.source === "file") {
      next.playlistPath = validatedPlaylist(answers.filename, seedRoot);
      delete next.url;
    } else if (answers.source !== "keep" || (!next.url && !next.playlistPath)) {
      throw new Error("Choose an IPTV URL or an imported M3U file");
    }
    if (answers.epgUrl) next.epgUrl = validatedURL(answers.epgUrl);
  } else {
    if (answers.url) next.url = validatedURL(answers.url);
    if (!next.url) throw new Error("A service URL is required");
    if (provider === "plex" || provider === "jellyfin") {
      if (answers.token) next.token = validatedText(answers.token, 4096);
      if (!next.token) throw new Error("A provider token is required");
    }
    if (provider === "jellyfin") {
      if (answers.userId) next.userId = validatedText(answers.userId, 200);
      if (!next.userId) throw new Error("A Jellyfin user ID is required");
    }
    if (provider === "stremio") {
      if (answers.catalogId) next.catalogId = validatedText(answers.catalogId, 200);
      if (!next.catalogId) throw new Error("A Stremio catalog ID is required");
      if (answers.mediaType) next.mediaType = validatedText(answers.mediaType, 40);
    }
  }
  return next;
}

function readConfig(seedRoot) {
  const gatewayDir = path.join(seedRoot, "gateway");
  if (!fs.lstatSync(gatewayDir).isDirectory()) throw new Error("Invalid gateway volume");
  const file = path.join(gatewayDir, "providers.json");
  const stat = fs.lstatSync(file);
  if (!stat.isFile() || stat.size > 1024 * 1024)
    throw new Error("Invalid providers.json; existing settings were preserved");
  let config;
  try {
    config = JSON.parse(fs.readFileSync(file, "utf8"));
  } catch {
    // Parser diagnostics may quote input, including credentials in this private file.
    throw new Error("Invalid providers.json; existing settings were preserved");
  }
  if (!config || typeof config !== "object" || Array.isArray(config))
    throw new Error("Invalid providers.json; existing settings were preserved");
  return { config, file, gatewayDir };
}

export function saveProvider(seedRoot, provider, answers, uid, gid) {
  const { config, file, gatewayDir } = readConfig(seedRoot);
  config[provider] = providerPatch(provider, answers, config[provider], seedRoot);
  const temporary = path.join(gatewayDir, `.providers-${crypto.randomUUID()}.tmp`);
  let fd;
  try {
    fd = fs.openSync(temporary, "wx", 0o600);
    fs.writeFileSync(fd, JSON.stringify(config, null, 2) + "\n");
    fs.fchownSync(fd, uid, gid);
    fs.fchmodSync(fd, 0o600);
    fs.fsyncSync(fd);
    fs.closeSync(fd);
    fd = undefined;
    fs.renameSync(temporary, file);
    const directory = fs.openSync(gatewayDir, "r");
    try {
      fs.fsyncSync(directory);
    } finally {
      fs.closeSync(directory);
    }
  } finally {
    if (fd !== undefined) fs.closeSync(fd);
    if (fs.existsSync(temporary)) fs.unlinkSync(temporary);
  }
}

function question(label, hidden = false) {
  return new Promise((resolve, reject) => {
    process.stderr.write(label);
    let answer = "";
    const stdin = process.stdin;
    stdin.setRawMode(true);
    stdin.resume();
    const finish = (error) => {
      stdin.removeListener("data", onData);
      stdin.setRawMode(false);
      stdin.pause();
      process.stderr.write("\n");
      if (error) reject(error);
      else resolve(answer.trim());
    };
    const onData = (chunk) => {
      for (const byte of chunk) {
        if (byte === 3) return finish(new Error("Cancelled"));
        if (byte === 13 || byte === 10) return finish();
        if (byte === 127 || byte === 8) {
          if (answer.length) {
            answer = answer.slice(0, -1);
            if (!hidden) process.stderr.write("\b \b");
          }
          continue;
        }
        if (byte < 32 || byte === 127 || answer.length >= 4096) continue;
        answer += String.fromCharCode(byte);
        if (!hidden) process.stderr.write(String.fromCharCode(byte));
      }
    };
    stdin.on("data", onData);
  });
}

async function main() {
  const provider = process.argv[2];
  if (!SUPPORTED.has(provider) || !process.stdin.isTTY)
    throw new Error(
      "Usage: docker compose run --rm --no-deps --entrypoint node initialize /configure-provider.mjs {iptv|plex|jellyfin|stremio} (interactive terminal required)",
    );
  const seedRoot = process.env.ZOMBIE_SEED_ROOT || "/seed";
  const uid = Number(process.env.ZOMBIE_UID || 1000);
  const gid = Number(process.env.ZOMBIE_GID || 1000);
  if (![uid, gid].every((id) => Number.isSafeInteger(id) && id > 0))
    throw new Error("Invalid service identity");
  const answers = {};
  if (provider === "iptv") {
    const source = await question("IPTV source: 1 URL, 2 imported M3U file, 3 keep existing: ");
    answers.source = { 1: "url", 2: "file", 3: "keep" }[source];
    if (answers.source === "url") answers.url = await question("M3U URL (hidden): ", true);
    if (answers.source === "file")
      answers.filename = await question("M3U filename in media volume: ");
    answers.epgUrl = await question("XMLTV URL (optional; hidden): ", true);
  } else {
    answers.url = await question(
      `${provider} HTTP(S) address (blank keeps existing; hidden): `,
      true,
    );
    if (provider === "plex" || provider === "jellyfin")
      answers.token = await question("Provider token (blank keeps existing; hidden): ", true);
    if (provider === "jellyfin")
      answers.userId = await question("Jellyfin user ID (blank keeps existing): ");
    if (provider === "stremio") {
      answers.catalogId = await question(
        "Stremio catalog ID from manifest (blank keeps existing): ",
      );
      answers.mediaType = await question(
        "Catalog media type (blank keeps existing/default movie): ",
      );
    }
  }
  saveProvider(seedRoot, provider, answers, uid, gid);
  process.stderr.write(
    `${provider} saved in the private gateway volume. Restart gateway to apply.\n`,
  );
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((error) => {
    process.stderr.write(`Configuration unchanged: ${error.message}\n`);
    process.exitCode = 1;
  });
}
