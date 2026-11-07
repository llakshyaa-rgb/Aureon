import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from aureon.agents import plan_run, chat_command
from aureon.db import initialize

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


    def test_chat_queues_full_mission_and_deduplicates_current_message(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "aureon.sqlite3"
            initialize(db)
            message = ("Create an astronomy T-shirt for students in India. "
                       "Selling price 699 INR, product cost 280 INR, shipping 60 INR. "
                       "Make the design, listing, economics and marketing drafts.")
            task = self.mission()
            response = {"content": json.dumps({
                "reply": "I'll prepare the product workflow and save the local drafts.",
                "tasks": [task], "needs_input": ""
            }), "provider": "test", "model": "test-model"}
            with patch("aureon.llm.generate", return_value=response) as generate:
                result = chat_command(db, message, [
                    {"role": "user", "content": message}
                ])
            self.assertEqual(result["status"], "queued")
            prompt = generate.call_args.args[2]
            self.assertEqual(prompt.count(message), 1)

    def test_chat_rejects_unhelpful_short_response_to_long_request(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "aureon.sqlite3"
            initialize(db)
            message = ("Please research and create a complete product launch workflow "
                       "with design, pricing, listing and marketing drafts.")
            response = {"content": json.dumps({
                "reply": "interests", "tasks": [], "needs_input": ""
            }), "provider": "test", "model": "test-model"}
            with patch("aureon.llm.generate", return_value=response):
                with self.assertRaisesRegex(RuntimeError, "incomplete answer"):
                    chat_command(db, message)


if __name__ == "__main__":
    unittest.main()
