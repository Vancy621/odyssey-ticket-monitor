import os
import sys
import json
import hashlib
import time
import requests
from bs4 import BeautifulSoup

# ==================== 配置 ====================
BARK_KEY = os.environ.get("BARK_KEY", "")
# 改用移动端页面，反爬更弱
CINEMA_URL = "https://m.maoyan.com/cinema/37534"
KEYWORD = "奥德赛"
STATE_FILE = "state.json"
# =============================================

def send_bark(title, body, jump_url=None):
    """推送Bark通知"""
    if not BARK_KEY:
        print("❌ BARK_KEY 未设置，请在 Secrets 里添加")
        return False
    try:
        url = f"https://api.day.app/{BARK_KEY}/{title}/{body}"
        if jump_url:
            url += f"?url={jump_url}&isArchive=1"
        else:
            url += "?isArchive=1"
        print(f"正在推送: {url[:60]}...")
        r = requests.get(url, timeout=10)
        print(f"Bark返回: {r.status_code}")
        return r.status_code == 200
    except Exception as e:
        print(f"❌ Bark异常: {e}")
        return False

def fetch_schedule():
    """使用Session+移动端UA抓取"""
    session = requests.Session()
    
    # 先访问首页建立cookie
    session.get("https://m.maoyan.com/", headers={
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
    }, timeout=10)
    
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh-Hans;q=0.9",
        "Referer": "https://m.maoyan.com/",
    }
    
    # 重试3次
    for attempt in range(3):
        try:
            print(f"第{attempt+1}次尝试...")
            resp = session.get(CINEMA_URL, headers=headers, timeout=20)
            resp.encoding = "utf-8"
            print(f"状态码: {resp.status_code}, 长度: {len(resp.text)}")
            
            if len(resp.text) < 800:
                print(f"内容过短，疑似被拦截: {resp.text[:150]}")
                time.sleep(3)
                continue
            
            soup = BeautifulSoup(resp.text, "html.parser")
            text = soup.get_text(separator="\n")
            
            if any(x in text for x in ["验证码", "captcha", "访问受限", "请稍后"]):
                print("触发反爬验证")
                time.sleep(3)
                continue
            
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            matched = [l for l in lines if KEYWORD in l or "Odyssey" in l]
            if not matched:
                matched = lines[:50]  # 记录页面指纹
            
            return "\n".join(matched)
        except Exception as e:
            print(f"第{attempt+1}次失败: {e}")
            time.sleep(3)
    
    return None

def main():
    print(f"\n{'='*50}")
    print(f"⏰ {time.strftime('%Y-%m-%d %H:%M:%S')} 开始检查")
    print(f"BARK_KEY: {'✅已设置' if BARK_KEY else '❌未设置'}")
    
    state = {}
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)
    
    content = fetch_schedule()
    
    if content is None:
        print("❌ 连续3次抓取失败，被猫眼反爬拦截")
        # 关键：即使被反爬也发通知，让你知道脚本还活着
        send_bark(
            title="⚠️ 奥德赛监控-反爬提醒",
            body="GitHub美国IP被猫眼拦截，建议改用国内方案（见下文）",
            jump_url=CINEMA_URL
        )
        sys.exit(0)
    
    current_hash = hashlib.md5(content.encode("utf-8")).hexdigest()
    last_hash = state.get("hash")
    
    print(f"当前指纹: {current_hash[:16]}...")
    print(f"上次指纹: {last_hash[:16] if last_hash else '无'}...")
    print(f"内容: {content[:100]}...")
    
    if last_hash is None:
        print("📝 首次运行，发送测试推送...")
        send_bark(
            title="🎬 监控已启动",
            body="前滩太古里《奥德赛》监控开始运行，当前页面已记录。",
            jump_url=CINEMA_URL
        )
    elif last_hash != current_hash:
        print("🔔 检测到排片变化！")
        send_bark(
            title="🎬 奥德赛排片更新！",
            body="前滩太古里MOViE MOViE《奥德赛》排片有变化，快抢票！",
            jump_url=CINEMA_URL
        )
    else:
        print("✅ 页面无变化")
    
    state["hash"] = current_hash
    state["last_check"] = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    print(f"{'='*50}\n")

if __name__ == "__main__":
    main()
