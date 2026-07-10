# 反检测模块 (Anti-Detect)

降低被平台识别为机器人的风险,包含四层防护。**重要:这些措施只能降低风险,不能保证零风险。请用小号 + 控制规模 + 遵守平台规则。**

## 防护层级

### 第一层:截图风控感知(P0,核心)
每页请求后截图 → LLM 多模态识别 → 判断风控类型 → 主动停止或退避。

**这是最关键的一层**:在账号被封之前主动停下,而不是撞墙触发升级处置。

- LLM 通道(优先):截图 base64 → OpenAI 兼容多模态接口 → 结构化判断
- 本地兜底(LLM 不可用):页面文本匹配风险关键词
- HTTP 兜底:471/461/403 状态码直接判定

识别的风控类型:
| 类型 | 含义 | 默认处理 |
|------|------|---------|
| `normal` | 正常 | 继续 |
| `slider` | 滑块验证码 | 停止(或开启自动通过) |
| `sms` | 短信验证 | 停止 |
| `login_expired` | 登录失效 | 停止 |
| `risk_block` | 封禁提示 | 立即停止 |

### 第二层:行为拟人化(P0)
降低请求的"机械感":
- **随机停顿**:固定 `sleep(2)` → `sleep(2 + random(0,3))`
- **页面停留**:进入页面后停 3 秒(模拟阅读)
- **滚动模拟**:向下滚动 3 次(很多平台检测是否滚动)
- **鼠标移动**:点击前先移动鼠标(可选)

### 第三层:智能退避(P1)
检测到风控时的指数退避:
- 首次退避 60 秒 → 后续翻倍 → 上限 30 分钟
- 连续 3 次风控 → 停止该账号(防止硬冲升级处置)
- 与多账号池协同:停号后自动切下一个

### 第四层:滑块自动通过(P2,可选)
复用 `tools/slider_util.py` 的 opencv 模板匹配 + 拟人化轨迹:
- 识别滑块缺口 → 生成加速/减速轨迹 → page.mouse 拖动
- **成功率有限**(各平台机制不同),谨慎开启

## 配置

`config/base_config.py`:

```python
ENABLE_ANTI_DETECT = False       # 总开关(默认关)
HUMANIZE_SLEEP_JITTER = 3        # 随机抖动秒数
HUMANIZE_PAGE_STAY_SEC = 3       # 页面停留秒数
HUMANIZE_SCROLL_TIMES = 3        # 滚动次数
ANTI_DETECT_SCREENSHOT = True    # 截图风控感知
ANTI_DETECT_ON_RISK = "stop"     # 风控响应:stop / backoff
ANTI_DETECT_BACKOFF_BASE = 60    # 首次退避秒数
ANTI_DETECT_RISK_LIMIT = 3       # 连续风控停号阈值
ANTI_DETECT_AUTO_SLIDER = False  # 滑块自动通过
```

`.env`(复用 AI Agent 的 LLM 配置,用于截图识别):
```bash
LLM_API_KEY=sk-...               # 必须支持多模态(如 gpt-4o)
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o
```

## 用法

```bash
# 启用反检测(需配合 LLM 配置做截图识别)
uv run main.py --platform xhs --lt qrcode --type search \
  --keywords "广州越秀两房出租" --enable_anti_detect yes
```

## 工作流程

```
crawler 每页完成后:
  1. guard.check_risk()    → 截图 + LLM 识别
  2. 若 is_risk:
       guard.handle(result) → 按策略返回 stop/backoff/slider
       stop → 抛 RiskControlError,main 编排器捕获 → 切换账号或退出
  3. 若 normal:
       guard.humanized_sleep() → 随机停顿
       guard.simulate_browse() → 滚动模拟
```

## 接入新平台

各平台 crawler 的 search 循环里,把 `asyncio.sleep(...)` 替换为:

```python
# 反检测:截图感知 + 拟人化停顿
risk = await self.anti_detect.check_risk()
if risk.is_risk:
    action = await self.anti_detect.handle(risk)
    if action == "stop":
        from anti_detect import RiskControlError
        raise RiskControlError(risk)
await self.anti_detect.humanized_sleep(config.CRAWLER_MAX_SLEEP_SEC)
await self.anti_detect.simulate_browse()
```

并在 `start()` 创建 context_page 后调用:
```python
self.anti_detect.attach_page(self.context_page)
```

## 文件结构

```
anti_detect/
├── __init__.py       # 导出 AntiDetectGuard 等
├── types.py          # RiskType 枚举 + RiskResult + 风险关键词表
├── detector.py       # 截图风控感知(LLM + 本地兜底 + HTTP 兜底)
├── humanize.py       # 行为拟人化(随机停顿/滚动/停留/鼠标)
├── backoff.py        # 智能退避(指数增长 + 达上限停止)
├── slider.py         # 滑块自动通过(opencv + 拟人轨迹)
├── guard.py          # AntiDetectGuard 协调器(统一入口)
└── README.md
```

## 重要提醒

- **不保证零风险**:反检测是猫鼠游戏,平台会持续升级检测
- **用小号**:绝不要用主账号做采集
- **控制规模**:关键词少、抓取量小、间隔大
- **首次遇风控就停**:不要硬冲,升级处置可能导致封号
- **遵守平台规则**:仅限个人学习,禁止商业用途
