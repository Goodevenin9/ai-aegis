"""Generate scene narration WAV files for the full-feature demonstration."""

from __future__ import annotations

import json
from pathlib import Path
import wave

import win32com.client


ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "tmp" / "full-feature-video"
SCENES_PATH = Path(__file__).with_name("scenes.json")


def choose_voice(speaker, preferred_name: str):
    for voice in speaker.GetVoices():
        if preferred_name.lower() in voice.GetDescription().lower():
            return voice
    return speaker.GetVoices().Item(0)


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as stream:
        return stream.getnframes() / float(stream.getframerate())


def main() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    scenes = json.loads(SCENES_PATH.read_text(encoding="utf-8"))
    speaker = win32com.client.Dispatch("SAPI.SpVoice")
    speaker.Voice = choose_voice(speaker, "Microsoft Zira")
    speaker.Rate = 0
    speaker.Volume = 100
    stream = win32com.client.Dispatch("SAPI.SpFileStream")

    for index, scene in enumerate(scenes, 1):
        output = WORK / f"voice-{index:02d}.wav"
        stream.Open(str(output), 3, False)
        speaker.AudioOutputStream = stream
        speaker.Speak(scene["narration"])
        stream.Close()
        scene["voice_file"] = str(output)
        scene["voice_duration"] = round(wav_duration(output), 3)

    runtime = WORK / "scenes-runtime.json"
    runtime.write_text(json.dumps(scenes, ensure_ascii=False, indent=2), encoding="utf-8")
    print(runtime)


if __name__ == "__main__":
    main()
