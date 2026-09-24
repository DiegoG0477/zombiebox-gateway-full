import crypto from "node:crypto";
import fs from "node:fs";
import net from "node:net";
import path from "node:path";
import { fileURLToPath } from "node:url";

const MAX_CONFIG_BYTES = 64 * 1024;

export function dialAddress(value) {
  if (typeof value !== "string" || net.isIPv4(value) === false)
    throw new Error("Specify one IPv4 LAN address");
  const octets = value.split(".").map(Number);
  if (
    octets[0] === 0 ||
    octets[0] === 127 ||
    (octets[0] === 169 && octets[1] === 254) ||
    octets[0] >= 224
  )
    throw new Error("Specify a unicast IPv4 LAN address");
  return value;
}

function privateDirectory(seedRoot) {
  try {
    const root = fs.lstatSync(seedRoot);
    const directory = path.join(seedRoot, "youtube-receiver");
    if (root.isDirectory() && fs.lstatSync(directory).isDirectory()) return directory;
  } catch {
    // Keep host paths out of operator-facing errors.
  }
  throw new Error("Invalid receiver volume; existing settings were preserved");
}

function readConfig(file) {
  let fd;
  try {
    fd = fs.openSync(file, fs.constants.O_RDONLY | fs.constants.O_NOFOLLOW);
    const stat = fs.fstatSync(fd);
    if (!stat.isFile() || stat.size < 1 || stat.size > MAX_CONFIG_BYTES)
      throw new Error("Invalid receiver configuration; existing settings were preserved");
    const bytes = Buffer.allocUnsafe(MAX_CONFIG_BYTES + 1);
    let length = 0;
    while (length < bytes.length) {
      const read = fs.readSync(fd, bytes, length, bytes.length - length, length);
      if (read === 0) break;
      length += read;
    }
    if (length > MAX_CONFIG_BYTES)
      throw new Error("Invalid receiver configuration; existing settings were preserved");
    const config = JSON.parse(bytes.toString("utf8", 0, length));
    if (
      !config ||
      typeof config !== "object" ||
      Array.isArray(config) ||
      typeof config.token !== "string" ||
      config.token.length < 32
    )
      throw new Error("Invalid receiver configuration; existing settings were preserved");
    return config;
  } catch {
    // Native or parser errors can include private file contents or platform paths.
    throw new Error("Invalid receiver configuration; existing settings were preserved");
  } finally {
    if (fd !== undefined) fs.closeSync(fd);
  }
}

export function saveYouTubeDialAddress(seedRoot, address, uid, gid) {
  const selected = dialAddress(address);
  if (![uid, gid].every((id) => Number.isSafeInteger(id) && id > 0 && id < 2147483647))
    throw new Error("Invalid service identity");
  const directory = privateDirectory(seedRoot);
  const file = path.join(directory, "receiver.json");
  const config = readConfig(file);
  if (config.dialAddresses?.length === 1 && config.dialAddresses[0] === selected) return;
  config.dialAddresses = [selected];
  const temporary = path.join(directory, `.receiver-${crypto.randomUUID()}.tmp`);
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
    const directoryFD = fs.openSync(directory, "r");
    try {
      fs.fsyncSync(directoryFD);
    } finally {
      fs.closeSync(directoryFD);
    }
  } finally {
    if (fd !== undefined) fs.closeSync(fd);
    if (fs.existsSync(temporary)) fs.unlinkSync(temporary);
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    if (process.argv.length !== 3)
      throw new Error("Usage: configure-youtube-dial.mjs <IPv4 LAN address>");
    saveYouTubeDialAddress(
      process.env.ZOMBIE_SEED_ROOT || "/seed",
      process.argv[2],
      Number(process.env.ZOMBIE_UID || 1000),
      Number(process.env.ZOMBIE_GID || 1000),
    );
    process.stdout.write("YouTube DIAL LAN address saved. Restart the receiver service.\n");
  } catch (error) {
    process.stderr.write(`YouTube DIAL address unchanged: ${error.message}\n`);
    process.exitCode = 1;
  }
}
