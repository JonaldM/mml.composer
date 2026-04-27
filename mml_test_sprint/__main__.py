"""Entry point for ``python -m mml_test_sprint``.

Parses CLI flags into environment variables *before* importing the
runner so the config module sees the override values. All flags are
optional — unset values fall back to the defaults in ``config.py``.

Flags:
    --target URL              (sets MML_TEST_BASE_URL)
    --user EMAIL              (sets MML_TEST_LOGIN_EMAIL)
    --password PASSWORD       (sets MML_TEST_LOGIN_PASSWORD)
    --database NAME           (sets MML_TEST_DATABASE)
    --module NAME             filter to a single module group
                              (e.g. ``freight``); without it the runner
                              executes every registered group.
    --headed                  run with a visible browser (HEADLESS=0)
    --no-installed-check      skip the SSH installed-modules query
"""
import argparse
import os
import sys


def _apply_cli_to_env(argv):
    parser = argparse.ArgumentParser(
        prog="mml_test_sprint",
        description="MML Module Test Sprint — Playwright UI tests")
    parser.add_argument("--target", "--base-url", dest="target",
                        help="Odoo base URL (default: from config.py)")
    parser.add_argument("--user", "--login", dest="user",
                        help="Odoo login email")
    parser.add_argument("--password", dest="password",
                        help="Odoo login password")
    parser.add_argument("--database", dest="database",
                        help="Odoo database name")
    parser.add_argument("--module", dest="module",
                        choices=("freight", "platform", "data", "all"),
                        default="all",
                        help="Module group to run (default: all)")
    parser.add_argument("--headed", action="store_true",
                        help="Show the browser window (HEADLESS=0)")
    parser.add_argument("--no-installed-check", action="store_true",
                        help="Skip the SSH installed-modules query")
    args = parser.parse_args(argv)

    if args.target:
        os.environ["MML_TEST_BASE_URL"] = args.target
    if args.user:
        os.environ["MML_TEST_LOGIN_EMAIL"] = args.user
    if args.password:
        os.environ["MML_TEST_LOGIN_PASSWORD"] = args.password
    if args.database:
        os.environ["MML_TEST_DATABASE"] = args.database
    if args.headed:
        os.environ["MML_TEST_HEADLESS"] = "0"
    if args.no_installed_check:
        os.environ["MML_TEST_SKIP_INSTALLED_CHECK"] = "1"
    os.environ["MML_TEST_MODULE_GROUP"] = args.module
    return args


if __name__ == "__main__":
    _apply_cli_to_env(sys.argv[1:])
    # Defer import until after env vars are set so config.py picks them up.
    from mml_test_sprint.runner import main
    main()
