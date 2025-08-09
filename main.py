import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
import os
import datetime
import time
import json
import io

load_dotenv()

schedules = []

next_id = 1  # 다음 스케줄 ID

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=".", intents=intents)


def get_user_schedules(guild_id, user_id):
    """사용자의 스케줄 목록을 가져옵니다"""
    return [schedule for schedule in schedules
            if schedule['server'] == guild_id and schedule['user'] == user_id]


def find_schedule_by_id(schedule_id, guild_id, user_id):
    """ID로 스케줄을 찾습니다 (본인 것만)"""
    for schedule in schedules:
        if (schedule['id'] == schedule_id and
                schedule['server'] == guild_id and
                schedule['user'] == user_id):
            return schedule
    return None


def format_timestamp(timestamp):
    """타임스탬프를 읽기 좋은 형태로 변환합니다"""
    return datetime.datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


def format_interval(seconds):
    """초를 읽기 좋은 형태로 변환합니다"""
    if seconds < 60:
        return f"{seconds}초"
    elif seconds < 3600:
        return f"{seconds // 60}분"
    elif seconds < 86400:
        return f"{seconds // 3600}시간"
    else:
        return f"{seconds // 86400}일"


@bot.tree.command(name="list", description="스케줄 목록을 가져옵니다")
async def list_schedules(interaction: discord.Interaction):
    user_schedules = get_user_schedules(interaction.guild_id, interaction.user.id)

    embed = discord.Embed(
        title="📅 내 스케줄 목록",
        color=0x00ff00,
        timestamp=datetime.datetime.now()
    )
    embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.avatar)

    if not user_schedules:
        embed.description = "등록된 스케줄이 없습니다."
        embed.color = 0x808080
    else:
        for i, schedule in enumerate(user_schedules):
            channel = bot.get_channel(schedule['channel'])
            channel_name = channel.name if channel else f"채널 ID: {schedule['channel']}"

            next_run = schedule['date']
            if schedule['last'] > 0:
                next_run = schedule['last'] + schedule['interval']

            embed.add_field(
                name=f"🔸 스케줄 #{schedule['id']}",
                value=f"**메시지:** {schedule['message']}\n"
                      f"**채널:** #{channel_name}\n"
                      f"**다음 실행:** {format_timestamp(next_run)}\n"
                      f"**반복 간격:** {format_interval(schedule['interval'])}",
                inline=True
            )

    embed.set_footer(text=f"총 {len(user_schedules)}개의 스케줄")
    await interaction.response.send_message(embed=embed)


class ScheduleCreateModal(discord.ui.Modal, title="📅 새 스케줄 생성"):
    def __init__(self, channel: discord.TextChannel):
        super().__init__()
        self.channel = channel

    message = discord.ui.TextInput(
        label="메시지",
        placeholder="전송할 메시지를 입력하세요...",
        max_length=2000,
        style=discord.TextStyle.paragraph
    )

    date = discord.ui.TextInput(
        label="실행 날짜",
        placeholder="YYYY-MM-DD 형식 (예: 2025-12-25)",
        max_length=10,
        min_length=10
    )

    time = discord.ui.TextInput(
        label="실행 시간",
        placeholder="HH:MM 형식 (예: 14:30)",
        max_length=5,
        min_length=4
    )

    interval = discord.ui.TextInput(
        label="반복 간격 (분)",
        placeholder="분 단위로 입력 (예: 60)",
        max_length=4,
        default="60"
    )

    async def on_submit(self, interaction: discord.Interaction):
        global next_id

        try:
            # 날짜 파싱
            date_parts = self.date.value.split('-')
            if len(date_parts) != 3:
                raise ValueError("잘못된 날짜 형식")

            year, month, day = map(int, date_parts)

            # 시간 파싱
            time_parts = self.time.value.split(':')
            if len(time_parts) != 2:
                raise ValueError("잘못된 시간 형식")

            hour, minute = map(int, time_parts)

            # 간격 파싱
            interval_minutes = int(self.interval.value)
            if interval_minutes <= 0:
                raise ValueError("간격은 0보다 커야 합니다")

            # 날짜 유효성 검사
            target_date = datetime.datetime(year, month, day, hour, minute)
            timestamp = int(target_date.timestamp())

            if timestamp < time.time():
                embed = discord.Embed(
                    title="❌ 오류",
                    description="과거 시간으로는 스케줄을 설정할 수 없습니다.",
                    color=0xff0000
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            new_schedule = {
                'id': next_id,
                'server': interaction.guild_id,
                'channel': self.channel.id,
                'message': self.message.value,
                'user': interaction.user.id,
                'date': timestamp,
                'interval': interval_minutes * 60,  # 분을 초로 변환
                'last': 0
            }

            schedules.append(new_schedule)
            next_id += 1

            embed = discord.Embed(
                title="✅ 스케줄 생성 완료",
                color=0x00ff00,
                timestamp=datetime.datetime.now()
            )
            embed.add_field(name="🆔 스케줄 ID", value=f"#{new_schedule['id']}", inline=True)
            embed.add_field(name="💬 메시지",
                            value=self.message.value[:100] + ("..." if len(self.message.value) > 100 else ""),
                            inline=False)
            embed.add_field(name="📺 채널", value=self.channel.mention, inline=True)
            embed.add_field(name="🕐 첫 실행", value=format_timestamp(timestamp), inline=True)
            embed.add_field(name="🔄 반복 간격", value=format_interval(new_schedule['interval']), inline=True)
            embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.avatar)
            embed.set_footer(text="스케줄이 성공적으로 생성되었습니다!")

            await interaction.response.send_message(embed=embed)

        except ValueError as e:
            embed = discord.Embed(
                title="❌ 입력 오류",
                description="올바른 형식으로 입력해주세요:\n"
                            "• **날짜**: YYYY-MM-DD (예: 2025-12-25)\n"
                            "• **시간**: HH:MM (예: 14:30)\n"
                            "• **간격**: 양수 (분 단위)",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            embed = discord.Embed(
                title="❌ 오류",
                description=f"스케줄 생성 중 오류가 발생했습니다: {str(e)}",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        embed = discord.Embed(
            title="❌ 오류",
            description="알 수 없는 오류가 발생했습니다. 다시 시도해주세요.",
            color=0xff0000
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="create", description="새 스케줄을 생성합니다")
async def create_schedule(interaction: discord.Interaction, channel: discord.TextChannel):
    modal = ScheduleCreateModal(channel)
    await interaction.response.send_modal(modal)


@bot.tree.command(name="update", description="스케줄을 수정합니다")
async def update_schedule(
        interaction: discord.Interaction,
        schedule_id: int,
        message: str = None,
        channel: discord.TextChannel = None,
        year: int = None,
        month: int = None,
        day: int = None,
        hour: int = None,
        minute: int = None,
        interval_minutes: int = None
):
    schedule = find_schedule_by_id(schedule_id, interaction.guild_id, interaction.user.id)

    if not schedule:
        embed = discord.Embed(
            title="❌ 오류",
            description=f"스케줄 #{schedule_id}를 찾을 수 없습니다.",
            color=0xff0000
        )
        await interaction.response.send_message(embed=embed)
        return

    # 수정할 내용들
    updates = []

    if message:
        schedule['message'] = message
        updates.append(f"메시지: {message}")

    if channel:
        schedule['channel'] = channel.id
        updates.append(f"채널: {channel.mention}")

    if all(v is not None for v in [year, month, day, hour]):
        try:
            minute = minute or 0
            target_date = datetime.datetime(year, month, day, hour, minute)
            timestamp = int(target_date.timestamp())

            if timestamp < time.time():
                embed = discord.Embed(
                    title="❌ 오류",
                    description="과거 시간으로는 스케줄을 설정할 수 없습니다.",
                    color=0xff0000
                )
                await interaction.response.send_message(embed=embed)
                return

            schedule['date'] = timestamp
            schedule['last'] = 0  # 시간 변경시 last 초기화
            updates.append(f"실행 시간: {format_timestamp(timestamp)}")

        except ValueError:
            embed = discord.Embed(
                title="❌ 오류",
                description="올바르지 않은 날짜/시간입니다.",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed)
            return

    if interval_minutes:
        schedule['interval'] = interval_minutes * 60
        updates.append(f"반복 간격: {format_interval(schedule['interval'])}")

    if not updates:
        embed = discord.Embed(
            title="❌ 오류",
            description="수정할 내용을 입력해주세요.",
            color=0xff0000
        )
        await interaction.response.send_message(embed=embed)
        return

    embed = discord.Embed(
        title="✅ 스케줄 수정 완료",
        color=0x00ff00,
        timestamp=datetime.datetime.now()
    )
    embed.add_field(name="스케줄 ID", value=f"#{schedule_id}", inline=False)
    embed.add_field(name="수정된 내용", value="\n".join(updates), inline=False)
    embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.avatar)

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="delete", description="스케줄을 삭제합니다")
async def delete_schedule(interaction: discord.Interaction, schedule_id: int):
    schedule = find_schedule_by_id(schedule_id, interaction.guild_id, interaction.user.id)

    if not schedule:
        embed = discord.Embed(
            title="❌ 오류",
            description=f"스케줄 #{schedule_id}를 찾을 수 없습니다.",
            color=0xff0000
        )
        await interaction.response.send_message(embed=embed)
        return

    schedules.remove(schedule)

    embed = discord.Embed(
        title="🗑️ 스케줄 삭제 완료",
        color=0xff6b6b,
        timestamp=datetime.datetime.now()
    )
    embed.add_field(name="삭제된 스케줄", value=f"#{schedule_id} - {schedule['message']}", inline=False)
    embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.avatar)

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="info", description="특정 스케줄의 상세 정보를 봅니다")
async def schedule_info(interaction: discord.Interaction, schedule_id: int):
    schedule = find_schedule_by_id(schedule_id, interaction.guild_id, interaction.user.id)

    if not schedule:
        embed = discord.Embed(
            title="❌ 오류",
            description=f"스케줄 #{schedule_id}를 찾을 수 없습니다.",
            color=0xff0000
        )
        await interaction.response.send_message(embed=embed)
        return

    channel = bot.get_channel(schedule['channel'])
    channel_name = channel.name if channel else f"채널 ID: {schedule['channel']}"

    next_run = schedule['date']
    if schedule['last'] > 0:
        next_run = schedule['last'] + schedule['interval']

    embed = discord.Embed(
        title=f"📋 스케줄 #{schedule['id']} 정보",
        color=0x3498db,
        timestamp=datetime.datetime.now()
    )
    embed.add_field(name="💬 메시지", value=schedule['message'], inline=False)
    embed.add_field(name="📺 채널", value=f"#{channel_name}", inline=True)
    embed.add_field(name="🕐 다음 실행", value=format_timestamp(next_run), inline=True)
    embed.add_field(name="🔄 반복 간격", value=format_interval(schedule['interval']), inline=True)
    embed.add_field(name="📅 생성일", value=format_timestamp(schedule['date']), inline=True)

    if schedule['last'] > 0:
        embed.add_field(name="⏰ 마지막 실행", value=format_timestamp(schedule['last']), inline=True)
    else:
        embed.add_field(name="⏰ 마지막 실행", value="아직 실행되지 않음", inline=True)

    embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.avatar)
    embed.set_footer(text=f"스케줄 ID: {schedule['id']}")

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="export", description="내 스케줄 목록을 JSON 파일로 내보냅니다")
async def export_schedules(interaction: discord.Interaction):
    user_schedules = get_user_schedules(interaction.guild_id, interaction.user.id)

    if not user_schedules:
        embed = discord.Embed(
            title="❌ 오류",
            description="내보낼 스케줄이 없습니다.",
            color=0xff0000
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    # 사용자 스케줄을 export용 형태로 변환 (민감한 정보 제외)
    export_data = {
        "export_info": {
            "user_id": interaction.user.id,
            "username": interaction.user.display_name,
            "guild_id": interaction.guild_id,
            "export_date": datetime.datetime.now().isoformat(),
            "total_schedules": len(user_schedules)
        },
        "schedules": []
    }

    for schedule in user_schedules:
        export_schedule = {
            "id": schedule['id'],
            "channel": schedule['channel'],
            "message": schedule['message'],
            "date": schedule['date'],
            "interval": schedule['interval'],
            "last": schedule['last']
        }
        export_data["schedules"].append(export_schedule)

    # JSON 파일 생성
    json_content = json.dumps(export_data, indent=2, ensure_ascii=False)

    # 파일 생성 및 전송
    file = discord.File(
        io.BytesIO(json_content.encode('utf-8')),
        filename=f"schedules_{interaction.user.display_name}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )

    embed = discord.Embed(
        title="📤 스케줄 내보내기 완료",
        color=0x00ff00,
        timestamp=datetime.datetime.now()
    )
    embed.add_field(name="📊 내보낸 스케줄 수", value=f"{len(user_schedules)}개", inline=True)
    embed.add_field(name="📅 내보내기 날짜", value=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), inline=True)
    embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.avatar)
    embed.set_footer(text="JSON 파일을 다운로드하여 백업하세요!")

    await interaction.response.send_message(embed=embed, file=file, ephemeral=True)


class ImportScheduleModal(discord.ui.Modal, title="📥 스케줄 가져오기 옵션"):
    def __init__(self):
        super().__init__()

    json_content = discord.ui.TextInput(
        label="JSON 내용",
        placeholder="JSON 파일의 내용을 여기에 붙여넣으세요...",
        style=discord.TextStyle.paragraph,
        max_length=4000
    )

    overwrite = discord.ui.TextInput(
        label="기존 스케줄 처리",
        placeholder="덮어쓰기: overwrite, 추가: add (기본값: add)",
        max_length=10,
        default="add",
        required=False
    )

    async def on_submit(self, interaction: discord.Interaction):
        global next_id

        try:
            import_data = json.loads(self.json_content.value)

            # JSON 구조 검증
            if "schedules" not in import_data or not isinstance(import_data["schedules"], list):
                raise ValueError("올바르지 않은 JSON 구조입니다.")

            # 기존 스케줄 처리
            if self.overwrite.value.lower() == "overwrite":
                # 사용자의 기존 스케줄 모두 삭제
                global schedules
                schedules = [s for s in schedules
                             if not (s['server'] == interaction.guild_id and s['user'] == interaction.user.id)]

            imported_count = 0
            skipped_count = 0

            for schedule_data in import_data["schedules"]:
                try:
                    # 필수 필드 검증
                    required_fields = ['channel', 'message', 'date', 'interval']
                    if not all(field in schedule_data for field in required_fields):
                        skipped_count += 1
                        continue

                    # 채널 존재 여부 확인
                    channel = bot.get_channel(schedule_data['channel'])
                    if not channel or channel.guild.id != interaction.guild_id:
                        skipped_count += 1
                        continue

                    # 과거 시간 확인
                    schedule_time = schedule_data['date']
                    if schedule_data.get('last', 0) == 0:  # 아직 실행되지 않은 스케줄
                        if schedule_time < time.time():
                            skipped_count += 1
                            continue

                    new_schedule = {
                        'id': next_id,
                        'server': interaction.guild_id,
                        'channel': schedule_data['channel'],
                        'message': schedule_data['message'],
                        'user': interaction.user.id,
                        'date': schedule_data['date'],
                        'interval': schedule_data['interval'],
                        'last': schedule_data.get('last', 0)
                    }

                    schedules.append(new_schedule)
                    next_id += 1
                    imported_count += 1

                except Exception as e:
                    skipped_count += 1
                    continue

            embed = discord.Embed(
                title="📥 스케줄 가져오기 완료",
                color=0x00ff00,
                timestamp=datetime.datetime.now()
            )
            embed.add_field(name="✅ 가져온 스케줄", value=f"{imported_count}개", inline=True)

            if skipped_count > 0:
                embed.add_field(name="⚠️ 건너뛴 스케줄", value=f"{skipped_count}개", inline=True)
                embed.add_field(name="건너뛴 이유",
                                value="• 채널이 존재하지 않음\n• 과거 시간 스케줄\n• 잘못된 데이터",
                                inline=False)

            embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.avatar)
            embed.set_footer(text="가져오기가 완료되었습니다!")

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except json.JSONDecodeError:
            embed = discord.Embed(
                title="❌ JSON 오류",
                description="올바르지 않은 JSON 형식입니다. 파일 내용을 다시 확인해주세요.",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except ValueError as e:
            embed = discord.Embed(
                title="❌ 데이터 오류",
                description=str(e),
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            embed = discord.Embed(
                title="❌ 오류",
                description=f"가져오기 중 오류가 발생했습니다: {str(e)}",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="import", description="JSON 파일에서 스케줄을 가져옵니다")
async def import_schedules(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📥 스케줄 가져오기",
        description="**사용법:**\n"
                    "1. 내보낸 JSON 파일을 텍스트 에디터로 열기\n"
                    "2. 파일 내용 전체를 복사\n"
                    "3. 모달 창에 붙여넣기\n"
                    "4. 가져오기 옵션 선택\n\n"
                    "**옵션:**\n"
                    "• `add`: 기존 스케줄에 추가 (기본값)\n"
                    "• `overwrite`: 기존 스케줄 삭제 후 가져오기",
        color=0x3498db
    )
    embed.set_footer(text="아래 모달을 통해 JSON 내용을 입력하세요")

    modal = ImportScheduleModal()
    await interaction.response.send_modal(modal)


# 스케줄 실행 루프
@tasks.loop(seconds=60)  # 1분마다 확인
async def check_schedules():
    current_time = int(time.time())
    for schedule in schedules:
        should_run = False

        if schedule['last'] == 0:
            # 처음 실행
            if current_time >= schedule['date']:
                should_run = True
        else:
            # 반복 실행
            if current_time >= schedule['last'] + schedule['interval']:
                should_run = True

        if should_run:
            channel = bot.get_channel(schedule['channel'])
            if channel:
                try:
                    await channel.send(schedule['message'])
                    schedule['last'] = current_time
                    print(f"스케줄 #{schedule['id']} 실행됨")
                except Exception as e:
                    print(f"스케줄 #{schedule['id']} 실행 오류: {e}")


@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Logged in as {bot.user.name}")
    check_schedules.start()  # 스케줄 확인 루프 시작


bot.run(os.getenv("TOKEN"))