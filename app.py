import json, os, csv, time
from datetime import datetime, timezone
from urllib.request import Request, urlopen
import streamlit as st
import pandas as pd

st.set_page_config(page_title="BTC 自动短线模拟机器人", page_icon="₿", layout="wide")
st.title("₿ BTC 自动短线交易机器人")
st.caption("5 分钟 K 线 · 10 倍杠杆 · 仅模拟交易 · 不连接交易所账户")
st.warning("自动交易任务由 GitHub Actions 定时运行；免费任务可能延迟或失败。此页面仅查看行情与状态，不会下真实订单。")

def get_price():
    req=Request("https://api.exchange.coinbase.com/products/BTC-USD/ticker", headers={"User-Agent":"BTC-Paper-Bot/1.0"})
    with urlopen(req, timeout=10) as r: return json.loads(r.read().decode())["price"]

c1,c2,c3=st.columns(3)
try:
    price=float(get_price())
    c1.metric("BTC 参考价", f"${price:,.2f}")
except Exception as e:
    c1.metric("BTC 参考价", "暂不可用")
    st.caption(f"行情获取失败：{e}")

state_path="state.json"
if os.path.exists(state_path):
    with open(state_path,encoding="utf-8") as f: state=json.load(f)
    c2.metric("模拟余额", f"${state.get('balance',1000):,.2f}")
    c3.metric("累计已实现盈亏", f"${state.get('realized_pnl',0):,.2f}")
    st.subheader("机器人状态")
    st.write("最近动作：", state.get("last_action","尚无记录"))
    st.write("最新信号：", state.get("signal","等待运行"))
    st.write("最后更新时间（UTC）：", state.get("updated_at","未知"))
    pos=state.get("position")
    if pos:
        st.info(f"持仓：{pos['side']} | 入场 ${pos['entry']:,.2f} | 数量 {pos['size_btc']:.6f} BTC | 保证金 ${pos['margin']:.2f}")
    else:
        st.write("当前持仓：空仓")
else:
    c2.metric("模拟余额", "$1,000.00")
    c3.metric("累计已实现盈亏", "$0.00")
    st.info("尚未运行机器人。部署 GitHub Actions 后，状态文件会在 bot-state 分支生成。")

if os.path.exists("trades.csv"):
    st.subheader("交易记录")
    try:
        df=pd.read_csv("trades.csv")
        st.dataframe(df.tail(100), use_container_width=True)
        st.download_button("下载交易 CSV", df.to_csv(index=False).encode("utf-8-sig"), "trades.csv", "text/csv")
    except Exception as e: st.caption(f"交易记录暂不可读：{e}")
st.caption("策略是示例规则，不构成投资建议。手续费、滑点、资金费率与真实强平机制均未完整模拟；回测和模拟结果不代表未来收益。")
