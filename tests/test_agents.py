import unittest
from aureon.agents import plan_run

class AgentPlanTests(unittest.TestCase):
    def mission(self):
        return {
            "kind": "commerce.mission",
            "payload": {
                "product_title": "Astronomy T-shirt",
                "concept": "Minimalist planets and orbital lines",
                "audience": "Students and young adults",
                "product_type": "T-shirt",
                "destination": "India",
                "selling_price": 699,
                "product_cost": 280,
                "keywords": ["astronomy", "space", "minimalist"],
                "style": "geometric",
                "palette": "midnight",
                "currency": "INR",
                "geo": "IN",
                "shipping_cost": 60
            }
        }

    def test_commerce_mission_is_a_supported_ai_plan_task(self):
        plan = plan_run("Create astronomy shirt", [self.mission()])
        self.assertEqual(plan["tasks"][0]["kind"], "commerce.mission")
        self.assertEqual(plan["tasks"][0]["payload"]["selling_price"], 699)

    def test_commerce_mission_accepts_optional_cost_assumptions(self):
        task = self.mission()
        task["payload"]["platform_fee_rate"] = 0.05
        task["payload"]["payment_fee_rate"] = 0.02
        self.assertEqual(len(plan_run("Create shirt", [task])["tasks"]), 1)

    def test_commerce_mission_rejects_unknown_fields(self):
        task = self.mission()
        task["payload"]["publish_now"] = True
        with self.assertRaisesRegex(ValueError, "unsupported fields"):
            plan_run("Create shirt", [task])

    def test_commerce_mission_requires_core_product_inputs(self):
        task = self.mission()
        del task["payload"]["audience"]
        with self.assertRaisesRegex(ValueError, "missing audience"):
            plan_run("Create shirt", [task])

if __name__ == "__main__":
    unittest.main()
