# 构建上下文是仓库根（compose 里 context: .），因此路径都带 python-agent/ 前缀
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY python-agent/pyproject.toml ./
COPY python-agent/app ./app
COPY python-agent/eval ./eval
COPY python-agent/ui ./ui
# 政策库是运行时依赖，容器里必须存在（会话库/Chroma 由 volume 持久化）
COPY data/policies ./data/policies

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
