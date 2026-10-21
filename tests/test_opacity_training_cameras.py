"""CPU coverage for calibrated, image-free V3 training inputs."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from opacity_training_cameras import TrainingCameras


class CameraTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.data = root / 'input/shirt/Sequence1'
        self.stage1 = root / 'output/shirt/stage1'
        self.stage2 = root / 'output/shirt/stage2/Sequence1'
        self.calibration = {
            'ids': 5, 'shape': [11, 9],
            'intrinsics': [[20, 0, 3.8], [0, 21, 5.2], [0, 0, 1]],
            'extrinsics': [[0, -1, 0, 1], [1, 0, 0, 2], [0, 0, 1, 3]],
        }
        self.view = dict(img_name='Cam005', width=9, height=11, fx=20, fy=21,
                         rotation=[[0, 1, 0], [-1, 0, 0], [0, 0, 1]], position=[-2, 1, -3])

    def write(self, folder, value):
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'cameras.json').write_text(json.dumps(value))

    def load(self, **kwargs):
        return TrainingCameras(self.data, self.stage2, self.stage1, **kwargs)

    def delivery(self):
        self.write(self.stage1, {'Cam005': self.calibration, 'Cam006': self.calibration})
        self.write(self.stage2, [self.view])

    def test_delivery_without_images_uses_only_registered_views(self):
        self.delivery()
        with patch('opacity_training_cameras.Image.open', side_effect=AssertionError('must not read images')):
            cameras = self.load()
        self.assertFalse(self.data.exists())
        self.assertEqual(cameras.names, ['Cam005'])
        self.assertEqual(cameras.provenance['available_camera_count'], 1)
        self.assertEqual(cameras.provenance['image_shapes'], {'Cam005': [11, 9]})
        self.assertEqual(len(cameras.provenance['calibration_sha256']), 64)
        self.assertEqual(len(cameras.provenance['selection_sha256']), 64)
        with self.assertRaisesRegex(ValueError, 'unique calibrated'):
            self.load(names=['Cam006'])

    def test_preserves_principal_point_and_extrinsic_convention(self):
        self.delivery()
        cameras = self.load(render_scale=.5)
        params = cameras.parameters('Cam005')
        self.assertEqual((params['height'], params['width']), (6, 4))
        self.assertEqual((params['fx'], params['fy']), (10, 10.5))
        self.assertAlmostEqual(params['cx'], 1.9)
        self.assertAlmostEqual(params['cy'], 2.6)
        np.testing.assert_array_equal(params['R'], self.view['rotation'])
        np.testing.assert_array_equal(params['T'], [1, 2, 3])
        np.testing.assert_array_equal(cameras.parameters('Cam005')['T'], params['T'])

    def test_input_calibration_has_priority(self):
        self.delivery()
        self.write(self.data, {'Cam005': self.calibration})
        (self.stage1 / 'cameras.json').write_text('invalid unused JSON')
        cameras = self.load()
        self.assertEqual(cameras.provenance['calibration_path'], str(self.data / 'cameras.json'))

    def test_legacy_image_directory_and_jpeg_dimensions(self):
        calibration = copy.deepcopy(self.calibration)
        calibration.pop('shape')
        self.write(self.data, {'Cam005': calibration})
        folder = self.data / 'Cam005/rgb_images'
        folder.mkdir(parents=True)
        Image.new('RGB', (9, 11)).save(folder / '000000.jpg')
        cameras = self.load()
        self.assertEqual(cameras.shapes['Cam005'], (11, 9))
        self.assertIsNone(cameras.provenance['selection_path'])

    def test_legacy_stage2_calibration_dictionary(self):
        self.write(self.stage2, {'Cam005': self.calibration})
        cameras = self.load()
        self.assertEqual(cameras.names, ['Cam005'])
        self.assertEqual(cameras.provenance['calibration_path'], str(self.stage2 / 'cameras.json'))

    def test_rendering_list_alone_cannot_recover_principal_point(self):
        self.write(self.stage2, [self.view])
        with self.assertRaisesRegex(FileNotFoundError, 'Full calibration'):
            self.load()

    def test_rejects_inconsistent_view_metadata(self):
        self.delivery()
        for key, value, message in [('width', 10, 'dimensions'), ('fx', 22, 'focal'),
                                    ('position', [2, 1, -3], 'pose'),
                                    ('rotation', np.eye(3).tolist(), 'pose')]:
            with self.subTest(key=key):
                view = dict(self.view, **{key: value})
                self.write(self.stage2, [view])
                with self.assertRaisesRegex(ValueError, message):
                    self.load()

    def test_rejects_missing_duplicate_and_empty_views(self):
        self.delivery()
        for views, message in [([dict(self.view, img_name='Cam099')], 'missing full calibration'),
                               ([self.view, self.view], 'Duplicate'), ([], 'No selected'),
                               ([dict(self.view, img_name='../bad')], 'Invalid camera name')]:
            with self.subTest(message=message):
                self.write(self.stage2, views)
                with self.assertRaisesRegex(ValueError, message):
                    self.load()

    def test_rejects_invalid_calibration_without_silent_fallback(self):
        self.delivery()
        for key, value in [('shape', [0, 9]), ('shape', [11.5, 9]),
                           ('intrinsics', [[float('nan'), 0, 4], [0, 21, 5], [0, 0, 1]]),
                           ('extrinsics', [[1, 0, 0, 0], [0, 2, 0, 0], [0, 0, 1, 0]])]:
            with self.subTest(key=key, value=value):
                self.write(self.data, {'Cam005': dict(self.calibration, **{key: value})})
                with self.assertRaises(ValueError):
                    self.load()

    def test_requires_shape_or_real_image(self):
        self.delivery()
        calibration = dict(self.calibration)
        calibration.pop('shape')
        self.write(self.stage1, {'Cam005': calibration})
        with self.assertRaisesRegex(FileNotFoundError, 'calibration needs shape'):
            self.load()

    def test_metadata_only_input_requires_explicit_view_inventory(self):
        self.write(self.stage1, {'Cam005': self.calibration})
        with self.assertRaisesRegex(ValueError, 'No selected cameras'):
            self.load()

    def test_explicit_selection_and_limit(self):
        self.write(self.stage2, {f'Cam{i:03d}': self.calibration for i in range(10)})
        self.assertEqual(len(self.load().names), 8)
        self.assertEqual(self.load(names=['Cam009', 'Cam002']).names, ['Cam009', 'Cam002'])
        for names in [[], ['Cam002', 'Cam002'], [f'Cam{i:03d}' for i in range(9)]]:
            with self.assertRaises(ValueError):
                self.load(names=names)


if __name__ == '__main__':
    unittest.main()
