import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest

from src.cards.diagnosis_card import DiagnosisCardBuilder
from src.cards.morning_report_card import MorningReportCardBuilder
from src.analysis.diagnosis import DiagnosisResult
from src.analysis.morning_report import MorningReport


class TestDiagnosisCardBuilder:
    def setup_method(self):
        self.builder = DiagnosisCardBuilder()

    def test_build_success(self):
        result = DiagnosisResult(
            symbol="600519",
            name="贵州茅台",
            score=85,
            strategy="进攻型",
            summary="趋势向好，可继续持有",
            support=1680.0,
            resistance=1750.0,
            stop_loss=1650.0,
            analysis_text="## 技术速览\n- 趋势：上升",
            warnings=["数据延迟 3 分钟"],
            alert_triggered=False,
            alert_msg="",
        )
        card = self.builder.build(result)

        assert card["schema"] == "2.0"
        assert card["header"]["template"] == "red"  # 进攻型对应红色
        assert "贵州茅台(600519)" in card["header"]["title"]["content"]
        assert len(card["body"]["elements"]) > 0

    def test_build_with_alert(self):
        result = DiagnosisResult(
            symbol="600519",
            name="贵州茅台",
            score=70,
            strategy="防御型",
            alert_triggered=True,
            alert_msg="较成本价上涨 6.0%",
            analysis_text="分析内容",
        )
        card = self.builder.build(result)

        assert "🔴 " in card["header"]["title"]["content"]
        assert card["header"]["template"] == "orange"  # 防御型对应橙色

    def test_build_guanwang(self):
        result = DiagnosisResult(
            symbol="600519",
            name="贵州茅台",
            score=50,
            strategy="观望型",
        )
        card = self.builder.build(result)
        assert card["header"]["template"] == "blue"

    def test_build_error_card(self):
        card = self.builder.build_error_card("600519", "数据暂不可用")
        assert card["header"]["title"]["content"] == "600519 查询失败"
        assert card["header"]["template"] == "grey"

    def test_build_no_price_data(self):
        result = DiagnosisResult(
            symbol="600519",
            name="贵州茅台",
            score=85,
            strategy="进攻型",
            support=None,
            resistance=None,
            stop_loss=None,
            analysis_text="分析内容",
        )
        card = self.builder.build(result)
        # 支撑压力位为空时不应有相关元素
        assert card["schema"] == "2.0"


class TestMorningReportCardBuilder:
    def setup_method(self):
        self.builder = MorningReportCardBuilder()

    def test_build_success(self):
        report = MorningReport(
            date="2024-04-26",
            content="# 晨报\n\n## 全球市场\n美股上涨",
            warnings=["港股数据暂不可用"],
        )
        card = self.builder.build(report)

        assert card["schema"] == "2.0"
        assert "投资晨报 2024-04-26" in card["header"]["title"]["content"]
        assert card["header"]["template"] == "blue"
        assert len(card["body"]["elements"]) > 0

    def test_build_empty_content(self):
        report = MorningReport(date="2024-04-26", content="")
        card = self.builder.build(report)
        assert "晨报内容为空" in str(card)

    def test_build_delay_warning(self):
        card = self.builder.build_delay_warning("08:25")
        assert "晨报生成延迟" in card["header"]["title"]["content"]
        assert "08:25" in str(card)
