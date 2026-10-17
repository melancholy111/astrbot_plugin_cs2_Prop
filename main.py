from __future__ import annotations

import asyncio
import json
import random
from pathlib import Path

import astrbot.api.message_components as Comp
from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, MessageChain, filter
from astrbot.api.star import Context, Star

MAP_ALIASES = {
    "mirage": {"mirage", "荒漠迷城", "米垃圾"},
    "dust2": {"dust2", "dust", "炙热沙城", "沙二"},
    "inferno": {"inferno", "炼狱小镇", "小镇"},
    "nuke": {"nuke", "核子危机"},
    "anubis": {"anubis", "阿努比斯"},
    "ancient": {"ancient", "远古遗迹", "遗迹"},
}


class Main(Star):
    def __init__(self, context: Context, config: AstrBotConfig | None = None):
        super().__init__(context)
        self.config = config or {}
        self._subscriptions: dict[str, str | None] = {}
        self._job_ids: list[str] = []
        self._lock = asyncio.Lock()

        data_path = Path(__file__).resolve().parent / "lineups.json"
        try:
            payload = json.loads(data_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.exception("Failed to load lineups.json from %s", data_path)
            payload = {}
        maps = payload.get("maps", {})
        self._maps: dict = maps if isinstance(maps, dict) else {}

    async def initialize(self) -> None:
        """Load subscriptions and register the daily push jobs."""
        raw = await self.get_kv_data("subscriptions", {})
        subscriptions = raw if isinstance(raw, dict) else {}
        normalized: dict[str, dict] = {}
        for umo, value in subscriptions.items():
            if isinstance(value, dict):
                normalized[umo] = {
                    "map": value.get("map"),
                    "bot_id": value.get("bot_id") or "",
                }
            else:
                normalized[umo] = {"map": value, "bot_id": ""}
        self._subscriptions = normalized
        await self._schedule_jobs()

    async def terminate(self) -> None:
        """Remove cron jobs created by this plugin instance."""
        await self._clear_jobs()

    async def _schedule_jobs(self) -> None:
        """Create one cron job per configured daily send time."""
        await self._clear_jobs()

        raw_times = self.config.get("send_times", ["12:00"])
        if isinstance(raw_times, str):
            raw_times = [raw_times]
        if not isinstance(raw_times, list):
            raw_times = ["12:00"]

        send_times: list[str] = []
        for item in raw_times:
            label = str(item).strip()
            try:
                hour_text, minute_text = label.split(":", 1)
                hour = int(hour_text)
                minute = int(minute_text)
                if not (0 <= hour <= 23 and 0 <= minute <= 59):
                    raise ValueError
                send_times.append(f"{hour:02d}:{minute:02d}")
            except (TypeError, ValueError):
                logger.warning("Ignoring invalid daily send time: %s", item)

        if not send_times:
            send_times = ["12:00"]
        send_times = sorted(set(send_times))

        timezone = str(self.config.get("timezone") or "Asia/Shanghai")
        for time_label in send_times:
            hour, minute = time_label.split(":")
            cron_expression = f"{minute} {hour} * * *"
            try:
                job = await self.context.cron_manager.add_basic_job(
                    name=f"cs2_prop_daily_{time_label.replace(':', '')}",
                    cron_expression=cron_expression,
                    handler=self._send_daily,
                    description=f"CS2 daily utility push at {time_label}",
                    timezone=timezone,
                    payload={"time_label": time_label},
                    enabled=True,
                    persistent=False,
                )
                self._job_ids.append(job.job_id)
                logger.info(
                    "Scheduled CS2 daily utility push at %s (%s).",
                    time_label,
                    timezone,
                )
            except Exception:
                logger.exception(
                    "Failed to schedule CS2 daily utility push at %s",
                    time_label,
                )

    async def _clear_jobs(self) -> None:
        """Remove all cron jobs tracked by this plugin instance."""
        for job_id in self._job_ids:
            try:
                await self.context.cron_manager.delete_job(job_id)
            except Exception:
                logger.warning("Failed to remove cron job %s", job_id)
        self._job_ids.clear()

    async def _send_daily(self, time_label: str) -> None:
        """Push one utility lineup to every subscribed session."""
        subscriptions = dict(self._subscriptions)
        if not subscriptions:
            logger.info(
                "No subscribed sessions for the %s CS2 utility push.",
                time_label,
            )
            return

        for umo, state in subscriptions.items():
            map_key = state.get("map") if isinstance(state, dict) else state
            item = self._pick_lineup(map_key)
            if item is None:
                logger.warning("No lineup data available for session %s.", umo)
                continue
            text_chain = MessageChain().message(self._build_lineup_text(item))
            video_chain = self._build_lineup_video(item)
            try:
                text_ok = await self.context.send_message(umo, text_chain)
                if not text_ok:
                    logger.warning(
                        "Failed to deliver CS2 utility push to %s.",
                        umo,
                    )
                if video_chain.chain:
                    await self.context.send_message(umo, video_chain)
            except Exception:
                logger.exception(
                    "Failed to deliver CS2 utility push to %s.",
                    umo,
                )

    def _pick_lineup(self, map_key: str | None) -> dict | None:
        """Pick a lineup for the requested map, or a random map."""
        if not self._maps:
            return None

        chosen_key = (
            map_key if map_key in self._maps else random.choice(list(self._maps))
        )
        map_data = self._maps.get(chosen_key)
        if not isinstance(map_data, dict):
            return None
        lineups = map_data.get("lineups", [])
        if not isinstance(lineups, list) or not lineups:
            return None
        lineup = random.choice(lineups)
        if not isinstance(lineup, dict):
            return None
        return {
            "map_key": chosen_key,
            "map_name": map_data.get("name") or chosen_key,
            "lineup": lineup,
        }

    def _build_lineup_text(self, item: dict) -> str:
        """Build the text message for a lineup."""
        lineup = item["lineup"]
        side_label = {"t": "T阵营", "ct": "CT阵营"}.get(
            str(lineup.get("side", "t")).lower(),
            "通用",
        )
        return (
            "【CS2实用道具】\n"
            f"{item['map_name']}{side_label}{lineup.get('title', '')}\n"
            f"投掷方式：{lineup.get('throw', '')}\n"
            f"说明：{lineup.get('desc', '')}"
        )

    def _build_lineup_video(self, item: dict) -> MessageChain:
        """Build the teaching video message for a lineup."""
        chain = MessageChain()
        video = item["lineup"].get("video", "")
        if video:
            chain.chain.append(Comp.Video.fromURL(video))
        return chain

    def _resolve_map(self, raw: str) -> str | None:
        """Resolve a user-provided map name or alias."""
        key = raw.strip().lower()
        if key in {"random", "随机"}:
            return "random"
        for map_key, aliases in MAP_ALIASES.items():
            if key in aliases:
                return map_key
        return None

    def _map_display_name(self, map_key: str | None) -> str:
        """Return the display name for a map key."""
        if map_key is None or map_key == "random":
            return "随机"
        map_data = self._maps.get(map_key)
        if isinstance(map_data, dict) and map_data.get("name"):
            return str(map_data["name"])
        return map_key

    def _list_maps(self) -> list[str]:
        """Return map keys that contain at least one lineup."""
        return [
            key
            for key, data in self._maps.items()
            if isinstance(data, dict) and data.get("lineups")
        ]

    async def _persist_subscriptions(self) -> None:
        """Persist the current subscription table to the plugin KV store."""
        await self.put_kv_data("subscriptions", dict(self._subscriptions))

    @filter.command("subscribe", alias={"订阅", "每日道具"})
    async def subscribe(self, event: AstrMessageEvent):
        """订阅本会话的每日 CS2 道具推送"""
        async with self._lock:
            current = self._subscriptions.get(event.unified_msg_origin, {})
            self._subscriptions[event.unified_msg_origin] = {
                "map": current.get("map") or None,
                "bot_id": event.get_self_id() or "",
            }
            await self._persist_subscriptions()
        yield event.plain_result(
            "已开启每日 CS2 道具推送，当前为随机地图。发送 /map 地图名 可切换地图。"
        )

    @filter.command("unsubscribe", alias={"退订", "取消订阅"})
    async def unsubscribe(self, event: AstrMessageEvent):
        """取消本会话的每日 CS2 道具推送"""
        async with self._lock:
            existed = event.unified_msg_origin in self._subscriptions
            self._subscriptions.pop(event.unified_msg_origin, None)
            await self._persist_subscriptions()
        if existed:
            yield event.plain_result("已关闭本会话的每日 CS2 道具推送。")
        else:
            yield event.plain_result("本会话尚未订阅，无需取消。")

    @filter.command("map", alias={"地图"})
    async def map_cmd(self, event: AstrMessageEvent, map_name: str = None):
        """查看或切换本会话的每日道具地图"""
        if not map_name:
            state = self._subscriptions.get(event.unified_msg_origin)
            current_map = state.get("map") if isinstance(state, dict) else state
            current = self._map_display_name(current_map)
            available = "、".join(
                self._map_display_name(key) for key in self._list_maps()
            )
            yield event.plain_result(
                f"当前地图：{current}\n可选地图：{available}、随机"
            )
            return

        resolved = self._resolve_map(map_name)
        if resolved is None:
            available = "、".join(
                self._map_display_name(key) for key in self._list_maps()
            )
            yield event.plain_result(
                f"没有找到地图 {map_name}。可选：{available}、随机"
            )
            return

        async with self._lock:
            self._subscriptions[event.unified_msg_origin] = (
                {
                    "map": None if resolved == "random" else resolved,
                    "bot_id": event.get_self_id() or "",
                }
            )
            await self._persist_subscriptions()
        yield event.plain_result(
            f"本会话每日道具地图已切换为：{self._map_display_name(resolved)}"
        )

    @filter.command("nade", alias={"道具", "学道具"})
    async def nade(self, event: AstrMessageEvent):
        """立即学习一个 CS2 实用道具"""
        state = self._subscriptions.get(event.unified_msg_origin)
        map_key = state.get("map") if isinstance(state, dict) else state
        item = self._pick_lineup(map_key)
        if item is None:
            yield event.plain_result("暂无可用的道具数据，请稍后再试。")
            return
        yield event.plain_result(self._build_lineup_text(item))
        video_chain = self._build_lineup_video(item)
        if video_chain.chain:
            yield event.chain_result(video_chain.chain)
