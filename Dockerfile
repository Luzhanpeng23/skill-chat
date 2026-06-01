FROM python:3.12-slim

WORKDIR /app

# 系统依赖 (pandoc 用于 epub/pdf 解析)
RUN apt-get update && apt-get install -y --no-install-recommends pandoc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 创建数据目录
RUN mkdir -p data/uploads data/archives books skills

EXPOSE 8000

CMD ["python", "-m", "app"]
