"""Train a tiny original Vayron checkpoint from a user-supplied UTF-8 text file."""
import argparse
from pathlib import Path

from vayron_core.training import TrainingConfig, train_text
from vayron_core.neural import VayronModelConfig


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True, help="UTF-8 text file you have rights to use")
    parser.add_argument("--output", default="artifacts/vayron-smoke")
    parser.add_argument("--steps", type=int, default=20)
    parser.add_argument("--sequence-length", type=int, default=64)
    parser.add_argument("--layers", type=int, default=2)
    parser.add_argument("--width", type=int, default=64)
    args = parser.parse_args()
    text = Path(args.data).read_text(encoding="utf-8")
    report = train_text(
        text,
        args.output,
        model_config=VayronModelConfig(d_model=args.width, n_heads=4, n_layers=args.layers, max_seq_len=args.sequence_length),
        training_config=TrainingConfig(max_steps=args.steps, batch_size=2),
    )
    print(report)


if __name__ == "__main__":
    main()
