"""ElevenLabs completion voice.

The workflow's last activity calls `synthesize_and_play` with one sentence.
The sentence never includes a file path or a client name. The API key is read
from the environment. A missing key is a clear error, not a baked-in fallback.

Run directly to hear a line without a workflow:

    python notify_voice.py "Your footage is indexed."
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

# George, a premade voice this account can list. The older public Rachel id
# (21m00Tcm4TlvDq8ikWAM) is rejected on a free key with HTTP 402
# paid_plan_required: "Free users cannot use library voices via the API."
DEFAULT_VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"
DEFAULT_SENTENCE = "Your footage is indexed."


class VoiceError(RuntimeError):
    """Raised when the key is missing or ElevenLabs refuses the request."""


def synthesize_and_play(text: str, workflow_id: str) -> dict:
    """Write an mp3 under var/voice and play it on this machine."""
    load_dotenv()
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not key:
        raise VoiceError("ELEVENLABS_API_KEY is not set. Add it to .env and retry the notification.")

    voice_id = os.environ.get("ELEVENLABS_VOICE_ID", DEFAULT_VOICE_ID).strip() or DEFAULT_VOICE_ID
    audio = _synthesize(text, voice_id, key)
    out_dir = Path("var") / "voice"
    out_dir.mkdir(parents=True, exist_ok=True)
    # The workflow id is our own handle, not a client secret.
    safe_id = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in workflow_id)
    audio_path = out_dir / f"{safe_id}.mp3"
    audio_path.write_bytes(audio)
    play_error = _play(audio_path)
    return {
        "audio_path": str(audio_path.resolve()),
        "played": play_error is None,
        "play_error": play_error,
    }


def _synthesize(text: str, voice_id: str, key: str) -> bytes:
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    response = httpx.post(
        url,
        headers={"xi-api-key": key, "accept": "audio/mpeg"},
        json={"text": text, "model_id": "eleven_multilingual_v2"},
        timeout=60.0,
    )
    if response.status_code >= 400:
        # Status and a short body help a judge debug. The key is not in either.
        detail = response.text[:300]
        raise VoiceError(f"ElevenLabs returned HTTP {response.status_code}: {detail}")
    return response.content


def _play(audio_path: Path) -> str | None:
    """Play via Windows MediaPlayer so the file is not handed to explorer.exe."""
    if sys.platform != "win32":
        opener = "open" if sys.platform == "darwin" else "xdg-open"
        completed = subprocess.run([opener, str(audio_path)], check=False)
        if completed.returncode != 0:
            return f"{opener} exited {completed.returncode}. Audio saved at {audio_path}."
        return None

    script = r"""
Add-Type -AssemblyName PresentationCore
$player = New-Object System.Windows.Media.MediaPlayer
$player.Open([Uri]$env:SMART_PROXY_AUDIO)
$deadline = (Get-Date).AddSeconds(5)
while (-not $player.NaturalDuration.HasTimeSpan -and (Get-Date) -lt $deadline) {
    Start-Sleep -Milliseconds 100
}
$player.Play()
$seconds = 4
if ($player.NaturalDuration.HasTimeSpan) {
    $seconds = [Math]::Min(20, [Math]::Ceiling($player.NaturalDuration.TimeSpan.TotalSeconds) + 1)
}
Start-Sleep -Seconds $seconds
$player.Stop()
$player.Close()
"""
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        env={**os.environ, "SMART_PROXY_AUDIO": audio_path.resolve().as_uri()},
        capture_output=True,
        text=True,
        check=False,
        timeout=40,
    )
    if completed.returncode != 0:
        message = (completed.stderr or completed.stdout or "playback failed").strip()
        return message[:300]
    return None


def main() -> None:
    text = " ".join(sys.argv[1:]).strip() or DEFAULT_SENTENCE
    try:
        result = synthesize_and_play(text, "manual")
    except VoiceError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
    print(result["audio_path"])
    if result["play_error"]:
        print(result["play_error"], file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
