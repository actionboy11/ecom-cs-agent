# 部署与镜像发布

## 镜像命名

`docker-compose.yml` 里三个镜像都写死了名字和版本，不再依赖仓库目录名：

| 服务 | 镜像 | 来源 |
|---|---|---|
| Python Agent | `ghcr.io/actionboy11/ecom-cs-agent-python:0.1.0` | `build.context: .`（需要 `data/policies`） |
| Java 服务 | `ghcr.io/actionboy11/ecom-cs-agent-java:0.1.0` | `build: ./java-service` |
| 工作台 | 复用 Python 镜像 | 只覆盖 `command`（Streamlit） |
| MySQL | `mysql:8.4` | 官方镜像 |

**为什么固定**：

- 不写 `image` 时，Compose 会拼 `<目录名>-<服务名>:latest`，换目录就变名字，且没有版本
- 固定后 `docker compose build`、`docker push`、K8s 清单、回滚都引用同一串标识
- 发版只改版本号（`0.1.0` → `0.2.0`），并在 git tag 里同步

## 本地构建与启动

```bash
cp .env.example .env          # 填 DEEPSEEK_API_KEY / JWT_SECRET / INTERNAL_AUDIT_TOKEN
docker compose build          # 产物即上表的固定 tag
docker compose up -d
docker compose ps             # 四个服务应为 healthy
```

镜像名固定后，`docker images` 里看到的就是：

```
ghcr.io/actionboy11/ecom-cs-agent-python:0.1.0
ghcr.io/actionboy11/ecom-cs-agent-java:0.1.0
```

## 推送与发版

```bash
# 1) 登录（GitHub PAT，需 write:packages）
echo "$GHCR_TOKEN" | docker login ghcr.io -u actionboy11 --password-stdin

# 2) 构建并推送固定 tag
docker compose build
docker compose push

# 3) 回滚：改回旧版本号或直接指定旧 tag
docker pull ghcr.io/actionboy11/ecom-cs-agent-java:0.0.9
```

发版检查单：

1. 改 `docker-compose.yml` 里的版本号（两处：Java、Python）
2. 打 git tag：`git tag v0.2.0 && git push origin v0.2.0`
3. `docker compose build && docker compose push`
4. 用新 tag 起一遍全栈，确认 `/api/health`、`/api/v1/health`、`/_stcore/health` 都是 200

## 生产注意

- **不要用 `latest`**：回滚时无法区分版本；`0.1.0` 这类不可变 tag 才能回滚
- **固定 digest**：高要求场景把 `image:` 换成 `...@sha256:<digest>`，防止 tag 被覆盖
- **密钥**：`.env` 不进镜像；`JWT_SECRET` 必须 Java 与 Python 共用同一个值
- **MySQL**：`data/mysql` 是 bind mount，升级前先备份；生产建议用托管数据库并配 `SPRING_DATASOURCE_URL`
- **端口**：`3308/8080/8000/8501` 是本地演示端口，生产由反向代理统一入口并加 TLS
- **工作台**：Streamlit 是演示级 UI，生产需前置鉴权（OIDC/网关）而不是仅靠应用内登录

## 常见问题

| 现象 | 原因 / 处理 |
|---|---|
| `docker pull` 报 `failed size validation` | 本机代理损坏 Docker Hub 层 → 用镜像源拉基础镜像后 `docker tag` 成官方名（见 [DEMO.md](DEMO.md)） |
| `compose up` 后 Java unhealthy | 看 `docker compose logs java-service`；确认 `MYSQL_HOST=mysql`、`JWT_SECRET` 已设置 |
| 镜像名里出现目录名 | 检查服务是否漏了 `image:`；本项目已全部显式指定 |
