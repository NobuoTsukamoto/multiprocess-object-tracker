import dataclasses
import sys
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
