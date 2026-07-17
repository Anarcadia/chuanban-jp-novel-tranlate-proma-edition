---
name: chuanban-jp-novel-tranlate-proma-edition
description: Proma-optimized Japanese novel translation skill for preparing md/txt/epub sources, translating long works into Chinese with terminology continuity, resuming chapter progress, merging the final manuscript, and packaging Pixiv-style ePub output.
---

# 船板日语小说翻译 Proma 版

这个 skill 用来处理日语长篇小说翻译：它会把 `.md`、`.txt` 或 `.epub` 小说素材整理成可翻译的章节文件，自动判断超长章节并实际拆分，随后按章节持续翻译成中文，维护术语、摘要和断点进度。翻译完成后，它还能合并全文，并配合 Pixiv 封面/插图流程制作 ePub。

这是 **Proma edition**。本版针对 Proma 的工作区和子进程编排方式优化：主进程负责准备素材、维护进度和串行调度，章节翻译由 Proma 子进程按 `references/worker.md` 执行，并且必须等待上一章完成后再启动下一章。这个编排方式不是通用 agent 协议。如果在 Codex、Claude Code 或其他 agent 环境中使用，请切换到对应环境版本，或让 AI 先把子进程调用机制改成该环境的 sub-agent 调用名、参数传递方式、等待/恢复机制和返回格式。

建议精翻模型使用 `claude-opus-4.6`，日常翻译模型使用 `DeepSeek-v4-pro`。`DeepSeek-V4-Pro` 必须使用官方 API、官方源的第三方中转 API，或者 OpenRouter 提供的非 SiliconFlow 供应商源；否则容易在翻译过程中撞到审核，出现拒绝翻译的状况。其他模型不保证翻译质量，也不保证这个长篇串行流程的稳定性。

日常使用时，先初始化项目，再用 `prepare_source.py` 读取小说原始文件并生成 `source/` 和 `progress.yaml`。之后 Proma 主进程按章节串行调用 worker 完成翻译；遇到术语歧义时可以询问用户，也可以切换到全自动模式。最后用合并和 ePub 脚本输出成品。

1. 初始化翻译项目。
2. 用 `prepare_source.py` 自动读取 `.md` / `.txt` / `.epub`，抽取章节并按长度拆分。
3. 确认工作模式和风格指南。
4. 严格按章节串行翻译，维护术语表、摘要和进度。
5. 必要时执行术语替换、回退或外接 API 自检。
6. 合并译文到 `final/full_translation.md`。
7. 可选：提取/下载 Pixiv 封面，制作并修复 ePub。

详细执行步骤见 [references/workflow.md](references/workflow.md)。

## Proma 编排规则

- 长篇翻译必须串行处理章节。后一章依赖前一章的术语、摘要和风格状态。
- 主进程只做调度与确认；具体章节翻译交给 Proma 子进程，并按 [references/worker.md](references/worker.md) 执行。
- 其他 agent 环境不要直接照搬 Proma 子进程机制；Codex 和 Claude Code 需要分别改成它们自己的 sub-agent 调用名、任务参数格式和等待机制。
- 术语表必须保留结尾标记 `# ═══ 术语表结束 ═══`，新增术语写在标记之前。
- 默认工作模式为“询问模式”；用户要求提速时可切换为“全自动模式”。
- 建议精翻模型为 `claude-opus-4.6`，日常翻译模型为 `DeepSeek-v4-pro`；`DeepSeek-V4-Pro` 需使用官方 API、官方源第三方中转 API，或 OpenRouter 非 SiliconFlow 供应商源。
- 翻译素材入口支持 `.md` / `.markdown` / `.txt` / `.epub`。
- ePub 制作脚本需要已经整理好的 TXT/Markdown 小说文件；本包不负责抓取网络小说正文。

## 脚本

```bash
python scripts/init_project.py create ./my_translation 我的小说 日语 中文
python scripts/prepare_source.py ./my_translation ./novel.epub --overwrite
python scripts/merge_output.py ./my_translation
python scripts/create_epub.py ./my_translation/final/full_translation.md -i images -o novel.epub
python scripts/fix_epub.py novel.epub novel_final.epub
```

## 依赖

基础翻译脚本使用 Python 3。可选功能依赖：

```bash
pip install pyyaml requests playwright
playwright install chromium
```
