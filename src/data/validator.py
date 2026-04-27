"""数据校验：停牌检测、空值检查、异常价格标记。"""

import math
from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    """数据校验结果。"""

    is_valid: bool = True
    is_suspended: bool = False
    has_null: bool = False
    is_abnormal_price: bool = False
    warnings: list[str] = field(default_factory=list)
    fallback_needed: bool = False


class DataValidator:
    """校验金融数据质量。"""

    ABNORMAL_CHANGE_PCT = 20.0  # 涨跌幅绝对值超过 20% 视为异常

    def validate_quote(self, data: dict) -> ValidationResult:
        """校验个股行情数据。"""
        result = ValidationResult()

        if not data:
            result.is_valid = False
            result.fallback_needed = True
            result.warnings.append("返回数据为空")
            return result

        volume = data.get("volume")
        if volume is None or volume == 0:
            result.is_suspended = True
            result.fallback_needed = True
            result.warnings.append("成交量为 0，可能停牌")

        for key in ("open", "high", "low", "close"):
            val = data.get(key)
            if val is None or (isinstance(val, float) and math.isnan(val)):
                result.has_null = True
                result.fallback_needed = True
                result.warnings.append(f"{key} 字段为空值")

        change_pct = data.get("change_pct")
        if change_pct is not None and abs(change_pct) > self.ABNORMAL_CHANGE_PCT:
            result.is_abnormal_price = True
            result.warnings.append(f"涨跌幅异常: {change_pct:.2f}%")

        result.is_valid = not (result.is_suspended or result.has_null)
        return result

    def validate_market_data(self, data: dict) -> ValidationResult:
        """校验全球市场数据（简化版）。"""
        result = ValidationResult()

        if not data:
            result.is_valid = False
            result.fallback_needed = True
            result.warnings.append("返回数据为空")
            return result

        if not any(v is not None for v in data.values()):
            result.is_valid = False
            result.fallback_needed = True
            result.warnings.append("所有关键字段均为空")
            return result

        return result
