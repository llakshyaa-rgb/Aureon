import tempfile
import unittest
from pathlib import Path
from aureon.db import initialize
from aureon.workflows import initialize_workspace
from aureon.experiments import create_experiment, record_variant_observation, compare_experiment


class MarketingExperimentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "a.sqlite3"
        initialize(self.db)
        initialize_workspace(self.db)

    def tearDown(self):
        self.temp.cleanup()

    def test_variant_observations_aggregate_and_leader_is_descriptive(self):
        experiment = create_experiment(self.db, "Headline test", "Clear headline improves orders",
            "instagram", [{"key":"A","label":"Control"},{"key":"B","label":"Benefit-led"}])
        record_variant_observation(self.db, experiment["id"], "A",
            {"impressions":1000,"clicks":50,"orders":5,"spend":20,"revenue":100,"currency":"INR"})
        record_variant_observation(self.db, experiment["id"], "B",
            {"impressions":1000,"clicks":80,"orders":12,"spend":25,"revenue":180,"currency":"INR"})
        result = compare_experiment(self.db, experiment["id"])
        self.assertEqual(result["leading_variant"]["key"], "B")
        self.assertEqual(result["variants"][0]["conversion_rate"], 0.1)
        self.assertIn("No statistical significance", result["warning"])

    def test_variant_currency_mismatch_rejected(self):
        experiment = create_experiment(self.db, "Test", "Hypothesis", "email",
            [{"key":"A","label":"A"},{"key":"B","label":"B"}])
        record_variant_observation(self.db, experiment["id"], "A",
            {"impressions":10,"clicks":1,"orders":1,"currency":"USD"})
        with self.assertRaises(ValueError):
            record_variant_observation(self.db, experiment["id"], "B",
                {"impressions":10,"clicks":1,"orders":1,"currency":"INR"})

    def test_campaign_cannot_be_used_as_experiment(self):
        from aureon.marketing import create_campaign
        campaign = create_campaign(self.db, "Campaign", "Mug", "Readers", "instagram",
                                   "Good quality", "See more")
        with self.assertRaises(ValueError):
            compare_experiment(self.db, campaign["id"])


if __name__ == "__main__":
    unittest.main()
