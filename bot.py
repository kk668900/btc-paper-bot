import json, os, csv, time
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

STATE_FILE = "state.json"
TRADES_FILE = "trades.csv"
SYMBOL = "BTC-USD"
LEVERAGE = 10
START_BALANCE = 1000.0
RISK_FRACTION = 0.10
TAKE_PROFIT_PCT = 0.012
STOP_LOSS_PCT = 0.006
FEE_RATE = 0.0006
MAX_DAILY_LOSS = 0.05
MAX_HOLD_TICKS = 6

def utc_now():
    return datetime.now(timezone.utc).isoformat()

def get_candles():
    # Coinbase public market data: 5-minute candles
    url = "https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=300"
    req = Request(url, headers={"User-Agent":"BTC-Paper-Bot/1.0"})
    with urlopen(req, timeout=15) as r:
        raw = json.loads(r.read().decode("utf-8"))
    # Coinbase rows: [time, low, high, open, close, volume], newest first
    rows = sorted(raw, key=lambda x: x[0])
    return [{"time": int(x[0]), "low": float(x[1]), "high": float(x[2]),
             "open": float(x[3]), "close": float(x[4]), "volume": float(x[5])}
            for x in rows if len(x) >= 6]

def ema(values, period):
    if len(values) < period: return None
    k = 2 / (period + 1)
    out = values[0]
    for v in values[1:]:
        out = v * k + out * (1-k)
    return out

def rsi(values, period=14):
    if len(values) < period + 1: return 50.0
    gains, losses = [], []
    for i in range(-period, 0):
        d = values[i] - values[i-1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    ag, al = sum(gains)/period, sum(losses)/period
    if al == 0: return 100.0 if ag else 50.0
    return 100 - 100/(1+ag/al)

def signal(candles):
    closes = [c["close"] for c in candles]
    if len(closes) < 30:
        return "HOLD", {"reason":"K线不足"}
    fast, slow = ema(closes[-24:], 9), ema(closes[-30:], 21)
    rv = rsi(closes, 14)
    # Conservative rule: require trend and RSI confirmation; otherwise stay flat.
    if fast is not None and slow is not None and fast > slow and 52 <= rv <= 68:
        return "LONG", {"rsi":round(rv,2),"ema_fast":round(fast,2),"ema_slow":round(slow,2)}
    if fast is not None and slow is not None and fast < slow and 32 <= rv <= 48:
        return "SHORT", {"rsi":round(rv,2),"ema_fast":round(fast,2),"ema_slow":round(slow,2)}
    return "HOLD", {"rsi":round(rv,2),"ema_fast":round(fast or 0,2),"ema_slow":round(slow or 0,2)}

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f: return json.load(f)
    return {"balance":START_BALANCE,"equity":START_BALANCE,"position":None,
            "trades":0,"wins":0,"realized_pnl":0.0,"day":datetime.now(timezone.utc).date().isoformat(),
            "daily_start_balance":START_BALANCE,"last_candle":0,"last_action":"初始化","updated_at":utc_now()}

def save_state(state):
    state["updated_at"] = utc_now()
    with open(STATE_FILE, "w", encoding="utf-8") as f: json.dump(state, f, ensure_ascii=False, indent=2)

def ensure_trade_file():
    if not os.path.exists(TRADES_FILE):
        with open(TRADES_FILE, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(["time_utc","action","side","price","size_btc","pnl","balance","note"])

def log_trade(action, side, price, size, pnl, balance, note):
    ensure_trade_file()
    with open(TRADES_FILE, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([utc_now(),action,side,f"{price:.2f}",f"{size:.8f}",f"{pnl:.4f}",f"{balance:.2f}",note])

def close_position(state, price, reason):
    p = state["position"]
    if not p: return
    direction = 1 if p["side"] == "LONG" else -1
    gross = (price - p["entry"]) * p["size_btc"] * direction
    fees = (p["entry"] + price) * p["size_btc"] * FEE_RATE
    pnl = gross - fees
    state["balance"] += pnl
    state["realized_pnl"] += pnl
    state["trades"] += 1
    if pnl > 0: state["wins"] += 1
    state["position"] = None
    state["last_action"] = f"平仓 {reason}，盈亏 ${pnl:.2f}"
    log_trade("CLOSE", p["side"], price, p["size_btc"], pnl, state["balance"], reason)

def tick():
    state = load_state()
    candles = get_candles()
    if len(candles) < 30: raise RuntimeError("获取到的 5 分钟 K 线不足")
    last = candles[-1]
    price = last["close"]
    sig, details = signal(candles)
    today = datetime.now(timezone.utc).date().isoformat()
    if state.get("day") != today:
        state["day"] = today
        state["daily_start_balance"] = state["balance"]
    if last["time"] == state.get("last_candle"):
        state["last_action"] = "等待下一根 5 分钟 K 线"
        save_state(state)
        print(state["last_action"])
        return
    state["last_candle"] = last["time"]
    p = state.get("position")
    if p:
        direction = 1 if p["side"] == "LONG" else -1
        move = (price - p["entry"]) / p["entry"] * direction
        p["ticks_held"] = p.get("ticks_held", 0) + 1
        if move >= TAKE_PROFIT_PCT:
            close_position(state, price, "止盈")
        elif move <= -STOP_LOSS_PCT:
            close_position(state, price, "止损")
        elif p["ticks_held"] >= MAX_HOLD_TICKS:
            close_position(state, price, "持仓超时")
        elif sig != "HOLD" and sig != p["side"]:
            close_position(state, price, "信号反转")
    # Daily drawdown guard. No new trades if limit hit.
    daily_loss = (state["daily_start_balance"] - state["balance"]) / max(state["daily_start_balance"], 1)
    if not state.get("position") and daily_loss < MAX_DAILY_LOSS and sig in ("LONG","SHORT"):
        margin = max(0, state["balance"] * RISK_FRACTION)
        notional = margin * LEVERAGE
        size = notional / price
        if size > 0:
            state["position"] = {"side":sig,"entry":price,"size_btc":size,"margin":margin,
                                 "opened_at":utc_now(),"ticks_held":0}
            state["last_action"] = f"模拟开仓 {sig}，价格 ${price:.2f}"
            log_trade("OPEN", sig, price, size, 0, state["balance"], json.dumps(details, ensure_ascii=False))
    elif daily_loss >= MAX_DAILY_LOSS:
        state["last_action"] = "已触发当日亏损保护，停止新开仓"
    else:
        state["last_action"] = f"观望；信号={sig}，价格=${price:.2f}"
    p = state.get("position")
    if p:
        direction = 1 if p["side"] == "LONG" else -1
        unrealized = (price-p["entry"]) * p["size_btc"] * direction
        state["equity"] = state["balance"] + unrealized
    else:
        state["equity"] = state["balance"]
    state["last_price"] = price
    state["signal"] = sig
    state["signal_details"] = details
    state["daily_loss_fraction"] = daily_loss
    save_state(state)
    print(json.dumps(state, ensure_ascii=False))

if __name__ == "__main__":
    tick()
