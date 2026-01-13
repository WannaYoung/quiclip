from __future__ import annotations

from dataclasses import dataclass

MEDIA_ROOT = "/Users/yang"


@dataclass(frozen=True)
class AppConfig:
    """应用配置。

    - 媒体根目录：用于在服务器端浏览/选择视频文件（不是本机上传）
    """

    media_root: str

    @staticmethod
    def from_env() -> "AppConfig":
        return AppConfig(media_root=MEDIA_ROOT)
