# Workshop AI

Workshop AI 是面向本地生活服务的双边平台：客户按服务类型和地区发现服务商，沟通需求、预约上门、确认报价、支付并评价。演示数据位于伊斯坦布尔，金额单位为土耳其里拉（TRY）。本仓库是个人求职展示版本，包含 FastAPI 后端、Expo 多端应用，以及中文 Case Study 网站。

先看 [Case Study 网站源码](showcase/site)，再体验客户、服务商与管理员三种角色。公开 Demo 正在准备 Vercel / Railway 部署，目前没有已验收的线上地址；[部署说明](docs/public-deployment.md)和[发布前检查表](docs/release/pre-publication-checklist.md)记录当前边界。作品集 PDF 仍是待修订草稿，当前不作为提交材料或公开下载交付。

English summary: Workshop AI is a local-services marketplace with a FastAPI backend, an Expo app and a Chinese recruiter-facing case study. The local full stack supports optional integrations; the public demo uses seeded roles and simulated payments. Hosted acceptance is pending, and the portfolio PDF remains a draft.

## 能力与演示边界

- 发现服务商：服务标签、省／市／区筛选、价格和可用时间，浏览资料、作品与评论。
- 客户与服务商实时聊天：WebSocket 消息、预约关联、报价沟通。
- 预约流程：请求 → 上门报价 → 上门费 → 到达凭证 → 最终报价 → 服务费 → 完成 → 评价。
- 管理员工作台：用户、身份和服务资质审核、预约、支付、结算、退款与投诉。
- 可选 AI 辅助：客户对话、任务与推荐；未配置模型时展示降级提示，基础浏览和预约仍可使用。

| 环境 | 组成与用途 | 支付、AI 与账户边界 |
| --- | --- | --- |
| 本地完整版（local-full） | Docker Compose：PostgreSQL、Redis、API、Celery、Expo Web、Milvus、TEI | 默认 `DEMO_MODE=false`，使用 iyzico Sandbox；模型、OAuth、Places、SMTP 由开发者自行配置 |
| 公开演示（public-demo，部署准备中） | 两个独立静态站点（Case Study 与 Expo Web）+ Railway API/PostgreSQL；可选 Redis | `DEMO_MODE=true`、`WORKSHOP_PAYMENT_MODE=demo`；一键角色、模拟支付、敏感动作限制、AI 配额；可省略 Milvus/TEI/Celery |

模拟支付不扣款，Sandbox 卡和商户资料均为厂商测试样例。公开演示不可用于真实订单、真实身份证件或真实支付资料。演示角色共享数据，运营重置会清空演示修改；重置必须由操作员通过专用命令执行，普通 API 重启不触发重置。

AI 不是基础流程的必需依赖。公开模式有每日和每分钟请求配额，但配额不等于金额预算；A$30 月度上限仍需平台预算／告警、用量观察和停用预案配合。托管核心流程、实际模型提供商、费用上限与新录屏尚待后续验收，不把本地测试等同于线上验收。

## 架构与目录

| 层 | 技术 |
| --- | --- |
| API／数据 | FastAPI、SQLAlchemy、Alembic、PostgreSQL 16 |
| 身份认证 | RS256 JWT、可撤销 refresh-token 会话 |
| 实时协作 | WebSocket、Redis；可选 Celery |
| 应用 | Expo／React Native，支持 Web、iOS、Android |
| 评论检索与 AI | 可选 Milvus、TEI 嵌入、兼容模型 API |

```text
backend/          API、模型、路由与服务
frontend/mobile/  Expo 客户端
showcase/site/    中文 Case Study 网站
migrations/       Alembic 迁移
tests/            后端与发布策略测试
docs/             API、架构、部署与验收说明
scripts/          密钥生成与配置／公开内容检查
```

## 本地启动：Docker 完整版

需要 Docker。分离调试需要 Python 3.11+ 和 Node.js 24.19+。默认本机端口为 PostgreSQL 5436、Redis 6379、TEI 8091、API 8000、Web 8090；启动前确认端口未被其他项目占用。以下命令仅供在自己管理的本地环境运行。

```sh
cp .env.example .env
# 如需 AI，配置自己的 LLM_PROVIDER 与对应 API key
docker compose up --build
```

打开 [本地应用](http://127.0.0.1:8090)、[API 文档](http://127.0.0.1:8000/docs)或[健康检查](http://127.0.0.1:8000/health)。Compose 自动迁移并初始化演示数据，普通种子不联系 iyzico。首次 TEI 启动会下载模型权重到本地卷；评论向量使用 `Qwen3-Embedding-0.6B`（1024 维）。容器内部使用 Compose 服务名，不要将容器的数据库或 TEI 地址指向 `127.0.0.1`。

本地邮件默认 `console`，不联系邮箱；默认发件人为不可投递的 `workshop-demo@example.invalid`。启用 `smtp` 时显式填写自己的用户名、密码和发件地址。所有 `.env`、JWT PEM 和平台凭据只保留在本地，不能提交。

## 分离调试：主机 API 与 Expo

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env
python scripts/generate_jwt_keys.py
docker compose up -d postgres redis
alembic upgrade head
python -m backend.seed_locations
python -m backend.seed_demo_data
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Windows 激活命令为 `.venv\Scripts\activate`。密钥生成器写入 `backend/certs/jwt-private.pem` 与 `jwt-public.pem`，请勿提交。默认数据库为 `postgresql+psycopg://workshop:workshop@127.0.0.1:5436/workshop`；地区参考数据与可选演示账户分开初始化。

另开终端运行客户端：

```sh
cd frontend/mobile
cp .env.example .env
npm ci
npm start
# 或 npm run web / npm run ios / npm run android
```

浏览器使用 `EXPO_PUBLIC_API_BASE_URL=http://127.0.0.1:8000`；同 Wi-Fi 手机需将 `EXPO_PUBLIC_LAN_API_BASE_URL` 显式设为自己机器的 LAN 地址。Web 可容器运行，iOS／Android 在主机运行。主机 API 可省略向量检索依赖；需要评论检索时启动 `docker compose up -d tei`，按 `.env.example` 配置 `EMBEDDING_*`。

## 本地演示账户与 Sandbox

普通种子创建 36 个用户、30 个服务商、300 个预约，密码均为 `Demo1234`。

| 角色 | 演示邮箱 |
| --- | --- |
| 管理员 | `demo_admin@workshop.ai` |
| 客户 | `demo_customer_1@workshop.ai` 至 `demo_customer_5@workshop.ai` |
| 服务商 | `demo_provider_1@workshop.ai` 至 `demo_provider_30@workshop.ai` |

本地完整版的 iyzico Sandbox 测试卡为 `5526080000000006`、`4603450000000000`、`4987490000000002`，搭配未来到期日与格式正确的 CVV。测试卡不转移真实资金。种子中的商户邮箱、电话、IBAN 与身份字段是 Sandbox 固定测试资料，详见 [API 使用](docs/api-usage.md)与 `backend/utils/marketplace_seed.py`；不可将它们当作真实客户记录。服务商 6–9 保留为负面入驻样例，其余 26 个具有确定性的商户资料草稿。

仅在已配置自己 Sandbox 账户并明确需要外部调用时运行：

```sh
docker compose exec api python -m backend.seed_sandbox_submerchants --provider-id 29
```

这条命令会向 Sandbox 发起请求并保存外部状态／键／错误；普通种子只创建本地草稿。新预约需要身份和服务资质审核通过，以及有效 payout account。取消不会自动退款；退款遵循客户请求、服务商处理、管理员申诉流程，外部结算／退款确认后才写入本地终态。

## 配置与集成

| 配置 | 用途 |
| --- | --- |
| `WORKSHOP_DATABASE_URL`、`WORKSHOP_JWT_*` | 数据库、签名密钥与 token 生命周期 |
| `WORKSHOP_CORS_ORIGINS` | 明确允许的 Web 来源；公开部署只接受准确 HTTPS origin |
| `DEMO_MODE`、`WORKSHOP_PUBLIC_DEPLOYMENT` | 演示行为与公开部署保护；默认关闭 |
| `WORKSHOP_PAYMENT_MODE` | `iyzico_sandbox` 或 `demo` |
| `DEMO_AI_DAILY_LIMIT`、`DEMO_AI_PER_MINUTE_LIMIT` | 正整数 AI 配额 |
| `LLM_PROVIDER`、`LLM_API_KEY`／供应商 key | 选择模型提供商与私有凭据 |
| `LLM_BASE_URL`、`LLM_MODEL` | 显式覆盖模型预设；切换供应商时检查旧覆盖值 |
| `EMBEDDING_*` | 评论向量；Compose 默认本地 TEI，与聊天模型独立 |
| `WORKSHOP_EMAIL_BACKEND`、`WORKSHOP_SMTP_*`、`WORKSHOP_EMAIL_FROM` | 本地 console／memory 或自行配置的 SMTP |
| `WORKSHOP_GOOGLE_CLIENT_IDS`、`WORKSHOP_APPLE_CLIENT_IDS` | 后端社交登录受众验证 |
| `WORKSHOP_GOOGLE_MAPS_API_KEY` | 服务端 Places API (New) 代理，不放入 Expo 环境 |
| `IYZICO_*` | Sandbox 凭据、回调、返回地址与 checkout 超时 |
| `EXPO_PUBLIC_API_BASE_URL`、`EXPO_PUBLIC_WS_BASE_URL` | 构建时注入 API／WS 地址；公开部署要求 HTTPS／WSS |

前端 `EXPO_PUBLIC_*` 与 Case Study `VITE_*` 会进入浏览器构建，不能保存秘密。精确环境值、AI 降级、重置与回滚步骤见 [环境矩阵](docs/deployment/environment-matrix.md)、[演示运维](docs/deployment/public-demo.md)和[回滚手册](docs/deployment/rollback.md)。`.env.example` 与未来的 `.env.production.example` 仅允许无秘密模板；真实平台地址确定后再创建生产模板。

Google 登录需配置 Web、iOS、Android OAuth client ID，后端配置受众列表，前端配置对应 `EXPO_PUBLIC_GOOGLE_*_CLIENT_ID`；iOS／Android 需要 development build，Expo Go 不支持该重定向。Apple 登录仅 iOS，bundle ID 为 `com.comp5703.workshopai`，需开启 Sign in with Apple；Expo Go 测试可增加 `host.exp.Exponent` 受众。新账户需要接受条款。

模型提供商支持 `qwen`、`openai`（`gpt`）、`claude`、`kimi`、`kimi-code`、`deepseek`、`grok`、`custom`，以 `backend/llm_provider.py` 的实现与显式覆盖为准。本地管理员 Customer AI 页面可配置开发者 API 或受支持的订阅登录，配置会以 `0600` 写入忽略的 `backend/certs/`，覆盖本地环境直到清除。公开 Demo 的管理员敏感配置受限；本次检查未验收实际提供商／订阅登录，也没有付费调用。

## Case Study 与验证

```sh
cd showcase/site
npm ci
npm run dev
# npm test -- --run / npm run test:policy / npm run build / npm run test:e2e
```

网站的公开链接通过 `.env.example` 说明的构建配置注入；没有确认地址时显示准备状态。当前 PDF 保留为本地草稿，待后续修订后再考虑加入公开快照。

后端可运行 `pytest -q` 与 `ruff check backend tests scripts`；完整迁移／重置验证需要独立 PostgreSQL 测试数据库。前端运行 `npm run test:ci`、`npm run typecheck`、`npm run build:web`。公开内容使用 `python scripts/check_public_copy.py .` 与固定版本 Gitleaks 检查。CI 检查构建、迁移、策略与网站响应式体验；托管线上核心流程仍需后续独立验收。

认证密码保存在 `authentication_identities`；JWT 的 `sub` 为用户 ID，`sid` 绑定 refresh-token `jti` 以支持退出撤销。`/ws/me` 与 `/ws/chats/{id}` 连接后要求先发送 `{ "type": "auth", "token": "<access_token>" }`。

更多细节：[后端能力地图](docs/backend-feature-map.md)、[API 约定](docs/backend-api-standard.md)、[API 使用](docs/api-usage.md)。

## 来源与授权

本项目源自经团队成员共同授权用于个人求职展示的课程团队项目。本仓库是独立维护、修复和部署的个人展示版本，不与原团队仓库同步。
