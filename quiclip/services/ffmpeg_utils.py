from __future__ import annotations

"""ffmpeg/ffprobe 相关工具封装。

仅提供本项目所需的最小能力：读取时长、裁剪、合并。
"""

import json
import os
import subprocess
from dataclasses import dataclass


class FfmpegError(RuntimeError):
    """ffmpeg/ffprobe 调用失败。"""


@dataclass(frozen=True)
class VideoMeta:
    """视频元信息（当前仅包含时长）。"""

    duration_seconds: float


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    """运行子进程并返回结果（不抛异常，由调用方检查 returncode）。"""
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def ensure_ffmpeg_available() -> None:
    """检查 ffmpeg/ffprobe 是否可用。"""

    for exe in ("ffmpeg", "ffprobe"):
        p = _run([exe, "-version"])
        if p.returncode != 0:
            raise FfmpegError(f"未检测到 {exe}，请先安装并确保在 PATH 中可用。\n{p.stderr}")


def probe_video_meta(path: str) -> VideoMeta:
    """使用 ffprobe 获取视频元信息（目前只需要时长）。"""

    ensure_ffmpeg_available()

    p = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            path,
        ]
    )
    if p.returncode != 0:
        raise FfmpegError(f"ffprobe 失败：{p.stderr}")

    try:
        data = json.loads(p.stdout)
        duration = float(data["format"]["duration"])
    except Exception as e:  # noqa: BLE001
        raise FfmpegError(f"解析 ffprobe 输出失败：{e}")

    return VideoMeta(duration_seconds=duration)


def fast_trim_to_mp4(
    input_path: str,
    start_sec: float,
    end_sec: float,
    output_path: str,
) -> None:
    """无重编码裁剪（mp4 容器），输出用于后续 concat。"""

    ensure_ffmpeg_available()

    if end_sec <= start_sec:
        raise ValueError("结束时间必须大于开始时间")

    duration_sec = float(end_sec) - float(start_sec)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # 说明：
    # - 无重编码（-c copy）会按关键帧对齐，时间会偏差；这里改为重编码以保证区间时长准确
    # - -t 使用“持续时间”，避免 -to 在不同位置的语义差异
    # - -ss 放在 -i 前用于快速 seek，速度优先，精度可控制在 1 秒内
    # - -movflags +faststart 便于在线播放
    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{start_sec:.3f}",
        "-i",
        input_path,
        "-t",
        f"{duration_sec:.3f}",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "18",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-avoid_negative_ts",
        "make_zero",
        "-movflags",
        "+faststart",
        output_path,
    ]

    p = _run(cmd)
    if p.returncode != 0:
        raise FfmpegError(f"裁剪失败：{p.stderr}")


def fast_concat_mp4(inputs: list[str], output_path: str) -> None:
    """无重编码 concat（concat demuxer）。

    注意：
    - 输入文件必须编码参数一致（常见于同一来源/同一编码设置）
    """

    ensure_ffmpeg_available()

    if not inputs:
        raise ValueError("没有输入文件")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # concat demuxer 需要一个 list 文件
    list_file = output_path + ".txt"
    with open(list_file, "w", encoding="utf-8") as f:
        for p in inputs:
            # ffmpeg concat list 对路径有特殊要求
            escaped = p.replace("'", "\\'")
            f.write(f"file '{escaped}'\n")

    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        list_file,
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        output_path,
    ]

    p = _run(cmd)
    try:
        os.remove(list_file)
    except OSError:
        pass

    if p.returncode != 0:
        raise FfmpegError(f"合并失败：{p.stderr}")
