from arc3math.arena.db import Database
from arc3math.arena.official import run_official_arena
from arc3math.engine.remote_adapter import ArcSnapshot, RemoteArcClient, RemoteArcEnv, parse_arc_action


def snapshot(action_id=0, state="NOT_FINISHED", value=1):
    return ArcSnapshot.from_json(
        {
            "game_id": "ls20-016295f7601e",
            "guid": "guid-1",
            "frame": [[[value for _ in range(4)] for _ in range(4)]],
            "state": state,
            "levels_completed": 0 if state != "WIN" else 1,
            "win_levels": 2,
            "action_input": {"id": action_id},
            "available_actions": [1, 2, 3, 4],
        }
    )


class FakeClient:
    def __init__(self):
        self.actions = []
        self.reset_calls = []

    def list_games(self):
        return [{"game_id": "ls20-016295f7601e", "title": "LS20"}]

    def open_scorecard(self, **kwargs):
        return "card-1"

    def close_scorecard(self, card_id):
        return {"card_id": card_id, "score": 0}

    def reset(self, game_id, card_id, guid=None):
        self.reset_calls.append((game_id, card_id, guid))
        return snapshot(0, value=1)

    def action(self, game_id, guid, action_id, **kwargs):
        self.actions.append((game_id, guid, action_id, kwargs))
        state = "WIN" if len(self.actions) >= 2 else "NOT_FINISHED"
        return snapshot(action_id, state=state, value=action_id + 1)


def test_parse_arc_action_aliases():
    assert parse_arc_action("ACTION1") == 1
    assert parse_arc_action("A4") == 4
    assert parse_arc_action(7) == 7


def test_remote_env_reset_and_step():
    fake = FakeClient()
    env = RemoteArcEnv("ls20-016295f7601e", "card-1", client=fake)
    obs = env.reset()
    assert obs["guid"] == "guid-1"
    assert env.action_space() == ["ACTION1", "ACTION2", "ACTION3", "ACTION4"]
    obs = env.step("ACTION2")
    assert obs["grid"][0][0] == 3
    assert fake.actions[0][2] == 2


def test_official_arena_persists_real_frame_events():
    db = Database()
    fake = FakeClient()
    result = run_official_arena(
        {"episodes": 1, "game_source": "official", "game_id": "ls20-016295f7601e", "card_id": "card-1", "max_steps": 3},
        db=db,
        client=fake,
    )
    assert result["game_id"] == "ls20-016295f7601e"
    assert result["episodes"][0]["result"] == "win"
    episodes = db.list_episodes(result["run_id"])
    events = db.episode_events(episodes[0]["id"])
    assert events[0]["type"] == "episode_start"
    assert events[0]["payload"]["official"] is True
    observations = [event for event in events if event["type"] == "observation"]
    assert observations[0]["payload"]["grid"][0][0] == 1
    assert observations[-1]["payload"]["official_state"] == "WIN"
