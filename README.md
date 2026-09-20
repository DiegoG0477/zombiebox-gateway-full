# Gateway Full

From the root, `make full-up` builds the core from `../gateway/`; `make full-down` stops it. Do not run the native gateway on the same port simultaneously.

The bootstrap scratch image contains only the Go binary: no shell, FFmpeg or CA bundle. This suffices for health; add a runtime with verified CA certificates and separate workers when outbound provider requests are implemented. This is not a complete media distribution yet.

Core budget: 256 MiB and two CPUs. Future providers need pinned versions, healthchecks, opt-in profiles and separate resource budgets. See `../third_party/README.md` for wrapper boundaries.
