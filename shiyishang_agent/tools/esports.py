from __future__ import annotations

import urllib.parse
from datetime import datetime, timezone
from typing import Any

from .common import get_json


ENDPOINT = "https://match-api.hupu.com/1/8.2.10/matchallapi/bff/standard/getScheduleListByTagForH5"
SOURCE_NAME = "hupu_lol_schedule"
STATUS_MAP = {
    "COMPLETED": "completed",
    "INPROGRESS": "live",
    "NOTSTARTED": "upcoming",
}
VALID_STATUSES = {"completed", "live", "upcoming", "all"}
VALID_RESULTS = {"win", "loss", "draw", "all"}
VALID_SORTS = {"newest", "oldest"}


def _walk(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _integer(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _same_team(actual: Any, requested: str) -> bool:
    return bool(actual) and str(actual).strip().casefold() == requested.strip().casefold()


def _contains(actual: Any, requested: str) -> bool:
    return requested.casefold() in str(actual or "").casefold()


def _utc_time(timestamp_ms: Any) -> str | None:
    timestamp = _integer(timestamp_ms)
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _normalize_team(member: dict[str, Any], include_team_meta: bool) -> dict[str, Any]:
    team = {
        "name": member.get("memberName"),
        "score": _integer(member.get("memberBaseScore")),
    }
    if include_team_meta:
        team.update({
            "id": member.get("memberId"),
            "logo": member.get("memberLogo"),
            "extra_score": member.get("memberExtraScore"),
            "big_score": member.get("memberBigScore"),
            "type": member.get("memberType"),
            "description": member.get("memberDesc"),
        })
    return team


def _winner(teams: list[dict[str, Any]], winner_id: Any, completed: bool) -> dict[str, Any] | None:
    if winner_id not in (None, ""):
        official = next((team for team in teams if str(team.get("id")) == str(winner_id)), None)
        if official:
            return {"id": official.get("id"), "name": official.get("name"), "method": "official"}
    if completed and len(teams) == 2:
        left, right = teams
        if left["score"] is not None and right["score"] is not None and left["score"] != right["score"]:
            derived = left if left["score"] > right["score"] else right
            return {"id": derived.get("id"), "name": derived.get("name"), "method": "score"}
    return None


def _team_result(teams: list[dict[str, Any]], winner: dict[str, Any] | None, requested_team: str, completed: bool) -> str | None:
    if not requested_team or not completed:
        return None
    selected = next((team for team in teams if _same_team(team.get("name"), requested_team)), None)
    if not selected:
        return None
    if winner:
        return "win" if _same_team(winner.get("name"), requested_team) else "loss"
    if len(teams) == 2 and teams[0]["score"] is not None and teams[0]["score"] == teams[1]["score"]:
        return "draw"
    return None


def _normalize_match(item: dict[str, Any], requested_team: str, include_team_meta: bool, include_live_link: bool, include_details: bool) -> dict[str, Any]:
    raw_status = item.get("matchStatus")
    status = STATUS_MAP.get(str(raw_status), "unknown")
    against = item.get("againstInfo") or {}
    teams = [_normalize_team(member, include_team_meta) for member in against.get("memberInfos") or []]
    winner = _winner(teams, against.get("winnerMemberId"), status == "completed")
    normalized: dict[str, Any] = {
        "id": item.get("matchId"),
        "unique_key": item.get("uniqueKey"),
        "business_type": item.get("businessType"),
        "sub_business_type": item.get("subMatchBusinessType"),
        "match_type": item.get("matchType"),
        "event": item.get("matchIntroduction"),
        "stage": item.get("matchName"),
        "description": item.get("matchDesc"),
        "status": status,
        "status_code": raw_status,
        "status_text": item.get("matchStatusDesc"),
        "start_date": item.get("matchStartDate"),
        "start_timestamp_ms": _integer(item.get("matchStartTimeStamp")),
        "start_time_utc": _utc_time(item.get("matchStartTimeStamp")),
        "teams": teams,
        "winner": winner,
        "result_for_team": _team_result(teams, winner, requested_team, status == "completed"),
        "rating_count_text": item.get("scoreCountText"),
    }
    if include_live_link:
        normalized["live_room_link"] = item.get("liveRoomLink")
        normalized["extra_photo_link"] = item.get("extraPhotoLink")
        normalized["live_sources"] = item.get("liveSourceInfos") or []
    if include_details:
        normalized.update({
            "mid_game_stage": item.get("midGameStageInfo"),
            "score_item": item.get("scoreItemInfo"),
            "custom_description": item.get("customDescInfo"),
            "extra_info": item.get("extraInfo"),
            "subscription": item.get("subscribeInfo"),
            "score_item_key": item.get("scoreItemKey"),
            "source_last_request_timestamp_ms": _integer(item.get("lastReqTimeStamp")),
        })
    return normalized


def _legacy_status(scope: str | None, status: str | None) -> str:
    if status:
        return status
    return {"recent": "completed", "upcoming": "upcoming", "all": "all"}.get(scope or "recent", "invalid")


def get_lol_schedule(
    team: str = "",
    opponent: str = "",
    event: str = "",
    stage: str = "",
    date: str = "",
    date_from: str = "",
    date_to: str = "",
    status: str | None = None,
    result: str = "all",
    sort: str | None = None,
    limit: int = 10,
    include_live_link: bool = False,
    include_team_meta: bool = True,
    include_details: bool = False,
    scope: str | None = None,
) -> dict[str, Any]:
    """Query and normalize the Hupu League of Legends schedule feed.

    ``scope`` remains supported for older callers. New callers should use
    ``status`` with completed, live, upcoming, or all.
    """
    selected_status = _legacy_status(scope, status)
    selected_sort = sort or ("newest" if selected_status == "completed" else "oldest")
    if selected_status not in VALID_STATUSES:
        return {"ok": False, "error": "status must be completed, live, upcoming, or all"}
    if result not in VALID_RESULTS:
        return {"ok": False, "error": "result must be win, loss, draw, or all"}
    if selected_sort not in VALID_SORTS:
        return {"ok": False, "error": "sort must be newest or oldest"}
    if result != "all" and not team:
        return {"ok": False, "error": "result filtering requires team"}
    try:
        selected_limit = max(1, min(int(limit), 100))
    except (TypeError, ValueError):
        return {"ok": False, "error": "limit must be an integer"}

    query = urllib.parse.urlencode({
        "businessType": "common",
        "datasource": "navigation",
        "scheduleName": "英雄联盟赛事",
        "businessId": "lol",
        "tab": 1,
    })
    retrieved_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    data = get_json(f"{ENDPOINT}?{query}", headers={"Referer": "https://offline-download.hupu.com/"})
    if not isinstance(data, dict) or not data.get("success"):
        return {
            "ok": False,
            "error": data.get("errorMsg") or data.get("msg") or "data source returned an unsuccessful response" if isinstance(data, dict) else "invalid data source response",
            "source": SOURCE_NAME,
        }

    raw_matches = [item for item in _walk(data.get("result")) if "againstInfo" in item and "matchStartDate" in item]
    feed_dates = sorted(str(item.get("matchStartDate")) for item in raw_matches if item.get("matchStartDate"))
    feed_status_counts = {"completed": 0, "live": 0, "upcoming": 0, "unknown": 0}
    for item in raw_matches:
        feed_status_counts[STATUS_MAP.get(str(item.get("matchStatus")), "unknown")] += 1

    matches: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw_matches:
        identity = str(item.get("uniqueKey") or item.get("matchId"))
        if not identity or identity in seen:
            continue
        normalized = _normalize_match(item, team, include_team_meta, include_live_link, include_details)
        team_names = [entry.get("name") for entry in normalized["teams"]]
        if team and not any(_same_team(name, team) for name in team_names):
            continue
        if opponent:
            opponents = [name for name in team_names if not team or not _same_team(name, team)]
            if not any(_same_team(name, opponent) for name in opponents):
                continue
        if event and not _contains(normalized["event"], event):
            continue
        if stage and not _contains(normalized["stage"], stage):
            continue
        start_date = normalized["start_date"] or ""
        if date and start_date != date:
            continue
        if date_from and start_date < date_from:
            continue
        if date_to and start_date > date_to:
            continue
        if selected_status != "all" and normalized["status"] != selected_status:
            continue
        if result != "all" and normalized["result_for_team"] != result:
            continue
        seen.add(identity)
        matches.append(normalized)

    matches.sort(key=lambda match: (match.get("start_timestamp_ms") or 0, match.get("id") or ""), reverse=selected_sort == "newest")
    available_dates = sorted(match["start_date"] for match in matches if match.get("start_date"))
    total_matched = len(matches)
    matches = matches[:selected_limit]
    result_data = data.get("result") or {}
    return {
        "ok": True,
        "source": {
            "name": SOURCE_NAME,
            "endpoint": ENDPOINT,
            "retrieved_at": retrieved_at,
            "anchor_match_id": result_data.get("anchorMatchId") if isinstance(result_data, dict) else None,
            "trace_id": data.get("traceId"),
            "host_name": data.get("hostName"),
            "response_status": data.get("status"),
            "error_code": data.get("errorCode"),
            "message": data.get("msg"),
            "feed": {
                "total_matches": len(raw_matches),
                "coverage": {"from": feed_dates[0] if feed_dates else None, "to": feed_dates[-1] if feed_dates else None},
                "status_counts": feed_status_counts,
            },
        },
        "query": {
            "team": team or None,
            "opponent": opponent or None,
            "event": event or None,
            "stage": stage or None,
            "date": date or None,
            "date_from": date_from or None,
            "date_to": date_to or None,
            "status": selected_status,
            "result": result,
            "sort": selected_sort,
            "limit": selected_limit,
        },
        "total_matched": total_matched,
        "returned": len(matches),
        "coverage": {"from": available_dates[0] if available_dates else None, "to": available_dates[-1] if available_dates else None},
        "matches": matches,
    }
