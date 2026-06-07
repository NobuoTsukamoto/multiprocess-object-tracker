"""
Copyright (c) 2025 Nobuo Tsukamoto
This software is released under the MIT License.
See the LICENSE file in the project root for more information.

Shared-memory ring buffer for transferring frames between processes
without pickling the image bytes.

Lifecycle:
  - Main process creates a SharedFramePool (owner). It allocates N
    shared_memory blocks plus a free-slot Queue and a data Queue.
  - Subprocesses (writer / reader) receive a SharedFrameSpec and call
    SharedFrameAccessor(spec) inside their run() to attach.
  - On shutdown, accessors call .close(); the owner calls .cleanup()
    once to unlink the segments.
"""

import time
from dataclasses import dataclass
from multiprocessing import Queue
from multiprocessing import shared_memory
from queue import Empty, Full
from typing import List, Tuple

import numpy as np

from data_models import FrameRef


# multiprocessing.Queue uses a feeder thread, so an item can be in flight
# immediately after put_nowait() while get_nowait() still reports Empty.
# Keep this retry tiny: it smooths over pipe/feeder timing without turning
# the camera and tracking loops into blocking back-pressure points.
# With the current values, one helper call can add up to about 2 ms.
# A writer under slot pressure may call it for free-slot lookup and again
# for eviction, so the worst-case extra wait is about 4 ms per frame.
_QUEUE_GET_RETRIES = 2
_QUEUE_GET_RETRY_DELAY_SEC = 0.001


def _get_nowait_with_retry(
    queue: Queue,
    retries: int = _QUEUE_GET_RETRIES,
    delay_sec: float = _QUEUE_GET_RETRY_DELAY_SEC,
):
    """Get without materially blocking, tolerating Queue feeder latency."""
    for attempt in range(retries + 1):
        try:
            return queue.get_nowait()
        except Empty:
            if attempt >= retries:
                raise
            time.sleep(delay_sec)


@dataclass
class SharedFrameSpec:
    """Serializable handle that subprocesses use to attach to a pool."""

    names: List[str]
    shape: Tuple[int, ...]
    dtype: str
    free_queue: Queue
    data_queue: Queue


class SharedFramePool:
    """Owner-side pool. Created in the main process."""

    def __init__(
        self,
        n_slots: int,
        shape: Tuple[int, ...],
        dtype: str,
        data_queue: Queue,
    ):
        self.shape = tuple(shape)
        self.dtype = np.dtype(dtype)
        nbytes = int(np.prod(self.shape)) * self.dtype.itemsize

        self.shms = [
            shared_memory.SharedMemory(create=True, size=nbytes)
            for _ in range(n_slots)
        ]
        self.free_queue: Queue = Queue(maxsize=n_slots)
        for i in range(n_slots):
            self.free_queue.put(i)
        self.data_queue = data_queue
        self._active = False

    @property
    def spec(self) -> SharedFrameSpec:
        return SharedFrameSpec(
            names=[s.name for s in self.shms],
            shape=self.shape,
            dtype=str(self.dtype),
            free_queue=self.free_queue,
            data_queue=self.data_queue,
        )

    @property
    def is_active(self) -> bool:
        return self._active

    def mark_active(self):
        """Mark this pool as owned by running worker processes."""
        self._active = True

    def mark_inactive(self):
        """Mark this pool as safe for owner-side queue repair/reset."""
        self._active = False

    def reset_free_slots(self):
        """Drain queues and refill free_queue with all slots.

        Call only after all workers/accessors using this pool have
        stopped. Calling while a writer or reader can still hold a slot
        breaks slot ownership: a slot may be returned to free_queue while
        another process is still reading from or writing to it.

        This owner-side reset is intentionally guarded instead of being
        made lock-heavy; normal frame transfer stays fast, and lifecycle
        code must make the stopped-workers precondition explicit.
        """
        if self._active:
            raise RuntimeError(
                "reset_free_slots() must only be called after all workers "
                "using this pool have stopped."
            )

        for q in (self.free_queue, self.data_queue):
            while True:
                try:
                    _get_nowait_with_retry(q)
                except Empty:
                    break
        for i in range(len(self.shms)):
            self.free_queue.put(i)

    def cleanup(self):
        for s in self.shms:
            try:
                s.close()
            except Exception:
                pass
            try:
                s.unlink()
            except Exception:
                pass
        self.shms = []


class SharedFrameAccessor:
    """Used by sub-processes (writer or reader) to access a pool."""

    def __init__(self, spec: SharedFrameSpec):
        self.spec = spec
        self.dtype = np.dtype(spec.dtype)
        self.shape = tuple(spec.shape)
        self.shms = [shared_memory.SharedMemory(name=n) for n in spec.names]
        self.views = [
            np.ndarray(self.shape, dtype=self.dtype, buffer=s.buf)
            for s in self.shms
        ]

    # ------------------- writer side -------------------
    def write(self, frame: np.ndarray, frame_id: int, timestamp: float) -> bool:
        """Copy `frame` into a free slot and publish a FrameRef.

        If no free slot is available, drop the oldest queued FrameRef
        and reuse its slot (matches the previous "evict oldest" policy).
        Returns True if a frame was published, False if it was dropped.
        """
        # Sanity check shape
        if frame.shape != self.shape:
            # Caller is expected to ensure shapes match; bail safely.
            return False

        try:
            slot = _get_nowait_with_retry(self.spec.free_queue)
        except Empty:
            # No free slot: try evicting oldest pending frame.
            try:
                old: FrameRef = _get_nowait_with_retry(self.spec.data_queue)
                slot = old.slot
            except Empty:
                return False  # consumers + queue racing; drop this frame

        np.copyto(self.views[slot], frame)
        try:
            self.spec.data_queue.put_nowait(
                FrameRef(frame_id=frame_id, timestamp=timestamp, slot=slot)
            )
            return True
        except Full:
            # Couldn't enqueue; return slot to free pool.
            try:
                self.spec.free_queue.put_nowait(slot)
            except Full:
                pass
            return False

    # ------------------- reader side -------------------
    def read(self, timeout: float = 1.0):
        """Block up to `timeout` seconds for a FrameRef.

        Returns (FrameRef, np.ndarray copy of frame). The slot is
        returned to the free pool before this call returns, so the
        caller may keep the returned ndarray indefinitely.
        Raises queue.Empty on timeout.
        """
        ref: FrameRef = self.spec.data_queue.get(timeout=timeout)
        frame = self.views[ref.slot].copy()
        try:
            self.spec.free_queue.put_nowait(ref.slot)
        except Full:
            pass
        return ref, frame

    def read_nowait(self):
        ref: FrameRef = self.spec.data_queue.get_nowait()
        frame = self.views[ref.slot].copy()
        try:
            self.spec.free_queue.put_nowait(ref.slot)
        except Full:
            pass
        return ref, frame

    def read_latest(self, timeout: float = 1.0, max_skip: int | None = None):
        """Block for the next FrameRef, then skip ahead to the newest one.

        Blocks up to `timeout` seconds for the first FrameRef, then
        drains additional queued refs without blocking, returning the
        slots of the skipped (older) frames to the free pool. If `max_skip`
        is None, all queued frames are skipped (latest); if `max_skip` <= 0,
        none are skipped (FIFO); otherwise, at most `max_skip` frames are skipped
        and only the selected frame is copied and returned.

        This keeps a slow consumer near real-time instead of falling
        progressively further behind by processing every frame FIFO. A
        bounded skip can reduce tracker instability caused by large
        frame_id jumps.
        Returns (FrameRef, np.ndarray copy of frame, skipped_count). Raises
        queue.Empty on timeout.
        """
        if max_skip is not None:
            max_skip = max(0, max_skip)

        ref: FrameRef = self.spec.data_queue.get(timeout=timeout)
        skipped_count = 0
        while True:
            if max_skip is not None and skipped_count >= max_skip:
                break
            try:
                newer: FrameRef = _get_nowait_with_retry(self.spec.data_queue)
            except Empty:
                break
            # Discard the older frame: release its slot, keep the newer.
            try:
                self.spec.free_queue.put_nowait(ref.slot)
            except Full:
                pass
            ref = newer
            skipped_count += 1

        frame = self.views[ref.slot].copy()
        try:
            self.spec.free_queue.put_nowait(ref.slot)
        except Full:
            pass
        return ref, frame, skipped_count

    def close(self):
        for s in self.shms:
            try:
                s.close()
            except Exception:
                pass
        self.shms = []
        self.views = []
