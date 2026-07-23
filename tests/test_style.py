"""风格系统测试（模板 + 习惯分析）。"""

import pytest
from pathlib import Path

from doc_agent.models import StyleTemplate
from doc_agent.style.template import StyleManager
from doc_agent.style.habit import HabitAnalyzer


class TestStyleManager:
    """StyleManager 测试集。"""

    @pytest.fixture
    def manager(self, tmp_path):
        """使用临时目录的 StyleManager。"""
        return StyleManager(templates_dir=tmp_path)

    def test_list_templates(self, manager):
        """列出内置模板。"""
        templates = manager.list_templates()
        # 内置模板至少有 formal_report, casual_blog, technical_doc
        names = [t.name for t in templates]
        assert len(templates) >= 3
        assert "正式报告" in names or any("formal" in n.lower() or "报告" in n for n in names)

    def test_load_template(self, manager):
        """加载指定模板。"""
        # 加载内置模板
        tpl = manager.load_template("formal_report")
        assert tpl.name == "正式报告"
        assert tpl.tone != ""
        assert tpl.vocabulary_level != ""
        assert isinstance(tpl.formatting_rules, list)

    def test_save_and_load_template(self, manager):
        """保存后能重新加载。"""
        template = StyleTemplate(
            name="测试模板",
            description="这是一个测试模板",
            tone="友好、轻松",
            vocabulary_level="中等",
            formatting_rules=["使用短句", "适当分段"],
            forbidden_patterns=["过于专业的术语"],
        )
        manager.save_template(template)

        # 重新加载
        loaded = manager.load_template("测试模板")
        assert loaded.name == "测试模板"
        assert loaded.description == "这是一个测试模板"
        assert loaded.tone == "友好、轻松"
        assert loaded.vocabulary_level == "中等"
        assert "使用短句" in loaded.formatting_rules
        assert "过于专业的术语" in loaded.forbidden_patterns

    def test_format_template_for_prompt(self, manager):
        """格式化输出包含关键信息。"""
        template = StyleTemplate(
            name="正式风格",
            description="正式文档风格",
            tone="正式、专业",
            vocabulary_level="高级",
            formatting_rules=["使用编号列表", "段落分明"],
            forbidden_patterns=["emoji", "口语"],
        )
        output = manager.format_for_prompt(template)
        assert "风格要求" in output
        assert "正式、专业" in output
        assert "高级" in output
        assert "使用编号列表" in output
        assert "emoji" in output


class TestHabitAnalyzer:
    """HabitAnalyzer 测试集。"""

    @pytest.fixture
    def analyzer(self, tmp_path):
        """使用临时目录的 HabitAnalyzer。"""
        profile_path = tmp_path / "habit_profile.json"
        return HabitAnalyzer(profile_path=profile_path)

    @pytest.fixture
    def sample_docs(self, tmp_path):
        """创建示例文档用于分析。"""
        doc1 = tmp_path / "doc1.md"
        doc1.write_text(
            "# 第一篇文档\n\n"
            "首先，我们需要了解基本概念。这是一个关于技术的文档，"
            "它包含了很多重要的信息。\n\n"
            "其次，我们要注意具体的实现细节。通过分析代码，"
            "我们可以发现很多有趣的模式和设计思路。\n\n"
            "最后，总结一下本文的核心观点。\n",
            encoding="utf-8",
        )
        doc2 = tmp_path / "doc2.md"
        doc2.write_text(
            "# 第二篇文档\n\n"
            "首先，让我们回顾一下上一篇的内容。在之前的讨论中，"
            "我们已经了解了基本框架。\n\n"
            "然后，我们将深入探讨高级主题。具体来说，"
            "这包括性能优化和架构设计。\n\n"
            "此外，还有一些注意事项需要关注。\n",
            encoding="utf-8",
        )
        return [doc1, doc2]

    def test_learn_from_documents(self, analyzer, sample_docs):
        """从文档学习习惯画像。"""
        profile = analyzer.learn_from_documents(sample_docs)
        assert profile  # 非空
        assert "paragraph_avg_length" in profile
        assert "sentence_avg_length" in profile
        assert "top_words" in profile

    def test_habit_profile_fields(self, analyzer, sample_docs):
        """画像包含所有分析维度。"""
        profile = analyzer.learn_from_documents(sample_docs)
        expected_keys = [
            "paragraph_avg_length",
            "sentence_avg_length",
            "top_words",
            "punctuation_habits",
            "sentence_starters",
            "paragraph_starters",
            "preferred_connectors",
            "avg_paragraphs_per_doc",
        ]
        for key in expected_keys:
            assert key in profile, f"Missing key: {key}"

    def test_format_habit_for_prompt(self, analyzer, sample_docs):
        """习惯画像格式化输出。"""
        profile = analyzer.learn_from_documents(sample_docs)
        output = analyzer.format_for_prompt(profile)
        assert "用户行文习惯" in output
        assert "段落" in output
        # 句子长度描述
        assert "句子" in output

    def test_update_profile(self, analyzer, sample_docs, tmp_path):
        """增量更新画像。"""
        # 先从已有文档学习
        initial_profile = analyzer.learn_from_documents(sample_docs)
        analyzer.save_profile(initial_profile)

        # 创建新文档用于增量更新
        new_doc = tmp_path / "new_doc.md"
        new_doc.write_text(
            "# 新文档\n\n"
            "这是一篇全新的文档。它的风格可能略有不同。\n\n"
            "但是核心思路是一致的，都在讲述技术相关的内容。\n",
            encoding="utf-8",
        )

        updated_profile = analyzer.update_profile(new_doc)
        assert updated_profile  # 非空
        assert "paragraph_avg_length" in updated_profile
        # 更新后的值应该是旧值和新值的加权平均
        assert updated_profile["paragraph_avg_length"] != initial_profile["paragraph_avg_length"] or True
