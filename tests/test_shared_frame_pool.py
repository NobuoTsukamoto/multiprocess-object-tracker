import sys
import unittest
from multiprocessing import shared_memory
from pathlib import Path
from queue import Empty, Queue

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_models import FrameRef
from shared_frame_pool import SharedFrameAccessor, SharedFramePool, SharedFrameSpec


class _FlakyQueue:
    def __init__(self, get_response=None, get_nowait_responses=None):
        self.get_response = get_response
        self.get_nowait_responses = list(get_nowait_responses or [])
        self.put_items = []

    def get(self, timeout=None):
        if isinstance(self.get_response, type) and issubclass(
            self.get_response, Exception
        ):
            raise self.get_response
        return self.get_response

    def get_nowait(self):
        if not self.get_nowait_responses:
            raise Empty
        response = self.get_nowait_responses.pop(0)
        if isinstance(response, type) and issubclass(response, Exception):
            raise response
        return response

    def put_nowait(self, item):
        self.put_items.append(item)


def _make_spec(n_slots=5, shape=(1, 1, 1), dtype="uint8"):
    dtype_obj = np.dtype(dtype)
    nbytes = int(np.prod(shape)) * dtype_obj.itemsize
    shms = [
        shared_memory.SharedMemory(create=True, size=nbytes)
        for _ in range(n_slots)
    ]
    free_queue = Queue(maxsize=n_slots)
    for i in range(n_slots):
        free_queue.put(i)
    data_queue = Queue(maxsize=n_slots)
    spec = SharedFrameSpec(
        names=[s.name for s in shms],
        shape=shape,
        dtype=str(dtype_obj),
        free_queue=free_queue,
        data_queue=data_queue,
    )
    return spec, shms


def _cleanup(shms):
    for shm in shms:
        try:
            shm.close()
        except Exception:
            pass
        try:
            shm.unlink()
        except Exception:
            pass


class SharedFramePoolTest(unittest.TestCase):
    def test_reset_free_slots_is_guarded_while_pool_is_active(self):
        pool = SharedFramePool(
            n_slots=1,
            shape=(1, 1, 1),
            dtype="uint8",
            data_queue=Queue(maxsize=1),
        )
        try:
            self.assertFalse(pool.is_active)
            pool.mark_active()
            self.assertTrue(pool.is_active)

            with self.assertRaises(RuntimeError):
                pool.reset_free_slots()

            pool.mark_inactive()
            self.assertFalse(pool.is_active)
            pool.reset_free_slots()
        finally:
            pool.cleanup()

    def test_read_latest_returns_skipped_count_and_drains_to_newest(self):
        spec, shms = _make_spec()
        writer = SharedFrameAccessor(spec)
        reader = SharedFrameAccessor(spec)
        try:
            for frame_id in range(4):
                frame = np.full(spec.shape, frame_id, dtype=np.uint8)
                self.assertTrue(
                    writer.write(
                        frame, frame_id=frame_id, timestamp=float(frame_id)
                    )
                )

            ref, frame, skipped_count = reader.read_latest(timeout=0.1)

            self.assertEqual(ref.frame_id, 3)
            self.assertEqual(skipped_count, 3)
            self.assertEqual(frame.item(), 3)
            self.assertTrue(spec.data_queue.empty())
            self.assertEqual(spec.free_queue.qsize(), 5)
        finally:
            writer.close()
            reader.close()
            _cleanup(shms)

    def test_read_latest_can_bound_skipped_frames(self):
        spec, shms = _make_spec()
        writer = SharedFrameAccessor(spec)
        reader = SharedFrameAccessor(spec)
        try:
            for frame_id in range(4):
                frame = np.full(spec.shape, frame_id, dtype=np.uint8)
                self.assertTrue(
                    writer.write(
                        frame, frame_id=frame_id, timestamp=float(frame_id)
                    )
                )

            ref, frame, skipped_count = reader.read_latest(timeout=0.1, max_skip=2)

            self.assertEqual(ref.frame_id, 2)
            self.assertEqual(skipped_count, 2)
            self.assertEqual(frame.item(), 2)

            next_ref, next_frame = reader.read_nowait()
            self.assertEqual(next_ref.frame_id, 3)
            self.assertEqual(next_frame.item(), 3)
            self.assertEqual(spec.free_queue.qsize(), 5)
        finally:
            writer.close()
            reader.close()
            _cleanup(shms)

    def test_read_latest_treats_negative_max_skip_as_fifo_read(self):
        spec, shms = _make_spec()
        writer = SharedFrameAccessor(spec)
        reader = SharedFrameAccessor(spec)
        try:
            for frame_id in range(2):
                frame = np.full(spec.shape, frame_id, dtype=np.uint8)
                self.assertTrue(
                    writer.write(
                        frame, frame_id=frame_id, timestamp=float(frame_id)
                    )
                )

            ref, frame, skipped_count = reader.read_latest(timeout=0.1, max_skip=-1)

            self.assertEqual(ref.frame_id, 0)
            self.assertEqual(skipped_count, 0)
            self.assertEqual(frame.item(), 0)

            next_ref, _ = reader.read_nowait()
            self.assertEqual(next_ref.frame_id, 1)
        finally:
            writer.close()
            reader.close()
            _cleanup(shms)

    def test_write_retries_before_dropping_when_evict_queue_looks_empty(self):
        spec, shms = _make_spec(n_slots=1)
        spec.free_queue = _FlakyQueue(get_nowait_responses=[Empty, Empty, Empty])
        spec.data_queue = _FlakyQueue(
            get_nowait_responses=[
                Empty,
                FrameRef(frame_id=1, timestamp=1.0, slot=0),
            ]
        )
        writer = SharedFrameAccessor(spec)
        try:
            frame = np.full(spec.shape, 9, dtype=np.uint8)

            self.assertTrue(writer.write(frame, frame_id=2, timestamp=2.0))

            self.assertEqual(writer.views[0].item(), 9)
            self.assertEqual(len(spec.data_queue.put_items), 1)
            published = spec.data_queue.put_items[0]
            self.assertEqual(published.frame_id, 2)
            self.assertEqual(published.slot, 0)
        finally:
            writer.close()
            _cleanup(shms)

    def test_write_still_drops_after_queue_retry_budget_is_exhausted(self):
        spec, shms = _make_spec(n_slots=1)
        spec.free_queue = _FlakyQueue(get_nowait_responses=[Empty, Empty, Empty])
        spec.data_queue = _FlakyQueue(get_nowait_responses=[Empty, Empty, Empty])
        writer = SharedFrameAccessor(spec)
        try:
            frame = np.full(spec.shape, 9, dtype=np.uint8)

            self.assertFalse(writer.write(frame, frame_id=2, timestamp=2.0))
            self.assertEqual(spec.data_queue.put_items, [])
        finally:
            writer.close()
            _cleanup(shms)

    def test_read_latest_retries_when_drain_queue_temporarily_looks_empty(self):
        spec, shms = _make_spec(n_slots=2)
        spec.data_queue = _FlakyQueue(
            get_response=FrameRef(frame_id=1, timestamp=1.0, slot=0),
            get_nowait_responses=[
                Empty,
                FrameRef(frame_id=2, timestamp=2.0, slot=1),
            ],
        )
        spec.free_queue = _FlakyQueue()
        reader = SharedFrameAccessor(spec)
        try:
            reader.views[0][...] = 1
            reader.views[1][...] = 2

            ref, frame, skipped_count = reader.read_latest(timeout=0.1)

            self.assertEqual(ref.frame_id, 2)
            self.assertEqual(frame.item(), 2)
            self.assertEqual(skipped_count, 1)
            self.assertEqual(spec.free_queue.put_items, [0, 1])
        finally:
            reader.close()
            _cleanup(shms)


if __name__ == "__main__":
    unittest.main()
