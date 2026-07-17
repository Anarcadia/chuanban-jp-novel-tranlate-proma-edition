# Proma 工作流

本流程是 `chuanban-jp-novel-tranlate-proma-edition` 的 Proma 专属编排版。主进程负责项目初始化、素材准备、进度判断、用户交互和章节调度；章节翻译由 Proma 子进程执行。每次只能启动一个章节子进程，必须等当前章节完成、术语表和摘要写回后，再进入下一章。

如果在 Codex、Claude Code 或其他 agent 环境中使用，不要直接照搬这里的子进程描述。需要先把“启动章节子进程、传参、阻塞等待、术语询问恢复、返回格式”改成对应环境的 sub-agent 工具名与具体机制。

## 1. 初始化项目

```bash
python scripts/init_project.py create "<项目路径>" "<项目名>" "日语" "中文"
```

生成结构：

```text
{项目名}/
├── config/
│   ├── terms.yaml
│   ├── term_notes.yaml
│   ├── summary.yaml
│   ├── progress.yaml
│   └── segment_map.yaml
├── source/
├── output/
├── logs/
└── final/
    └── full_translation.md
```

## 2. 准备源文件

推荐用自动准备脚本读取原始小说文件：

```bash
python scripts/prepare_source.py "<项目路径>" "<小说文件>"
```

支持格式：

- `.md`
- `.markdown`
- `.txt`
- `.epub`

脚本会自动：

- 抽取章节
- 估算章节长度
- 对超长章节实际拆分
- 写入 `source/`
- 更新 `config/progress.yaml`
- 保存 `config/segment_map.yaml`

常用参数：

```bash
--target 3500 --max 4500 --min 1500 --ratio 1.5 --overlap 3 --overwrite
```

如果你已经有切好的章节文件，也可以手动放入 `source/`。支持 `.md`、`.txt`，建议文件名带三位序号，例如 `001_第一話.md`。

扫描章节：

```bash
python scripts/init_project.py scan "<项目路径>"
```

手动放入章节时才需要扫描；使用 `prepare_source.py` 时会自动更新进度文件。

首次开始前确认：

- 工作模式：询问模式 / 全自动模式
- 风格指南：写入 `config/summary.yaml`
- 是否已有断点：读取 `config/progress.yaml`

## 3. 可选：只分析分段

如果只想查看已有 `source/` 章节是否过长，而不改写文件：

```bash
python scripts/segment_analyzer.py "<项目路径>" --save
```

常用参数：

```bash
--target 3500 --max 4500 --min 1500 --ratio 1.5 --overlap 3
```

分段后的翻译单元就是实际输出单元，例如 `027_a_translated.md`、`027_b_translated.md`。

## 4. 翻译主循环

每次只处理一个章节。Proma 主进程向章节子进程传入项目路径、章节号、章节文件、源语言、目标语言和工作模式；子进程按 [worker.md](worker.md) 执行，完成后只返回一行确认。

1. 读取 `source/{章节文件}`。
2. 读取 `config/summary.yaml`、`config/terms.yaml`、上一章译文末尾。
3. 按 [worker.md](worker.md) 完成翻译。
4. 写入 `output/{原文件名去扩展名}_translated.md`。
5. 更新 `terms.yaml`、`term_notes.yaml`、`summary.yaml`、`progress.yaml`。
6. 返回简短进度。

确认当前章完成后，再进入下一章。

## 5. 术语维护

术语歧义：

- 询问模式：暂停，给出候选译法，等待用户选择。
- 全自动模式：自行决断，记录理由和置信度。

批量替换：

```bash
python scripts/batch_replace.py "<项目路径>" "<旧术语>" "<新术语>" --dry-run
python scripts/batch_replace.py "<项目路径>" "<旧术语>" "<新术语>"
```

## 6. 回退与重译

预览回退：

```bash
python scripts/rollback.py "<项目路径>" 5
```

确认回退：

```bash
python scripts/rollback.py "<项目路径>" 5 --confirm
```

回退后检查 `config/progress.yaml`，再重译对应章节。

## 7. 合并全文

```bash
python scripts/merge_output.py "<项目路径>"
```

输出：

```text
{项目路径}/final/full_translation.md
```

如不需要章节分隔标记：

```bash
python scripts/merge_output.py "<项目路径>" full_translation.md --no-markers
```

## 8. Pixiv 封面与 ePub

已有小说文件和本地图片：

```bash
python scripts/create_epub.py novel.md -i images -o novel.epub
python scripts/fix_epub.py novel.epub novel_final.epub
```

需要从 Pixiv 系列页提取封面：

```bash
python scripts/extract_covers.py "<series_id>"
python scripts/download_covers.py "covers_<series_id>.json"
python scripts/create_epub.py novel.md -i images -o novel.epub
python scripts/fix_epub.py novel.epub novel_final.epub
```

图片命名约定：

- `series_cover.jpg`：书籍封面
- `chapter_001.jpg`：第 1 章封面
- `[uploadedimage:12345678]`：正文插图标记
- `![alt](path)`：Markdown 图片标记
