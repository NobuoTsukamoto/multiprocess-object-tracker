import dataclasses
import sys
import unittest
from pathlib import Path
from typing import Any, List

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import data_models
from data_models import FrameRef, TrackInfo, TrackingResult, WorkerError


class DataclassAggregationTest(unittest.TestCase):
    # R-DM-01: every IPC structure is a @dataclass aggregated in
    # data_models.py — nothing missing, nothing extra.

    IPC_TYPES = (FrameRef, TrackInfo, TrackingResult, WorkerError)

    def test_all_ipc_structures_are_dataclasses(self):
        for cls in self.IPC_TYPES:
            with self.subTest(cls=cls.__name__):
                self.assertTrue(dataclasses.is_dataclass(cls))

    def test_data_models_defines_exactly_the_ipc_structures(self):
        defined = {
            name
            for name, obj in vars(data_models).items()
            if isinstance(obj, type)
            and dataclasses.is_dataclass(obj)
            and obj.__module__ == "data_models"
        }

        self.assertEqual(
            defined, {"FrameRef", "TrackInfo", "TrackingResult", "WorkerError"}
        )


class FrameRefContractTest(unittest.TestCase):
    # R-DM-03: FrameRef is a lightweight slot reference — exactly
    # frame_id/timestamp/slot, never the image payload itself.

    def test_fields_are_exactly_frame_id_timestamp_slot(self):
        fields = {f.name: f.type for f in dataclasses.fields(FrameRef)}

        self.assertEqual(
            fields, {"frame_id": int, "timestamp": float, "slot": int}
        )

    def test_all_fields_are_required(self):
        for field in dataclasses.fields(FrameRef):
            with self.subTest(field=field.name):
                self.assertIs(field.default, dataclasses.MISSING)
                self.assertIs(field.default_factory, dataclasses.MISSING)


class TrackInfoContractTest(unittest.TestCase):
    # R-DM-05: TrackInfo is the GUI list entry — exactly track_id/class_id
    # (box/score live in TrackingResult.detections).

    def test_fields_are_exactly_track_id_and_class_id(self):
        fields = {f.name: f.type for f in dataclasses.fields(TrackInfo)}

        self.assertEqual(fields, {"track_id": int, "class_id": int})


class TrackingResultContractTest(unittest.TestCase):
    # R-DM-06/07: five required fields plus two latency fields that
    # default to 0.0 (backward compatibility with five-argument callers).

    def test_field_names_and_types(self):
        fields = {f.name: f.type for f in dataclasses.fields(TrackingResult)}

        self.assertEqual(
            fields,
            {
                "frame_id": int,
                "timestamp": float,
                "track_infos": List[TrackInfo],
                "detections": Any,
                "process_time_ms": float,
                "queue_latency_ms": float,
                "total_latency_ms": float,
            },
        )

    def test_only_latency_fields_are_optional(self):
        required = [
            f.name
            for f in dataclasses.fields(TrackingResult)
            if f.default is dataclasses.MISSING
            and f.default_factory is dataclasses.MISSING
        ]

        self.assertEqual(
            required,
            ["frame_id", "timestamp", "track_infos", "detections", "process_time_ms"],
        )

    def test_latency_fields_default_to_zero(self):
        # R-DM-07: a five-argument construction still works and yields 0.0.
        result = TrackingResult(
            frame_id=1,
            timestamp=0.0,
            track_infos=[],
            detections=None,
            process_time_ms=5.0,
        )

        self.assertEqual(result.queue_latency_ms, 0.0)
        self.assertEqual(result.total_latency_ms, 0.0)


if __name__ == "__main__":
    unittest.main()
