import sys
import unittest
from multiprocessing import shared_memory
from pathlib import Path
from queue import Queue

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from shared_frame_pool import SharedFrameAccessor, SharedFrameSpec


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


if __name__ == "__main__":
    unittest.main()
