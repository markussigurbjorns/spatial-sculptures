"""Check independent experiments, causal dripping, and inactive feedback outside Blender."""

import importlib
import math
import unittest

prototype = importlib.import_module("prototypes.001_resonant_surface.build")
simulation = importlib.import_module("prototypes.001_resonant_surface.simulation")
feedback = importlib.import_module("prototypes.001_resonant_surface.feedback")


class PrototypeTests(unittest.TestCase):
    def test_experiments_do_not_change_defaults(self) -> None:
        baseline = prototype.load_config()
        close = prototype.load_config("002_close_frequencies")
        close.exciters[0]["amplitude"] = 8
        baseline.basin["radius_x"] = 2
        fresh = prototype.load_config()
        self.assertEqual(fresh.basin["radius_x"], 0.72)
        self.assertEqual(fresh.exciters[0]["amplitude"], 1)
        self.assertEqual(fresh.exciters[1]["frequency"], 61.3)
        self.assertEqual(prototype.load_config("001_three_exciters"), fresh)

    def test_close_frequency_beating_is_sampled(self) -> None:
        config = prototype.load_config("002_close_frequencies")
        frequencies = [source["frequency"] for source in config.exciters]
        self.assertEqual(frequencies, [59, 59.08, 59.17])
        beat_period = 1 / ((frequencies[1] - frequencies[0]) * config.water["time_scale"])
        self.assertAlmostEqual(beat_period, 12.5)
        self.assertGreater(config.animation["seconds"], beat_period)
        self.assertGreater(config.animation["fps"], 2 * max(frequencies))

    def test_drop_and_ripple_share_the_impact_clock(self) -> None:
        config = prototype.load_config()
        interval = config.drip["interval"]
        self.assertEqual(simulation.impact_ages(interval - 0.01, config), ())
        self.assertTrue(simulation.droplet_state(interval - 0.01, config)[0])
        self.assertFalse(simulation.droplet_state(interval, config)[0])
        self.assertEqual(simulation.impact_ages(interval, config), (0.0,))
        self.assertAlmostEqual(simulation.impact_ages(interval + 0.2, config)[0], 0.2)
        self.assertTrue(all(age <= 5 for age in simulation.impact_ages(20, config)))

    def test_later_impacts_are_not_delayed_by_float_rounding(self) -> None:
        config = prototype.load_config()
        for time in (3.2, 6.4, 9.6, 12.8, 16.0, 19.2):
            self.assertFalse(simulation.droplet_state(time, config)[0])
            self.assertAlmostEqual(simulation.impact_ages(time, config)[-1], 0.0)

    def test_fixed_water_edge_and_finite_field(self) -> None:
        config = prototype.load_config()
        self.assertAlmostEqual(simulation.displacement(config.water["radius_x"], 0, 5, config), 0.0)
        for time in (0, 3.2, 3.4, 10, 20):
            value = simulation.displacement(0.2, -0.1, time, config)
            self.assertTrue(math.isfinite(value))
            self.assertLess(abs(value), 0.05)

    def test_feedback_is_a_proposal_without_configuration_mutation(self) -> None:
        config = prototype.load_config()
        samples = feedback.sample_field(config, 3.4)
        self.assertEqual(set(samples), {"hydrophone_1", "hydrophone_2"})
        routes = [feedback.FeedbackRoute("hydrophone_1", 2, gain=1000, limit=0.02)]
        targets = feedback.apply_feedback(samples, routes)
        self.assertLessEqual(abs(targets[2]), 0.02)
        self.assertEqual(config, prototype.load_config())

    def test_unknown_experiment_and_invalid_drip_fail_early(self) -> None:
        with self.assertRaises(ValueError):
            prototype.load_config("../missing")
        config = prototype.load_config()
        config.drip["interval"] = 0
        with self.assertRaises(ValueError):
            config.validate()


if __name__ == "__main__":
    unittest.main()
