from __future__ import annotations

import os
from typing import Any, Dict, List

import gradio as gr

from quiclip.config import AppConfig
from quiclip.services.clip_merge import merge_videos
from quiclip.services.file_browser import VIDEO_EXTS
from quiclip.services.ffmpeg_utils import FfmpegError


def build_merge_tab(config: AppConfig) -> None:
    """构建“视频合并”Tab。"""

    state_videos = gr.State([])  # List[Dict]
    media_root_abs = os.path.abspath(config.media_root)

    def _resolve_selected_path(path_value: str | None) -> str | None:
        if not path_value:
            return None
        full = os.path.abspath(path_value)
        if not full.startswith(media_root_abs):
            return None
        if not os.path.isfile(full):
            return None
        if os.path.splitext(full)[1].lower() not in VIDEO_EXTS:
            return None
        return full

    def _safe_dir(path_value: str | None) -> str:
        if not path_value:
            return media_root_abs
        full = os.path.abspath(path_value)
        if not full.startswith(media_root_abs):
            return media_root_abs
        if os.path.isdir(full):
            return full
        parent = os.path.dirname(full)
        if os.path.isdir(parent) and parent.startswith(media_root_abs):
            return parent
        return media_root_abs

    def _normalize_selected_file(path_value: str | None) -> str:
        resolved = _resolve_selected_path(path_value)
        return resolved or ""

    def _videos_to_rows(videos: List[Dict[str, Any]]):
        rows: List[List[Any]] = []
        for i, v in enumerate(videos, start=1):
            try:
                rel_label = os.path.relpath(str(v["path"]), media_root_abs)
            except Exception:  # noqa: BLE001
                rel_label = str(v.get("label") or v.get("path") or "")
            rows.append([i, rel_label])
        return rows

    gr.Markdown("## 1) 选择服务器端视频文件")
    file_explorer = gr.FileExplorer(
        label="视频文件",
        root_dir=media_root_abs,
        file_count="single",
        glob="**/*",
        ignore_glob="**/.*",
        height=240,
    )
    selected_file_path = gr.Textbox(label="文件完整路径", interactive=False, value="")
    add_btn = gr.Button("添加到合并列表")

    gr.Markdown("## 2) 合并列表（可删除/调整顺序）")
    with gr.Row():
        videos_df = gr.Dataframe(
            headers=["序号", "文件"],
            datatype=["number", "str"],
            value=[],
            interactive=False,
            row_count=(0, "dynamic"),
            col_count=(2, "fixed"),
            label="视频列表",
        )

    with gr.Row():
        idx_box = gr.Number(label="操作序号（1 开始）", value=1, precision=0)
        up_btn = gr.Button("上移")
        down_btn = gr.Button("下移")
        del_btn = gr.Button("删除")
        clear_btn = gr.Button("清空列表")

    gr.Markdown("## 3) 快速合并")
    with gr.Row():
        output_dir = gr.Textbox(label="输出路径", value=media_root_abs, interactive=True)
        run_btn = gr.Button("快速合并")

    output_video = gr.Video(label="输出预览")
    status_text = gr.Markdown("")

    def _default_out_dir_from_file(path_value: str | None) -> str:
        path = _resolve_selected_path(path_value)
        if not path:
            return media_root_abs
        return _safe_dir(os.path.dirname(path))

    def _add(path_value: str | None, videos: List[Dict[str, Any]]):
        path = _resolve_selected_path(path_value)
        if not path:
            return videos, _videos_to_rows(videos), media_root_abs

        videos = list(videos)
        if not any(v.get("path") == path for v in videos):
            videos.append({"label": os.path.basename(path), "path": path})
        return videos, _videos_to_rows(videos), _safe_dir(os.path.dirname(path))

    def _move(videos: List[Dict[str, Any]], idx: float, direction: int):
        videos = list(videos)
        i = int(idx) - 1
        j = i + direction
        if i < 0 or i >= len(videos) or j < 0 or j >= len(videos):
            return videos, _videos_to_rows(videos)
        videos[i], videos[j] = videos[j], videos[i]
        return videos, _videos_to_rows(videos)

    def _delete(videos: List[Dict[str, Any]], idx: float):
        videos = list(videos)
        i = int(idx) - 1
        if i < 0 or i >= len(videos):
            return videos, _videos_to_rows(videos)
        videos.pop(i)
        return videos, _videos_to_rows(videos)

    def _clear():
        return [], []

    def _run(videos: List[Dict[str, Any]], out_dir_value: str | None):
        try:
            paths = [v["path"] for v in videos]
            out_dir = _safe_dir(out_dir_value)
            out_path = merge_videos(paths, out_dir)
            return out_path, f"**完成**：`{os.path.relpath(out_path, media_root_abs)}`"
        except (FfmpegError, ValueError) as e:
            return None, f"**错误**：{e}"
        except Exception as e:  # noqa: BLE001
            return None, f"**未知错误**：{e}"

    file_explorer.change(_normalize_selected_file, inputs=[file_explorer], outputs=[selected_file_path])
    file_explorer.change(_default_out_dir_from_file, inputs=[file_explorer], outputs=[output_dir])

    add_btn.click(_add, inputs=[selected_file_path, state_videos], outputs=[state_videos, videos_df, output_dir])

    def _select_row(evt: gr.SelectData):
        try:
            return int(evt.index[0]) + 1
        except Exception:  # noqa: BLE001
            return 1

    videos_df.select(_select_row, inputs=None, outputs=[idx_box])

    up_btn.click(lambda vids, idx: _move(vids, idx, -1), inputs=[state_videos, idx_box], outputs=[state_videos, videos_df])
    down_btn.click(lambda vids, idx: _move(vids, idx, 1), inputs=[state_videos, idx_box], outputs=[state_videos, videos_df])
    del_btn.click(_delete, inputs=[state_videos, idx_box], outputs=[state_videos, videos_df])
    clear_btn.click(_clear, outputs=[state_videos, videos_df])

    run_btn.click(_run, inputs=[state_videos, output_dir], outputs=[output_video, status_text])
