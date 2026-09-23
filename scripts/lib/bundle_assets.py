"""Shared source-free bundle assets; runtime configuration is never copied."""

import hashlib
import shutil
import subprocess


def copy_assets(root, core, output):
    for filename in ("install.sh", "control.sh", "README.md", "LICENSE", "NOTICE"):
        shutil.copy2(root / filename, output / filename)
    shutil.copytree(
        root / "scripts",
        output / "scripts",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    for filename in (
        "wrappers/mediamtx/mediamtx.yml",
        "wrappers/rebrowser/seccomp_profile.json",
    ):
        target = output / "assets" / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(core / filename, target)
    # A small host may need longer than the generator's bound for UHD samples.
    # The generator below validates every reused file and replaces invalid ones.
    cached = root / ".local/gateway/probes"
    probes = output / "assets/probes"
    probes.mkdir(parents=True, exist_ok=True)
    for name in ("high-2160.mp4", "hevc-1080.mp4", "hevc-2160.mp4"):
        source = cached / name
        if source.is_file() and not source.is_symlink():
            shutil.copy2(source, probes / name)
    for generator in ("generate-probes.py", "generate-extended-probes.py"):
        subprocess.run(
            [
                "python3",
                str(core / "scripts" / generator),
                "--output",
                str(probes),
            ],
            check=True,
        )


def checksums(output):
    entries = []
    for path in sorted(output.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS":
            with path.open("rb") as source:
                digest = hashlib.file_digest(source, "sha256").hexdigest()
            entries.append(f"{digest}  {path.relative_to(output)}\n")
    (output / "SHA256SUMS").write_text("".join(entries))
