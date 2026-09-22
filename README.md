# 我的健身教练

一个无需安装依赖的多模态健身教练 Agent。它按一天三个阶段工作：

- 早上记录体重、精力、酸痛和睡眠，由 AI 生成当天饮食与运动计划；
- 训练后记录实际运动、时长和计划完成度，立即生成针对性的拉伸建议；
- 晚上记录全天饮食、照片和排便情况，完成当日复盘；
- 第二天早上由模型结合完整记录给前一天 0–100 分并解释依据；
- 每天记录体重和测量时间，并将最近 14 天体重趋势交给教练判断；
- 身高固定按 158 cm 作为个人档案使用，不需要每天重复填写；
- 记录排便次数、状态和不适，帮助教练调整膳食纤维、饮水和食物结构；
- 通过兼容 OpenAI Chat Completions 的视觉模型识别饮食照片，分析食物结构和粗略热量；
- 将最近 14 天的训练、睡眠、精力和酸痛反馈一起交给模型，动态调整第二天训练负荷；
- 持续积累结构化历史数据，为数据量足够后训练独立的个性化 ML 模型做好准备；
- 支持邮箱+密码账号和 HttpOnly 会话 cookie；每个账号只能看到自己的打卡记录。默认使用本地 SQLite，设置 `DATABASE_URL` 后使用 Supabase PostgreSQL；
- 查看最近 6 条打卡记录。

## 使用

1. 复制配置模板并填入 API Key：

```bash
cp .env.example .env
```

编辑 `.env`，至少填写 `OPENAI_API_KEY`。默认模型为 `qwen/qwen3.8-27b`，也可以通过 `OPENAI_MODEL` 和 `OPENAI_BASE_URL` 使用其他兼容服务。

如果你的 Key 以 `gsk_` 开头，它是 Groq Key。本项目会在仍使用默认 OpenAI 地址时自动切换到 Groq，并使用支持图片的 Llama 4 Scout；也可以手动设置：

```env
OPENAI_BASE_URL=https://api.groq.com/openai/v1
OPENAI_MODEL=qwen/qwen3.8-27b
```

2. 启动本地代理：

```bash
python3 server.py
```

3. 访问 <http://localhost:8000>。页面会按时间默认进入早上、训练后或晚上阶段，也可以随时手动切换。

## 部署到 Render + Supabase

1. 在 Supabase 创建项目，复制连接池（Transaction pooler 也可以）连接字符串。
2. 将项目推送到 GitHub，在 Render 创建 Web Service，运行时选择 Python；`render.yaml` 已提供构建和启动配置。
3. 在 Render 环境变量中设置 `DATABASE_URL`、`OPENAI_API_KEY`，以及可选的 `OPENAI_BASE_URL`、`OPENAI_MODEL`。`COOKIE_SECURE=true` 适用于 Render HTTPS。
4. 部署完成后打开 Render URL，注册账号即可。不要提交 `.env` 或把密钥写进代码；Supabase 数据库表会在服务首次启动时自动创建。

## 安全与边界

- API Key 只在服务端 `server.py` 读取，浏览器不会看到 Key；密码使用标准库 PBKDF2-HMAC-SHA256 哈希，登录凭据通过 HttpOnly、SameSite cookie 传递；`.env` 已被 `.gitignore` 忽略。
- 每次最多发送 4 张图片，整个请求限制为 18 MB；不要上传包含他人脸部或其他敏感信息的照片。
- 模型只能进行辅助性建议，不能诊断疾病。出现疼痛、胸闷、眩晕等症状时停止训练并寻求专业帮助。
- 如果没有配置 API Key，页面会明确提示配置错误，不会把本地规则结果伪装成 AI 结果。
