from flask import Flask, render_template, request, redirect, url_for, flash
import pymysql
import json
import requests
from datetime import datetime, timedelta
import calendar
from collections import defaultdict
import math
import statistics

with open("/home/declan/src/config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

DB_CONFIG = config.get("database", {})
BOT_API_URL = "http://localhost:8000"  # 봇 FastAPI 서버 주소

app = Flask(__name__)
app.secret_key = "13252134"  # flash 메시지용


def get_db_connection():
    return pymysql.connect(
        host=DB_CONFIG.get("host", "localhost"),
        user=DB_CONFIG.get("user", "root"),
        password=DB_CONFIG.get("password", "declan94264@"),
        database=DB_CONFIG.get("database", "hastati_logger_database"),
        port=DB_CONFIG.get("port", 3306),
        charset="utf8mb4",
        autocommit=True,
    )


@app.route("/users")
def list_users():
    db = get_db_connection()
    users = []
    try:
        with db.cursor() as cursor:
            cursor.execute("SELECT user_id, username, nickname, role_name FROM tracked_users")
            users = cursor.fetchall()
    finally:
        db.close()
    return render_template("users.html", users=users)


@app.route("/users/add", methods=["POST"])
def add_user():
    username = request.form.get("username")
    if not username:
        flash("유저명을 입력해주세요.", "error")
        return redirect(url_for("list_users"))

    res = requests.post(f"{BOT_API_URL}/verify_user", json={"name": username})
    data = res.json()

    if data.get("success"):
        flash(f"✅ 유저 {username} 등록 성공 (ID: {data.get('user_id')})", "success")
    else:
        flash(f"❌ 등록 실패: {data.get('reason')}", "error")

    return redirect(url_for("list_users"))


@app.route("/users/delete/<int:user_id>")
def delete_user(user_id):
    db = get_db_connection()
    try:
        with db.cursor() as cursor:
            cursor.execute("DELETE FROM tracked_users WHERE user_id = %s", (user_id,))
            cursor.execute("DELETE FROM voice_sessions WHERE user_id = %s", (user_id,))
    finally:
        db.close()
    return redirect(url_for("list_users"))


@app.route("/channels")
def list_channels():
    db = get_db_connection()
    channels = []
    try:
        with db.cursor() as cursor:
            cursor.execute("SELECT channel_id, name FROM tracked_channels WHERE enabled = TRUE")
            channels = cursor.fetchall()
    finally:
        db.close()
    return render_template("channels.html", channels=channels)


@app.route("/channels/add", methods=["POST"])
def add_channel():
    channel_name = request.form.get("name")
    if not channel_name:
        flash("채널 이름을 입력해주세요.", "error")
        return redirect(url_for("list_channels"))

    res = requests.post(f"{BOT_API_URL}/verify_channel", json={"name": channel_name})
    data = res.json()

    if data.get("success"):
        flash(f"✅ 채널 {channel_name} 등록 성공 (ID: {data.get('channel_id')})", "success")
    else:
        flash(f"❌ 등록 실패: {data.get('reason')}", "error")

    return redirect(url_for("list_channels"))


@app.route("/channels/delete/<int:channel_id>")
def delete_channel(channel_id):
    db = get_db_connection()
    try:
        with db.cursor() as cursor:
            cursor.execute("UPDATE tracked_channels SET enabled = FALSE WHERE channel_id = %s", (channel_id,))
    finally:
        db.close()
    return redirect(url_for("list_channels"))


@app.route("/report")
def report_user_list():
    db = get_db_connection()
    try:
        with db.cursor() as cursor:
            cursor.execute("SELECT DISTINCT user_id, username FROM voice_sessions ORDER BY username")
            users = cursor.fetchall()
    finally:
        db.close()
    return render_template("report_users.html", users=users)


@app.route("/report/<int:user_id>")
def report(user_id):
    return redirect(url_for("report_range", user_id=user_id, days=7))


@app.route("/report/<int:user_id>/<int:days>")
def report_range(user_id, days):
    db = get_db_connection()
    try:
        with db.cursor() as cursor:
            end_date = datetime.now()
            if days == 0:
                start_date = datetime(2000, 1, 1)  # 전체 기간
            else:
                start_date = end_date - timedelta(days=days)

            cursor.execute(
                """
                SELECT username, start_time, end_time, duration_sec
                FROM voice_sessions
                WHERE user_id = %s AND start_time BETWEEN %s AND %s
            """,
                (user_id, start_date, end_date),
            )
            sessions = cursor.fetchall()

        if not sessions:
            return f"<h3>사용자 {user_id}의 활동 기록이 없습니다.</h3>"

        username = sessions[0][0]
        total_seconds = sum(row[3] for row in sessions)
        total_minutes = total_seconds // 60
        entry_count = len(sessions)
        average_minutes = total_minutes // entry_count if entry_count else 0

        weekday_totals = defaultdict(int)
        hourly_totals = defaultdict(int)
        active_days = set()

        for row in sessions:
            start = row[1]
            duration = row[3]
            weekday_totals[start.weekday()] += duration
            hour = start.hour
            hourly_totals[hour] += duration
            active_days.add(start.date())

        most_active_day = max(weekday_totals.items(), key=lambda x: x[1])
        most_active_hour_range = max(hourly_totals.items(), key=lambda x: x[1])

        def hour_range(hour):
            return f"{hour:02d}:00 ~ {hour+1:02d}:00"

        num_active_days = len(active_days) or 1
        avg_entries_per_day = entry_count / num_active_days

        return render_template(
            "report.html",
            username=username,
            user_id=user_id,
            total_minutes=total_minutes,
            entry_count=entry_count,
            avg_minutes=average_minutes,
            top_day=calendar.day_name[most_active_day[0]],
            top_day_minutes=most_active_day[1] // 60,
            top_hour_range=hour_range(most_active_hour_range[0]),
            hour_minutes=most_active_hour_range[1] // 60,
            days=days,
            avg_entries=avg_entries_per_day,
        )
    finally:
        db.close()


@app.route("/report/summary")
def report_summary():
    db = get_db_connection()
    try:
        with db.cursor() as cursor:
            cursor.execute(
                """
                SELECT user_id, username, start_time, duration_sec
                FROM voice_sessions
                ORDER BY username
            """
            )
            sessions = cursor.fetchall()

        if not sessions:
            return "<h3>활동 기록이 없습니다.</h3>"

        user_stats = defaultdict(
            lambda: {"username": "", "total_seconds": 0, "entry_count": 0, "active_days": set()}
        )

        for row in sessions:
            user_id, username, start_time, duration_sec = row
            stats = user_stats[user_id]
            stats["username"] = username
            stats["total_seconds"] += duration_sec
            stats["entry_count"] += 1
            stats["active_days"].add(start_time.date())

        summary = []
        total_all_seconds = 0
        user_total_minutes_list = []

        for user_id, stats in user_stats.items():
            total_minutes = stats["total_seconds"] // 60
            entry_count = stats["entry_count"]
            active_days = len(stats["active_days"])
            avg_minutes = total_minutes // entry_count if entry_count else 0
            avg_entries_per_day = entry_count / active_days if active_days else 0

            summary.append(
                {
                    "user_id": user_id,
                    "username": stats["username"],
                    "total_minutes": total_minutes,
                    "entry_count": entry_count,
                    "avg_minutes": avg_minutes,
                    "active_days": active_days,
                    "avg_entries": round(avg_entries_per_day, 2),
                }
            )

            user_total_minutes_list.append(total_minutes)
            total_all_seconds += stats["total_seconds"]

        # \U0001f4ca 전체 통계 계산
        total_all_minutes = total_all_seconds // 60
        total_users = len(summary)
        avg_minutes_per_user = total_all_minutes // total_users if total_users else 0

        max_user = max(summary, key=lambda u: u["total_minutes"])
        min_user = min(summary, key=lambda u: u["total_minutes"])

        std_dev = int(statistics.stdev(user_total_minutes_list)) if len(user_total_minutes_list) >= 2 else 0

        overall_stats = {
            "total_users": total_users,
            "total_all_minutes": total_all_minutes,
            "avg_minutes_per_user": avg_minutes_per_user,
            "max_user": max_user,
            "min_user": min_user,
            "std_dev": std_dev,
        }
        summary.sort(key=lambda u: u["total_minutes"], reverse=True)
        return render_template("report_summary.html", summary=summary, overall=overall_stats)

    finally:
        db.close()


@app.route("/report/heatmap")
def hastati_heatmap():
    db = get_db_connection()
    try:
        with db.cursor() as cursor:
            now = datetime.now()
            start_time = now - timedelta(days=7)

            cursor.execute(
                """
                SELECT vs.user_id, tu.username, tu.nickname, vs.start_time
                FROM voice_sessions vs
                LEFT JOIN tracked_users tu ON vs.user_id = tu.user_id
                WHERE vs.start_time >= %s
            """,
                (start_time,),
            )
            rows = cursor.fetchall()

        date_labels = [(now - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(6, -1, -1)]
        heatmap = {date: [{"count": 0, "users": set()} for _ in range(24)] for date in date_labels}

        for user_id, username, nickname, start in rows:
            date_str = start.strftime("%Y-%m-%d")
            hour = start.hour
            display_name = nickname or username
            if date_str in heatmap:
                cell = heatmap[date_str][hour]
                cell["users"].add(display_name)
                cell["count"] = len(cell["users"])

        for hour_cells in heatmap.values():
            for cell in hour_cells:
                cell["users"] = list(sorted(cell["users"]))

        return render_template("components/heatmap_component.html", heatmap=heatmap, date_labels=date_labels)
    finally:
        db.close()


@app.route("/report/focus")
def report_focus_view():
    now = datetime.now()

    def get_focus_map(start_time):
        db = get_db_connection()
        try:
            with db.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT user_id, start_time, duration_sec
                    FROM voice_sessions
                    WHERE start_time >= %s
                """,
                    (start_time,),
                )
                rows = cursor.fetchall()
        finally:
            db.close()

        if not rows:
            return {}, 0, 0, 0

        total_duration = 0
        time_blocks = defaultdict(int)
        user_totals = defaultdict(int)

        for user_id, start, duration in rows:
            key = start.hour
            time_blocks[key] += duration
            user_totals[user_id] += duration
            total_duration += duration

        focus_map = {}
        for hour in range(24):
            dur = time_blocks.get(hour, 0)
            if dur > 0:
                percent = round(dur / total_duration * 100, 2)
                focus_map[hour] = {"percent": percent}

        sorted_users = sorted(user_totals.items(), key=lambda x: x[1], reverse=True)
        top_n = math.ceil(len(sorted_users) * 0.2)
        top_duration = sum(x[1] for x in sorted_users[:top_n])
        top_ratio = round(top_duration / total_duration * 100, 2)

        return focus_map, top_n, top_ratio, len(user_totals)

    ranges = [
        ("1일", now - timedelta(days=1)),
        ("7일", now - timedelta(days=7)),
        ("30일", now - timedelta(days=30)),
        ("전체", datetime(2020, 1, 1)),
    ]

    focus_data = []
    pareto_data = []

    for label, start_time in ranges:
        fmap, top_n, top_ratio, total_users = get_focus_map(start_time)
        focus_data.append((label, fmap))
        pareto_data.append({"label": label, "top_n": top_n, "top_ratio": top_ratio, "total_users": total_users})

    return render_template("components/focus_component.html", focus_data=focus_data, pareto_data=pareto_data)


@app.route("/report/pareto")
def report_pareto_view():
    now = datetime.now()
    ranges = {
        "1일": now - timedelta(days=1),
        "7일": now - timedelta(days=7),
        "30일": now - timedelta(days=30),
        "전체": datetime(2020, 1, 1),
    }

    db = get_db_connection()
    try:
        with db.cursor() as cursor:
            cursor.execute(
                """
                SELECT user_id, start_time, duration_sec
                FROM voice_sessions
            """
            )
            rows = cursor.fetchall()

        pareto_data = []

        for label, cutoff in ranges.items():
            filtered = [(uid, dur) for uid, start, dur in rows if start >= cutoff]
            if not filtered:
                pareto_data.append((label, None))
                continue

            user_totals = defaultdict(int)
            for uid, dur in filtered:
                user_totals[uid] += dur

            total_duration = sum(user_totals.values())
            sorted_users = sorted(user_totals.items(), key=lambda x: x[1], reverse=True)

            def calc_ratio(top_n):
                return round(sum(x[1] for x in sorted_users[:top_n]) / total_duration * 100, 2)

            top2 = calc_ratio(2)
            top5 = calc_ratio(5)
            top20pct = calc_ratio(max(1, int(len(sorted_users) * 0.2)))

            pareto_data.append((label, {"top2": top2, "top5": top5, "top20pct": top20pct, "total_users": len(user_totals)}))

        return render_template("components/pareto_component.html", pareto_data=pareto_data)
    finally:
        db.close()


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/manage")
def manage_page():
    db = get_db_connection()
    users = []
    channels = []
    try:
        with db.cursor() as cursor:
            cursor.execute("SELECT user_id, username, nickname, role_name FROM tracked_users")
            users = cursor.fetchall()
            cursor.execute("SELECT channel_id, name FROM tracked_channels WHERE enabled = TRUE")
            channels = cursor.fetchall()
    finally:
        db.close()

    return render_template("manage.html", users=users, channels=channels)


@app.route("/manage/add", methods=["POST"])
def manage_add():
    target = request.form.get("target")
    db = get_db_connection()

    if target == "user":
        username = request.form.get("username")
        if not username:
            flash("유저명을 입력해주세요.", "error")
        else:
            res = requests.post(f"{BOT_API_URL}/verify_user", json={"name": username})
            data = res.json()
            if data.get("success"):
                flash(f"✅ 유저 {username} 등록 성공 (ID: {data.get('user_id')})", "success")
            else:
                flash(f"❌ 등록 실패: {data.get('reason')}", "error")

    elif target == "channel":
        channel_name = request.form.get("name")
        if not channel_name:
            flash("채널명을 입력해주세요.", "error")
        else:
            res = requests.post(f"{BOT_API_URL}/verify_channel", json={"name": channel_name})
            data = res.json()
            if data.get("success"):
                flash(f"✅ 채널 {channel_name} 등록 성공 (ID: {data.get('channel_id')})", "success")
            else:
                flash(f"❌ 등록 실패: {data.get('reason')}", "error")

    return redirect(url_for("manage_page"))


@app.route("/manage/delete/user/<int:user_id>")
def manage_delete_user(user_id):
    db = get_db_connection()
    try:
        with db.cursor() as cursor:
            cursor.execute("DELETE FROM tracked_users WHERE user_id = %s", (user_id,))
    finally:
        db.close()
    return redirect(url_for("manage_page"))


@app.route("/manage/delete/channel/<int:channel_id>")
def manage_delete_channel(channel_id):
    db = get_db_connection()
    try:
        with db.cursor() as cursor:
            cursor.execute("UPDATE tracked_channels SET enabled = FALSE WHERE channel_id = %s", (channel_id,))
    finally:
        db.close()
    return redirect(url_for("manage_page"))


if __name__ == "__main__":
    app.run(debug=True)
