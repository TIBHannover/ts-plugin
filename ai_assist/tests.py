import json
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, call, patch

from django.test import TestCase
from django.urls import reverse

from . import agents, tasks


class StartAgentViewTests(TestCase):
    @patch("ai_assist.views.redis_client")
    @patch("ai_assist.views.run_agent_task")
    @patch("user_service.libs.decorators.Auth")
    @patch("user_service.libs.decorators.get_headers_dict", return_value={})
    @patch("user_service.libs.decorators.get_username_from_request", return_value="alice")
    @patch("user_service.libs.decorators.is_csrf_valid", return_value=True)
    @patch("ai_assist.views.get_username_from_request", return_value="alice")
    @patch("ai_assist.views.build_user_prompt", return_value="normalized prompt")
    def test_start_agent_returns_task_token_and_websocket_details(self, build_prompt, view_owner, csrf, owner, headers, auth, task, redis):
        task.delay.return_value = Mock(id="task-123")

        response = self.client.post(
            reverse("start_agent"),
            data=json.dumps({"label": "New term", "description": "A useful definition", "category": "Process"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 202)
        payload = response.json()
        self.assertEqual(payload["task_id"], "task-123")
        self.assertTrue(payload["websocket_token"])
        self.assertEqual(
            payload["websocket_path"],
            f"/ws/ai_assist/agent/{payload['run_id']}/",
        )
        build_prompt.assert_called_once_with(
            "New term",
            "A useful definition",
            "Process:activity,event,action,occurrence,procedure",
        )
        task.delay.assert_called_once_with(
            run_id=payload["run_id"], input_text="normalized prompt"
        )
        redis.delete.assert_called_once()

    def test_start_agent_requires_authentication(self):
        response = self.client.post(
            reverse("start_agent"), data=json.dumps({"input": "x"}), content_type="application/json"
        )

        self.assertIn(response.status_code, (401, 403))

    @patch("ai_assist.views.run_agent_task")
    @patch("user_service.libs.decorators.Auth")
    @patch("user_service.libs.decorators.get_headers_dict", return_value={})
    @patch("user_service.libs.decorators.get_username_from_request", return_value="alice")
    @patch("user_service.libs.decorators.is_csrf_valid", return_value=True)
    def test_start_agent_rejects_invalid_json(self, csrf, owner, headers, auth, task):
        response = self.client.post(
            reverse("start_agent"), data="{", content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)
        task.delay.assert_not_called()

    @patch("ai_assist.views.run_agent_task")
    @patch("user_service.libs.decorators.Auth")
    @patch("user_service.libs.decorators.get_headers_dict", return_value={})
    @patch("user_service.libs.decorators.get_username_from_request", return_value="alice")
    @patch("user_service.libs.decorators.is_csrf_valid", return_value=True)
    def test_start_agent_rejects_non_object_json_bodies(self, csrf, owner, headers, auth, task):
        for body in ("[]", '"text"', "null"):
            with self.subTest(body=body):
                response = self.client.post(
                    reverse("start_agent"), data=body, content_type="application/json"
                )
                self.assertEqual(response.status_code, 400)

        task.delay.assert_not_called()

    @patch("ai_assist.views.run_agent_task")
    @patch("user_service.libs.decorators.Auth")
    @patch("user_service.libs.decorators.get_headers_dict", return_value={})
    @patch("user_service.libs.decorators.get_username_from_request", return_value="alice")
    @patch("user_service.libs.decorators.is_csrf_valid", return_value=True)
    def test_start_agent_rejects_missing_required_fields(self, csrf, owner, headers, auth, task):
        response = self.client.post(
            reverse("start_agent"),
            data=json.dumps({"label": "Term", "description": "Definition"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        task.delay.assert_not_called()

    @patch("ai_assist.views.run_agent_task")
    @patch("user_service.libs.decorators.Auth")
    @patch("user_service.libs.decorators.get_headers_dict", return_value={})
    @patch("user_service.libs.decorators.get_username_from_request", return_value="alice")
    @patch("user_service.libs.decorators.is_csrf_valid", return_value=True)
    def test_start_agent_rejects_unsupported_category(self, csrf, owner, headers, auth, task):
        response = self.client.post(
            reverse("start_agent"),
            data=json.dumps({"label": "Term", "description": "Definition", "category": "Unknown"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        task.delay.assert_not_called()

    @patch("ai_assist.views.redis_client")
    @patch("ai_assist.views.run_agent_task")
    @patch("user_service.libs.decorators.Auth")
    @patch("user_service.libs.decorators.get_headers_dict", return_value={})
    @patch("user_service.libs.decorators.get_username_from_request", return_value="alice")
    @patch("user_service.libs.decorators.is_csrf_valid", return_value=True)
    @patch("ai_assist.views.get_username_from_request", return_value="alice")
    def test_start_agent_rolls_back_when_task_enqueue_fails(self, view_owner, csrf, owner, headers, auth, task, redis):
        redis.set.return_value = True
        task.delay.side_effect = RuntimeError("broker unavailable")

        response = self.client.post(
            reverse("start_agent"),
            data=json.dumps({"label": "Term", "description": "Definition", "category": "Process"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 503)
        deleted_keys = redis.delete.call_args.args
        self.assertIn("agent:", deleted_keys[0])
        self.assertTrue(any(key.endswith(":owner") for key in deleted_keys))
        self.assertTrue(any(key.endswith(":socket_token") for key in deleted_keys))

class AgentTests(TestCase):
    @patch("ai_assist.agents.validate_final_response", return_value=(True, '{"parent_label": "P", "ontology": "O", "parent_iri": "I"}', ""))
    @patch("ai_assist.agents.call_openrouter")
    def test_run_agent_records_final_json_response(self, call_openrouter, validate):
        call_openrouter.return_value = (
            {"content": '{"parent_label": "P", "ontology": "O", "parent_iri": "I"}'},
            {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
        )
        result = {"usage_stats": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}, "search_call_count": 0, "is_final": False, "needs_user_input": False}
        messages = []

        agents.run_agent(messages, result)

        self.assertTrue(result["is_final"])
        self.assertEqual(result["parent_iri"], "I")
        self.assertEqual(result["usage_stats"]["total_tokens"], 3)
        self.assertEqual(messages[-1]["content"], call_openrouter.return_value[0]["content"])
        validate.assert_called_once()

    @patch("ai_assist.agents.call_openrouter")
    def test_run_agent_pauses_for_assistant_question(self, call_openrouter):
        call_openrouter.return_value = (
            {"content": '{"question": "Which domain should I use?"}'},
            {},
        )
        result = {"usage_stats": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}, "search_call_count": 0, "is_final": False, "needs_user_input": False}
        messages = []

        agents.run_agent(messages, result)

        self.assertTrue(result["needs_user_input"])
        self.assertEqual(result["question"], "Which domain should I use?")
        self.assertFalse(result["is_final"])


class AgentTaskTests(TestCase):
    @patch("ai_assist.tasks.fail_run")
    @patch("ai_assist.tasks.redis_client")
    def test_initial_ready_queue_failure_marks_run_failed(self, redis, fail_run):
        redis.blpop.side_effect = RuntimeError("Redis unavailable")

        tasks.run_agent_task("run-1", "start")

        fail_run.assert_called_once_with("run-1")

    @patch("ai_assist.tasks.fail_run")
    @patch("ai_assist.tasks.redis_client")
    def test_resume_state_read_failure_marks_run_failed(self, redis, fail_run):
        redis.get.side_effect = RuntimeError("Redis unavailable")

        tasks.resume_agent_task("run-1")

        fail_run.assert_called_once_with("run-1")

    @patch("ai_assist.tasks.cleanup_run")
    @patch("ai_assist.tasks.emit")
    @patch("ai_assist.tasks.redis_client")
    def test_run_agent_exception_emits_error_and_cleans_up(self, redis, emit, cleanup):
        redis.get.return_value = None
        state = {"messages": [], "response": tasks.new_response(), "steps": 0}

        with patch("ai_assist.tasks.run_agent", side_effect=RuntimeError("LLM unavailable")):
            tasks.run_conversation("run-1", state)

        self.assertEqual(emit.call_args.args[0], {"type": "error", "message": "Assistant run failed."})
        cleanup.assert_called_once_with("run-1")

    @patch("ai_assist.tasks.cleanup_run")
    @patch("ai_assist.tasks.run_agent")
    @patch("ai_assist.tasks.redis_client")
    def test_worker_aborts_when_socket_never_becomes_ready(self, redis, run_agent, cleanup):
        redis.blpop.return_value = None

        tasks.run_agent_task("run-1", "start")

        run_agent.assert_not_called()
        cleanup.assert_called_once_with("run-1")

    @patch("ai_assist.tasks.emit")
    @patch("ai_assist.tasks.redis_client")
    def test_worker_allows_at_most_40_llm_turns(self, redis, emit):
        redis.get.return_value = None
        redis.lpop.return_value = None
        state = {"messages": [], "response": tasks.new_response(), "steps": 0}

        with patch("ai_assist.tasks.run_agent", side_effect=lambda messages, response: None) as run_agent:
            tasks.run_conversation("run-1", state)

        self.assertEqual(run_agent.call_count, tasks.AGENT_MAX_LOOPS)
        self.assertTrue(any(entry.args[0]["type"] == "error" for entry in emit.call_args_list))

    @patch("ai_assist.tasks.save_state")
    @patch("ai_assist.tasks.emit")
    @patch("ai_assist.tasks.redis_client")
    def test_worker_persists_resumable_state_when_question_is_needed(self, redis, emit, save_state):
        redis.get.return_value = None
        state = {"messages": [], "response": tasks.new_response(), "steps": 0}

        with patch("ai_assist.tasks.run_agent", side_effect=lambda messages, response: response.update(needs_user_input=True, question="Clarify")):
            tasks.run_conversation("run-1", state)

        self.assertEqual(state["steps"], 1)
        save_state.assert_called_once_with("run-1", state)
        self.assertTrue(any(entry.args[0]["type"] == "question" for entry in emit.call_args_list))

    @patch("ai_assist.tasks.run_conversation")
    @patch("ai_assist.tasks.redis_client")
    def test_resume_task_loads_saved_state(self, redis, run_conversation):
        saved = {"messages": [], "response": tasks.new_response(), "steps": 3}
        redis.get.return_value = json.dumps(saved)

        tasks.resume_agent_task("run-1")

        run_conversation.assert_called_once_with("run-1", saved)

    @patch("ai_assist.tasks.redis_client")
    def test_pending_feedback_is_drained_in_fifo_order(self, redis):
        redis.lpop.side_effect = ["first", "second", None]
        messages = []

        tasks.add_pending_user_input(messages, "run-1")

        self.assertEqual(
            messages,
            [
                {"role": "user", "content": "first"},
                {"role": "user", "content": "second"},
            ],
        )


class AgentConsumerTests(IsolatedAsyncioTestCase):
    def make_consumer(self, token="secret"):
        from .consumers import AgentConsumer

        consumer = AgentConsumer()
        consumer.scope = {
            "url_route": {"kwargs": {"run_id": "run-1"}},
            "query_string": f"token={token}".encode(),
        }
        consumer.channel_layer = Mock()
        consumer.channel_layer.group_add = AsyncMock()
        consumer.channel_layer.group_discard = AsyncMock()
        consumer.channel_name = "channel-1"
        consumer.accept = AsyncMock()
        consumer.close = AsyncMock()
        consumer.send = AsyncMock()
        return consumer

    @patch("ai_assist.consumers.redis_client")
    async def test_connect_requires_socket_token_and_marks_run_ready(self, redis):
        consumer = self.make_consumer()
        redis.get.return_value = "secret"
        consumer.send_json = AsyncMock()

        with patch("ai_assist.consumers.sync_to_async", side_effect=lambda fn: AsyncMock(side_effect=fn)):
            await consumer.connect()

        consumer.accept.assert_awaited_once()
        redis.rpush.assert_called_once_with("agent:run-1:ready", "1")
        redis.expire.assert_called_once_with("agent:run-1:ready", 60)
        consumer.send_json.assert_awaited_once_with({"type": "connected", "run_id": "run-1"})

    @patch("ai_assist.consumers.redis_client")
    async def test_connect_rejects_wrong_socket_token(self, redis):
        consumer = self.make_consumer(token="wrong")
        redis.get.return_value = "secret"

        with patch("ai_assist.consumers.sync_to_async", side_effect=lambda fn: AsyncMock(side_effect=fn)):
            await consumer.connect()

        consumer.close.assert_awaited_once_with(code=4403)
        consumer.accept.assert_not_awaited()
        redis.rpush.assert_not_called()

    @patch("ai_assist.consumers.redis_client")
    async def test_receive_user_message_queues_and_resumes_waiting_run(self, redis):
        consumer = self.make_consumer()
        redis.rpush.return_value = 1
        redis.get.return_value = "1"
        redis.set.return_value = True

        with patch("ai_assist.consumers.sync_to_async", side_effect=lambda fn: AsyncMock(side_effect=fn)), patch("ai_assist.consumers.current_app.send_task") as send_task:
            await consumer.receive(text_data=json.dumps({"type": "user_message", "message": "feedback"}))

        redis.rpush.assert_called_once_with("agent:run-1:input", "feedback")
        redis.expire.assert_called_once_with("agent:run-1:input", 3600)
        redis.set.assert_called_once_with("agent:run-1:resuming", "1", nx=True, ex=60)
        redis.delete.assert_called_once_with(
            "agent:run-1:awaiting_input", "agent:run-1:resuming"
        )
        send_task.assert_called_once_with("ai_assist.tasks.resume_agent_task", args=["run-1"])

    @patch("ai_assist.consumers.redis_client")
    async def test_resume_dispatch_failure_keeps_awaiting_state(self, redis):
        consumer = self.make_consumer()
        consumer.send_json = AsyncMock()
        redis.get.return_value = "1"
        redis.set.return_value = True

        with patch("ai_assist.consumers.sync_to_async", side_effect=lambda fn: AsyncMock(side_effect=fn)), patch(
            "ai_assist.consumers.current_app.send_task", side_effect=RuntimeError("broker unavailable")
        ):
            await consumer.receive(
                text_data=json.dumps({"type": "user_message", "message": "reply"})
            )

        consumer.send_json.assert_awaited_once_with(
            {"type": "error", "message": "Unable to resume assistant."}
        )
        redis.delete.assert_called_once_with("agent:run-1:resuming")
        self.assertNotIn(
            call("agent:run-1:awaiting_input"), redis.delete.call_args_list
        )

    @patch("ai_assist.consumers.redis_client")
    async def test_receive_uses_text_data_and_rejects_invalid_json(self, redis):
        consumer = self.make_consumer()
        consumer.send_json = AsyncMock()

        with patch("ai_assist.consumers.sync_to_async", side_effect=lambda fn: AsyncMock(side_effect=fn)):
            await consumer.receive(text_data="{")

        consumer.send_json.assert_awaited_once_with({"type": "error", "message": "Invalid JSON."})
        redis.rpush.assert_not_called()
