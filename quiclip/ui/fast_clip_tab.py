from __future__ import annotations

import os
import tempfile
import time
from typing import Any, Dict, List, Tuple

import gradio as gr

try:
    from gradio_rangeslider import RangeSlider as ExternalRangeSlider
except Exception:  # noqa: BLE001
    ExternalRangeSlider = None

from quiclip.config import AppConfig
from quiclip.services.clip_merge import ClipSegment, clip_and_merge
from quiclip.services.file_browser import VIDEO_EXTS
from quiclip.services.ffmpeg_utils import FfmpegError, probe_video_meta


def build_fast_clip_tab(config: AppConfig) -> None:
    """构建“快速剪辑”Tab。"""

    state_segments = gr.State([])  # List[Dict]
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

    gr.HTML(
        """
        <style>
          #qc-fast-preview-wrap {
            width: 66.6667%;
            min-width: 400px;
            margin-left: auto;
            margin-right: auto;
          }
          @media (max-width: 600px) {
            #qc-fast-preview-wrap {
              width: 100%;
              min-width: 0;
            }
          }
          #qc-fast-video-preview video {
            object-fit: contain;
          }
          .qc-fast-left {
            display: flex;
            flex-direction: column;
            height: 100%;
          }
          #qc-fast-load-btn {
            margin-top: auto;
          }
        </style>
        """
    )

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
    load_btn = gr.Button("加载视频")

    gr.Markdown("## 预览")
    gr.HTML('<div id="qc-fast-preview-wrap">')
    video_preview = gr.Video(label="视频预览", elem_id="qc-fast-video-preview")
    gr.HTML("</div>")

    meta_text = gr.Markdown("")

    gr.Markdown("## 2) 选择截取区间")
    if ExternalRangeSlider is not None:
        range_slider = ExternalRangeSlider(label="截取区间（秒）", minimum=0, maximum=1, value=(0, 1))
        start_slider = None
        end_slider = None
    else:
        range_slider = None
        start_slider = gr.Slider(label="开始时间（秒）", minimum=0, maximum=1, value=0, step=0.1)
        end_slider = gr.Slider(label="结束时间（秒）", minimum=0, maximum=1, value=1, step=0.1)
    add_btn = gr.Button("添加到列表")

    gr.Markdown("## 3) 待剪辑合并区间列表（可删除/调整顺序）")

    with gr.Row():
        segments_df = gr.Dataframe(
            headers=["序号", "文件", "开始(秒)", "结束(秒)"],
            datatype=["number", "str", "number", "number"],
            value=[],
            interactive=False,
            row_count=(0, "dynamic"),
            col_count=(4, "fixed"),
            label="区间列表",
        )

    with gr.Row():
        idx_box = gr.Number(label="操作序号（1 开始）", value=1, precision=0)
        up_btn = gr.Button("上移")
        down_btn = gr.Button("下移")
        del_btn = gr.Button("删除")
        clear_btn = gr.Button("清空列表")

    gr.Markdown("## 4) 快速剪辑合并")
    with gr.Row():
        selected_output_dir = gr.Textbox(label="输出目录", interactive=True, value=media_root_abs)
        run_btn = gr.Button("快速剪辑合并")

    output_video = gr.Video(label="输出预览")
    status_text = gr.Markdown("")

    def _make_preview_clip(path: str, start_sec: float, end_sec: float) -> str | None:
        try:
            start = max(float(start_sec), 0.0)
            end = max(float(end_sec), 0.0)
            if end <= start:
                return None

            duration = min(end - start, 8.0)
            out_dir = tempfile.mkdtemp(prefix="quiclip_preview_")
            ts = time.strftime("%Y%m%d-%H%M%S")
            out_path = os.path.join(out_dir, f"preview-{ts}.mp4")
            cmd = [
                "ffmpeg",
                "-y",
                "-ss",
                f"{start:.3f}",
                "-i",
                path,
                "-t",
                f"{duration:.3f}",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "28",
                "-an",
                "-movflags",
                "+faststart",
                out_path,
            ]
            import subprocess

            p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if p.returncode != 0:
                return None
            return out_path
        except Exception:  # noqa: BLE001
            return None

    def _load_video_for_range(path_value: str | None, out_dir_value: str | None):
        path = _resolve_selected_path(path_value)
        if not path:
            return None, "**提示**：请选择有效的视频文件。", gr.update(), _safe_dir(out_dir_value)

        try:
            meta = probe_video_meta(path)
        except Exception as e:  # noqa: BLE001
            return None, f"**错误**：读取视频信息失败：{e}", gr.update(), _safe_dir(out_dir_value)

        rel_label = os.path.relpath(path, media_root_abs)
        md = f"**文件**：`{rel_label}`  \n**时长**：{meta.duration_seconds:.3f} 秒"
        max_v = max(meta.duration_seconds, 0.1)
        range_update = gr.update(minimum=0, maximum=max_v, value=(0, min(meta.duration_seconds, 5.0)))
        return path, md, range_update, _safe_dir(os.path.dirname(path))

    def _load_video_for_sliders(path_value: str | None, out_dir_value: str | None):
        path = _resolve_selected_path(path_value)
        if not path:
            return None, "**提示**：请选择有效的视频文件。", gr.update(), gr.update(), _safe_dir(out_dir_value)

        try:
            meta = probe_video_meta(path)
        except Exception as e:  # noqa: BLE001
            return None, f"**错误**：读取视频信息失败：{e}", gr.update(), gr.update(), _safe_dir(out_dir_value)

        rel_label = os.path.relpath(path, media_root_abs)
        md = f"**文件**：`{rel_label}`  \n**时长**：{meta.duration_seconds:.3f} 秒"
        max_v = max(meta.duration_seconds, 0.1)
        start_update = gr.update(minimum=0, maximum=max_v, value=0)
        end_update = gr.update(minimum=0, maximum=max_v, value=min(meta.duration_seconds, 5.0))
        return path, md, start_update, end_update, _safe_dir(os.path.dirname(path))

    def _default_out_dir_from_file(path_value: str | None) -> str:
        path = _resolve_selected_path(path_value)
        if not path:
            return media_root_abs
        return _safe_dir(os.path.dirname(path))

    def _segments_to_rows(segments: List[Dict[str, Any]]):
        rows: List[List[Any]] = []
        for i, s in enumerate(segments, start=1):
            try:
                rel_label = os.path.relpath(str(s["path"]), media_root_abs)
            except Exception:  # noqa: BLE001
                rel_label = str(s.get("label") or s.get("path") or "")
            rows.append([i, rel_label, float(s["start_sec"]), float(s["end_sec"])])
        return rows

    def _add_segment(path_value: str | None, start_sec: float, end_sec: float, segments: List[Dict[str, Any]]):
        path = _resolve_selected_path(path_value)
        if not path:
            return segments, _segments_to_rows(segments)

        start, end = float(start_sec), float(end_sec)
        if end <= start:
            return segments, _segments_to_rows(segments)
        segments = list(segments)
        segments.append({"label": os.path.basename(path), "path": path, "start_sec": start, "end_sec": end})
        return segments, _segments_to_rows(segments)

    def _move(segments: List[Dict[str, Any]], idx: float, direction: int):
        segments = list(segments)
        i = int(idx) - 1
        j = i + direction
        if i < 0 or i >= len(segments) or j < 0 or j >= len(segments):
            return segments, _segments_to_rows(segments)
        segments[i], segments[j] = segments[j], segments[i]
        return segments, _segments_to_rows(segments)

    def _delete(segments: List[Dict[str, Any]], idx: float):
        segments = list(segments)
        i = int(idx) - 1
        if i < 0 or i >= len(segments):
            return segments, _segments_to_rows(segments)
        segments.pop(i)
        return segments, _segments_to_rows(segments)

    def _clear():
        return [], []

    def _run(segments: List[Dict[str, Any]], out_dir_value: str | None):
        try:
            out_dir = _safe_dir(out_dir_value)
            segs = [
                ClipSegment(input_path=s["path"], start_sec=float(s["start_sec"]), end_sec=float(s["end_sec"]))
                for s in segments
            ]
            out_path = clip_and_merge(segs, out_dir)
            return out_path, f"**完成**：`{os.path.relpath(out_path, media_root_abs)}`"
        except (FfmpegError, ValueError) as e:
            return None, f"**错误**：{e}"
        except Exception as e:  # noqa: BLE001
            return None, f"**未知错误**：{e}"

    if range_slider is not None:
        file_explorer.change(_normalize_selected_file, inputs=[file_explorer], outputs=[selected_file_path])
        file_explorer.change(_default_out_dir_from_file, inputs=[file_explorer], outputs=[selected_output_dir])

        load_btn.click(
            _load_video_for_range,
            inputs=[selected_file_path, selected_output_dir],
            outputs=[video_preview, meta_text, range_slider, selected_output_dir],
        )

        def _preview_from_range(path_value: str | None, r: Tuple[float, float]):
            path = _resolve_selected_path(path_value)
            if not path:
                return gr.update()
            preview = _make_preview_clip(path, float(r[0]), float(r[1]))
            return preview

        release_fn = getattr(range_slider, "release", None)
        if callable(release_fn):
            release_fn(_preview_from_range, inputs=[selected_file_path, range_slider], outputs=[video_preview])
        else:
            range_slider.change(_preview_from_range, inputs=[selected_file_path, range_slider], outputs=[video_preview])

        def _add_from_range(path_value: str | None, r: Tuple[float, float], segments: List[Dict[str, Any]]):
            return _add_segment(path_value, float(r[0]), float(r[1]), segments)

        add_btn.click(
            _add_from_range,
            inputs=[selected_file_path, range_slider, state_segments],
            outputs=[state_segments, segments_df],
        )
    else:
        file_explorer.change(_normalize_selected_file, inputs=[file_explorer], outputs=[selected_file_path])
        file_explorer.change(_default_out_dir_from_file, inputs=[file_explorer], outputs=[selected_output_dir])

        load_btn.click(
            _load_video_for_sliders,
            inputs=[selected_file_path, selected_output_dir],
            outputs=[video_preview, meta_text, start_slider, end_slider, selected_output_dir],
        )

        def _preview_from_sliders(path_value: str | None, start_sec: float, end_sec: float):
            path = _resolve_selected_path(path_value)
            if not path:
                return gr.update()
            preview = _make_preview_clip(path, float(start_sec), float(end_sec))
            return preview

        release_start = getattr(start_slider, "release", None)
        release_end = getattr(end_slider, "release", None)
        if callable(release_start):
            release_start(_preview_from_sliders, inputs=[selected_file_path, start_slider, end_slider], outputs=[video_preview])
        else:
            start_slider.change(_preview_from_sliders, inputs=[selected_file_path, start_slider, end_slider], outputs=[video_preview])

        if callable(release_end):
            release_end(_preview_from_sliders, inputs=[selected_file_path, start_slider, end_slider], outputs=[video_preview])
        else:
            end_slider.change(_preview_from_sliders, inputs=[selected_file_path, start_slider, end_slider], outputs=[video_preview])

        add_btn.click(
            _add_segment,
            inputs=[selected_file_path, start_slider, end_slider, state_segments],
            outputs=[state_segments, segments_df],
        )

    def _select_row(evt: gr.SelectData):
        try:
            return int(evt.index[0]) + 1
        except Exception:  # noqa: BLE001
            return 1

    segments_df.select(_select_row, inputs=None, outputs=[idx_box])

    up_btn.click(lambda segs, idx: _move(segs, idx, -1), inputs=[state_segments, idx_box], outputs=[state_segments, segments_df])
    down_btn.click(lambda segs, idx: _move(segs, idx, 1), inputs=[state_segments, idx_box], outputs=[state_segments, segments_df])
    del_btn.click(_delete, inputs=[state_segments, idx_box], outputs=[state_segments, segments_df])
    clear_btn.click(_clear, outputs=[state_segments, segments_df])

    run_btn.click(_run, inputs=[state_segments, selected_output_dir], outputs=[output_video, status_text])
