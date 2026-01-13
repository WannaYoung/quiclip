"""Gradio 应用入口。
 
 提供两个功能 Tab：快速剪辑合并、视频合并。
 """
 
import os

import gradio as gr

from quiclip.config import AppConfig
from quiclip.ui.fast_clip_tab import build_fast_clip_tab
from quiclip.ui.merge_tab import build_merge_tab


def build_app() -> gr.Blocks:
    """构建 Gradio UI 并返回 Blocks 实例。"""
    config = AppConfig.from_env()

    with gr.Blocks(title="QuiClip") as demo:
        gr.Markdown("# QuiClip\n\n一个简洁的服务器端视频快速剪辑与合并工具。")
        gr.Markdown(
            f"**媒体根目录**：`{config.media_root}`"
        )

        with gr.Tabs():
            with gr.Tab("快速剪辑"):
                build_fast_clip_tab(config)
            with gr.Tab("视频合并"):
                build_merge_tab(config)

    return demo


if __name__ == "__main__":
    demo = build_app()
    enable_queue = os.environ.get("QUICLIP_ENABLE_QUEUE", "0").strip() in {"1", "true", "yes", "on"}
    launcher = demo.queue() if enable_queue else demo
    config = AppConfig.from_env()
    launcher.launch(
        server_name=os.environ.get("GRADIO_SERVER_NAME", "0.0.0.0"),
        server_port=int(os.environ.get("GRADIO_SERVER_PORT", "7860")),
        debug=True,
        show_error=True,
        allowed_paths=[os.path.abspath(config.media_root)],
    )
