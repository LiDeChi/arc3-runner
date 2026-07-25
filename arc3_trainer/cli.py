#!/usr/bin/env python3
"""
ARC3 Adversarial Training Platform — CLI entry point.

Usage:
  python -m arc3_trainer.cli train --rounds 100 --output-dir ./output
  python -m arc3_trainer.cli eval --task task.json
  python -m arc3_trainer.cli eval --dir ./tasks/
  python -m arc3_trainer.cli dashboard
  python -m arc3_trainer.cli export --output solver.py
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def add_train_subparser(subparsers):
    p = subparsers.add_parser("train", help="Run adversarial training")
    p.add_argument("--rounds", type=int, default=100, help="Number of training rounds")
    p.add_argument("--beam-width", type=int, default=50, help="Beam search width")
    p.add_argument("--max-depth", type=int, default=5, help="Max program depth")
    p.add_argument("--output-dir", type=str, default="training_output",
                   help="Output directory for checkpoints")
    p.add_argument("--seed", type=int, default=None, help="Random seed")
    p.add_argument("--resume", action="store_true",
                   help="Resume training from latest checkpoint in output-dir")
    p.add_argument("--official-ratio", type=float, default=0.0,
                   help="Fraction of official ARC tasks vs synthetic (0.0-1.0)")
    p.add_argument("--official-tasks-dir", type=str, default="",
                   help="Directory of official ARC task JSON files")
    p.set_defaults(func=cmd_train)


def add_eval_subparser(subparsers):
    p = subparsers.add_parser("eval", help="Evaluate solver on tasks")
    p.add_argument("--task", type=str, help="Single task JSON file")
    p.add_argument("--dir", type=str, help="Directory of task JSON files")
    p.add_argument("--beam-width", type=int, default=50)
    p.add_argument("--max-depth", type=int, default=5)
    p.set_defaults(func=cmd_eval)


def add_dashboard_subparser(subparsers):
    p = subparsers.add_parser("dashboard", help="Launch web dashboard")
    p.add_argument("--host", type=str, default="127.0.0.1", help="Host to bind")
    p.add_argument("--port", type=int, default=8080, help="Port to bind")
    p.add_argument("--load-dir", type=str, default=None,
                   help="Load historical checkpoint data from this directory for display")
    p.set_defaults(func=cmd_dashboard)


def add_export_subparser(subparsers):
    p = subparsers.add_parser("export", help="Export trained solver")
    p.add_argument("--output", type=str, default="exported_solver.py",
                   help="Output file path")
    p.set_defaults(func=cmd_export)


def cmd_train(args):
    from arc3_trainer.trainer.loop import TrainingLoop, TrainConfig

    # If official ratio set but no dir specified, use demo tasks
    official_tasks_dir = getattr(args, 'official_tasks_dir', '')
    official_ratio = getattr(args, 'official_ratio', 0.0)
    if official_ratio > 0 and not official_tasks_dir:
        from arc3_trainer.generator.demo_official import DEMO_OFFICIAL_DIR
        official_tasks_dir = DEMO_OFFICIAL_DIR
        logger.info("Using demo official tasks from %s", official_tasks_dir)

    config = TrainConfig(
        rounds=args.rounds,
        beam_width=args.beam_width,
        max_depth=args.max_depth,
        output_dir=args.output_dir,
        log_every=10,
        save_every=50,
        official_ratio=official_ratio,
        official_tasks_dir=official_tasks_dir,
    )
    if args.resume:
        loop = TrainingLoop.load_checkpoint(
            checkpoint_dir=args.output_dir,
            config=config,
            seed=args.seed,
        )
        logger.info(f"Resuming training from round {loop.current_round}")
    else:
        loop = TrainingLoop(config=config, seed=args.seed)

    logger.info(f"Starting training: {args.rounds} rounds, "
                f"beam_width={args.beam_width}, max_depth={args.max_depth}")
    profile = loop.train()
    logger.info(f"Training complete. Overall rate: {profile.overall_rate():.1%}")
    logger.info(f"Checkpoints saved to {args.output_dir}/")


def cmd_eval(args):
    from arc3_trainer.agent.solver import Solver
    from arc3_trainer.eval.evaluator import Evaluator

    solver = Solver(beam_width=args.beam_width, max_depth=args.max_depth)
    evaluator = Evaluator(solver=solver)

    if args.task:
        task_path = Path(args.task)
        if task_path.suffix == ".json":
            from arc3_trainer.eval.evaluator import Evaluator
            import json
            with open(task_path) as f:
                task_json = json.load(f)
            score = evaluator.evaluate_json(task_json)
            status = "✓" if score.success else "✗"
            print(f"{status} {task_path.name}: {'solved' if score.success else 'failed'}")
        else:
            result = evaluator.evaluate([task_path])
            Evaluator.print_report(result)

    if args.dir:
        result = evaluator.evaluate_dir(args.dir)
        Evaluator.print_report(result)

    if not args.task and not args.dir:
        logger.error("Specify --task or --dir for evaluation")
        sys.exit(1)


def cmd_dashboard(args):
    try:
        from arc3_trainer.dashboard.server import run_server
        run_server(host=args.host, port=args.port, load_dir=args.load_dir)
    except ImportError as e:
        logger.error(str(e))
        sys.exit(1)


def cmd_export(args):
    from arc3_trainer.trainer.loop import TrainingLoop, TrainConfig
    loop = TrainingLoop(config=TrainConfig(rounds=1))
    loop.export_solver(args.output)
    logger.info(f"Solver exported to {args.output}")


def main():
    parser = argparse.ArgumentParser(
        description="ARC3 Adversarial Training Platform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    add_train_subparser(subparsers)
    add_eval_subparser(subparsers)
    add_dashboard_subparser(subparsers)
    add_export_subparser(subparsers)

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
