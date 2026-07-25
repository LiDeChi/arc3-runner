from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
from statistics import median
import json

from arc3math.agent import run_episode
from arc3math.arena.loop import run_to_jsonl
from arc3math.engine import load_game


def main() -> None:
    parser = ArgumentParser()
    parser.add_argument("--game", help="GameSpec JSON path")
    parser.add_argument("--out", help="Write JSONL event stream to this path")
    parser.add_argument("--episodes", type=int, default=5)
    parser.add_argument("--source", choices=["handwritten", "adversarial", "official"], default="handwritten")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--game-id", help="Official ARC-AGI-3 game_id, e.g. ls20-016295f7601e")
    parser.add_argument("--card-id", help="Existing official ARC scorecard card_id")
    parser.add_argument("--max-steps", type=int, default=10, help="Max actions per official episode")
    parser.add_argument("--base-url", help="Official ARC API base URL")
    parser.add_argument("--close-scorecard", action="store_true", help="Close auto-opened official scorecard at the end")
    args = parser.parse_args()

    if args.game:
        game = load_game(args.game)
        trace = run_episode(game, episode_id="cli-episode")
        events = trace.events
        if args.out:
            with open(args.out, "w", encoding="utf-8") as fh:
                for event in events:
                    fh.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
        else:
            for event in events:
                print(json.dumps(event, ensure_ascii=False, sort_keys=True))
        print(json.dumps(trace.summary(), ensure_ascii=False, sort_keys=True))
        return

    config = {
        "episodes": args.episodes,
        "source": args.source,
        "seed": args.seed,
        "game_id": args.game_id,
        "card_id": args.card_id,
        "max_steps": args.max_steps,
        "base_url": args.base_url,
        "official": {"close_scorecard": args.close_scorecard},
    }
    events = run_to_jsonl(config, args.out)
    ends = [e["payload"] for e in events if e["type"] == "episode_end"]
    summary = {
        "episodes": len(ends),
        "wins": sum(1 for e in ends if e.get("result") == "win"),
        "overconf_p50": median([e.get("overconf", 0.0) for e in ends]) if ends else 0.0,
    }
    if args.source == "adversarial" and len(ends) >= 60:
        first = [e.get("overconf", 0.0) for e in ends[:30]]
        last = [e.get("overconf", 0.0) for e in ends[-30:]]
        summary["first30_overconf_p50"] = median(first)
        summary["last30_overconf_p50"] = median(last)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
