"""Mux synchronized scene narration into the Playwright-recorded demo."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "tmp" / "full-feature-video"
DELIVERY = Path(r"C:\Users\19546\Desktop\aiaegis国赛最终交付物")
OUTPUT = DELIVERY / "AI-Aegis-全功能演示-中英双语-20260920.mp4"
FFMPEG = Path(
    r"C:\Users\19546\AppData\Local\Microsoft\WinGet\Packages"
    r"\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe"
    r"\ffmpeg-8.1.2-full_build\bin\ffmpeg.exe"
)


def main() -> None:
    scenes = json.loads((WORK / "scenes-runtime.json").read_text(encoding="utf-8"))
    timings = json.loads((WORK / "timings.json").read_text(encoding="utf-8"))
    command = [str(FFMPEG), "-y", "-i", timings["raw_video"]]
    for scene in scenes:
        command += ["-i", scene["voice_file"]]
    endcard = WORK / "endcard.png"
    command += ["-loop", "1", "-i", str(endcard)]

    filters = []
    labels = []
    for index, timing in enumerate(timings["scenes"], 1):
        delay = int(timing["voice_start_ms"])
        label = f"a{index}"
        filters.append(f"[{index}:a]adelay={delay}:all=1,volume=1.0[{label}]")
        labels.append(f"[{label}]")
    filters.append(
        "".join(labels)
        + f"amix=inputs={len(labels)}:duration=longest:normalize=0,alimiter=limit=0.95,apad[aout]"
    )
    end_start = timings["scenes"][-1]["ready_ms"] / 1000.0
    end_duration = scenes[-1]["voice_duration"] + 1.55
    image_input = len(scenes) + 1
    filters += [
        f"[0:v]trim=start=0:end={end_start:.3f},setpts=PTS-STARTPTS,fps=30[vmain]",
        f"[{image_input}:v]scale=1600:900,trim=duration={end_duration:.3f},setpts=PTS-STARTPTS,fps=30[vend]",
        "[vmain][vend]concat=n=2:v=1:a=0[vout]",
    ]
    command += [
        "-filter_complex", ";".join(filters),
        "-map", "[vout]", "-map", "[aout]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "19",
        "-pix_fmt", "yuv420p", "-r", "30",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart", "-shortest", str(OUTPUT),
    ]
    DELIVERY.mkdir(parents=True, exist_ok=True)
    subprocess.run(command, check=True)
    print(OUTPUT)


if __name__ == "__main__":
    main()
