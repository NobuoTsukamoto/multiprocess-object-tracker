from types import SimpleNamespace

from object_tracking_controller import FRAME_READ_TIMEOUT_SEC, ObjectTrackingController


class _FramePoolStub:
    def __init__(self):
        self.calls = []

    def read(self, timeout):
        self.calls.append(("read", timeout))
        return "ref", "image"

    def read_latest(self, timeout, max_skip=None):
        self.calls.append(("read_latest", timeout, max_skip))
        return "ref", "image", 3


class _LoggerStub:
    def __init__(self):
        self.warning_messages = []

    def warning(self, message):
        self.warning_messages.append(message)


def _make_controller(policy, max_frame_skip=2, logger=None):
    controller = object.__new__(ObjectTrackingController)
    controller.track_config = SimpleNamespace(
        frame_read_policy=policy,
        max_frame_skip=max_frame_skip,
    )
    controller.logger = logger
    return controller


def test_read_frame_uses_fifo_policy_without_skipping():
    controller = _make_controller("fifo")
    frame_pool = _FramePoolStub()

    result = controller._read_frame(frame_pool)

    assert result == ("ref", "image", 0)
    assert frame_pool.calls == [("read", FRAME_READ_TIMEOUT_SEC)]


def test_read_frame_uses_latest_policy_without_max_skip():
    controller = _make_controller("latest")
    frame_pool = _FramePoolStub()

    result = controller._read_frame(frame_pool)

    assert result == ("ref", "image", 3)
    assert frame_pool.calls == [("read_latest", FRAME_READ_TIMEOUT_SEC, None)]


def test_read_frame_clamps_bounded_latest_skip_to_non_negative_integer():
    controller = _make_controller("bounded_latest", max_frame_skip=-5)
    frame_pool = _FramePoolStub()

    controller._read_frame(frame_pool)

    assert frame_pool.calls == [("read_latest", FRAME_READ_TIMEOUT_SEC, 0)]


def test_read_frame_unknown_policy_warns_and_falls_back_to_bounded_latest():
    logger = _LoggerStub()
    controller = _make_controller("surprise", max_frame_skip=4, logger=logger)
    frame_pool = _FramePoolStub()

    controller._read_frame(frame_pool)

    assert frame_pool.calls == [("read_latest", FRAME_READ_TIMEOUT_SEC, 4)]
    assert len(logger.warning_messages) == 1
    assert "surprise" in logger.warning_messages[0]
