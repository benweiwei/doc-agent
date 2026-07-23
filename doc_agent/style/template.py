"""风格模板管理模块。

管理 YAML 格式的风格模板文件，支持加载、保存、删除和格式化为 Prompt 文本。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import yaml

from doc_agent.models import StyleTemplate

logger = logging.getLogger(__name__)

# 内置模板目录（包内随附的示例模板）
_BUILTIN_TEMPLATES_DIR = Path(__file__).parent / "templates"


class StyleManager:
    """风格模板管理器。

    负责 YAML 格式风格模板的 CRUD 操作以及将模板格式化为 LLM Prompt 文本。
    """

    def __init__(self, templates_dir: Optional[Path] = None) -> None:
        """初始化 StyleManager。

        Args:
            templates_dir: 模板存储目录，默认 ~/.doc-agent/styles/。
        """
        if templates_dir is not None:
            self.templates_dir = Path(templates_dir)
        else:
            self.templates_dir = Path.home() / ".doc-agent" / "styles"
        self.templates_dir.mkdir(parents=True, exist_ok=True)

    def list_templates(self) -> list[StyleTemplate]:
        """列出所有可用模板（用户目录 + 内置目录）。

        Returns:
            StyleTemplate 列表。
        """
        templates: list[StyleTemplate] = []
        seen_names: set[str] = set()

        # 用户自定义模板优先
        for source_dir in [self.templates_dir, _BUILTIN_TEMPLATES_DIR]:
            if not source_dir.exists():
                continue
            for yaml_file in sorted(source_dir.glob("*.yaml")):
                try:
                    tpl = self._load_from_file(yaml_file)
                    if tpl.name not in seen_names:
                        templates.append(tpl)
                        seen_names.add(tpl.name)
                except Exception as e:
                    logger.warning("跳过无效模板文件 '%s': %s", yaml_file, e)

        return templates

    def load_template(self, name: str) -> StyleTemplate:
        """加载指定名称的模板。

        先搜索用户目录，再搜索内置目录。

        Args:
            name: 模板名称（文件名不含扩展名，或模板的 name 字段）。

        Returns:
            StyleTemplate 实例。

        Raises:
            FileNotFoundError: 如果模板不存在。
        """
        # 尝试按文件名查找
        for source_dir in [self.templates_dir, _BUILTIN_TEMPLATES_DIR]:
            file_path = source_dir / f"{name}.yaml"
            if file_path.exists():
                return self._load_from_file(file_path)

        # 尝试按模板 name 字段查找
        for source_dir in [self.templates_dir, _BUILTIN_TEMPLATES_DIR]:
            if not source_dir.exists():
                continue
            for yaml_file in source_dir.glob("*.yaml"):
                try:
                    tpl = self._load_from_file(yaml_file)
                    if tpl.name == name:
                        return tpl
                except Exception:
                    continue

        raise FileNotFoundError(f"模板 '{name}' 不存在")

    def save_template(self, template: StyleTemplate) -> None:
        """保存模板到用户目录的 YAML 文件。

        文件名使用模板 name 字段（替换空格为下划线）。

        Args:
            template: 要保存的 StyleTemplate 实例。
        """
        filename = self._name_to_filename(template.name)
        file_path = self.templates_dir / filename

        data = {
            "name": template.name,
            "description": template.description,
            "tone": template.tone,
            "vocabulary_level": template.vocabulary_level,
            "formatting_rules": template.formatting_rules,
            "forbidden_patterns": template.forbidden_patterns,
        }

        self.templates_dir.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        logger.info("模板已保存: %s", file_path)

    def delete_template(self, name: str) -> None:
        """删除用户目录中的模板文件。

        Args:
            name: 模板名称。

        Raises:
            FileNotFoundError: 如果模板不存在于用户目录。
        """
        filename = self._name_to_filename(name)
        file_path = self.templates_dir / filename

        if not file_path.exists():
            # 尝试按 name 字段查找
            found = False
            for yaml_file in self.templates_dir.glob("*.yaml"):
                try:
                    tpl = self._load_from_file(yaml_file)
                    if tpl.name == name:
                        yaml_file.unlink()
                        found = True
                        logger.info("模板已删除: %s", yaml_file)
                        break
                except Exception:
                    continue
            if not found:
                raise FileNotFoundError(f"用户模板 '{name}' 不存在，无法删除")
        else:
            file_path.unlink()
            logger.info("模板已删除: %s", file_path)

    def format_for_prompt(self, template: StyleTemplate) -> str:
        """将模板格式化为可注入 Prompt 的文本。

        Args:
            template: StyleTemplate 实例。

        Returns:
            格式化后的纯文本字符串。
        """
        lines: list[str] = []
        lines.append("## 风格要求")
        lines.append(f"- 语气：{template.tone}")
        lines.append(f"- 用词层次：{template.vocabulary_level}")

        if template.formatting_rules:
            lines.append("- 格式规则：")
            for i, rule in enumerate(template.formatting_rules, 1):
                lines.append(f"  {i}. {rule}")

        if template.forbidden_patterns:
            lines.append(f"- 禁止使用：{'、'.join(template.forbidden_patterns)}")

        return "\n".join(lines)

    # ─── 兼容旧接口 ──────────────────────────────────────────────────────────────

    def get_template(self, name: str) -> str:
        """兼容旧 TemplateManager.get_template 接口。

        Args:
            name: 模板名称。

        Returns:
            格式化后的 Prompt 文本，加载失败时返回空字符串。
        """
        try:
            tpl = self.load_template(name)
            return self.format_for_prompt(tpl)
        except FileNotFoundError:
            logger.warning("模板 '%s' 未找到", name)
            return ""

    # ─── 私有方法 ─────────────────────────────────────────────────────────────────

    def _load_from_file(self, file_path: Path) -> StyleTemplate:
        """从 YAML 文件加载模板。"""
        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict):
            raise ValueError(f"无效的模板文件格式: {file_path}")

        return StyleTemplate(
            name=data.get("name", file_path.stem),
            description=data.get("description", ""),
            tone=data.get("tone", ""),
            vocabulary_level=data.get("vocabulary_level", ""),
            formatting_rules=data.get("formatting_rules", []),
            forbidden_patterns=data.get("forbidden_patterns", []),
        )

    @staticmethod
    def _name_to_filename(name: str) -> str:
        """将模板名转为文件名。"""
        # 简单替换：空格→下划线，去除特殊字符
        import re
        clean = re.sub(r"[^\w\u4e00-\u9fff\-]", "_", name)
        return f"{clean}.yaml"


# 向后兼容别名
TemplateManager = StyleManager

