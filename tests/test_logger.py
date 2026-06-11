import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from loguru import logger as loguru_logger

from config_manager import LoggingConfig
from logger import Logger


class SinkSelectionTest(unittest.TestCase):
    """R-LOG-02/03/04/06: sink/level/format wiring, with loguru mocked."""

    def configure(self, **kwargs):
        config = LoggingConfig(**kwargs)
        with mock.patch("logger.logger") as loguru_mock:
            Logger(config)
        return loguru_mock

    def test_console_output_uses_stdout_sink(self):
        # R-LOG-02
        loguru_mock = self.configure(level="INFO", output="console")

        loguru_mock.add.assert_called_once()
        self.assertIs(loguru_mock.add.call_args.args[0], sys.stdout)

    def test_non_console_output_is_used_as_sink_path(self):
        # R-LOG-03
        loguru_mock = self.configure(level="INFO", output="logs/app.log")

        self.assertEqual(loguru_mock.add.call_args.args[0], "logs/app.log")

    def test_level_is_uppercased(self):
        # R-LOG-04
        loguru_mock = self.configure(level="debug", output="console")

        self.assertEqual(loguru_mock.add.call_args.kwargs["level"], "DEBUG")

    def test_performance_level_is_registered(self):
        # R-LOG-06
        loguru_mock = self.configure(level="INFO", output="console")

        loguru_mock.level.assert_any_call(
            "PERFORMANCE", no=38, color="<yellow>", icon="🚀"
        )

    def test_handlers_are_reset_before_adding(self):
        # R-LOG-10: remove() always precedes add() (no configured-skip guard).
        loguru_mock = self.configure(level="INFO", output="console")

        loguru_mock.remove.assert_called_once_with()
        method_order = [c[0] for c in loguru_mock.method_calls]
        self.assertLess(method_order.index("remove"), method_order.index("add"))


class RealLoguruTest(unittest.TestCase):
    """R-LOG-03/07/08/09 against the real (process-global) loguru logger."""

    def tearDown(self):
        # Leave no handlers behind for other tests / later output.
        loguru_logger.remove()

    def test_file_sink_writes_log_lines(self):
        # R-LOG-03: a non-"console" output becomes a file sink.
        with tempfile.TemporaryDirectory() as tmp_dir:
            log_path = Path(tmp_dir) / "test.log"
            log = Logger(LoggingConfig(level="INFO", output=str(log_path))).get_logger()

            log.info("hello file sink")

            log.remove()  # flush and close before the directory is removed
            self.assertIn("hello file sink", log_path.read_text(encoding="utf-8"))

    def test_repeated_construction_is_idempotent(self):
        # R-LOG-07: re-registering PERFORMANCE must not leak ValueError.
        Logger(LoggingConfig(level="INFO", output="console"))
        Logger(LoggingConfig(level="INFO", output="console"))  # must not raise

        self.assertEqual(loguru_logger.level("PERFORMANCE").no, 38)

    def test_get_logger_returns_global_loguru_logger(self):
        # R-LOG-08
        wrapper = Logger(LoggingConfig(level="INFO", output="console"))

        self.assertIs(wrapper.get_logger(), loguru_logger)

    def test_invalid_level_raises_explicit_value_error(self):
        # R-LOG-09: unknown level fails fast with a clear message.
        with self.assertRaises(ValueError) as ctx:
            Logger(LoggingConfig(level="NOPE", output="console"))

        self.assertIn("Invalid logging level", str(ctx.exception))
        self.assertIn("NOPE", str(ctx.exception))

    def test_performance_is_accepted_as_level(self):
        # R-LOG-09 boundary: the custom level is registered before
        # validation, so level="performance" is valid configuration.
        Logger(LoggingConfig(level="performance", output="console"))  # must not raise


if __name__ == "__main__":
    unittest.main()
