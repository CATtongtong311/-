"""诊股分析：数据获取 + LLM 分析 + 结果封装。"""

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger

from src.data.fetcher import DataFetcher
from src.llm.claude_code_client import ClaudeCodeClient
from src.llm.prompts import DIAGNOSIS_SYSTEM, build_diagnosis_prompt
from src.portfolio.parser import PortfolioParser


@dataclass
class DiagnosisResult:
    """诊股结果。"""

    symbol: str
    name: str
    score: int = 0
    strategy: str = "观望型"
    summary: str = ""
    support: float | None = None
    resistance: float | None = None
    stop_loss: float | None = None
    analysis_text: str = ""
    warnings: list[str] = field(default_factory=list)
    alert_triggered: bool = False
    alert_msg: str = ""
    source: str = "claude"
    # 模块执行状态跟踪
    module_status: dict[str, str] = field(default_factory=dict)


class DiagnosisAnalyzer:
    """诊股分析器：整合数据获取、持仓上下文和 LLM 分析。"""

    def __init__(
        self,
        data_fetcher: DataFetcher,
        llm_client: ClaudeCodeClient,
        portfolio_parser: PortfolioParser | None = None,
    ):
        self.data_fetcher = data_fetcher
        self.llm = llm_client
        self.portfolio = portfolio_parser or PortfolioParser()

    def analyze(self, symbol: str, name: str = "") -> DiagnosisResult:
        """对指定股票进行完整诊股分析，带模块状态跟踪。"""
        logger.info("开始诊股分析: {}", symbol)
        result = DiagnosisResult(symbol=symbol, name=name)
        module_status: dict[str, str] = {}

        # 1. 获取实时行情
        quote = None
        try:
            quote = self.data_fetcher.get_stock_quote(symbol)
            if quote.source == "failed":
                module_status["行情获取"] = f"失败: {'; '.join(quote.warnings)}"
                result.warnings.extend(quote.warnings)
                result.source = "failed"
            else:
                module_status["行情获取"] = "成功"
                result.warnings.extend(quote.warnings)
        except Exception as e:
            module_status["行情获取"] = f"异常: {e}"
            result.warnings.append(f"行情获取异常: {e}")
            result.source = "failed"

        if result.source == "failed":
            result.module_status = module_status
            logger.error("诊股分析失败 [{}]: 行情获取失败", symbol)
            return result

        # 2. 获取新闻
        news = []
        try:
            news = self.data_fetcher.get_news(symbol)
            module_status["新闻获取"] = "成功" if news else "成功(无数据)"
        except Exception as e:
            module_status["新闻获取"] = f"失败: {e}"

        # 3. 获取持仓上下文
        holding_dict = None
        try:
            holding = self.portfolio.get_holding(symbol)
            if holding:
                holding_dict = {
                    "cost_price": holding.cost_price,
                    "quantity": holding.quantity,
                    "sector": holding.sector,
                    "notes": holding.notes,
                }
                name = name or holding.name
                module_status["持仓上下文"] = "成功"
            else:
                module_status["持仓上下文"] = "成功(非持仓)"
        except Exception as e:
            module_status["持仓上下文"] = f"失败: {e}"

        # 4. 检查 ±5% 警示
        try:
            if quote and quote.close is not None and holding and holding.cost_price:
                alert_triggered, alert_msg = self.portfolio.should_alert(
                    symbol, quote.close
                )
                result.alert_triggered = alert_triggered
                result.alert_msg = alert_msg
                if alert_triggered:
                    logger.warning("持仓警示: {}", alert_msg)
                module_status["持仓警示"] = "成功"
            else:
                module_status["持仓警示"] = "跳过"
        except Exception as e:
            module_status["持仓警示"] = f"失败: {e}"

        # 5. 构建 prompt 并调用 Claude Code（超时 600s）
        data_payload = {
            "symbol": symbol,
            "name": name or symbol,
            "quote": {
                "open": quote.open,
                "high": quote.high,
                "low": quote.low,
                "close": quote.close,
                "volume": quote.volume,
                "change_pct": quote.change_pct,
                "turnover": quote.turnover,
            },
            "news": [
                {"title": n.get("title", ""), "summary": n.get("summary", "")[:150]}
                for n in (news or [])
            ],
            "holding": holding_dict,
        }

        file_prompt = (
            "以下是股票分析所需数据（JSON格式）：\n"
            f"```json\n{json.dumps(data_payload, ensure_ascii=False, indent=2)}\n```\n\n"
            "请根据以上数据进行四维度分析。\n"
            "请严格按照以下格式返回纯 JSON（不要 Markdown 代码块，不要其他文字）：\n"
            '{"score": 0-100, "strategy": "进攻型/防御型/观望型", '
            '"support": [数值1, 数值2], "resistance": [数值1, 数值2], '
            '"stop_loss": "数值", "reason": "一句话总结"}'
        )

        analysis_text = ""
        try:
            analysis_text = self.llm.chat(
                messages=[
                    {"role": "system", "content": DIAGNOSIS_SYSTEM},
                    {"role": "user", "content": file_prompt},
                ],
                temperature=0.3,
                max_tokens=4096,
                timeout=600,  # 诊股超时 10 分钟
            )
            if analysis_text:
                module_status["AI分析"] = "成功"
            else:
                module_status["AI分析"] = "失败: 返回空结果"
                result.warnings.append("AI 分析服务暂不可用")
        except subprocess.TimeoutExpired:
            module_status["AI分析"] = "失败: 超时(600s)"
            result.warnings.append("AI 分析服务超时")
        except Exception as e:
            module_status["AI分析"] = f"失败: {e}"
            result.warnings.append(f"AI 分析异常: {e}")

        if not analysis_text:
            result.source = "failed"
            result.module_status = module_status
            logger.error("诊股分析失败 [{}]: AI分析返回空结果", symbol)
            return result

        # 6. 解析结构化数据
        try:
            parsed = self._parse_analysis(symbol, name, analysis_text)
            result.score = parsed.score
            result.strategy = parsed.strategy
            result.summary = parsed.summary
            result.support = parsed.support
            result.resistance = parsed.resistance
            result.stop_loss = parsed.stop_loss
            result.analysis_text = analysis_text
            module_status["结果解析"] = "成功"
        except Exception as e:
            module_status["结果解析"] = f"失败: {e}"
            result.warnings.append(f"结果解析异常: {e}")

        result.name = name or symbol
        result.warnings.extend(quote.warnings)
        result.module_status = module_status

        logger.info(
            "诊股分析完成: {} 评分={} 策略={} 模块状态={}",
            symbol, result.score, result.strategy, module_status,
        )
        return result

    def _parse_analysis(self, symbol: str, name: str, text: str) -> DiagnosisResult:
        """从 LLM 输出中解析结构化字段（优先 JSON，回退正则）。"""
        result = DiagnosisResult(symbol=symbol, name=name)

        # 优先尝试 JSON 解析（Claude Code 可直接返回 JSON）
        data = ClaudeCodeClient.extract_json(text)
        if data:
            result.score = data.get("score", 0)
            result.strategy = data.get("strategy", "观望型")
            result.summary = data.get("reason", "")[:200]
            support = data.get("support")
            if isinstance(support, list) and support:
                result.support = float(support[0])
            elif isinstance(support, (int, float, str)):
                result.support = float(support)
            resistance = data.get("resistance")
            if isinstance(resistance, list) and resistance:
                result.resistance = float(resistance[0])
            elif isinstance(resistance, (int, float, str)):
                result.resistance = float(resistance)
            stop_loss = data.get("stop_loss")
            if stop_loss is not None:
                try:
                    result.stop_loss = float(stop_loss)
                except (ValueError, TypeError):
                    pass
            if result.score > 0:
                return result

        # 回退到 Markdown 正则解析
        score_match = re.search(r"综合评分[:：]\s*(\d+)/100", text)
        if score_match:
            result.score = int(score_match.group(1))

        # 解析策略建议
        strategy_match = re.search(r"策略建议[:：]\s*(进攻型|防御型|观望型)", text)
        if strategy_match:
            result.strategy = strategy_match.group(1)

        # 解析支撑/压力位
        support_match = re.search(r"支撑\s*[:：]?\s*(\d+\.?\d*)", text)
        if support_match:
            result.support = float(support_match.group(1))

        resistance_match = re.search(r"压力\s*[:：]?\s*(\d+\.?\d*)", text)
        if resistance_match:
            result.resistance = float(resistance_match.group(1))

        stop_match = re.search(r"止损(?:参考)?\s*[:：]?\s*(\d+\.?\d*)", text)
        if stop_match:
            result.stop_loss = float(stop_match.group(1))

        # 一句话总结
        summary_match = re.search(r"一句话总结[:：](.+)", text)
        if summary_match:
            result.summary = summary_match.group(1).strip()

        return result
