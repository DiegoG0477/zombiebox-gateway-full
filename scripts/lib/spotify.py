"""Default go-librespot configuration; existing account state is preserved."""


def prepare_spotify(folder):
    daemon = folder / "state/config.yml"
    if not daemon.exists():
        daemon.write_text("""device_name: Zombie Box Spotify
device_type: speaker
credentials:
  type: device_auth
zeroconf_enabled: false
audio_backend: pipe
audio_output_pipe: /state/audio.pcm
audio_output_pipe_format: s16le
audio_output_pipe_wait_for_reader: true
volume_steps: 100
initial_volume: 75
server:
  enabled: true
  address: 127.0.0.1
  port: 3678
""")
    daemon.chmod(0o600)
