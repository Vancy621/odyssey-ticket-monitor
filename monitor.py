import os
import sys
import json
import hashlib
import time
import requests
from bs4 import BeautifulSoup

# ==================== 配置 ====================
BARK_KEY = os.environ.get("BARK_KEY", "")
CINEMA_URL = "https://www.maoyan.com/cinema/37534?poi=1153113439"
KEYWORD = "奥德赛"
STATE_FILE = "state.json"
# =============================================

def send_bark(title, body, jump_url=None):
    """推送Bark通知"""
    if not BARK_KEY:
        print("⚠️ BARK_KEY 未设置")
        return
    try:
        url = f"https://api.day.app/{BARK_KEY}/{title}/{body}"
        if jump_url:
            url += f"?url={jump_url}&isArchive=1"
        else:
            url += "?isArchive=1"
        r = requests.get(url, timeout=10)
        print(f"Bark推送状态: {r.status_code}")
    except Exception as e:
        print(f"Bark推送失败: {e}")

def fetch_schedule():
    """抓取影院排片页面"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }
    try:
        resp = requests.get(CINEMA_URL, headers=headers, timeout=20)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")
        text = soup.get_text(separator="\n")
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        
        # 反爬检测：如果页面异常短或出现验证码，跳过
        full_text = "\n".join(lines)
        if "验证码" in full_text or "captcha" in full_text.lower() or len(full_text) < 800:
            print("⚠️ 可能触发反爬，本次跳过")
            return None
        
        # 提取包含"奥德赛"或"Odyssey"的行
        matched = [l for l in lines if KEYWORD in l or "Odyssey" in l]
        
        # 如果没找到关键词，也记录页面特征（防止漏掉）
        if not matched:
            # 记录页面哈希的前几行作为基准
            matched = lines[:30]
        
        content = "\n".join(matched)
        return content
    except Exception as e:
        print(f"抓取失败: {e}")
        return None

def main():
    print(f"⏰ {time.strftime('%Y-%m-%d %H:%M:%S')} 开始检查...")
    
    # 读取上次状态
    state = {}
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)
    
    content = fetch_schedule()
    if content is None:
        print("抓取异常，退出")
        sys.exit(0)
    
    current_hash = hashlib.md5(content.encode("utf-8")).hexdigest()
    last_hash = state.get("hash")
    
    print(f"当前哈希: {current_hash}")
    print(f"上次哈希: {last_hash}")
    print(f"内容预览: {content[:150]}...")
    
    # 判断变化
    if last_hash is None:
        print("📝 首次运行，仅记录状态，不推送")
    elif last_hash != current_hash:
        print("🔔 检测到排片变化！")
        send_bark(
            title="🎬 奥德赛排片更新！",
            body="前滩太古里MOViE MOViE《奥德赛》排片有变化，快抢票！",
            jump_url=CINEMA_URL
        )
    else:
        print("✅ 暂无变化")
    
    # 保存状态
    state["hash"] = current_hash
    state["last_check"] = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
