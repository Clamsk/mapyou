"""Offline smoke/regression checks, not validation of scientific results."""
import unittest
import demo
import app


class DemoTests(unittest.TestCase):
    def setUp(self):
        self.client = demo.create_demo_app().test_client()
        self.weights = {k: 1.0 for k in app.FACILITY_CATEGORIES}
        self.radii = {k: v['default_radius'] for k, v in app.FACILITY_CATEGORIES.items()}

    def test_synthetic_shape(self):
        self.assertEqual(app.G.number_of_nodes(), 49)
        self.assertEqual(len(app.community_df), 6)
        self.assertEqual(len(app.facility_df), 32)

    def test_home_discloses_synthetic_data(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('合成数据演示', response.get_data(as_text=True))

    def test_health(self):
        result = self.client.get('/health').get_json()
        self.assertTrue(result['data_loaded'])
        self.assertTrue(result['synthetic_demo'])

    def test_calculate(self):
        response = self.client.post('/calculate', json={'leg_length': 0.85})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()['success'])
        self.assertIn('iframe', response.get_json()['map_html'])

    def test_documented_leg_length_limitation(self):
        row = app.community_df.iloc[0]
        a = app.calculate_accessibility(row, 0.5, self.weights, self.radii)
        b = app.calculate_accessibility(row, 1.2, self.weights, self.radii)
        self.assertEqual(a, b, 'Original server currently ignores leg length in facility counts')


if __name__ == '__main__':
    unittest.main()
