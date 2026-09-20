# Gateway Full

From the root, `make full-up` prepares private runtime directories and builds/starts the shared Go core. `make full-down` stops it. Binding defaults to localhost:8090. Do not run the native gateway concurrently.

The runtime image contains the Go binary and CA certificates. It runs with the configured host UID/GID, a read-only root filesystem, no capabilities, a writable SQLite directory, read-only config/media mounts and Fedora SELinux labels. It has a 256 MiB / two CPU budget. Docker does not contain the Android client or an external database.

Configuration starts empty (`{}`). Add credentials from the paired client or the server JSON/environment as described in [services and credentials](../docs/development/services-and-credentials.md). Private data survives container recreation.

FFmpeg, Threadfin, YouTube.js, go-librespot, UxPlay, MediaMTX and Rebrowser workers are not packaged in this checkpoint. Their upstream references are pinned locally; they are not operational integrations. The milestone registry tracks that remaining work explicitly.
