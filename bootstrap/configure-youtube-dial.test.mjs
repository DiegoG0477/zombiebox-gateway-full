import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { test } from "node:test";
import { dialAddress, saveYouTubeDialAddress } from "./configure-youtube-dial.mjs";

function fixture() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "zombie-dial-address-"));
  const directory = path.join(root, "youtube-receiver");
  fs.mkdirSync(directory);
  const file = path.join(directory, "receiver.json");
  const config = {
    token: "private-worker-token-0123456789abcdef",
    listen: "0.0.0.0",
    port: 8095,
    dialPort: 8096,
    customSetting: { keep: true },
  };
  fs.writeFileSync(file, JSON.stringify(config));
  return { root, directory, file, config };
}

test("selecting one LAN address preserves private receiver settings and file mode", () => {
  const { root, directory, file, config } = fixture();
  try {
    saveYouTubeDialAddress(root, "10.42.0.12", process.getuid(), process.getgid());
    assert.deepEqual(JSON.parse(fs.readFileSync(file, "utf8")), {
      ...config,
      dialAddresses: ["10.42.0.12"],
    });
    assert.equal(fs.statSync(file).mode & 0o777, 0o600);
    assert.deepEqual(fs.readdirSync(directory), ["receiver.json"]);

    saveYouTubeDialAddress(root, "192.168.1.10", process.getuid(), process.getgid());
    assert.deepEqual(JSON.parse(fs.readFileSync(file, "utf8")).dialAddresses, ["192.168.1.10"]);
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});

test("invalid, loopback, link-local, multicast and unspecified addresses are rejected", () => {
  for (const address of [
    "",
    "localhost",
    "::1",
    "0.0.0.0",
    "0.10.0.1",
    "127.0.0.1",
    "127.1.2.3",
    "169.254.2.1",
    "224.0.0.1",
    "239.1.2.3",
    "255.255.255.255",
    "10.42.0.1/24",
    "010.42.0.1",
    "10.42.0.256",
    "10.42.0.1\nsecret",
  ]) {
    assert.throws(() => dialAddress(address), `accepted ${JSON.stringify(address)}`);
  }
  assert.equal(dialAddress("172.16.5.9"), "172.16.5.9");
});

test("malformed or oversized private configuration remains untouched without secret disclosure", () => {
  const { root, file } = fixture();
  try {
    for (const content of [
      '{"token":"private-worker-token-0123456789abcdef",oops}',
      "x".repeat(64 * 1024 + 1),
      '{"listen":"0.0.0.0"}',
    ]) {
      fs.writeFileSync(file, content);
      assert.throws(
        () => saveYouTubeDialAddress(root, "10.42.0.12", process.getuid(), process.getgid()),
        (error) => !error.message.includes("private-worker-token"),
      );
      assert.equal(fs.readFileSync(file, "utf8"), content);
    }
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});

test("symbolic links for the receiver file or volume are rejected", () => {
  const { root, directory, file } = fixture();
  try {
    const other = path.join(root, "other.json");
    fs.renameSync(file, other);
    fs.symlinkSync(other, file);
    assert.throws(() =>
      saveYouTubeDialAddress(root, "10.42.0.12", process.getuid(), process.getgid()),
    );
    assert.equal(fs.readFileSync(other, "utf8"), fs.readFileSync(file, "utf8"));

    fs.unlinkSync(file);
    fs.rmdirSync(directory);
    fs.symlinkSync(root, directory);
    assert.throws(() =>
      saveYouTubeDialAddress(root, "10.42.0.12", process.getuid(), process.getgid()),
    );
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});
