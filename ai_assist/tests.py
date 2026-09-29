from decimal import Decimal
from uuid import uuid4

from django.test import TestCase

from .models import AiAssistSession
from .session_logging import record_model_output


class SessionLoggingTests(TestCase):
    def test_record_model_output_aggregates_openrouter_cost(self):
        run_id = uuid4()
        AiAssistSession.objects.create(run_id=run_id, workflow="term_request")

        record_model_output(
            run_id,
            {"content": "result"},
            {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
                "cost": 0.00125,
            },
        )

        session = AiAssistSession.objects.get(run_id=run_id)
        self.assertEqual(session.cost_usd, Decimal("0.001250000000"))
