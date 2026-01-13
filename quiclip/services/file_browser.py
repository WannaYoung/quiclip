from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List


VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".m4v", ".avi", ".ts", ".wmv"}


@dataclass(frozen=True)
class FileItem:
    label: str
    path: str


def list_video_files(media_root: str, relative_dir: str = "") -> List[FileItem]:
    """列出 media_root 下（可选子目录）的视频文件。

    说明：
    - 用于“服务器文件选择”，不涉及本机上传
    - 只扫描一层目录，避免误扫过多文件
    """

    base_dir = os.path.normpath(os.path.join(media_root, relative_dir))

    if not os.path.isdir(media_root):
        return []

    # 防止目录穿越
    media_root_abs = os.path.abspath(media_root)
    base_dir_abs = os.path.abspath(base_dir)
    if not base_dir_abs.startswith(media_root_abs):
        return []

    items: List[FileItem] = []
    try:
        for name in sorted(os.listdir(base_dir_abs)):
            path = os.path.join(base_dir_abs, name)
            if os.path.isfile(path) and os.path.splitext(name)[1].lower() in VIDEO_EXTS:
                rel_path = os.path.relpath(path, media_root_abs)
                items.append(FileItem(label=rel_path, path=path))
    except OSError:
        return []

    return items
