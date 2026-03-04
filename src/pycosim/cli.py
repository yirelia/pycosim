"""CLI entry point for PyCosim."""

from __future__ import annotations

import argparse
import logging
import sys


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="pycosim",
        description="PyCosim - Multi-FMU Co-Simulation Engine",
    )
    subparsers = parser.add_subparsers(dest="command")

    # --- simulate ---
    sim_parser = subparsers.add_parser("simulate", help="Run a simulation")
    sim_parser.add_argument("config", help="Path to JSON config file")
    sim_parser.add_argument("--parallel", action="store_true",
                            help="Enable parallel node execution")
    sim_parser.add_argument("--workers", type=int, default=None,
                            help="Max parallel workers")
    sim_parser.add_argument("-v", "--verbose", action="count", default=0,
                            help="Increase verbosity (-v, -vv)")

    # --- worker ---
    worker_parser = subparsers.add_parser("worker", help="Start a distributed worker")
    worker_parser.add_argument("--address", default="tcp://localhost:5555",
                               help="Coordinator ZMQ address")
    worker_parser.add_argument("--fmu", required=True, help="Path to FMU file")
    worker_parser.add_argument("--node-id", required=True, help="Node ID")
    worker_parser.add_argument("-v", "--verbose", action="count", default=0)

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    # Configure logging
    level = logging.WARNING
    if hasattr(args, "verbose"):
        if args.verbose == 1:
            level = logging.INFO
        elif args.verbose >= 2:
            level = logging.DEBUG
    logging.basicConfig(level=level, format="%(levelname)s: %(name)s: %(message)s")

    if args.command == "simulate":
        _cmd_simulate(args)
    elif args.command == "worker":
        _cmd_worker(args)


def _cmd_simulate(args) -> None:
    from pycosim.config.loader import load_graph
    from pycosim.engine.graph_executor import GraphExecutor

    graph = load_graph(args.config)
    executor = GraphExecutor(graph, parallel=args.parallel,
                             max_workers=args.workers)
    executor.execute()


def _cmd_worker(args) -> None:
    from pycosim.distributed.worker import Worker

    worker = Worker(
        fmu_path=args.fmu,
        node_id=args.node_id,
        coordinator_address=args.address,
    )
    worker.run()


if __name__ == "__main__":
    main()
