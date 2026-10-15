# BTC 自动短线模拟机器人（5 分钟 / 10 倍模拟杠杆）

此项目只做**模拟交易**，不连接交易所私钥，不会发送真实订单。

## 组成
- `bot.py`：单次机器人任务。读取 Coinbase 公共 BTC-USD 5 分钟 K 线，按 EMA 趋势 + RSI 规则开仓/平仓。
- `app.py`：Streamlit 状态面板。
- `.github/workflows/paper-bot.yml`：GitHub Actions 定时执行任务。
- `state.json` 和 `trades.csv`：模拟账户状态与交易记录，保存到独立的 `bot-state` 分支。

## 风险与限制
- GitHub Actions 定时任务不是交易所级别的实时系统，调度可能延迟，免费额度/政策也可能变化。
- 每次执行只处理一次最新的 5 分钟 K 线；如果漏掉多个周期，不会逐根重放所有历史K线。
- 10x 是模拟仓位名义杠杆，不是对真实保证金、强平、资金费率的精确建模。
- 该示例策略未经充分回测，可能亏损；模拟结果不能证明有盈利能力。

## 首次部署（手机网页操作）
1. 在 GitHub 创建一个 **Public** 或 **Private** 新仓库，例如 `btc-paper-bot`。
2. 上传本项目全部文件，保持 `.github/workflows/paper-bot.yml` 的路径不变。
3. 进入仓库 `Settings -> Actions -> General`，确认允许 Actions 执行工作流。
4. 进入 `Actions`，如果出现启用工作流提示，点击 **I understand my workflows, go ahead and enable them**。
5. 打开 `Actions -> BTC paper bot`，点击 **Run workflow** 手动运行一次。
6. 运行成功后会创建 `bot-state` 分支，里面有 `state.json` 和 `trades.csv`。之后计划每 5 分钟运行一次，但 GitHub 可能延迟调度。
7. 在 Streamlit Community Cloud 新建 App，选择此仓库的 `app.py`。注意 Streamlit Cloud 主分支默认不会自动读取 `bot-state` 分支；要查看状态/交易记录，可直接打开 `bot-state` 分支里的文件，或后续再接数据库同步。
8. 不要在仓库中添加任何真实交易所 API 密钥。

## 手动调试
在 GitHub Actions 手动运行工作流，查看日志中的信号和状态。首次运行可能因公开行情 API 限流或网络问题失败，重新运行即可。
