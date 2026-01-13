# QuiClip

一个简洁的服务器端视频快速剪辑与合并工具（Gradio + ffmpeg），输出 mp4，尽量使用 **无重编码**（`-c copy`）。

## 1. 环境准备

- 建议使用你的 conda 环境：`quiclip`
- 需要系统已安装 `ffmpeg` / `ffprobe`（并在 PATH 可用）

安装依赖：

```bash
pip install -r requirements.txt
```

## 2. 运行

```bash
python app.py
```

默认媒体根目录是 `./videos`，可通过环境变量指定：

```bash
export QUICLIP_MEDIA_ROOT=/path/to/videos
python app.py
```

输出目录默认 `./outputs`（可在界面修改）。

## 3. 使用说明

- **快速剪辑**：选择服务器端视频 -> 选择区间 -> 添加到列表 -> 调整顺序/删除 -> 一键剪辑合并。
- **视频合并**：选择多个服务器端视频 -> 调整顺序/删除 -> 一键合并。

## 4. 重要限制

- 无重编码 concat 要求输入片段的编码参数一致（通常同来源视频没问题）。
- 精确帧级裁剪在无重编码场景下不保证完全精确（受关键帧影响）。
