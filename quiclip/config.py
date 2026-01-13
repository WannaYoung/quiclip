from __future__ import annotations

"""应用配置。

当前仅包含媒体根目录，用于服务器端浏览/选择视频文件。
"""

from dataclasses import dataclass

MEDIA_ROOT = "/vol3/1003/Adult"


@dataclass(frozen=True)
class AppConfig:
    """应用配置。

    - 媒体根目录：用于在服务器端浏览/选择视频文件（不是本机上传）
    """

    media_root: str

    @staticmethod
    def from_env() -> "AppConfig":
        """从环境/常量加载配置。"""
        return AppConfig(media_root=MEDIA_ROOT)
