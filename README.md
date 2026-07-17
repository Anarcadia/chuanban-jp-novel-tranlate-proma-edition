# chuanban-jp-novel-tranlate-proma-edition

这是一个面向 Proma 工作区优化的日语小说翻译 skill。它把 `.md`、`.txt`、`.epub` 小说素材准备成可翻译章节，自动处理超长章节拆分，并围绕术语表、章节摘要、断点续翻和最终合并，支持从长篇翻译一直走到 Pixiv 风格 ePub 制作。

这个版本的重点不是单个脚本，而是一套 Proma 编排流程。主进程负责初始化、素材准备、进度管理和串行调度；每一章的翻译由 Proma 子进程执行，子进程读取 `references/worker.md` 的规则，完成翻译、术语更新、摘要更新和进度更新后，只返回简短确认。由于这套子进程机制采用 Proma 独有的编排方式，如果你在 Codex、Claude Code 或其他 agent 环境使用，请切换对应版本，或者先让 AI 把 skill 里的子进程调用方式改成目标环境的 sub-agent 调用名、参数格式、阻塞等待/恢复机制和返回约束。

模型选择也属于这个版本稳定运行的一部分。建议精翻使用 `claude-opus-4.6`，日常翻译使用 `DeepSeek-v4-pro`。使用 `DeepSeek-V4-Pro` 时，请走官方 API、官方源的第三方中转 API，或者 OpenRouter 提供的非 SiliconFlow 供应商源；其他来源容易撞审核，导致拒绝翻译。其他模型不保证翻译质量，也不保证长篇流程稳定。

包内保留了完整的 Proma skill 入口、worker 规则、项目模板，以及素材准备、初始化、分段、合并、术语替换、回退、自检和 ePub 制作脚本。发布版已移除原工作区私有路径、真实项目内容和成品文件。

## 快速开始

```bash
python scripts/init_project.py create ./my_translation 我的小说 日语 中文
```

准备翻译源文件，支持 `.md` / `.markdown` / `.txt` / `.epub`：

```bash
python scripts/prepare_source.py ./my_translation ./novel.epub --overwrite
```

合并译文：

```bash
python scripts/merge_output.py ./my_translation
```

制作 ePub：

```bash
python scripts/create_epub.py ./my_translation/final/full_translation.md -i images -o novel.epub
python scripts/fix_epub.py novel.epub novel_final.epub
```

## 可选依赖

```bash
pip install pyyaml requests playwright
playwright install chromium
```

## 素材准备

`prepare_source.py` 会自动完成：

- 识别输入格式：Markdown、TXT、EPUB
- 抽取章节：优先识别 Markdown 标题、`第X章`、`第X話`、`Chapter X`、序章/终章/闲话等标题
- 长度判断：默认 `target=3500`、`ratio=1.5`，超过约 `5250 tokens` 的章节会实际拆成多个翻译单元
- 写入 `source/`
- 更新 `config/progress.yaml`
- 写入 `config/segment_map.yaml`
