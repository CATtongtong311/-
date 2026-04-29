"""数据模型定义，基于 peewee ORM。"""

from datetime import datetime

from peewee import (CharField, DateField, DateTimeField, FloatField,
                    IntegerField, Model, TextField)

from src.core.database import get_db


class BaseModel(Model):
    """基础模型，自动绑定数据库连接。"""

    class Meta:
        database = get_db()


class PortfolioCache(BaseModel):
    """持仓缓存表：portfolio.md 解析失败时的回退存储。"""

    symbol = CharField(max_length=20, index=True, help_text="股票代码")
    name = CharField(max_length=100, help_text="股票名称")
    cost_price = FloatField(null=True, help_text="成本价")
    quantity = IntegerField(null=True, help_text="持仓数量")
    sector = CharField(max_length=50, null=True, help_text="所属板块")
    notes = TextField(null=True, help_text="备注")
    updated_at = DateTimeField(default=datetime.now, help_text="更新时间")

    class Meta:
        table_name = "portfolio_cache"


class DiagnosisHistory(BaseModel):
    """诊断历史记录表。"""

    symbol = CharField(max_length=20, index=True, help_text="股票代码")
    name = CharField(max_length=100, help_text="股票名称")
    query_time = DateTimeField(default=datetime.now, help_text="查询时间")
    current_price = FloatField(null=True, help_text="当前价")
    change_pct = FloatField(null=True, help_text="涨跌幅")
    analysis_text = TextField(help_text="AI 分析原文")
    strategy = CharField(max_length=20, null=True, help_text="策略建议：进攻/防御/观望")
    score = IntegerField(null=True, help_text="综合评分 0-100")
    llm_model = CharField(max_length=50, null=True, help_text="使用的 LLM 模型")

    class Meta:
        table_name = "diagnosis_history"


class ApiCallLog(BaseModel):
    """API 调用计数表：监控 Tushare 等数据源的额度消耗。"""

    source = CharField(max_length=50, index=True, help_text="数据源名称")
    endpoint = CharField(max_length=100, help_text="接口名称")
    call_date = DateField(index=True, help_text="调用日期")
    call_count = IntegerField(default=0, help_text="当日调用次数")
    error_count = IntegerField(default=0, help_text="当日错误次数")

    class Meta:
        table_name = "api_call_log"


class KimiRawData(BaseModel):
    """Kimi 原始数据表：保存 Kimi Agent 生成的原始回复内容。"""

    data_date = DateField(index=True, help_text="数据日期")
    task_type = CharField(max_length=20, help_text="任务类型：report/full/error")
    content = TextField(help_text="Kimi 原始回复内容")
    fetch_time = DateTimeField(default=datetime.now, help_text="获取时间")
    status = CharField(max_length=20, default="success", help_text="状态：success/failed")
    error_msg = TextField(null=True, help_text="错误信息")
    elapsed_sec = IntegerField(null=True, help_text="耗时（秒）")
    sentiment_mood = CharField(max_length=20, null=True, help_text="情绪标签：乐观/中性/悲观")
    sentiment_score = IntegerField(null=True, help_text="情绪评分 0-100")

    class Meta:
        table_name = "kimi_raw_data"
        indexes = (("data_date", "task_type"), True)


class MorningReportRecord(BaseModel):
    """晨报记录表：保留最近 7 天的晨报，过期自动清理。"""

    report_date = DateField(index=True, help_text="晨报日期")
    content = TextField(help_text="晨报内容（Markdown）")
    source = CharField(max_length=50, help_text="生成来源：kimi/failed")
    chat_id = CharField(max_length=100, default="", help_text="推送到的群聊 ID")
    sent_at = DateTimeField(default=datetime.now, help_text="发送时间")
    warnings = TextField(default="", help_text="生成过程中的警告信息")
    # 扩展字段：Kimi 来源与情绪数据
    kimi_source = CharField(max_length=50, default="", help_text="Kimi 具体来源标识")
    sentiment_mood = CharField(max_length=20, null=True, help_text="情绪标签：乐观/中性/悲观")
    sentiment_score = IntegerField(null=True, help_text="情绪评分 0-100")
    generation_elapsed_sec = IntegerField(null=True, help_text="生成耗时（秒）")

    class Meta:
        table_name = "morning_report_record"
