#!/usr/bin/env python3
"""Exercise the packaged gateway with synthetic local media; no real accounts."""

import json
import os
import subprocess
import tempfile
import time
import urllib.request
import uuid
from pathlib import Path

IMAGE = os.environ.get("ZOMBIE_SMOKE_IMAGE", "zombie-box-tv/gateway:0.1.0-dev.59")


def command(*args):
    return subprocess.check_output(args, text=True).strip()


def fixture(folder):
    captions = folder / "captions.srt"
    captions.write_text("1\n00:00:00,500 --> 00:00:02,500\nHello Zombie\n")
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=green:s=160x90:r=10",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=44100",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=880:sample_rate=44100",
            "-i",
            str(captions),
            "-map",
            "0:v",
            "-map",
            "1:a",
            "-map",
            "2:a",
            "-map",
            "3:s",
            "-t",
            "3",
            "-c:v",
            "libx264",
            "-threads",
            "1",
            "-c:a",
            "aac",
            "-c:s",
            "ass",
            "-metadata:s:a:0",
            "language=eng",
            "-metadata:s:a:1",
            "language=spa",
            str(folder / "tracks.mkv"),
        ],
        check=True,
        timeout=30,
    )


def exercise(base, folder):
    headers = {}

    def request(method, path, body=None, binary=False):
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(
            base + path,
            data=data,
            method=method,
            headers={**headers, "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=45) as response:
            payload = response.read(2 << 20)
            return payload if binary else json.loads(payload)

    registration = request(
        "POST",
        "/v1/devices/register",
        {
            "installationId": "tracks-smoke-device",
            "clientVersion": "dev.16-smoke",
            "protocolVersion": 1,
            "pairingCode": "123456",
            "platform": {"androidApi": 13},
        },
    )
    headers.update(
        {
            "X-Zombie-Device": "tracks-smoke-device",
            "Authorization": "Bearer " + registration["deviceToken"],
        }
    )
    item = request("GET", "/v1/home")["hero"]["item"]["id"]
    plan = request("POST", "/v1/playback", {"itemId": item, "mode": "DIRECT_PLAY"})
    original = "/v1/playback/" + plan["sessionId"]
    tracks = request("GET", original + "/tracks")
    assert tracks["available"] and len(tracks["tracks"]) == 3
    assert tracks["tracks"][1]["language"] == "spa"
    subtitles = request("GET", original + "/subtitles/3")
    assert subtitles["cues"][0]["text"] == "Hello Zombie"
    selected = request("POST", original + "/audio", {"audioId": 2, "positionMs": 1000})
    assert selected["timelineOffsetMs"] == 1000 and not selected["seekable"]
    request("DELETE", original)
    output = folder / "output.mp4"
    output.write_bytes(request("GET", selected["url"], binary=True))
    metadata = json.loads(
        command(
            "ffprobe",
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(output),
        )
    )
    assert len(metadata["streams"]) == 2
    assert metadata["streams"][1]["codec_name"] == "aac"
    assert 1.8 < float(metadata["format"]["duration"]) < 2.4
    replacement = "/v1/playback/" + selected["sessionId"]
    request(
        "PUT",
        replacement + "/progress",
        {"state": "PAUSED", "positionMs": 1250, "durationMs": 3000},
    )
    request("DELETE", replacement)
    resumed = request("POST", "/v1/playback", {"itemId": item, "mode": "TRANSCODE"})
    assert resumed["timelineOffsetMs"] == 1250 and resumed["resumePositionMs"] == 0
    request("DELETE", "/v1/playback/" + resumed["sessionId"])


def main():
    name = "zombie-tracks-smoke-" + uuid.uuid4().hex[:12]
    with tempfile.TemporaryDirectory(prefix="zombie-tracks-") as temporary:
        folder = Path(temporary)
        folder.chmod(0o755)
        fixture(folder)
        try:
            command(
                "docker",
                "run",
                "--detach",
                "--rm",
                "--name",
                name,
                "--read-only",
                "--tmpfs",
                "/data:uid=65532,gid=65532,mode=0700",
                "--volume",
                f"{folder}:/media:ro,Z",
                "--publish",
                "127.0.0.1::8090",
                "--env",
                "ZOMBIE_PAIRING_CODE=123456",
                IMAGE,
                "-listen",
                "0.0.0.0:8090",
                "-state",
                "/data/gateway.db",
                "-media-dir",
                "/media",
                "-media-tools",
            )
            address = command("docker", "port", name, "8090/tcp")
            base = "http://" + address
            for attempt in range(30):
                try:
                    with urllib.request.urlopen(base + "/health", timeout=1):
                        break
                except OSError:
                    if attempt == 29:
                        raise
                    time.sleep(0.2)
            exercise(base, folder)
            print(
                "PASS: packaged inventory, ASS cues, selected stream, timeline and SQLite resume"
            )
            print("PENDING: physical Android playback and synchronization")
        finally:
            subprocess.run(
                ["docker", "rm", "--force", name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )


if __name__ == "__main__":
    main()
