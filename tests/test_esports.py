import unittest
from unittest.mock import patch

from shiyishang_agent.tools.esports import get_lol_schedule


def match(date, status, left, left_score, right, right_score, match_id=None, event="Test event", stage="Group"):
    status_text = {"COMPLETED": "已结束", "INPROGRESS": "进行中", "NOTSTARTED": "未开始"}[status]
    left_id, right_id = f"{left}-id", f"{right}-id"
    winner_id = ""
    if status == "COMPLETED" and isinstance(left_score, int) and isinstance(right_score, int) and left_score != right_score:
        winner_id = left_id if left_score > right_score else right_id
    return {
        "businessType": "common_match",
        "subMatchBusinessType": "common_match",
        "matchType": "against",
        "matchId": match_id or f"{date}-{left}-{right}",
        "uniqueKey": f"match:{match_id or date + '-' + left + '-' + right}",
        "matchStartDate": date,
        "matchStartTimeStamp": str(int(date.replace("-", "")) * 1000),
        "matchStatus": status,
        "matchStatusDesc": status_text,
        "matchIntroduction": event,
        "matchName": stage,
        "matchDesc": "description",
        "scoreCountText": "100人评分" if status == "COMPLETED" else None,
        "liveRoomLink": "huputiyu://live",
        "extraPhotoLink": "https://image.test/poster.png",
        "liveSourceInfos": [{"name": "source"}],
        "againstInfo": {"winnerMemberId": winner_id, "memberInfos": [
            {"memberName": left, "memberBaseScore": str(left_score), "memberId": left_id, "memberLogo": f"https://logo/{left}.png"},
            {"memberName": right, "memberBaseScore": str(right_score), "memberId": right_id, "memberLogo": f"https://logo/{right}.png"},
        ]},
        "subscribeInfo": {"subScribeTitle": f"{left} vs {right}"},
        "scoreItemKey": {"outBizNo": "1"},
        "lastReqTimeStamp": 123,
    }


def payload(*matches, success=True):
    return {"success": success, "errorMsg": "failed" if not success else None, "traceId": "trace", "hostName": "host", "status": 200, "errorCode": 0, "msg": "ok", "result": {"anchorMatchId": "anchor", "dayGameData": list(matches)}}


class EsportsTests(unittest.TestCase):
    @patch("shiyishang_agent.tools.esports.get_json")
    def test_completed_is_sorted_descending_limited_and_uses_official_winner(self, get_json):
        get_json.return_value = payload(
            match("2026-06-01", "COMPLETED", "BLG", 3, "OLD", 0),
            match("2026-07-20", "NOTSTARTED", "BLG", "-", "NEXT", "-"),
            match("2026-07-17", "COMPLETED", "BLG", 1, "DK", 2),
            match("2026-07-16", "COMPLETED", "BLG", 1, "T1", 0),
        )
        result = get_lol_schedule(team="BLG", limit=2)
        self.assertEqual([item["start_date"] for item in result["matches"]], ["2026-07-17", "2026-07-16"])
        self.assertEqual(result["matches"][0]["result_for_team"], "loss")
        self.assertEqual(result["matches"][0]["winner"], {"id": "DK-id", "name": "DK", "method": "official"})
        self.assertEqual(result["total_matched"], 3)
        self.assertEqual(result["source"]["trace_id"], "trace")
        self.assertEqual(result["source"]["feed"]["status_counts"], {"completed": 3, "live": 0, "upcoming": 1, "unknown": 0})

    @patch("shiyishang_agent.tools.esports.get_json")
    def test_upcoming_excludes_live_and_is_ascending(self, get_json):
        get_json.return_value = payload(
            match("2026-07-24", "NOTSTARTED", "EDG", "-", "BLG", "-"),
            match("2026-07-19", "INPROGRESS", "BLG", 1, "GEN", 1),
            match("2026-07-23", "NOTSTARTED", "BLG", "-", "TT", "-"),
        )
        result = get_lol_schedule(team="BLG", status="upcoming")
        self.assertEqual([item["start_date"] for item in result["matches"]], ["2026-07-23", "2026-07-24"])

    @patch("shiyishang_agent.tools.esports.get_json")
    def test_exact_team_opponent_date_result_and_event_filters(self, get_json):
        get_json.return_value = payload(
            match("2026-07-01", "COMPLETED", "AG.AL", 0, "BLG", 3, event="LPL"),
            match("2026-07-02", "COMPLETED", "AL", 2, "BLG", 3, event="LPL"),
            match("2026-07-03", "COMPLETED", "AL", 3, "TES", 0, event="LPL"),
        )
        result = get_lol_schedule(team="AL", opponent="BLG", event="lpl", date_from="2026-07-02", date_to="2026-07-03", result="loss")
        self.assertEqual(result["returned"], 1)
        self.assertEqual(result["matches"][0]["start_date"], "2026-07-02")

    @patch("shiyishang_agent.tools.esports.get_json")
    def test_optional_full_details(self, get_json):
        get_json.return_value = payload(match("2026-07-19", "INPROGRESS", "T1", 1, "GEN", 1))
        result = get_lol_schedule(status="live", include_live_link=True, include_details=True)
        item = result["matches"][0]
        self.assertEqual(item["live_room_link"], "huputiyu://live")
        self.assertEqual(item["subscription"]["subScribeTitle"], "T1 vs GEN")
        self.assertEqual(item["teams"][0]["logo"], "https://logo/T1.png")
        self.assertIsNone(item["winner"])

    @patch("shiyishang_agent.tools.esports.get_json")
    def test_invalid_arguments_and_unsuccessful_source(self, get_json):
        self.assertFalse(get_lol_schedule(status="wrong")["ok"])
        self.assertFalse(get_lol_schedule(result="win")["ok"])
        self.assertFalse(get_lol_schedule(sort="sideways")["ok"])
        get_json.assert_not_called()
        get_json.return_value = payload(success=False)
        self.assertFalse(get_lol_schedule()["ok"])

    @patch("shiyishang_agent.tools.esports.get_json")
    def test_legacy_scope_is_supported(self, get_json):
        get_json.return_value = payload(match("2026-07-23", "NOTSTARTED", "BLG", "-", "TT", "-"))
        result = get_lol_schedule(team="BLG", scope="upcoming")
        self.assertEqual(result["query"]["status"], "upcoming")
        self.assertEqual(result["returned"], 1)


if __name__ == "__main__":
    unittest.main()
