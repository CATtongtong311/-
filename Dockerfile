# 使用 DaoCloud 镜像加速的 Python 3.12 精简镜像
FROM m.daocloud.io/docker.io/library/python:3.12-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖（部分 Python 包编译需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/

# 复制项目代码
COPY . .

# 创建数据/日志目录
RUN mkdir -p data logs

# 设置环境变量
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "from config.settings import get_settings; get_settings().validate()" || exit 1

# 入口命令
CMD ["python", "main.py"]
