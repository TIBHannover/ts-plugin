import json
from unittest.mock import Mock, patch

from django.test import TestCase
from django.urls import reverse


class StartAgentViewTests(TestCase):
    @patch("demos.views.redis_client")
    @patch("demos.views.run_agent_task")
    def test_start_agent_returns_task_and_websocket_details(self, task, redis):
        task.delay.return_value = Mock(id="task-123")

        response = self.client.post(
            reverse("start_agent"),
            data=json.dumps({"input": "Find a parent term"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 202)
        payload = response.json()
        self.assertEqual(payload["task_id"], "task-123")
        self.assertIn(payload["run_id"], payload["websocket_path"])
        task.delay.assert_called_once_with(
            run_id=payload["run_id"], input_text="Find a parent term"
        )
        redis.delete.assert_called_once()

    @patch("demos.views.run_agent_task")
    def test_start_agent_rejects_invalid_json(self, task):
        response = self.client.post(
            reverse("start_agent"), data="{", content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)
        task.delay.assert_not_called()
