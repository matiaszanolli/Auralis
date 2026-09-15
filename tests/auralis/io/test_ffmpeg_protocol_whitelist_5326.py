"""
FFmpeg/ffprobe inputs are pinned to plain files (#5326)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

No ffmpeg or ffprobe invocation passed ``-protocol_whitelist``. Whether a
content-sniffed HLS/concat playlist could reach the network or other local
files therefore rested on FFmpeg's own defaults. ``_probe_audio`` also had no
protocol guard of its own, and the scanner and windowed fingerprinting call it
directly. Both probe paths now run one argv from ``ffprobe_command``, which
applies the guard itself.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import http.server
import shutil
import subprocess
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from auralis.io import unified_loader
from auralis.io.loaders import ffmpeg_loader
from auralis.io.loaders.ffmpeg_loader import _probe_audio, ffprobe_command
from auralis.utils.logging import ModuleError

needs_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe not installed",
)

_PROBE_JSON = (
    '{"streams": [{"codec_type": "audio", "sample_rate": "44100", "channels": 2}], '
    '"format": {"duration": "1.0"}}'
)


class TestProbeArgv:
    @pytest.mark.parametrize("path", ["concat:a.mp3|b.mp3", "pipe:0", "data:audio/mp3;base64,AA"])
    def test_probe_audio_rejects_a_protocol_path_before_spawning(self, path):
        with patch.object(ffmpeg_loader.subprocess, "run") as run, \
                pytest.raises(ModuleError, match="URL/protocol inputs are not allowed"):
            _probe_audio(Path(path))

        run.assert_not_called()

    def test_both_probe_paths_run_the_same_whitelisted_argv(self):
        path = Path("/music/track.mp3")
        commands = []
        for probe in (ffmpeg_loader._probe_audio, unified_loader._get_info_with_ffprobe):
            run = MagicMock(return_value=MagicMock(returncode=0, stdout=_PROBE_JSON))
            with patch.object(unified_loader, "check_ffprobe", return_value=True), \
                    patch.object(ffmpeg_loader.subprocess, "run", run):
                probe(path)
            commands.append(run.call_args[0][0])

        assert commands[0] == commands[1] == ffprobe_command(str(path))
        whitelist = commands[0].index("-protocol_whitelist")
        assert commands[0][whitelist + 1] == "file"
        assert whitelist < commands[0].index("--")


@needs_ffmpeg
class TestRealFfprobe:
    def test_whitelisted_probe_still_reads_a_local_file(self, tmp_path):
        source = tmp_path / "tone.mp3"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-f", "lavfi",
             "-i", "sine=frequency=440:duration=1:sample_rate=44100", "-y", str(source)],
            check=True, timeout=60,
        )

        probe = _probe_audio(source)

        assert probe["sample_rate"] == 44100
        assert probe["channels"] == 1
        assert probe["duration"] == pytest.approx(1.0, abs=0.1)

    def test_a_playlist_cannot_reach_a_network_segment(self, tmp_path):
        requests: list[str] = []

        class _Recorder(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                requests.append(self.path)
                self.send_response(404)
                self.end_headers()

            def log_message(self, format, *args):
                pass

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Recorder)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            playlist = tmp_path / "list.m3u8"
            playlist.write_text(
                "#EXTM3U\n#EXT-X-TARGETDURATION:1\n#EXTINF:1,\n"
                f"http://127.0.0.1:{server.server_port}/segment.mp3\n#EXT-X-ENDLIST\n"
            )
            _probe_audio(playlist)
        finally:
            server.shutdown()
            server.server_close()

        assert requests == []
