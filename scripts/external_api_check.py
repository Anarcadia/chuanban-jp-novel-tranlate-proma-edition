#!/usr/bin/env python3
"""
外接API自检脚本
调用外部API（OpenAI兼容格式）执行翻译质量检查
"""

import os
import sys
import json
import yaml
from pathlib import Path
from datetime import datetime

try:
    import requests
except ImportError:
    print("需要安装requests库: pip install requests")
    sys.exit(1)


def load_config(project_path: str) -> dict:
    """加载自检配置"""
    config_file = Path(project_path) / "config" / "check_config.yaml"
    
    if not config_file.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_file}")
    
    with open(config_file, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_terms(project_path: str) -> str:
    """加载术语表"""
    terms_file = Path(project_path) / "config" / "terms.yaml"
    
    if not terms_file.exists():
        return ""
    
    with open(terms_file, "r", encoding="utf-8") as f:
        return f.read()


def call_external_api(endpoint: str, api_key: str, model: str, prompt: str) -> str:
    """调用外接API"""
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    data = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3
    }
    
    # 确保endpoint格式正确
    if not endpoint.endswith("/"):
        endpoint += "/"
    url = endpoint + "chat/completions"
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=120)
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"]
    except requests.exceptions.RequestException as e:
        raise Exception(f"API调用失败: {e}")


def check_chapter(project_path: str, chapter_num: int, check_type: str = "all"):
    """
    对单个章节执行自检
    
    Args:
        project_path: 项目目录路径
        chapter_num: 章节编号
        check_type: 检查类型 - "terms"(术语), "completeness"(完整性), "accuracy"(准确性), "all"(全部)
    """
    
    project_dir = Path(project_path)
    
    # 加载配置
    config = load_config(project_path)
    
    if config.get("状态") != "开启":
        print("自检模块未开启")
        return
    
    if config.get("模型来源") != "外接API":
        print("当前配置为内置模型，请使用内置自检流程")
        return
    
    api_config = config.get("外接API配置", {})
    endpoint = api_config.get("接入点", "")
    api_key = api_config.get("密钥", "")
    model = api_config.get("模型名", "")
    
    if not all([endpoint, api_key, model]):
        print("✗ 外接API配置不完整，请检查check_config.yaml")
        print("  需要配置: 接入点, 密钥, 模型名")
        return
    
    # 查找章节文件（支持 md 和 txt，兼容带/不带前导零）
    source_files = []
    output_files = []
    for ext in ("md", "txt"):
        source_files.extend((project_dir / "source").glob(f"*{chapter_num:03d}*.{ext}"))
        output_files.extend((project_dir / "output").glob(f"*{chapter_num:03d}*_translated.{ext}"))

    if not source_files:
        for ext in ("md", "txt"):
            source_files.extend((project_dir / "source").glob(f"*{chapter_num}*.{ext}"))

    if not output_files:
        for ext in ("md", "txt"):
            output_files.extend((project_dir / "output").glob(f"*{chapter_num}*_translated.{ext}"))
    
    if not source_files or not output_files:
        print(f"✗ 找不到第{chapter_num}章的源文件或译文文件")
        return
    
    source_file = source_files[0]
    output_file = output_files[0]
    
    with open(source_file, "r", encoding="utf-8") as f:
        source_content = f.read()
    
    with open(output_file, "r", encoding="utf-8") as f:
        translated_content = f.read()
    
    print(f"检查第{chapter_num}章: {output_file.name}")
    print(f"使用模型: {model}")
    print("-" * 50)
    
    results = []
    
    # 优先级1：术语检查
    if check_type in ["all", "terms"]:
        print("执行术语检查...")
        terms = load_terms(project_path)
        
        prompt = f"""请检查以下译文中的术语使用是否正确。

## 术语表

{terms}

## 原文

{source_content}

## 译文

{translated_content}

---

检查要点：
1. 术语表中的所有术语是否正确翻译
2. 是否有术语漏翻
3. 别称是否正确识别

如有问题，请按以下JSON格式输出（如无问题输出空数组[]）：
[
  {{"类型": "术语错翻/术语漏翻", "位置": "第X段", "原文": "xxx", "当前译文": "xxx", "正确译文": "xxx"}}
]
"""
        
        try:
            result = call_external_api(endpoint, api_key, model, prompt)
            results.append(("术语检查", result))
            print("  ✓ 术语检查完成")
        except Exception as e:
            print(f"  ✗ 术语检查失败: {e}")
    
    # 优先级2：完整性检查
    if check_type in ["all", "completeness"]:
        print("执行完整性检查...")
        
        prompt = f"""请对照原文检查译文的完整性。

## 原文

{source_content}

## 译文

{translated_content}

---

检查要点：
1. 是否有段落或句子遗漏
2. 是否有原文不存在的编造内容

如有问题，请按以下JSON格式输出（如无问题输出空数组[]）：
[
  {{"类型": "内容遗漏/内容编造", "位置": "第X段", "原文": "xxx", "译文": "xxx", "建议": "xxx"}}
]
"""
        
        try:
            result = call_external_api(endpoint, api_key, model, prompt)
            results.append(("完整性检查", result))
            print("  ✓ 完整性检查完成")
        except Exception as e:
            print(f"  ✗ 完整性检查失败: {e}")
    
    # 优先级3：准确性检查
    if check_type in ["all", "accuracy"]:
        print("执行准确性检查...")
        
        prompt = f"""请检查译文是否有明显的翻译错误。

## 原文

{source_content}

## 译文

{translated_content}

---

检查要点：只关注明显的意思翻译错误，不纠正风格问题。

如有问题，请按以下JSON格式输出（如无问题输出空数组[]）：
[
  {{"类型": "翻译错误", "位置": "第X段", "原文": "xxx", "错误译文": "xxx", "修正译文": "xxx", "理由": "xxx"}}
]
"""
        
        try:
            result = call_external_api(endpoint, api_key, model, prompt)
            results.append(("准确性检查", result))
            print("  ✓ 准确性检查完成")
        except Exception as e:
            print(f"  ✗ 准确性检查失败: {e}")
    
    # 写入日志
    log_file = project_dir / "logs" / "check_log.yaml"
    
    log_entry = f"""
- 章节: {chapter_num}
  检查时间: "{datetime.now().strftime('%Y-%m-%d %H:%M')}"
  检查模型: 外接API/{model}
  检查结果:
"""
    
    for check_name, check_result in results:
        log_entry += f"    {check_name}: |\n"
        for line in check_result.split('\n'):
            log_entry += f"      {line}\n"
    
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(log_entry)
    
    print("-" * 50)
    print(f"✓ 检查完成，结果已写入: {log_file}")


def main():
    if len(sys.argv) < 3:
        print("用法:")
        print("  python external_api_check.py <项目路径> <章节编号> [检查类型]")
        print()
        print("检查类型:")
        print("  all          全部检查（默认）")
        print("  terms        仅术语检查")
        print("  completeness 仅完整性检查")
        print("  accuracy     仅准确性检查")
        print()
        print("示例:")
        print("  python external_api_check.py ./my_translation 5")
        print("  python external_api_check.py ./my_translation 5 terms")
        print()
        print("配置说明:")
        print("  请在 config/check_config.yaml 中配置外接API信息：")
        print("  - 接入点: OpenAI兼容格式的API地址")
        print("  - 密钥: API密钥")
        print("  - 模型名: 使用的模型名称")
        return
    
    project_path = sys.argv[1]
    chapter_num = int(sys.argv[2])
    check_type = sys.argv[3] if len(sys.argv) > 3 else "all"
    
    check_chapter(project_path, chapter_num, check_type)


if __name__ == "__main__":
    main()
