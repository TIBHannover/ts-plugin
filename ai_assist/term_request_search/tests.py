import json
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, call, patch

from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from ai_assist import tasks
from ai_assist.consumers import AgentConsumer
from ai_assist import routing as root_routing
from ai_assist import urls as root_urls
from ai_assist import views as root_views
from ai_assist import transport

from . import agent, runner, state as workflow_state
from . import views as workflow_views


class PackageFacadeTests(SimpleTestCase):
    def test_root_facades_preserve_workflow_routes_and_views(self):
        self.assertEqual(
            [pattern.name for pattern in root_urls.urlpatterns],
            ["start_agent", "start_search", "start_term_request"],
        )
        self.assertIs(root_views.start_agent, workflow_views.start_agent)
        self.assertIs(root_views.start_search, workflow_views.start_search)
        self.assertIs(root_views.start_term_request, workflow_views.start_term_request)
        self.assertEqual(
            str(root_routing.websocket_urlpatterns[0].pattern),
            "ws/ai_assist/agent/<uuid:run_id>/",
        )

    def test_transport_values_preserve_existing_wire_contract(self):
        self.assertEqual(transport.run_redis_key("run-1", transport.RUN_REDIS_KEY_READY), "agent:run-1:ready")
        self.assertEqual(transport.run_group_name("run-1"), "agent_run_run-1")
        self.assertEqual(transport.WEBSOCKET_PATH_TEMPLATE, "/ws/ai_assist/agent/{run_id}/")
        self.assertEqual(transport.SERVER_MESSAGE_TYPE_CONNECTED, "connected")


class RootConsumerTests(IsolatedAsyncioTestCase):
    async def test_root_consumer_is_workflow_independent(self):
        with self.assertRaises(NotImplementedError):
            await AgentConsumer().handle_workflow_message({"type": "message"})


@override_settings(AI_ASSIST_ENABLED=True)
class StartAgentViewTests(TestCase):
    @patch("ai_assist.term_request_search.views.redis_client")
    @patch("ai_assist.term_request_search.views.run_agent_task")
    @patch("user_service.libs.decorators.Auth")
    @patch("user_service.libs.decorators.get_headers_dict", return_value={})
    @patch("user_service.libs.decorators.get_username_from_request", return_value="alice")
    @patch("user_service.libs.decorators.is_csrf_valid", return_value=True)
    @patch("ai_assist.term_request_search.views.build_term_request_agent_input", return_value="normalized prompt")
    def test_start_agent_returns_task_token_and_websocket_details(self, build_prompt, csrf, owner, headers, auth, task, redis):
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

    @patch("ai_assist.term_request_search.views.redis_client")
    @patch("ai_assist.term_request_search.views.run_agent_task")
    @patch("user_service.libs.decorators.Auth")
    @patch("user_service.libs.decorators.get_headers_dict", return_value={})
    @patch("user_service.libs.decorators.get_username_from_request", return_value="alice")
    @patch("user_service.libs.decorators.is_csrf_valid", return_value=True)
    @patch("ai_assist.term_request_search.views.build_search_agent_input", return_value="search prompt")
    def test_start_search_preserves_search_workflow_contract(
        self, build_prompt, csrf, owner, headers, auth, task, redis
    ):
        task.delay.return_value = Mock(id="search-task")

        response = self.client.post(
            reverse("start_search"),
            data=json.dumps({"description": "Find an existing term"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["workflow"], "search")
        build_prompt.assert_called_once_with("Find an existing term")
        task.delay.assert_called_once_with(
            run_id=response.json()["run_id"],
            input_text="search prompt",
            workflow="search",
        )

    @override_settings(AI_ASSIST_ENABLED=False)
    @patch("ai_assist.term_request_search.views.run_agent_task")
    @patch("user_service.libs.decorators.Auth")
    @patch("user_service.libs.decorators.get_headers_dict", return_value={})
    @patch("user_service.libs.decorators.get_username_from_request", return_value="alice")
    @patch("user_service.libs.decorators.is_csrf_valid", return_value=True)
    def test_start_search_is_disabled(self, csrf, owner, headers, auth, task):
        response = self.client.post(
            reverse("start_search"),
            data=json.dumps({"description": "Find an existing term"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)
        task.delay.assert_not_called()

    def test_start_agent_requires_authentication(self):
        response = self.client.post(
            reverse("start_agent"), data=json.dumps({"input": "x"}), content_type="application/json"
        )

        self.assertIn(response.status_code, (401, 403))

    @override_settings(AI_ASSIST_ENABLED=False)
    @patch("ai_assist.term_request_search.views.run_agent_task")
    @patch("user_service.libs.decorators.Auth")
    @patch("user_service.libs.decorators.get_headers_dict", return_value={})
    @patch("user_service.libs.decorators.get_username_from_request", return_value="alice")
    @patch("user_service.libs.decorators.is_csrf_valid", return_value=True)
    def test_start_agent_is_disabled_by_default(self, csrf, owner, headers, auth, task):
        response = self.client.post(
            reverse("start_agent"),
            data=json.dumps(
                {
                    "label": "New term",
                    "description": "A useful definition",
                    "category": "Process",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)
        task.delay.assert_not_called()

    @patch("ai_assist.term_request_search.views.run_agent_task")
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

    @patch("ai_assist.term_request_search.views.run_agent_task")
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

    @patch("ai_assist.term_request_search.views.run_agent_task")
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

    @patch("ai_assist.term_request_search.views.run_agent_task")
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

    @patch("ai_assist.term_request_search.views.redis_client")
    @patch("ai_assist.term_request_search.views.run_agent_task")
    @patch("user_service.libs.decorators.Auth")
    @patch("user_service.libs.decorators.get_headers_dict", return_value={})
    @patch("user_service.libs.decorators.get_username_from_request", return_value="alice")
    @patch("user_service.libs.decorators.is_csrf_valid", return_value=True)
    def test_start_agent_rolls_back_when_task_enqueue_fails(self, csrf, owner, headers, auth, task, redis):
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
    @patch("ai_assist.term_request_search.agent.validate_term_request_agent_response", return_value=(True, '{"candidates": [{"parent_label": "P", "ontology": "O", "parent_iri": "I"}, {"parent_label": "P2", "ontology": "O", "parent_iri": "I2"}, {"parent_label": "P3", "ontology": "O", "parent_iri": "I3"}]}', ""))
    @patch("ai_assist.term_request_search.agent.call_openrouter")
    def test_term_request_agent_records_final_json_response(self, call_openrouter, validate):
        call_openrouter.return_value = (
            {"content": '{"candidates": [{"parent_label": "P", "ontology": "O", "parent_iri": "I"}, {"parent_label": "P2", "ontology": "O", "parent_iri": "I2"}, {"parent_label": "P3", "ontology": "O", "parent_iri": "I3"}]}'},
            {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
        )
        result = {"usage_stats": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}, "search_call_count": 0, "is_final": False, "needs_user_input": False}
        messages = []

        agent.run_term_request_or_search_agent_turn(messages, result)

        self.assertTrue(result["is_final"])
        self.assertEqual(result["candidates"][0]["parent_iri"], "I")
        self.assertEqual(result["usage_stats"]["total_tokens"], 3)
        self.assertEqual(messages[-1]["content"], call_openrouter.return_value[0]["content"])
        validate.assert_called_once()

    @patch("ai_assist.term_request_search.agent.call_openrouter")
    def test_term_request_agent_pauses_for_assistant_question(self, call_openrouter):
        call_openrouter.return_value = (
            {"content": '{"question": "Which domain should I use?"}'},
            {},
        )
        result = {"usage_stats": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}, "search_call_count": 0, "is_final": False, "needs_user_input": False}
        messages = []

        agent.run_term_request_or_search_agent_turn(messages, result)

        self.assertTrue(result["needs_user_input"])
        self.assertEqual(result["question"], "Which domain should I use?")
        self.assertFalse(result["is_final"])

    @patch("ai_assist.term_request_search.agent.get_term_detail", return_value={})
    def test_term_request_agent_response_requires_three_distinct_candidates(self, get_term_detail):
        content = json.dumps(
            {
                "candidates": [
                    {"parent_label": "P", "ontology": "O", "parent_iri": "I"},
                    {"parent_label": "P2", "ontology": "O", "parent_iri": "I2"},
                ]
            }
        )

        is_valid, _, _ = agent.validate_term_request_agent_response(content)

        self.assertFalse(is_valid)
        get_term_detail.assert_not_called()


class AgentTaskTests(TestCase):
    @patch("ai_assist.tasks.run_term_request_search_agent")
    def test_celery_start_task_delegates_without_changing_signature(self, run_agent):
        tasks.run_agent_task("run-1", "input", "search")

        self.assertEqual(tasks.run_agent_task.name, "ai_assist.tasks.run_agent_task")
        run_agent.assert_called_once_with("run-1", "input", "search")

    @patch("ai_assist.tasks.resume_term_request_search_agent")
    def test_celery_resume_task_delegates_without_changing_signature(self, resume_agent):
        tasks.resume_agent_task("run-1")

        self.assertEqual(tasks.resume_agent_task.name, "ai_assist.tasks.resume_agent_task")
        resume_agent.assert_called_once_with("run-1")

    @patch("ai_assist.term_request_search.runner.cleanup_run")
    @patch("ai_assist.term_request_search.runner.emit_no_parent_found")
    @patch("ai_assist.term_request_search.runner.redis_client")
    @patch("ai_assist.term_request_search.runner.TERM_REQUEST_AGENT_MAX_REJECTIONS", 1)
    def test_resume_after_rejection_limit_terminates_and_cleans_up(
        self, redis, emit_no_parent_found, cleanup
    ):
        redis.get.side_effect = [json.dumps({"messages": [], "response": workflow_state.new_response(), "steps": 1}), "2"]

        runner.resume_term_request_search_agent("run-1")

        emit_no_parent_found.assert_called_once_with("run-1")
        cleanup.assert_called_once_with("run-1")

    @patch("ai_assist.term_request_search.runner.emit")
    def test_emit_done_sends_candidates(self, emit):
        candidates = [
            {"parent_label": "P", "ontology": "O", "parent_iri": "I"},
            {"parent_label": "P2", "ontology": "O", "parent_iri": "I2"},
            {"parent_label": "P3", "ontology": "O", "parent_iri": "I3"},
        ]

        runner.emit_done({"candidates": candidates, "error": None}, "run-1")

        emit.assert_called_once_with(
            {"type": "done", "candidates": candidates, "error": None}, "run-1"
        )

    @patch("ai_assist.term_request_search.runner.fail_run")
    @patch("ai_assist.term_request_search.runner.redis_client")
    def test_initial_ready_queue_failure_marks_run_failed(self, redis, fail_run):
        redis.blpop.side_effect = RuntimeError("Redis unavailable")

        runner.run_term_request_search_agent("run-1", "start")

        fail_run.assert_called_once_with("run-1")

    @patch("ai_assist.term_request_search.runner.fail_run")
    @patch("ai_assist.term_request_search.runner.redis_client")
    def test_resume_state_read_failure_marks_run_failed(self, redis, fail_run):
        redis.get.side_effect = RuntimeError("Redis unavailable")

        runner.resume_term_request_search_agent("run-1")

        fail_run.assert_called_once_with("run-1")

    @patch("ai_assist.term_request_search.runner.cleanup_run")
    @patch("ai_assist.term_request_search.runner.emit")
    @patch("ai_assist.term_request_search.runner.redis_client")
    def test_run_agent_exception_emits_error_and_cleans_up(self, redis, emit, cleanup):
        redis.get.return_value = None
        state = {"messages": [], "response": workflow_state.new_response(), "steps": 0}

        with patch("ai_assist.term_request_search.runner.run_term_request_or_search_agent_turn", side_effect=RuntimeError("LLM unavailable")):
            runner.run_conversation("run-1", state)

        self.assertEqual(emit.call_args.args[0], {"type": "error", "message": "Assistant run failed."})
        cleanup.assert_called_once_with("run-1")

    @patch("ai_assist.term_request_search.runner.cleanup_run")
    @patch("ai_assist.term_request_search.runner.run_term_request_or_search_agent_turn")
    @patch("ai_assist.term_request_search.runner.redis_client")
    def test_worker_aborts_when_socket_never_becomes_ready(self, redis, run_agent, cleanup):
        redis.blpop.return_value = None

        runner.run_term_request_search_agent("run-1", "start")

        run_agent.assert_not_called()
        cleanup.assert_called_once_with("run-1")

    @patch("ai_assist.term_request_search.runner.emit")
    @patch("ai_assist.term_request_search.runner.redis_client")
    def test_worker_allows_at_most_40_llm_turns(self, redis, emit):
        redis.get.return_value = None
        redis.lpop.return_value = None
        state = {"messages": [], "response": workflow_state.new_response(), "steps": 0}

        with patch("ai_assist.term_request_search.runner.run_term_request_or_search_agent_turn", side_effect=lambda messages, response: None) as run_agent:
            runner.run_conversation("run-1", state)

        self.assertEqual(run_agent.call_count, runner.TERM_REQUEST_AGENT_MAX_LOOPS)
        self.assertTrue(any(entry.args[0]["type"] == "error" for entry in emit.call_args_list))

    @patch("ai_assist.term_request_search.runner.save_state")
    @patch("ai_assist.term_request_search.runner.emit")
    @patch("ai_assist.term_request_search.runner.redis_client")
    def test_worker_persists_resumable_state_when_question_is_needed(self, redis, emit, save_state):
        redis.get.return_value = None
        state = {"messages": [], "response": workflow_state.new_response(), "steps": 0}

        with patch("ai_assist.term_request_search.runner.run_term_request_or_search_agent_turn", side_effect=lambda messages, response: response.update(needs_user_input=True, question="Clarify")):
            runner.run_conversation("run-1", state)

        self.assertEqual(state["steps"], 1)
        save_state.assert_called_once_with("run-1", state)
        self.assertTrue(any(entry.args[0]["type"] == "question" for entry in emit.call_args_list))

    @patch("ai_assist.term_request_search.runner.run_conversation")
    @patch("ai_assist.term_request_search.runner.redis_client")
    def test_resume_task_loads_saved_state(self, redis, run_conversation):
        saved = {"messages": [], "response": workflow_state.new_response(), "steps": 3}
        redis.get.return_value = json.dumps(saved)

        runner.resume_term_request_search_agent("run-1")

        run_conversation.assert_called_once_with("run-1", saved)

    @patch("ai_assist.term_request_search.runner.redis_client")
    def test_pending_feedback_is_drained_in_fifo_order(self, redis):
        redis.lpop.side_effect = ["first", "second", None]
        messages = []

        runner.add_pending_user_input(messages, "run-1")

        self.assertEqual(
            messages,
            [
                {"role": "user", "content": "first"},
                {"role": "user", "content": "second"},
            ],
        )


class AgentConsumerTests(IsolatedAsyncioTestCase):
    def setUp(self):
        self.settings_override = override_settings(AI_ASSIST_ENABLED=True)
        self.settings_override.enable()

    def tearDown(self):
        self.settings_override.disable()

    def make_consumer(self, token="secret"):
        from .consumer import TermRequestSearchConsumer

        consumer = TermRequestSearchConsumer()
        consumer.run_id = "run-1"
        consumer.group_name = "agent_run_run-1"
        consumer.scope = {
            "url_route": {"kwargs": {"run_id": "run-1"}},
            "query_string": f"token={token}".encode(),
        }
        consumer.channel_layer = Mock()
        consumer.channel_layer.group_add = AsyncMock()
        consumer.channel_layer.group_discard = AsyncMock()
        consumer.channel_layer.group_send = AsyncMock()
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

    @override_settings(AI_ASSIST_ENABLED=False)
    @patch("ai_assist.consumers.redis_client")
    async def test_connect_rejects_when_assist_is_disabled(self, redis):
        consumer = self.make_consumer()

        await consumer.connect()
        await consumer.disconnect(4403)

        consumer.close.assert_awaited_once_with(code=4403)
        consumer.accept.assert_not_awaited()
        consumer.channel_layer.group_discard.assert_not_awaited()
        redis.get.assert_not_called()

    @patch("ai_assist.consumers.redis_client")
    async def test_connect_rejects_wrong_socket_token(self, redis):
        consumer = self.make_consumer(token="wrong")
        redis.get.return_value = "secret"

        with patch("ai_assist.consumers.sync_to_async", side_effect=lambda fn: AsyncMock(side_effect=fn)):
            await consumer.connect()

        consumer.close.assert_awaited_once_with(code=4403)
        consumer.accept.assert_not_awaited()
        redis.rpush.assert_not_called()

    @patch("ai_assist.term_request_search.messages.redis_client")
    async def test_receive_user_message_queues_and_resumes_waiting_run(self, redis):
        consumer = self.make_consumer()
        redis.rpush.return_value = 1
        redis.get.return_value = "1"
        redis.set.return_value = True

        with patch("ai_assist.term_request_search.messages.sync_to_async", side_effect=lambda fn: AsyncMock(side_effect=fn)), patch("ai_assist.term_request_search.messages.current_app.send_task") as send_task:
            await consumer.receive(text_data=json.dumps({"type": "user_message", "message": "feedback"}))

        redis.rpush.assert_called_once_with("agent:run-1:input", "feedback")
        redis.expire.assert_called_once_with("agent:run-1:input", 3600)
        redis.set.assert_called_once_with("agent:run-1:resuming", "1", nx=True, ex=60)
        redis.delete.assert_called_once_with(
            "agent:run-1:awaiting_input", "agent:run-1:resuming"
        )
        send_task.assert_called_once_with("ai_assist.tasks.resume_agent_task", args=["run-1"])

    @patch("ai_assist.term_request_search.messages.redis_client")
    async def test_reject_waiting_recommendations_requests_a_reason(self, redis):
        consumer = self.make_consumer()
        redis.get.return_value = "1"
        redis.set.return_value = True
        redis.incr.return_value = 1

        with patch("ai_assist.term_request_search.messages.sync_to_async", side_effect=lambda fn: AsyncMock(side_effect=fn)):
            await consumer.receive(text_data=json.dumps({"type": "reject"}))

        redis.setex.assert_called_once_with(
            "agent:run-1:awaiting_rejection_reason", 3600, "1"
        )
        redis.delete.assert_called_once_with(
            "agent:run-1:awaiting_rejection", "agent:run-1:resuming"
        )
        consumer.channel_layer.group_send.assert_awaited_once_with(
            "agent_run_run-1",
            {
                "type": "agent.event",
                "payload": {
                    "type": "question",
                    "message": "Why do you reject these recommendations?",
                },
            },
        )

    @patch("ai_assist.term_request_search.messages.redis_client")
    async def test_reject_without_waiting_recommendations_is_a_no_op(self, redis):
        consumer = self.make_consumer()
        redis.get.return_value = None

        with patch("ai_assist.term_request_search.messages.sync_to_async", side_effect=lambda fn: AsyncMock(side_effect=fn)):
            await consumer.receive(text_data=json.dumps({"type": "reject"}))

        redis.set.assert_not_called()
        redis.incr.assert_not_called()
        consumer.channel_layer.group_send.assert_not_awaited()

    @override_settings(TERM_REQUEST_AI_ASSIST_MAX_REJECTIONS=1)
    @patch("ai_assist.term_request_search.messages.redis_client")
    async def test_reject_over_limit_dispatches_termination_resume(self, redis):
        consumer = self.make_consumer()
        redis.get.return_value = "1"
        redis.set.return_value = True
        redis.incr.return_value = 2

        with patch("ai_assist.term_request_search.messages.sync_to_async", side_effect=lambda fn: AsyncMock(side_effect=fn)), patch(
            "ai_assist.term_request_search.messages.current_app.send_task"
        ) as send_task:
            await consumer.receive(text_data=json.dumps({"type": "reject"}))

        send_task.assert_called_once_with(
            "ai_assist.tasks.resume_agent_task", args=["run-1"]
        )
        redis.delete.assert_called_once_with(
            "agent:run-1:awaiting_rejection", "agent:run-1:resuming"
        )

    @patch("ai_assist.term_request_search.messages.redis_client")
    async def test_resume_dispatch_failure_keeps_awaiting_state(self, redis):
        consumer = self.make_consumer()
        consumer.send_json = AsyncMock()
        redis.get.return_value = "1"
        redis.set.return_value = True

        with patch("ai_assist.term_request_search.messages.sync_to_async", side_effect=lambda fn: AsyncMock(side_effect=fn)), patch(
            "ai_assist.term_request_search.messages.current_app.send_task", side_effect=RuntimeError("broker unavailable")
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

    @patch("ai_assist.term_request_search.messages.redis_client")
    async def test_receive_uses_text_data_and_rejects_invalid_json(self, redis):
        consumer = self.make_consumer()
        consumer.send_json = AsyncMock()

        with patch("ai_assist.term_request_search.messages.sync_to_async", side_effect=lambda fn: AsyncMock(side_effect=fn)):
            await consumer.receive(text_data="{")

        consumer.send_json.assert_awaited_once_with({"type": "error", "message": "Invalid JSON."})
        redis.rpush.assert_not_called()

    @patch("ai_assist.term_request_search.consumer.TermRequestSearchMessageHandler")
    @patch("ai_assist.term_request_search.consumer.TermRequestSearchClientMessage.from_data")
    async def test_workflow_consumer_binds_parser_and_handler(self, parser, handler_class):
        consumer = self.make_consumer()
        message = object()
        parser.return_value = message
        handler = handler_class.return_value
        handler.handle = AsyncMock()

        await consumer.handle_workflow_message({"type": "user_message", "message": "x"})

        parser.assert_called_once_with({"type": "user_message", "message": "x"})
        handler_class.assert_called_once_with(consumer)
        handler.handle.assert_awaited_once_with(message)
