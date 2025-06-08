import discord
import pymysql
import json
import asyncio
import nest_asyncio
from fastapi import FastAPI, Request
import uvicorn
from threading import Thread
from discord.utils import get
from discord import app_commands
from datetime import datetime, timezone, timedelta
import logging
import queue
import threading
import os

# ---------- Settings and Logging ----------
KST = timezone(timedelta(hours=9))
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("bonfire_logger")

with open("/home/declan/src/config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

DISCORD_TOKEN = config["token"]
DB_CONFIG = config.get("database")
GUILD_ID = config.get("guild_id")

# ---------- Connection Pool ----------
class SimpleConnectionPool:
    def __init__(self, maxsize, **db_config):
        self._pool = queue.Queue(maxsize)
        self._lock = threading.Lock()
        self._db_config = db_config
        for _ in range(maxsize):
            self._pool.put(self._create_connection())

    def _create_connection(self):
        return pymysql.connect(**self._db_config)

    def get(self):
        with self._lock:
            if self._pool.empty():
                return self._create_connection()
            return self._pool.get()

    def put(self, conn):
        with self._lock:
            try:
                self._pool.put_nowait(conn)
            except queue.Full:
                conn.close()

DB_CONFIG.setdefault("autocommit", True)
db_pool = SimpleConnectionPool(maxsize=10, **DB_CONFIG)

def query_db(query, args=None, fetch=False):
    conn = db_pool.get()
    try:
        conn.ping(reconnect=True)
        with conn.cursor() as cursor:
            cursor.execute(query, args or ())
            result = cursor.fetchall() if fetch else None
        conn.commit()
        return result
    except Exception as e:
        logger.error(f"DB Error: {e}")
    finally:
        db_pool.put(conn)

def get_highest_role(member):
    roles = [r for r in member.roles if r.name != "@everyone"]
    return max(roles, key=lambda r: r.position).name if roles else None

def is_tracked_user(user_id):
    result = query_db("SELECT 1 FROM tracked_users WHERE user_id = %s", (user_id,), fetch=True)
    return bool(result)

def is_tracked_channel(channel_id):
    result = query_db("SELECT 1 FROM tracked_channels WHERE channel_id = %s AND enabled = TRUE", (channel_id,), fetch=True)
    return bool(result)

def save_session(user_id, username, channel_id, channel_name, start, end):
    duration_sec = int((end - start).total_seconds())
    if duration_sec < 5:
        return

    existing = query_db("SELECT id FROM voice_sessions WHERE user_id = %s AND start_time = %s", (user_id, start), fetch=True)
    if existing:
        query_db(
            """
            UPDATE voice_sessions
            SET end_time = %s, duration_sec = %s, created_at = %s
            WHERE id = %s
            """,
            (end, duration_sec, end, existing[0][0]),
        )
    else:
        query_db(
            """
            INSERT INTO voice_sessions (user_id, username, channel_id, channel_name, start_time, end_time, duration_sec)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (user_id, username, channel_id, channel_name, start, end, duration_sec),
        )

def get_current_url():
    try:
        with open("ngrok_url.txt", "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return None

# ---------- FastAPI ----------
app = FastAPI()
nest_asyncio.apply()

@app.post("/verify_user")
async def verify_user(request: Request):
    if bot.guild is None:
        return {"success": False, "reason": "Bot not ready"}
    data = await request.json()
    name = data.get("name")
    if not name:
        return {"success": False, "reason": "no_name"}

    member = get(bot.guild.members, name=name) or get(bot.guild.members, nick=name)
    if not member:
        return {"success": False, "reason": "not_found"}

    query_db(
        """
        INSERT INTO tracked_users (user_id, username, nickname, role_name)
        VALUES (%s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE username=VALUES(username), nickname=VALUES(nickname), role_name=VALUES(role_name)
        """,
        (member.id, member.name, member.nick, get_highest_role(member)),
    )

    return {"success": True, "user_id": member.id}

@app.post("/verify_channel")
async def verify_channel(request: Request):
    if bot.guild is None:
        return {"success": False, "reason": "Bot not ready"}
    data = await request.json()
    name = data.get("name")
    if not name:
        return {"success": False, "reason": "no_name"}

    channel = get(bot.guild.voice_channels, name=name)
    if not channel:
        return {"success": False, "reason": "not_found"}

    query_db(
        """
        INSERT INTO tracked_channels (channel_id, name)
        VALUES (%s, %s)
        ON DUPLICATE KEY UPDATE name=VALUES(name), enabled=TRUE
        """,
        (channel.id, channel.name),
    )

    return {"success": True, "channel_id": channel.id}

# ---------- Discord Bot ----------
class TrackingBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.guilds = True
        intents.members = True
        intents.voice_states = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.user_sessions = {}

    async def setup_hook(self):
        @app_commands.command(name="bonfire", description="현재 화톳불 링크를 확인합니다.")
        @app_commands.guild_only()
        async def bonfire_command(interaction: discord.Interaction):
            member = interaction.guild.get_member(interaction.user.id)
            if not member or not any(
                r.name in [
                    "✧˖*°࿐.*.｡ ⚔️레가투스⚔️.*.✧˖*°࿐",
                    "☽☆꧁༒🌞 태양신 🌞༒꧂☆☾",
                    "۞☆꧁༒☬ 세계수 ☬༒꧂☆۞",
                    "[뉴비관리팀장]",
                    "✧˖*°.*.｡✯마구스 팀장✯.*.✧˖*°",
                ]
                for r in member.roles
            ):
                await interaction.response.send_message(
                    "❌ 레가투스 이상만 가능합니다.", ephemeral=True
                )
                return

            url = get_current_url()
            if url:
                msg = (
                    f"🔥 화톳불 링크: {url}\n\n"
                    "⚠️ 처음 접속 시 **\"Visit Site\" 버튼을 한 번 눌러야** 정상 작동합니다."
                )
                await interaction.response.send_message(msg, ephemeral=True)
            else:
                await interaction.response.send_message(
                    "❗ ngrok 링크를 찾을 수 없습니다.", ephemeral=True
                )

        self.tree.add_command(bonfire_command, guild=discord.Object(id=GUILD_ID))
        await self.tree.sync(guild=discord.Object(id=GUILD_ID))

    async def on_ready(self):
        self.guild = discord.utils.get(self.guilds, id=GUILD_ID)
        logger.info(f"🤖 봇 로그인 완료: {self.user} (서버: {self.guild.name})")
        Thread(target=run_api, daemon=True).start()

    async def on_voice_state_update(self, member, before, after):
        now = datetime.now(KST)
        user_id = member.id
        username = member.name

        before_tracked = before.channel and is_tracked_channel(before.channel.id)
        after_tracked = after.channel and is_tracked_channel(after.channel.id)
        tracked_user = is_tracked_user(user_id)

        if before_tracked and tracked_user and (after.channel is None or not after_tracked):
            session = self.user_sessions.get(user_id)
            if session:
                save_session(
                    user_id,
                    username,
                    session["channel_id"],
                    session["channel_name"],
                    session["start"],
                    now,
                )
                logger.info(f"[퇴장] {username} ← {before.channel.name} @ {now}")
                self.user_sessions.pop(user_id, None)

        if after_tracked and tracked_user and (before.channel is None or not before_tracked):
            self.user_sessions[user_id] = {
                "start": now,
                "channel_id": after.channel.id,
                "channel_name": after.channel.name,
            }
            logger.info(f"[입장] {username} → {after.channel.name} @ {now}")

# ---------- Run ----------
def run_api():
    uvicorn.run(app, host="0.0.0.0", port=5000)

if __name__ == "__main__":
    bot = TrackingBot()
    try:
        logger.info("🎯 봇 실행 시작")
        bot.run(DISCORD_TOKEN)
    except Exception as e:
        logger.error(f"❌ 봇 실행 중 오류 발생: {e}")
