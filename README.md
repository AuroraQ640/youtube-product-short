# YouTube 产品短视频剪辑 Skill

将 YouTube 产品介绍、评测或 KOL 口播整理成 3 分钟以内的短片，保留原声，重排并烧录意大利语字幕，同时交付 1280×720 封面。

这是一个供 Codex 使用的剪辑工作流，采用 **yt-dlp + Python + FFmpeg**。无需连接 ChatCut。AI 负责理解内容、选段和核对结果，工具负责下载、时间换算和导出。

## 下载

- [Skill 安装包](dist/youtube-product-short.zip)：包含完整技能说明、参考文件和字幕辅助脚本。
- [PDF 操作手册](docs/YouTube_Product_Video_SOP.pdf)：6 页中文 SOP、检查清单和已完成案例。
- [查看 Skill 说明](skills/youtube-product-short/SKILL.md)

## 同事如何使用

### 1. 安装 Skill

下载上方 Skill 安装包，在 Codex 中打开存放压缩包的文件夹，然后发送：

> 请将当前文件夹中的 youtube-product-short.zip 解压并安装到我的 Codex 用户技能目录，保留完整目录结构。检查 Python、yt-dlp 和 FFmpeg 是否可用；缺少时协助配置。

也可以手动解压，将完整的 `youtube-product-short` 文件夹放入默认用户技能目录：

| 系统 | 默认位置 |
| --- | --- |
| Windows | `%USERPROFILE%\.codex\skills\youtube-product-short\` |
| macOS / Linux | `~/.codex/skills/youtube-product-short/` |

如果设置了 `CODEX_HOME`，使用 `$CODEX_HOME/skills/youtube-product-short/`。确保 `SKILL.md` 位于该文件夹的第一层，不要多套一层同名目录。让 Codex 确认已发现此 Skill 后再调用。

### 2. 提交剪辑任务

```text
使用 $youtube-product-short 剪辑下面的视频。
视频链接：填写 YouTube 链接
产品名称：填写产品名
按默认 SOP 执行。
```

有特殊要求直接写在后面，例如：

```text
这次控制在 90 秒以内，不要倍速，字幕改成英语，重点保留性能实测。
```

用户当次明确要求优先于默认设置。

### 3. 检查交付

| 项目 | 默认标准 |
| --- | --- |
| 成片 | MP4，H.264 + AAC，1280×720，横屏 16:9 |
| 时长 | 少于 180 秒 |
| 体积 | 少于 200,000,000 字节，即 200 MB |
| 倍速 | 1.1-1.2×，以听感和字幕可读性为准 |
| 字幕 | 意大利语硬字幕，另附 UTF-8 SRT |
| 封面 | 1280×720，优先 KOL 手持产品的真实截图 |
| 内容 | 产品亮相、卖点、规格、实测、接口/设计、总结，按原片内容取舍 |

## 工作流程

1. 获取视频信息、原声音轨和字幕。
2. 去掉滚动字幕重复行，按完整语义选取核心片段。
3. 先完成选段与速度，再计算成片时间轴。
4. 重排字幕，检查产品名、数字单位及自然断句。
5. 使用原片候选帧制作封面。
6. 检查实际时长、体积、解码、字幕和画面，再交付。

核心原则是 **先选段后包装**。保留测试条件、否定和比较对象；不把待机功耗改写成满载功耗，不拼接出原片没有表达的结论。

## 运行环境

- 可读写本地任务文件并运行命令的 Codex 环境。
- Python 3、yt-dlp、FFmpeg；FFmpeg 应支持 H.264/AAC、`subtitles` 或 `ass` 字幕滤镜及 `drawtext`。
- 获取 YouTube 素材时，需要可访问视频及字幕的网络环境。
- 字幕辅助脚本只使用 Python 标准库；完整视频剪辑仍需要 yt-dlp 和 FFmpeg。

工具路径由使用者的实际环境发现，包内不包含机器专属路径、账号凭证或媒体下载签名。此包不自带上述工具，也不自带原视频。

## 字幕时间重排脚本

支持 YouTube 含词级标记的滚动 VTT 和普通句级 VTT。输入选段计划后，输出初始 SRT 和按帧量化的时间映射报告。

从仓库根目录运行下面的一行命令：

```sh
python skills/youtube-product-short/scripts/retime_subtitles.py --vtt examples/sample.it.vtt --plan examples/edit-plan.json --output work/example.it.srt --report work/timing-report.json
```

示例字幕为自行编写的测试文本。真实任务应替换为对应视频字幕和选段表。脚本不会翻译，也不会替代语义选段、字幕校对和听感检查。

详细参数与 FFmpeg 参考：[本地执行工作流](skills/youtube-product-short/references/ffmpeg-workflow.md)。

## 仓库结构

```text
skills/youtube-product-short/
  SKILL.md
  agents/openai.yaml
  references/ffmpeg-workflow.md
  scripts/retime_subtitles.py
docs/YouTube_Product_Video_SOP.pdf
dist/youtube-product-short.zip
examples/edit-plan.json
examples/sample.it.vtt
```

## 已验证范围

该流程已用于一条 AX9 Max 产品介绍剪辑：174.6 秒、57.84 MB、1.18×、1280×720，并交付意大利语字幕及封面。辅助脚本已验证滚动字幕、普通多行字幕、不同速度、边界提示、意大利语重音字符和时间不重叠。

抽帧与解码检查不等于完整观看或听感核对。最终质量仍需结合原片、字幕和实际播放检查。PDF 中的原视频画面仅用于流程示例，原视频及人物画面的权利归各自权利人。
