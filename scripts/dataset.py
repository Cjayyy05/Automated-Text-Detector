"""Explicit local file preparation/annotation; no windows, capture or clipboard access."""

import argparse
from pathlib import Path

from stream_code_capture.dataset import annotate, load_dataset, prepare, split_datasets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare")
    prep.add_argument("sources", nargs="+", type=Path)
    prep.add_argument("--output", required=True, type=Path)
    prep.add_argument("--session", required=True)
    prep.add_argument("--kind", choices=("recording", "screenshot", "synthetic"), required=True)
    prep.add_argument("--stride", type=int, default=1)
    prep.add_argument("--start", type=int, default=0)
    prep.add_argument("--stop", type=int)
    prep.add_argument("--max-frames", type=int, default=3000)
    label = commands.add_parser("label")
    label.add_argument("manifest", type=Path)
    label.add_argument("--labels", type=Path, required=True)
    label.add_argument("--output", type=Path, required=True)
    check = commands.add_parser("audit")
    check.add_argument("manifest", type=Path)
    split = commands.add_parser("split")
    split.add_argument("manifests", nargs="+", type=Path)
    split.add_argument("--output", type=Path, required=True)
    split.add_argument("--seed", default="phase3-v1")
    split.add_argument("--holdout-fraction", type=float, default=0.25)
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            print(
                prepare(
                    args.sources,
                    args.output,
                    session=args.session,
                    kind=args.kind,
                    stride=args.stride,
                    start=args.start,
                    stop=args.stop,
                    max_frames=args.max_frames,
                )
            )
        elif args.command == "label":
            annotate(args.manifest, args.labels, args.output)
            print(args.output)
        elif args.command == "audit":
            data = load_dataset(args.manifest)
            print(f"Validated {len(data['frames'])} frames; source={data['source_kind']}")
        else:
            split_datasets(
                args.manifests, args.output, seed=args.seed, fraction=args.holdout_fraction
            )
            print(args.output)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(2, f"Dataset error: {exc}\n")


if __name__ == "__main__":
    main()
