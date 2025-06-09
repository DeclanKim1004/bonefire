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
import time
import jwt
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
logger = logging.getLogger("bonefire_logger")

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = json.load(f)

DISCORD_TOKEN = config["token"]
DB_CONFIG = config.get("database")
GUILD_ID = config.get("guild_id")
DM_TARGET_ID = 358637116290367491
HASTATI_ROLE_NAME = "━━♔⊱༻ 하스타티 ༺⊰♔━━"
LEGATUS_ROLE_NAME = "✧˖*°࿐.*.｡ ⚔️레가투스⚔️.*.✧˖*°࿐"
JWT_SECRET = config.get("jwt_secret", "change_me")

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

def is_hastati(roles: list[str]) -> bool:
    return HASTATI_ROLE_NAME in roles

def is_legatus(roles: list[str]) -> bool:
    return LEGATUS_ROLE_NAME in roles

def has_scar_access(roles: list[str]) -> bool:
    return any(
        r in roles
        for r in [
            HASTATI_ROLE_NAME,
            "☽☆꧁༒🌞 태양신 🌞༒꧂☆☾",
            "۞☆꧁༒☬ 세계수 ☬༒꧂☆۞",
            "[뉴비관리팀장]",
            "✧˖*°.*.｡✯마구스 팀장✯.*.✧˖*°",
        ]
    )

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

def create_signed_link(member: discord.Member) -> str | None:
    """Return a signed /scars link for the given member."""
    url = get_current_url()
    if not url:
        return None
    payload = {
        "uid": str(member.id),
        "exp": int(time.time()) + 300,
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
    return f"{url}/scars?token={token}"

def add_scar_note(target_user_id: str, target_username: str, content: str, added_by_id: str, added_by_name: str):
    """Insert a scar note about a user into the database."""
    query_db(
        """
        INSERT INTO scar_notes (target_user_id, target_username, added_by_id, added_by_name, content)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (target_user_id, target_username, added_by_id, added_by_name, content),
    )

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


@app.post("/notes")
async def add_note(request: Request):
    data = await request.json()
    required = [
        "target_user_id",
        "target_username",
        "content",
        "added_by_id",
        "added_by_name",
    ]
    if not all(key in data for key in required):
        return {"success": False, "reason": "missing_field"}
    add_scar_note(
        data["target_user_id"],
        data["target_username"],
        data["content"],
        data["added_by_id"],
        data["added_by_name"],
    )
    return {"success": True}


@app.get("/member_info/{user_id}")
async def member_info(user_id: int):
    """Return display name and role list for a Discord member."""
    if bot.guild is None:
        return {"success": False, "reason": "Bot not ready"}
    member = bot.guild.get_member(user_id)
    if member is None:
        try:
            member = await bot.fetch_member(user_id)
        except Exception:
            return {"success": False, "reason": "not_found"}

    return {
        "success": True,
        "display_name": member.display_name,
        "roles": [r.name for r in member.roles],
    }

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
        @app_commands.command(name="bonefire", description="현재 화톳불 링크를 확인합니다.")
        @app_commands.guild_only()
        async def bonefire_command(interaction: discord.Interaction):
            member = interaction.guild.get_member(interaction.user.id)
            if not member or not any(
                r.name in [
                    LEGATUS_ROLE_NAME,
                    "☽☆꧁༒🌞 태양신 🌞༒꧂☆☾",
                    "۞☆꧁༒☬ 세계수 ☬༒꧂☆۞",
                    "[뉴비관리팀장]",
                    "✧˖*°.*.｡✯마구스 팀장✯.*.✧˖*°",
                ]
                for r in member.roles
            ):
                await interaction.response.send_message(
                    f"❌ {LEGATUS_ROLE_NAME} 이상만 가능합니다.", ephemeral=True
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

        @app_commands.command(name="scar_the_ember", description="대상 유저에게 특이사항을 새깁니다")
        @app_commands.describe(target_user="기록 대상", note="내용")
        @app_commands.guild_only()
        async def scar_the_ember(
            interaction: discord.Interaction,
            target_user: discord.Member,
            note: str,
        ):
            member = interaction.guild.get_member(interaction.user.id)
            role_names = [r.name for r in member.roles]
            if not is_hastati(role_names):
                await interaction.response.send_message(
                    f"이 서약은 {HASTATI_ROLE_NAME}에게만 허락되어 있습니다.",
                    ephemeral=True,
                )
                timestamp = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
                dm_content = (
                    "🚫 /scar_the_ember 명령 실패 시도 감지\n\n"
                    f"🧑 사용자: {member.name} (ID: {member.id})\n"
                    f"📝 입력: /scar_the_ember @{target_user.display_name} {note}\n"
                    f"🕒 시각: {timestamp} (KST)\n"
                    f"📛 사유: {HASTATI_ROLE_NAME} 역할이 아님"
                )
                target = self.get_user(DM_TARGET_ID) or await self.fetch_user(DM_TARGET_ID)
                if target:
                    try:
                        await target.send(dm_content)
                    except Exception as e:
                        logger.error(f"/scar_the_ember DM 전송 실패: {e}")
                return

            await interaction.response.defer(ephemeral=True)
            add_scar_note(
                str(target_user.id),
                target_user.name,
                note,
                str(member.id),
                member.name,
            )
            await interaction.followup.send("✅ 특이사항이 기록되었습니다.", ephemeral=True)

        @app_commands.command(name="scars", description="특이사항 목록 링크를 받습니다")
        @app_commands.guild_only()
        async def scars_command(interaction: discord.Interaction):
            member = interaction.guild.get_member(interaction.user.id)
            role_names = [r.name for r in member.roles]
            if not has_scar_access(role_names):
                await interaction.response.send_message(
                    "❌ 열람 권한이 없습니다.", ephemeral=True
                )
                return
            link = create_signed_link(member)
            if not link:
                await interaction.response.send_message(
                    "❗ ngrok 링크를 찾을 수 없습니다.",
                    ephemeral=True,
                )
                return
            await interaction.response.send_message(link, ephemeral=True)

        self.tree.add_command(bonefire_command, guild=discord.Object(id=GUILD_ID))
        self.tree.add_command(scar_the_ember, guild=discord.Object(id=GUILD_ID))
        self.tree.add_command(scars_command, guild=discord.Object(id=GUILD_ID))
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

    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.nick != after.nick:
            before_nick = before.nick if before.nick is not None else before.name
            after_nick = after.nick if after.nick is not None else after.name
            msg = f"[닉변] {before_nick} → {after_nick} ({after.id})"
            logger.info(msg)
            target_user = self.get_user(DM_TARGET_ID)
            if target_user is None:
                try:
                    target_user = await self.fetch_user(DM_TARGET_ID)
                except Exception as e:
                    logger.error(f"DM 대상 유저 조회 실패: {e}")
                    target_user = None
            if target_user:
                try:
                    await target_user.send(msg)
                except Exception as e:
                    logger.error(f"닉변 DM 전송 실패: {e}")

# ---------- Run ----------
def run_api():
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    bot = TrackingBot()
    try:
        logger.info("🎯 봇 실행 시작")
        bot.run(DISCORD_TOKEN)
    except Exception as e:
        logger.error(f"❌ 봇 실행 중 오류 발생: {e}")
