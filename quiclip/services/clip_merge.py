from __future__ import annotations

"""剪辑区间与视频合并的业务封装。"""

import os
import tempfile
import time
from dataclasses import dataclass

from quiclip.services.ffmpeg_utils import fast_concat_mp4, fast_trim_to_mp4


@dataclass(frozen=True)
class ClipSegment:
    """一个剪辑区间（同一输入文件上的时间段）。"""

    input_path: str
    start_sec: float
    end_sec: float


def clip_and_merge(segments: list[ClipSegment], output_dir: str) -> str:
    """对多个区间进行无重编码裁剪后 concat 合并，返回输出文件路径。"""

    if not segments:
        raise ValueError("区间列表为空")

    os.makedirs(output_dir, exist_ok=True)

    ts = time.strftime("%Y%m%d-%H%M%S")
    output_path = os.path.join(output_dir, f"quiclip-clip-{ts}.mp4")

    with tempfile.TemporaryDirectory(prefix="quiclip_") as tmp:
        part_paths: list[str] = []
        for idx, seg in enumerate(segments, start=1):
            part_path = os.path.join(tmp, f"part_{idx:03d}.mp4")
            fast_trim_to_mp4(seg.input_path, seg.start_sec, seg.end_sec, part_path)
            part_paths.append(part_path)

        fast_concat_mp4(part_paths, output_path)

    return output_path


def merge_videos(video_paths: list[str], output_dir: str) -> str:
    """直接 concat 合并多个视频文件，返回输出文件路径。"""

    if not video_paths:
        raise ValueError("视频列表为空")

    os.makedirs(output_dir, exist_ok=True)

    ts = time.strftime("%Y%m%d-%H%M%S")
    output_path = os.path.join(output_dir, f"quiclip-merge-{ts}.mp4")
    fast_concat_mp4(video_paths, output_path)
    return output_path
