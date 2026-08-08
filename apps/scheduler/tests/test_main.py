from veridash_scheduler.main import build_parser


def test_once_flag_defaults_to_false() -> None:
    args = build_parser().parse_args([])

    assert args.once is False
