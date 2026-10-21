"""CPU checks for training data layout and the alpha calibration objective."""

import ast
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
import sys

import numpy as np
from PIL import Image
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from opacity_training_cameras import TrainingCameras


class TrainingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        source = ast.parse((Path(__file__).resolve().parents[1] / "train_opacity_v3.py").read_text())
        nodes = [node for node in source.body if isinstance(node, (ast.ClassDef, ast.FunctionDef))
                 and node.name in ("TrainingData", "foreground_l1")]
        self.scope = dict(Path=Path, json=json, np=np, Image=Image, torch=torch,
                          TrainingCameras=TrainingCameras,
                          read_obj=lambda path: dict(vertices=[[0, 0, 0]]),
                          DEFAULTS=SimpleNamespace(data_root=self.root / "data",
                                                   output_root=self.root / "assets", stage2="stage2"))
        exec(compile(ast.Module(body=nodes, type_ignores=[]), "training_helpers", "exec"), self.scope)

    def test_frame_shapes_and_camera_selection(self):
        folder = self.root / "data/shirt/Sequence1"
        (folder / "Cam001").mkdir(parents=True)
        (folder / "cameras.json").write_text(json.dumps({"Cam001": {
            "shape": [32, 40], "intrinsics": [[50, 0, 18], [0, 51, 15], [0, 0, 1]],
            "extrinsics": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 1]],
        }}))
        data = self.scope["TrainingData"]("shirt", "Sequence1", 8, .5)
        mesh, ambient, normal = data.frame_paths(0)
        for path in (mesh, ambient, normal):
            path.parent.mkdir(parents=True, exist_ok=True)
        mesh.touch()
        Image.new("L", (512, 512), color=128).save(ambient)
        Image.new("RGB", (512, 512), color=(128, 128, 255)).save(normal)
        data.validate([0])
        vertices, ao, normals = data.frame(0)
        self.assertEqual(tuple(ao.shape), (1, 512, 512))
        self.assertEqual(tuple(normals.shape), (3, 512, 512))
        self.assertEqual(tuple(vertices.shape), (1, 3))
        self.assertEqual(data.names, ["Cam001"])
        with self.assertRaises(FileNotFoundError):
            data.validate([1])
        with self.assertRaises(ValueError):
            self.scope["TrainingData"]("shirt", "Sequence1", 8, .5, ["unknown"])

    def test_training_camera_uses_calibration_dimensions_without_cuda(self):
        folder = self.root / 'assets/shirt/stage2/Sequence1'
        folder.mkdir(parents=True)
        (folder / 'cameras.json').write_text(json.dumps({'Cam001': {
            'shape': [32, 40], 'intrinsics': [[50, 0, 18], [0, 51, 15], [0, 0, 1]],
            'extrinsics': [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 1]],
        }}))
        self.scope['Camera'] = lambda **kwargs: SimpleNamespace(**kwargs)
        self.scope['focal2fov'] = lambda focal, pixels: 2 * np.arctan(pixels / (2 * focal))
        data = self.scope['TrainingData']('shirt', 'Sequence1', 8, .5)
        camera = data.camera('Cam001')
        self.assertEqual(tuple(camera.image.shape), (3, 16, 20))
        self.assertEqual((camera.fx, camera.fy, camera.cx, camera.cy), (25, 25.5, 9, 7.5))
        self.assertIs(data.camera('Cam001'), camera)

    def test_foreground_loss_and_gradient(self):
        original = torch.tensor([[0., .4], [.8, 1.]])
        predicted = (original * .7).requires_grad_()
        loss = self.scope["foreground_l1"](predicted, original * .5, original)
        weights = (original > 1e-3).float() + .25 * original
        expected = (weights * .2 * original).sum() / weights.sum()
        torch.testing.assert_close(loss, expected)
        loss.backward()
        self.assertTrue(torch.isfinite(predicted.grad).all())
        self.assertEqual(predicted.grad[0, 0], 0)
        with self.assertRaises(ValueError):
            self.scope["foreground_l1"](predicted, predicted, torch.zeros_like(predicted))


if __name__ == "__main__":
    unittest.main()
