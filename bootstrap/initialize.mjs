import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";

// Executed only inside the one-shot initialization container, never on the host.
const root = process.env.ZOMBIE_SEED_ROOT || "/seed";
const assets = process.env.ZOMBIE_SEED_ASSETS || "/assets";
const uid = Number(process.env.ZOMBIE_UID || 1000);
const gid = Number(process.env.ZOMBIE_GID || 1000);
if (![uid, gid].every((id) => Number.isSafeInteger(id) && id > 0 && id < 2147483647)) {
  throw new Error("Service UID/GID must be non-root numeric identities");
}

function directory(relative) {
  const destination = path.join(root, relative);
  fs.mkdirSync(destination, { recursive: true, mode: 0o700 });
  if (!fs.lstatSync(destination).isDirectory()) throw new Error("Expected a real directory");
  fs.chownSync(destination, uid, gid);
  fs.chmodSync(destination, 0o700);
  return destination;
}

function existing(relative) {
  const destination = path.join(root, relative);
  try {
    const stat = fs.lstatSync(destination);
    if (!stat.isFile() || stat.size > 1024 * 1024) throw new Error("Invalid configuration file");
    return fs.readFileSync(destination, "utf8");
  } catch (error) {
    if (error.code === "ENOENT") return null;
    throw error;
  }
}

function create(relative, contents, mode = 0o600) {
  const destination = path.join(root, relative);
  if (existing(relative) !== null) return;
  const temporary = destination + "." + crypto.randomUUID() + ".tmp";
  const fd = fs.openSync(temporary, "wx", mode);
  try {
    fs.writeFileSync(fd, contents);
    fs.fchownSync(fd, uid, gid);
    fs.fsyncSync(fd);
  } finally {
    fs.closeSync(fd);
  }
  try {
    fs.linkSync(temporary, destination); // Atomic create; never overwrite operator data.
  } catch (error) {
    if (error.code !== "EEXIST") throw error;
    existing(relative);
  } finally {
    fs.unlinkSync(temporary);
  }
}

function asset(relative, contents, mode = 0o600) {
  // Product-owned executable/probe assets follow the selected image on upgrade
  // and rollback. Operator configuration and credentials use create(), not this.
  const destination = path.join(root, relative);
  try {
    const stat = fs.lstatSync(destination);
    if (!stat.isFile() || stat.size > 32 * 1024 * 1024) throw new Error("Invalid generated asset");
    if (fs.readFileSync(destination).equals(contents)) return;
  } catch (error) {
    if (error.code !== "ENOENT") throw error;
  }
  const temporary = destination + "." + crypto.randomUUID() + ".tmp";
  try {
    fs.writeFileSync(temporary, contents, { flag: "wx", mode });
    fs.chownSync(temporary, uid, gid);
    fs.renameSync(temporary, destination);
  } finally {
    if (fs.existsSync(temporary)) fs.unlinkSync(temporary);
  }
}

function config(relative, defaults) {
  create(relative, JSON.stringify(defaults, null, 2) + "\n");
  return JSON.parse(existing(relative));
}

function replacePrivate(relative, contents) {
  const destination = path.join(root, relative);
  const temporary = destination + "." + crypto.randomUUID() + ".tmp";
  let fd;
  try {
    fd = fs.openSync(temporary, "wx", 0o600);
    fs.writeFileSync(fd, contents);
    fs.fchownSync(fd, uid, gid);
    fs.fsyncSync(fd);
    fs.closeSync(fd);
    fd = undefined;
    fs.renameSync(temporary, destination);
    const directory = fs.openSync(path.dirname(destination), "r");
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

function secret(relative, make, pattern) {
  create(relative, make() + "\n");
  const value = existing(relative).trim();
  if (!pattern.test(value)) throw new Error("Invalid stored secret; preserved for operator review");
  return value;
}

function token() {
  return crypto.randomBytes(32).toString("hex");
}

function workerConfig(service, filename, defaults) {
  const value = config(`${service}/${filename}`, { token: token(), ...defaults });
  if (typeof value.token !== "string" || value.token.length < 32)
    throw new Error("Invalid worker token");
  return value;
}

for (const name of [
  "gateway",
  "youtube",
  "youtube-pot",
  "youtube-receiver",
  "spotify",
  "airplay",
  "rebrowser",
  "mediamtx",
  "probes",
  "gateway-state",
  "media",
  "spotify-state",
  "airplay-state",
  "threadfin-state",
]) {
  directory(name);
}
const relay = secret("gateway/relay.key", token, /^[a-f0-9]{64}$/);
secret("gateway/operator.code", () => String(crypto.randomInt(100000, 1000000)), /^[0-9]{6}$/);
const youtube = workerConfig("youtube", "youtube.json", {
  cookie: "",
  poToken: "",
  visitorData: "",
});
// The optional resolver proxies the base worker with this same bearer token.
// Seed one shared identity so enabling the profile cannot silently break auth.
config("youtube-pot/pot.json", {
  token: youtube.token,
  upstream_url: "http://youtube:8091",
  bgutil_url: "http://bgutil-provider:4416",
  cooldown_seconds: 300,
  timeout_seconds: 12,
});
const receiver = workerConfig("youtube-receiver", "receiver.json", {
  listen: "0.0.0.0",
  port: 8095,
  dialPort: 8096,
});
const spotify = workerConfig("spotify", "worker.json", {
  mode: "spotify",
  listen: "host.docker.internal:8092",
  stateDir: "/state",
});
const airplay = workerConfig("airplay", "worker.json", {
  mode: "airplay",
  listen: "0.0.0.0:8093",
  stateDir: "/state",
  pin: String(crypto.randomInt(1000, 10000)),
});
const browser = workerConfig("rebrowser", "browser.json", {});

// Availability and account readiness are separate. An absent optional process is
// unavailable, never a core startup dependency. Existing operator choices win.
const providers = config("gateway/providers.json", {
  youtube: { enabled: true, url: "http://youtube:8091", token: youtube.token },
  youtube_receiver: {
    enabled: true,
    url: "http://host.docker.internal:8095",
    token: receiver.token,
  },
  spotify: {
    enabled: true,
    url: "http://host.docker.internal:8092",
    token: spotify.token,
  },
  airplay: { enabled: true, url: "http://host.docker.internal:8093", token: airplay.token },
  rebrowser: { enabled: true, url: "http://rebrowser:8094", token: browser.token },
});
// Upgrade only the former packaged address. Keep custom workers, tokens and
// account state untouched; the host-network listener is reachable via Docker.
if (providers.spotify?.url === "http://spotify:8092" && providers.spotify.token === spotify.token) {
  providers.spotify.url = "http://host.docker.internal:8092";
  replacePrivate("gateway/providers.json", JSON.stringify(providers, null, 2) + "\n");
}
create("spotify-state/config.yml", fs.readFileSync(path.join(assets, "spotify.yml")));
asset("gateway/launch.sh", fs.readFileSync(path.join(assets, "launch-gateway.sh")), 0o700);
create(
  "mediamtx/mediamtx.yml",
  fs.readFileSync(path.join(assets, "mediamtx.yml"), "utf8") +
    `\nauthHTTPAddress: http://gateway:8090/internal/relay/auth?key=${relay}\n`,
);
for (const entry of fs.readdirSync(path.join(assets, "probes"), { withFileTypes: true })) {
  if (!entry.isFile() || !/^[a-z0-9.-]+$/.test(entry.name))
    throw new Error("Invalid packaged probe");
  asset("probes/" + entry.name, fs.readFileSync(path.join(assets, "probes", entry.name)));
}
console.log(
  "Full volumes initialized. Existing settings and credentials preserved; no secret printed.",
);
