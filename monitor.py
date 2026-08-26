#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
猫眼电影放票检测脚本 - GitHub Actions 版
影院：上海前滩太古里 MOViE MOViE 影城（cinemaId=37534）
影片：奥德赛（movieId=1545360）
检测：由 GitHub Actions 每 5 分钟触发
通知：Bark
"""

import requests
import json
import urllib.parse
import os
from datetime import datetime


# ==================== 配置区域 ====================

CINEMA_ID = 37534
MOVIE_ID = 1545360

MOVIE_NAME = "奥德赛"
CINEMA_NAME = "MOViE MOViE 影城（前滩太古里店）"

# 只关注指定影厅（想监控全部就改成空列表 []）
TARGET_HALLS = ["IMAX 激光厅"]

# Bark（从环境变量读取）
BARK_KEY = os.environ.get("BARK_KEY", "")
BARK_SERVER = os.environ.get("BARK_SERVER", "https://api.day.app")

# 状态文件
STATE_FILE = ".ticket_monitor_state.json"


# ==================== 监控器 ====================

class TicketMonitor:

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 "
                "Mobile/15E148 Safari/604.1"
            ),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": "https://m.maoyan.com/",
        })
        self.previous_shows = {}
        self.load_state()

    def log(self, message):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{ts}] {message}")

    def load_state(self):
        if not os.path.exists(STATE_FILE):
            self.previous_shows = {}
            return
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                self.previous_shows = json.load(f)
            self.log(f"已加载历史状态，共 {len(self.previous_shows)} 条记录")
        except Exception as e:
            self.log(f"读取历史状态失败: {e}")
            self.previous_shows = {}

    def save_state(self):
        try:
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.previous_shows, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.log(f"保存状态失败: {e}")

    def fetch_cinema_data(self):
        url = "https://m.maoyan.com/ajax/cinemaDetail"
        params = {"cinemaId": CINEMA_ID}
        try:
            resp = self.session.get(url, params=params, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self.log(f"请求失败: {e}")
            return None

    def extract_movie_shows(self, data):
        if not data or "showData" not in data:
            return []
        movies = data["showData"].get("movies", [])
        target_movie = None
        for movie in movies:
            if movie.get("id") == MOVIE_ID or movie.get("nm") == MOVIE_NAME:
                target_movie = movie
                break
        if not target_movie:
            return []

        shows = target_movie.get("shows", [])
        result = []
        for day in shows:
            show_date = day.get("showDate", "")
            date_show = day.get("dateShow", "")
            for p in day.get("plist", []):
                show_info = {
                    "date": show_date,
                    "date_display": date_show,
                    "time": p.get("tm", ""),
                    "hall": p.get("th", ""),
                    "format": p.get("tp", ""),
                    "language": p.get("lang", ""),
                }
                if TARGET_HALLS and show_info["hall"] not in TARGET_HALLS:
                    continue
                result.append(show_info)
        return result

    def get_show_key(self, show):
        return f"{show['date']}_{show['time']}_{show['hall']}"

    def detect_changes(self, current_shows):
        return [show for show in current_shows if self.get_show_key(show) not in self.previous_shows]

    def update_state(self, current_shows):
        self.previous_shows = {self.get_show_key(show): show for show in current_shows}
        self.save_state()

    def send_bark(self, title, body):
        if not BARK_KEY:
            self.log("⚠️ 没有找到 BARK_KEY，跳过 Bark 推送")
            return
        try:
            title_encoded = urllib.parse.quote(title, safe="")
            body_encoded = urllib.parse.quote(body, safe="")
            url = f"{BARK_SERVER}/{BARK_KEY}/{title_encoded}/{body_encoded}"
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                self.log("📲 Bark 推送成功")
            else:
                self.log(f"Bark 推送失败: {resp.status_code}")
        except Exception as e:
            self.log(f"Bark 推送异常: {e}")

    def format_show_info(self, show):
        return f"📅 {show['date_display']} {show['time']} | {show['hall']} | {show['format']} | {show['language']}"

    def run_check(self):
        self.log("=" * 60)
        self.log("🎬 开始检测电影放票")
        self.log(f"影院: {CINEMA_NAME}")
        self.log(f"影片: {MOVIE_NAME}")
        self.log(f"目标影厅: {', '.join(TARGET_HALLS) if TARGET_HALLS else '全部'}")

        data = self.fetch_cinema_data()
        if not data:
            self.log("❌ 获取数据失败")
            return

        current_shows = self.extract_movie_shows(data)
        self.log(f"当前共有 {len(current_shows)} 个符合条件的场次")

        # 首次运行
        if not self.previous_shows:
            self.log("首次运行，初始化状态")
            self.update_state(current_shows)
            self.send_bark(
                "🎬 放票检测已启动",
                f"影院: {CINEMA_NAME}\n影片: {MOVIE_NAME}\n当前场次: {len(current_shows)} 场\n检测间隔: 5 分钟"
            )
            return

        # 检测新增
        new_shows = self.detect_changes(current_shows)
        if new_shows:
            self.log(f"🎉 发现 {len(new_shows)} 个新场次！")
            show_lines = "\n".join(self.format_show_info(show) for show in new_shows)
            body = f"{show_lines}\n\n👉 立即购票:\nhttps://www.maoyan.com/cinema/{CINEMA_ID}"
            self.send_bark(f"🎬 {MOVIE_NAME} 新场次放票！", body)
        else:

            self.log(
                "无新场次"
            )
            # 临时测试推送
            self.send_bark(
                "🎬 测试推送",
                "如果收到这条，说明 Bark 已经通了"
            )

        self.update_state(current_shows)
        self.log("✅ 本次检测完成")
        self.log("=" * 60)


if __name__ == "__main__":
    monitor = TicketMonitor()
    monitor.run_check()
