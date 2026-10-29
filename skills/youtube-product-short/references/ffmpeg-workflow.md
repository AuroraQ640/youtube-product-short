# 本地执行参考

仅在需要执行本地下载、时间变换或导出时读取。命令是参数示例；先发现工具并检查本次媒体格式，不直接复用其他视频的格式 ID。Windows 使用 PowerShell 参数数组或 Python `subprocess.run([...])`，不把未知标题、字幕、URL 拼接为 shell 代码。

## 1. 读取元数据与字幕

```text
yt-dlp --no-playlist --dump-json URL
yt-dlp --no-playlist --list-formats --list-subs URL
yt-dlp --no-playlist --skip-download --write-info-json \
  --write-subs --write-auto-subs --sub-langs it --sub-format vtt \
  -o "source.%(ext)s" URL
```

以上 `\` 仅表示排版续行；PowerShell 请用一行、数组参数或其自身续行语法。选择原语言音轨时检查 `language`、`format_note` 和默认原声音轨标识；不要仅因某个 M4A 质量最高就选中它。需要 JS 运行时时使用实际已安装的 yt-dlp 支持的运行时，并以当前命令帮助为准。

## 2. 获取媒体

先确认 `VIDEO_ID` 对应不高于 720p 的 MP4 视频、`AUDIO_ID` 对应原声，再使用：

```text
yt-dlp -f "VIDEO_ID+AUDIO_ID" --merge-output-format mp4 \
  --ffmpeg-location FFMPEG_PATH -o "source.%(ext)s" URL
```

如确需手动合并：

```text
ffmpeg -i video.mp4 -i audio.m4a -map 0:v:0 -map 1:a:0 \
  -c:v copy -c:a aac -movflags +faststart source.mp4
```

长片下载慢时，可以只获取已选区间，前后留 2-5 秒余量：

```text
yt-dlp --load-info-json source.info.json -f "VIDEO_ID+AUDIO_ID" \
  --download-sections "*250-315" \
  --ffmpeg-location FFMPEG_PATH -o "section-%(section_start)s.%(ext)s"
```

该例本地文件的原片起点是 250 秒。若保留原片 254.28-310.64 秒，本地精剪起点是 4.28 秒，保留长度为 56.36 秒。元数据中的临时媒体 URL 会过期，也可能绑定网络出口；过期后重新提取一次，仍失败则报告具体错误或请求可访问素材。不要公开元数据中的签名 URL。

## 3. 选段计划与字幕脚本

使用 JSON 记录原片秒数；片段按成片顺序排列，可重排。`fps` 应与实际导出一致。不同片段可以单独指定 `speed`，未指定时继承顶层值。

```json
{
  "fps": 30,
  "speed": 1.15,
  "segments": [
    {"start": 10.0, "end": 35.3, "label": "产品亮相"},
    {"start": 80.5, "end": 122.0, "label": "规格与实测"}
  ]
}
```

```text
python scripts/retime_subtitles.py --vtt source.it.vtt \
  --plan edit-plan.json --output product.it.srt --report timing-report.json
```

脚本支持含行内词级时间标记的 YouTube 自动 VTT 和普通句级 VTT，输出初始 SRT。普通 VTT 保留原句的时间范围，不根据字符数伪造词级时间。自动分组仍需人工语义校对；若字幕语言不是意大利语，时间变换不会自动翻译。

报告包含每段的 `frames`、`duration`、`timeline_start`。让 FFmpeg 与字幕使用这些值，避免多次取整导致切点后的累计偏移。词级字幕按词的起点是否落在保留范围内选择，防止上一句的滚动尾字残留；普通句级字幕保留与选段相交的字幕条。`partial_caption_units` 提示字幕单元跨越选段边界，需要人工查看，不能直接据此删除原话。

## 4. 精剪、倍速与合成

单段示意：输入前 `-ss` 为该文件内的偏移，`-t` 为倍速前保留时长。

```text
ffmpeg -ss LOCAL_START -t SOURCE_DURATION -i input.mp4 \
  -vf "setpts=(PTS-STARTPTS)/1.15,fps=30,scale=1280:720,setsar=1" \
  -af "asetpts=PTS-STARTPTS,atempo=1.15,aresample=48000" \
  -c:v libx264 -crf 20 -preset medium -pix_fmt yuv420p \
  -c:a aac -b:a 160k clip.mp4
```

该尺寸示例仅适用于 16:9 源。其他比例先确定裁切或留边方案，不拉伸人物和产品。需要精确累计时长时，视频用 `tpad` 后 `trim=end_frame=N`，音频用 `apad` 后 `atrim=duration=N/fps`，两者重置时间戳，再用 concat filter 合并。只补偿极小的帧量化差，不用长时间复制尾帧填充缺失素材。

字幕可用 ASS 精确控制两行布局，或用 SRT 的 subtitles filter：

```text
subtitles=product.it.srt:force_style='FontName=Arial,FontSize=20,Alignment=2,MarginV=22,Outline=1.4'
```

SRT filter 的字体和边距依赖 libass 脚本分辨率；以上仅为起点，不代表 720p 像素。若使用 ASS，明确 `PlayResX: 1280`、`PlayResY: 720`，再设置约 30-34 px 字号、40 px 底边距。字体须覆盖意大利语重音字符。以实际导出截图判断，不只检查参数。

使用相对字幕路径及明确的工作目录，避免 Windows 盘符冒号与 filter 转义冲突。不同编码参数的片段不能直接 `concat -c copy`；先统一参数或一次重编码合成。可用 `-movflags +faststart` 便于播放。

## 5. 封面与验证

从原视频精准截帧，默认叠加产品名即可，不替换真实产品或人物。用 FFmpeg 的 `drawbox` + `drawtext` 实现半透明黑底白字，字体路径和文字文件均由当前工作区明确提供。叠字前后各检查一次。

```text
ffmpeg -ss FRAME_TIME -i source.mp4 -frames:v 1 cover.png
ffprobe -v error -show_format -show_streams -of json final.mp4
ffmpeg -v error -i final.mp4 -f null -
```

没有 ffprobe 时可以使用 FFmpeg 媒体信息和文件大小读取替代，但需实测容器时长。黑屏、静音检测只是辅助：口播中的正常停顿或原片黑场不自动等于故障。字幕检查应包含语义覆盖、时间变换、开头/中间/结尾及每个拼接点抽查；可直接审听时再核对听感与口型同步。

推荐保存 `source/`、`work/`、`deliverables/` 三类文件。对外交付 MP4、封面、SRT；脚本与选段表可保留供改版，媒体元数据和临时签名链接不放进共享包。
