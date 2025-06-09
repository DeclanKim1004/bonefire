from flask import Flask, render_template, request, redirect, url_for, flash
import pymysql
import json
import requests
from datetime import datetime, timedelta
import calendar
from collections import defaultdict
import math
import statistics
import os
from typing import List, Tuple

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = json.load(f)

DB_CONFIG = config.get("database", {})
BOT_API_URL = "http://localhost:8000"  # 봇 FastAPI 서버 주소

app = Flask(__name__)
app.secret_key = "13252134"  # flash 메시지용

HASTATI_ROLE_NAME = "━━♔⊱༻ 하스타티 ༺⊰♔━━"
LEGATUS_ROLE_NAME = "✧˖*°࿐.*.｡ ⚔️레가투스⚔️.*.✧˖*°࿐"


def get_db_connection():
    return pymysql.connect(
        host=DB_CONFIG.get("host"),
        user=DB_CONFIG.get("user"),
        password=DB_CONFIG.get("password"),
        database=DB_CONFIG.get("database"),
        port=DB_CONFIG.get("port", 3306),
        charset="utf8mb4",
        autocommit=True,
    )


def check_access_and_report_visibility(member_roles: List[str]) -> Tuple[bool, bool]:
    """Determine access rights and reporter visibility based on roles."""
    is_hastati = HASTATI_ROLE_NAME in member_roles
    is_legatus = LEGATUS_ROLE_NAME in member_roles
    is_special_admin = any(
        r in member_roles
        for r in [
            "☽☆꧁༒🌞 태양신 🌞༒꧂☆☾",
            "۞☆꧁༒☬ 세계수 ☬༒꧂☆۞",
            "[뉴비관리팀장]",
            "✧˖*°.*.｡✯마구스 팀장✯.*.✧˖*°",
        ]
    )

    if is_special_admin:
        return True, True
    if is_hastati and is_legatus:
        return True, True
    if is_hastati:
        return True, False
    return False, False


@app.route("/embers")
def list_embers():
    db = get_db_connection()
    embers = []
    try:
        with db.cursor() as cursor:
            cursor.execute("SELECT user_id, username, nickname, role_name FROM tracked_users")
            embers = cursor.fetchall()
    finally:
        db.close()
    return render_template("embers.html", embers=embers)


@app.route("/embers/add", methods=["POST"])
def add_ember():
    username = request.form.get("username")
    if not username:
        flash("잿불 이름을 입력해주세요.", "error")
        return redirect(url_for("list_embers"))

    res = requests.post(f"{BOT_API_URL}/verify_user", json={"name": username})
    data = res.json()

    if data.get("success"):
        flash(f"🔥 잿불 {username}이 피어올랐습니다 (ID: {data.get('user_id')})", "success")
    else:
        flash(f"❄️ 불씨가 꺼졌습니다: {data.get('reason')}", "error")

    return redirect(url_for("list_embers"))


@app.route("/embers/delete/<int:ember_id>")
def delete_ember(ember_id):
    db = get_db_connection()
    try:
        with db.cursor() as cursor:
            cursor.execute("DELETE FROM tracked_users WHERE user_id = %s", (ember_id,))
            cursor.execute("DELETE FROM voice_sessions WHERE user_id = %s", (ember_id,))
    finally:
        db.close()
    return redirect(url_for("list_embers"))


@app.route("/pyres")
def list_pyres():
    db = get_db_connection()
    pyres = []
    try:
        with db.cursor() as cursor:
            cursor.execute("SELECT channel_id, name FROM tracked_channels WHERE enabled = TRUE")
            pyres = cursor.fetchall()
    finally:
        db.close()
    return render_template("pyres.html", pyres=pyres)


@app.route("/pyres/add", methods=["POST"])
def add_pyre():
    pyre_name = request.form.get("name")
    if not pyre_name:
        flash("장작더미 이름을 입력해주세요.", "error")
        return redirect(url_for("list_pyres"))

    res = requests.post(f"{BOT_API_URL}/verify_channel", json={"name": pyre_name})
    data = res.json()

    if data.get("success"):
        flash(f"🔥 장작더미 {pyre_name}이 추가되었습니다 (ID: {data.get('channel_id')})", "success")
    else:
        flash(f"❄️ 불씨가 꺼졌습니다: {data.get('reason')}", "error")

    return redirect(url_for("list_pyres"))


@app.route("/pyres/delete/<int:pyre_id>")
def delete_pyre(pyre_id):
    db = get_db_connection()
    try:
        with db.cursor() as cursor:
            cursor.execute("UPDATE tracked_channels SET enabled = FALSE WHERE channel_id = %s", (pyre_id,))
    finally:
        db.close()
    return redirect(url_for("list_pyres"))


@app.route("/flames")
def flames_ember_list():
    db = get_db_connection()
    try:
        with db.cursor() as cursor:
            cursor.execute("SELECT DISTINCT user_id, username FROM voice_sessions ORDER BY username")
            embers = cursor.fetchall()
    finally:
        db.close()
    return render_template("flames_embers.html", embers=embers)


@app.route("/flames/<int:ember_id>")
def flames(ember_id):
    return redirect(url_for("flames_range", ember_id=ember_id, days=7))


@app.route("/flames/<int:ember_id>/<int:days>")
def flames_range(ember_id, days):
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
                (ember_id, start_date, end_date),
            )
            sessions = cursor.fetchall()

        if not sessions:
            return f"<h3>사용자 {ember_id}의 활동 기록이 없습니다.</h3>"

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
            "flames.html",
            username=username,
            user_id=ember_id,
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


@app.route("/flames/summary")
def flames_summary():
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
        ember_total_minutes_list = []

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

            ember_total_minutes_list.append(total_minutes)
            total_all_seconds += stats["total_seconds"]

        # \U0001f4ca 전체 통계 계산
        total_all_minutes = total_all_seconds // 60
        total_embers = len(summary)
        avg_minutes_per_ember = total_all_minutes // total_embers if total_embers else 0

        max_ember = max(summary, key=lambda u: u["total_minutes"])
        min_ember = min(summary, key=lambda u: u["total_minutes"])

        std_dev = int(statistics.stdev(ember_total_minutes_list)) if len(ember_total_minutes_list) >= 2 else 0

        overall_stats = {
            "total_users": total_embers,
            "total_all_minutes": total_all_minutes,
            "avg_minutes_per_user": avg_minutes_per_ember,
            "max_user": max_ember,
            "min_user": min_ember,
            "std_dev": std_dev,
        }
        summary.sort(key=lambda u: u["total_minutes"], reverse=True)
        return render_template("flames_summary.html", summary=summary, overall=overall_stats)

    finally:
        db.close()


@app.route("/flames/heatmap")
def flames_heatmap():
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


@app.route("/flames/focus")
def flames_focus_view():
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
        ember_totals = defaultdict(int)

        for user_id, start, duration in rows:
            key = start.hour
            time_blocks[key] += duration
            ember_totals[user_id] += duration
            total_duration += duration

        focus_map = {}
        for hour in range(24):
            dur = time_blocks.get(hour, 0)
            if dur > 0:
                percent = round(dur / total_duration * 100, 2)
                focus_map[hour] = {"percent": percent}

        sorted_embers = sorted(ember_totals.items(), key=lambda x: x[1], reverse=True)
        top_n = math.ceil(len(sorted_embers) * 0.2)
        top_duration = sum(x[1] for x in sorted_embers[:top_n])
        top_ratio = round(top_duration / total_duration * 100, 2)

        return focus_map, top_n, top_ratio, len(ember_totals)

    ranges = [
        ("1일", now - timedelta(days=1)),
        ("7일", now - timedelta(days=7)),
        ("30일", now - timedelta(days=30)),
        ("전체", datetime(2020, 1, 1)),
    ]

    focus_data = []
    pareto_data = []

    for label, start_time in ranges:
        fmap, top_n, top_ratio, total_embers = get_focus_map(start_time)
        focus_data.append((label, fmap))
        pareto_data.append({"label": label, "top_n": top_n, "top_ratio": top_ratio, "total_users": total_embers})

    return render_template("components/focus_component.html", focus_data=focus_data, pareto_data=pareto_data)


@app.route("/flames/pareto")
def flames_pareto_view():
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

            ember_totals = defaultdict(int)
            for uid, dur in filtered:
                ember_totals[uid] += dur

            total_duration = sum(ember_totals.values())
            sorted_embers = sorted(ember_totals.items(), key=lambda x: x[1], reverse=True)

            def calc_ratio(top_n):
                return round(sum(x[1] for x in sorted_embers[:top_n]) / total_duration * 100, 2)

            top2 = calc_ratio(2)
            top5 = calc_ratio(5)
            # calculate top 20% based on ember totals
            top20pct = calc_ratio(max(1, int(len(sorted_embers) * 0.2)))

            pareto_data.append((label, {"top2": top2, "top5": top5, "top20pct": top20pct, "total_users": len(ember_totals)}))

        return render_template("components/pareto_component.html", pareto_data=pareto_data)
    finally:
        db.close()


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/kindle")
def kindle_page():
    db = get_db_connection()
    embers = []
    pyres = []
    try:
        with db.cursor() as cursor:
            cursor.execute("SELECT user_id, username, nickname, role_name FROM tracked_users")
            embers = cursor.fetchall()
            cursor.execute("SELECT channel_id, name FROM tracked_channels WHERE enabled = TRUE")
            pyres = cursor.fetchall()
    finally:
        db.close()

    return render_template("kindle.html", embers=embers, pyres=pyres)


@app.route("/kindle/add", methods=["POST"])
def kindle_add():
    target = request.form.get("target")
    db = get_db_connection()

    if target == "user":
        username = request.form.get("username")
        if not username:
            flash("잿불 이름을 입력해주세요.", "error")
        else:
            res = requests.post(f"{BOT_API_URL}/verify_user", json={"name": username})
            data = res.json()
            if data.get("success"):
                flash(f"🔥 잿불 {username}이 피어올랐습니다 (ID: {data.get('user_id')})", "success")
            else:
                flash(f"❄️ 불씨가 꺼졌습니다: {data.get('reason')}", "error")

    elif target == "channel":
        pyre_name = request.form.get("name")
        if not pyre_name:
            flash("장작더미 이름을 입력해주세요.", "error")
        else:
            res = requests.post(f"{BOT_API_URL}/verify_channel", json={"name": pyre_name})
            data = res.json()
            if data.get("success"):
                flash(f"🔥 장작더미 {pyre_name}이 추가되었습니다 (ID: {data.get('channel_id')})", "success")
            else:
                flash(f"❄️ 불씨가 꺼졌습니다: {data.get('reason')}", "error")

    return redirect(url_for("kindle_page"))


@app.route("/kindle/delete/ember/<int:ember_id>")
def kindle_delete_ember(ember_id):
    db = get_db_connection()
    try:
        with db.cursor() as cursor:
            cursor.execute("DELETE FROM tracked_users WHERE user_id = %s", (ember_id,))
    finally:
        db.close()
    return redirect(url_for("kindle_page"))


@app.route("/kindle/delete/pyre/<int:pyre_id>")
def kindle_delete_pyre(pyre_id):
    db = get_db_connection()
    try:
        with db.cursor() as cursor:
            cursor.execute("UPDATE tracked_channels SET enabled = FALSE WHERE channel_id = %s", (pyre_id,))
    finally:
        db.close()
    return redirect(url_for("kindle_page"))


@app.route("/scars")
def view_scars():
    """Display recorded scars with access control."""
    viewer_name = request.args.get("viewer", "Unknown")
    roles_param = request.args.get("roles", "")
    member_roles = [r.strip() for r in roles_param.split(",") if r.strip()]
    has_access, show_reporter = check_access_and_report_visibility(member_roles)
    if not has_access:
        return "<h3>열람 권한이 없습니다.</h3>"

    db = get_db_connection()
    notes = []
    try:
        with db.cursor() as cursor:
            cursor.execute(
                """
                SELECT target_username, content, added_by_name
                FROM scar_notes
                ORDER BY id DESC
                """
            )
            for row in cursor.fetchall():
                notes.append(
                    {
                        "target_name": row[0],
                        "description": row[1],
                        "added_by_name": row[2],
                    }
                )
    finally:
        db.close()

    return render_template(
        "scars.html",
        notes=notes,
        viewer_name=viewer_name,
        show_reporter=show_reporter,
    )


if __name__ == "__main__":
    app.run(debug=True)
