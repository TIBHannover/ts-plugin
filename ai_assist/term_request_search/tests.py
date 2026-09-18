import json
from threading import Barrier
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, call, patch

from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from ai_assist import functions as shared_functions, tasks
from ai_assist.consumers import AgentConsumer
from ai_assist import routing as root_routing
from ai_assist import urls as root_urls
from ai_assist import views as root_views
from ai_assist import transport
from ai_assist.models import Ontology

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


class BatchSearchTests(SimpleTestCase):
    @patch("ai_assist.functions.search")
    def test_searches_five_queries_in_parallel_with_default_page_and_size(self, search):
        barrier = Barrier(5)

        def search_result(query, **kwargs):
            barrier.wait(timeout=2)
            return "Error" if query == "failed" else [{"label": query}]

        search.side_effect = search_result
        excluded = [{"ontologyId": "onto", "iri": "iri"}]
        queries = ["one", "two", "three", "four", "failed"]

        result = shared_functions.batch_search(queries, "onto", excluded)

        self.assertEqual(result["one"], [{"label": "one"}])
        self.assertEqual(result["failed"], [])
        search.assert_has_calls(
            [
                call(query, ontologyId="onto", excludedCandidates=excluded)
                for query in queries
            ],
            any_order=True,
        )

    @patch("ai_assist.functions.search")
    def test_rejects_more_than_five_queries(self, search):
        result = shared_functions.batch_search([str(index) for index in range(6)])

        self.assertEqual(result, "Error: query must be a list of 1 to 5 unique strings")
        search.assert_not_called()

    @patch("ai_assist.functions.search")
    def test_rejects_duplicate_queries(self, search):
        result = shared_functions.batch_search(["term", "term"])

        self.assertEqual(result, "Error: query must be a list of 1 to 5 unique strings")
        search.assert_not_called()


class OntologiesListTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Ontology.objects.create(
            ontologyId="one",
            repo_url="https://github.com/example/one",
            definition="First",
            label="One",
            collection=["shared"],
            subjects=["biology"],
        )
        Ontology.objects.create(
            ontologyId="two",
            repo_url="https://github.com/example/two",
            definition="Second",
            label="Two",
            collection=["shared"],
            subjects=["chemistry"],
        )
        Ontology.objects.create(
            ontologyId="three",
            repo_url="https://github.com/example/three",
            definition="Third",
            label="Three",
            collection=["other"],
            subjects=["biology"],
        )
        Ontology.objects.create(
            ontologyId="external",
            repo_url="https://example.com/external",
            definition="External",
            label="External",
            collection=["shared"],
            subjects=["biology"],
        )

    def test_returns_all_ontologies_without_filters(self):
        self.assertCountEqual(
            [ontology["ontologyId"] for ontology in shared_functions.ontologies_list()],
            ["one", "two", "three"],
        )

    def test_can_include_ontologies_not_hosted_on_github(self):
        self.assertCountEqual(
            [
                ontology["ontologyId"]
                for ontology in shared_functions.ontologies_list(
                    hosted_on_github=False
                )
            ],
            ["one", "two", "three", "external"],
        )

    def test_filters_by_collection_and_subject(self):
        self.assertEqual(
            [
                ontology["ontologyId"]
                for ontology in shared_functions.ontologies_list("shared", "biology")
            ],
            ["one"],
        )

    def test_filters_by_collection(self):
        self.assertCountEqual(
            [
                ontology["ontologyId"]
                for ontology in shared_functions.ontologies_list(collection="shared")
            ],
            ["one", "two"],
        )

    def test_filters_by_subject(self):
        self.assertCountEqual(
            [
                ontology["ontologyId"]
                for ontology in shared_functions.ontologies_list(subject="biology")
            ],
            ["one", "three"],
        )


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
            "",
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

    @patch("ai_assist.term_request_search.views.run_agent_task")
    @patch("user_service.libs.decorators.Auth")
    @patch("user_service.libs.decorators.get_headers_dict", return_value={})
    @patch("user_service.libs.decorators.get_username_from_request", return_value="alice")
    @patch("user_service.libs.decorators.is_csrf_valid", return_value=True)
    def test_start_search_is_disabled(self, csrf, owner, headers, auth, task):
        with self.settings(AI_ASSIST_ENABLED=False):
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

    @patch("ai_assist.term_request_search.views.run_agent_task")
    @patch("user_service.libs.decorators.Auth")
    @patch("user_service.libs.decorators.get_headers_dict", return_value={})
    @patch("user_service.libs.decorators.get_username_from_request", return_value="alice")
    @patch("user_service.libs.decorators.is_csrf_valid", return_value=True)
    def test_start_agent_is_disabled_by_default(self, csrf, owner, headers, auth, task):
        with self.settings(AI_ASSIST_ENABLED=False):
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

        self.assertEqual(response.status_code, 400, response.content)
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
        self.assertTrue(any(key.endswith(":socket_token") for key in deleted_keys))

class AgentTests(TestCase):
    @patch("ai_assist.term_request_search.agent.call_openrouter")
    def test_removes_batch_search_after_three_calls_in_both_phases(self, call_openrouter):
        call_openrouter.return_value = ({"content": '{"candidates": []}'}, {})

        for phase in ("search", "term_request"):
            with self.subTest(phase=phase):
                response = workflow_state.new_response(phase)
                response["search_call_count"] = 3

                agent.run_term_request_or_search_agent_turn([], response)

                tools = call_openrouter.call_args.args[1]
                self.assertNotIn(
                    "batch_search", [tool["function"]["name"] for tool in tools]
                )

    @patch("ai_assist.term_request_search.agent.call_openrouter")
    def test_ontologies_list_is_only_available_once_for_term_requests(
        self, call_openrouter
    ):
        call_openrouter.return_value = ({"content": '{"candidates": []}'}, {})

        search_response = workflow_state.new_response("search")
        agent.run_term_request_or_search_agent_turn([], search_response)
        self.assertNotIn(
            "ontologies_list",
            [tool["function"]["name"] for tool in call_openrouter.call_args.args[1]],
        )

        term_response = workflow_state.new_response("term_request")
        agent.run_term_request_or_search_agent_turn([], term_response)
        tool_names = [
            tool["function"]["name"] for tool in call_openrouter.call_args.args[1]
        ]
        self.assertEqual(tool_names, ["ontologies_list"])

        term_response["ontologies_list_call_count"] = 1
        agent.run_term_request_or_search_agent_turn([], term_response)
        tool_names = [
            tool["function"]["name"] for tool in call_openrouter.call_args.args[1]
        ]
        self.assertNotIn("ontologies_list", tool_names)
        self.assertIn("get_roots", tool_names)
        self.assertIn("get_term_children", tool_names)
        self.assertNotIn("batch_search", tool_names)
        self.assertNotIn("search_under_term", tool_names)
        self.assertNotIn("get_individuals", tool_names)

    @patch("ai_assist.term_request_search.agent.call_openrouter")
    def test_search_phase_rejects_ontologies_list_tool_call(self, call_openrouter):
        call_openrouter.return_value = (
            {
                "content": "",
                "tool_calls": [
                    {
                        "id": "call-1",
                        "function": {
                            "name": "ontologies_list",
                            "arguments": "{}",
                        },
                    }
                ],
            },
            {},
        )
        ontologies_list = Mock()
        response = workflow_state.new_response("search")

        with patch.dict(
            agent.TERM_REQUEST_SEARCH_FUNCTIONS,
            {"ontologies_list": ontologies_list},
        ):
            messages = []
            agent.run_term_request_or_search_agent_turn(messages, response)

        ontologies_list.assert_not_called()
        self.assertEqual(
            json.loads(messages[-1]["content"]),
            {"error": "ontologies_list is not available for search."},
        )

    @patch("ai_assist.term_request_search.agent.call_openrouter")
    def test_term_request_executes_ontologies_list_only_once(self, call_openrouter):
        call_openrouter.return_value = (
            {
                "content": "",
                "tool_calls": [
                    {
                        "id": call_id,
                        "function": {"name": "ontologies_list", "arguments": "{}"},
                    }
                    for call_id in ("call-1", "call-2")
                ],
            },
            {},
        )
        ontologies_list = Mock(
            return_value=[
                {"ontologyId": ontology_id}
                for ontology_id in ("one", "two", "three", "four")
            ]
        )
        response = workflow_state.new_response("term_request")

        with patch.dict(
            agent.TERM_REQUEST_SEARCH_FUNCTIONS,
            {"ontologies_list": ontologies_list},
        ):
            messages = []
            agent.run_term_request_or_search_agent_turn(messages, response)

        ontologies_list.assert_called_once_with(hosted_on_github=True)
        self.assertEqual(
            json.loads(messages[-1]["content"]),
            {"error": "ontologies_list can only be called once."},
        )

    @patch("ai_assist.term_request_search.agent.call_openrouter")
    def test_term_request_limits_structural_search_to_three_ontologies(
        self, call_openrouter
    ):
        tool_calls = [
            {
                "id": "ontologies",
                "function": {"name": "ontologies_list", "arguments": "{}"},
            }
        ] + [
            {
                "id": f"roots-{ontology_id}",
                "function": {
                    "name": "get_roots",
                    "arguments": json.dumps(
                        {"ontologyId": ontology_id, "type": "class"}
                    ),
                },
            }
            for ontology_id in ("one", "two", "three", "four")
        ]
        call_openrouter.return_value = (
            {"content": "", "tool_calls": tool_calls},
            {},
        )
        ontologies_list = Mock(
            return_value=[
                {"ontologyId": ontology_id}
                for ontology_id in ("one", "two", "three", "four")
            ]
        )
        get_roots = Mock(return_value=[])
        response = workflow_state.new_response("term_request")

        with patch.dict(
            agent.TERM_REQUEST_SEARCH_FUNCTIONS,
            {"ontologies_list": ontologies_list, "get_roots": get_roots},
        ):
            messages = []
            agent.run_term_request_or_search_agent_turn(messages, response)

        self.assertEqual(get_roots.call_count, 3)
        self.assertEqual(response["selected_ontology_ids"], ["one", "two", "three"])
        self.assertEqual(
            json.loads(messages[-1]["content"]),
            {"error": "At most three ontologies can be selected."},
        )

    @patch("ai_assist.term_request_search.agent.call_openrouter")
    def test_term_request_rejects_duplicate_root_pages(self, call_openrouter):
        call_openrouter.return_value = (
            {
                "content": "",
                "tool_calls": [
                    {
                        "id": "ontologies",
                        "function": {"name": "ontologies_list", "arguments": "{}"},
                    }
                ]
                + [
                    {
                        "id": call_id,
                        "function": {
                            "name": "get_roots",
                            "arguments": json.dumps(
                                {
                                    "ontologyId": "one",
                                    "type": "class",
                                    "page": page,
                                }
                            ),
                        },
                    }
                    for call_id, page in (
                        ("roots-0", 0),
                        ("roots-1", 1),
                        ("roots-1-again", 1),
                    )
                ],
            },
            {},
        )
        functions = {
            "ontologies_list": Mock(return_value=[{"ontologyId": "one"}]),
            "get_roots": Mock(return_value=[]),
        }
        response = workflow_state.new_response("term_request")

        with patch.dict(agent.TERM_REQUEST_SEARCH_FUNCTIONS, functions):
            messages = []
            agent.run_term_request_or_search_agent_turn(messages, response)

        self.assertEqual(functions["get_roots"].call_count, 2)
        self.assertEqual(
            response["visited_root_pages"],
            [
                {"ontologyId": "one", "type": "class", "page": 0},
                {"ontologyId": "one", "type": "class", "page": 1},
            ],
        )
        self.assertEqual(
            json.loads(messages[-1]["content"]),
            {"error": "This ontology root page has already been visited."},
        )

    @patch("ai_assist.term_request_search.agent.call_openrouter")
    def test_term_request_tracks_and_rejects_revisited_nodes(self, call_openrouter):
        call_openrouter.return_value = (
            {
                "content": "",
                "tool_calls": [
                    {
                        "id": "ontologies",
                        "function": {"name": "ontologies_list", "arguments": "{}"},
                    },
                    {
                        "id": "roots",
                        "function": {
                            "name": "get_roots",
                            "arguments": '{"ontologyId": "one", "type": "class"}',
                        },
                    },
                ]
                + [
                    {
                        "id": call_id,
                        "function": {
                            "name": "get_term_children",
                            "arguments": json.dumps(
                                {
                                    "ontologyId": "one",
                                    "iri": "root",
                                    "term_type": "class",
                                    "page": page,
                                }
                            ),
                        },
                    }
                    for call_id, page in (
                        ("children-0", 0),
                        ("children-1", 1),
                        ("children-1-again", 1),
                    )
                ],
            },
            {},
        )
        functions = {
            "ontologies_list": Mock(return_value=[{"ontologyId": "one"}]),
            "get_roots": Mock(
                return_value=[
                    {"ontologyId": "one", "iri": "root", "type": "class"}
                ]
            ),
            "get_term_children": Mock(
                return_value=[
                    {"ontologyId": "one", "iri": "child", "type": "class"}
                ]
            ),
        }
        response = workflow_state.new_response("term_request")

        with patch.dict(agent.TERM_REQUEST_SEARCH_FUNCTIONS, functions):
            messages = []
            agent.run_term_request_or_search_agent_turn(messages, response)

        self.assertEqual(functions["get_term_children"].call_count, 2)
        self.assertEqual(
            response["visited_nodes"],
            [{"ontologyId": "one", "iri": "root"}],
        )
        self.assertEqual(
            response["visited_node_pages"],
            [
                {"ontologyId": "one", "iri": "root", "page": 0},
                {"ontologyId": "one", "iri": "root", "page": 1},
            ],
        )
        self.assertIn(
            {"ontologyId": "one", "iri": "child", "type": "class"},
            response["known_terms"],
        )
        self.assertEqual(
            json.loads(messages[-1]["content"]),
            {"error": "This ontology node page has already been visited."},
        )
        call_openrouter.return_value = ({"content": '{"candidates": []}'}, {})
        agent.run_term_request_or_search_agent_turn(messages, response)
        traversal_context = next(
            message["content"]
            for message in messages
            if message.get("role") == "system"
            and message.get("content", "").startswith(agent.TRAVERSAL_CONTEXT_PREFIX)
        )
        self.assertIn('"iri": "root"', traversal_context)

    @patch("ai_assist.term_request_search.agent.call_openrouter")
    def test_term_request_rejects_children_for_unknown_term(self, call_openrouter):
        call_openrouter.return_value = (
            {
                "content": "",
                "tool_calls": [
                    {
                        "id": "ontologies",
                        "function": {"name": "ontologies_list", "arguments": "{}"},
                    },
                    {
                        "id": "roots",
                        "function": {
                            "name": "get_roots",
                            "arguments": '{"ontologyId": "one", "type": "class"}',
                        },
                    },
                    {
                        "id": "children",
                        "function": {
                            "name": "get_term_children",
                            "arguments": '{"ontologyId": "one", "iri": "unknown", "term_type": "class"}',
                        },
                    },
                ],
            },
            {},
        )
        functions = {
            "ontologies_list": Mock(return_value=[{"ontologyId": "one"}]),
            "get_roots": Mock(
                return_value=[
                    {"ontologyId": "one", "iri": "root", "type": "class"}
                ]
            ),
            "get_term_children": Mock(),
        }

        with patch.dict(agent.TERM_REQUEST_SEARCH_FUNCTIONS, functions):
            messages = []
            agent.run_term_request_or_search_agent_turn(
                messages, workflow_state.new_response("term_request")
            )

        functions["get_term_children"].assert_not_called()
        self.assertEqual(
            json.loads(messages[-1]["content"]),
            {"error": "Select a term returned by get_roots or get_term_children."},
        )

    @patch("ai_assist.term_request_search.agent.call_openrouter")
    def test_search_phase_aggregates_batch_results(self, call_openrouter):
        call_openrouter.return_value = (
            {
                "content": "",
                "tool_calls": [
                    {
                        "id": "call-1",
                        "function": {
                            "name": "batch_search",
                            "arguments": '{"query": ["one", "two"]}',
                        },
                    }
                ],
            },
            {},
        )
        batch_search = Mock(
            return_value={
                "one": [{"label": "One"}],
                "two": [{"label": "Two"}],
            }
        )
        response = workflow_state.new_response("search")

        with patch.dict(
            agent.TERM_REQUEST_SEARCH_FUNCTIONS, {"batch_search": batch_search}
        ):
            agent.run_term_request_or_search_agent_turn([], response)

        self.assertEqual(response["search_call_count"], 1)
        self.assertEqual(
            response["search_results"], [{"label": "One"}, {"label": "Two"}]
        )

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

    @patch("ai_assist.term_request_search.agent.get_term_detail", return_value={})
    def test_term_request_candidates_must_be_reached_by_traversal(self, get_term_detail):
        content = json.dumps(
            {
                "candidates": [
                    {"parent_label": f"P{index}", "ontology": "O", "parent_iri": f"I{index}"}
                    for index in range(3)
                ]
            }
        )

        is_valid, _, feedback = agent.validate_term_request_agent_response(
            content,
            ["O"],
            [
                {"ontologyId": "O", "iri": "I0", "type": "class"},
                {"ontologyId": "O", "iri": "I1", "type": "class"},
            ],
        )

        self.assertFalse(is_valid)
        self.assertEqual(feedback, "Return candidates reached through the ontology traversal.")
        get_term_detail.assert_not_called()

    @patch("ai_assist.term_request_search.agent.get_term_detail")
    def test_term_request_candidate_labels_come_from_term_details(self, get_term_detail):
        get_term_detail.side_effect = lambda iri, ontology_id: {
            "label": f"Canonical {iri}",
            "iri": iri,
            "ontologyId": ontology_id,
        }
        content = json.dumps(
            {
                "candidates": [
                    {
                        "parent_label": "Invented",
                        "ontology": "O",
                        "parent_iri": f"I{index}",
                    }
                    for index in range(3)
                ]
            }
        )
        known_terms = [
            {"ontologyId": "O", "iri": f"I{index}", "type": "class"}
            for index in range(3)
        ]

        is_valid, final_response, _ = agent.validate_term_request_agent_response(
            content, ["O"], known_terms
        )

        self.assertTrue(is_valid)
        self.assertEqual(
            [
                candidate["parent_label"]
                for candidate in json.loads(final_response)["candidates"]
            ],
            ["Canonical I0", "Canonical I1", "Canonical I2"],
        )


class AgentTaskTests(TestCase):
    def test_normalize_state_backfills_structural_search_state(self):
        state = {"messages": [], "response": {}, "steps": 0}

        workflow_state.normalize_state(state)

        self.assertEqual(state["response"]["ontologies_list_call_count"], 0)
        self.assertEqual(state["response"]["available_ontology_ids"], [])
        self.assertEqual(state["response"]["selected_ontology_ids"], [])
        self.assertEqual(state["response"]["known_terms"], [])
        self.assertEqual(state["response"]["visited_root_pages"], [])
        self.assertEqual(state["response"]["visited_nodes"], [])
        self.assertEqual(state["response"]["visited_node_pages"], [])

    @patch("ai_assist.term_request_search.runner.run_conversation")
    @patch("ai_assist.term_request_search.runner.emit")
    @patch("ai_assist.term_request_search.runner.redis_client")
    def test_term_request_starts_directly_in_structural_phase(
        self, redis, emit, run_conversation
    ):
        redis.blpop.return_value = ("ready", "1")

        runner.run_term_request_search_agent("run-1", "input", "term_request")

        state = run_conversation.call_args.args[1]
        self.assertEqual(state["response"]["phase"], "term_request")
        self.assertIn(
            "Required structural search process", state["messages"][0]["content"]
        )

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
        redis.lpop.return_value = None
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

        with patch("ai_assist.term_request_search.runner.run_term_request_or_search_agent_turn", side_effect=lambda messages, response, run_id=None: None) as run_agent:
            runner.run_conversation("run-1", state)

        self.assertEqual(run_agent.call_count, runner.TERM_REQUEST_AGENT_MAX_LOOPS)
        self.assertTrue(any(entry.args[0]["type"] == "error" for entry in emit.call_args_list))

    @patch("ai_assist.term_request_search.runner.save_state")
    @patch("ai_assist.term_request_search.runner.emit")
    @patch("ai_assist.term_request_search.runner.redis_client")
    def test_worker_persists_resumable_state_when_question_is_needed(self, redis, emit, save_state):
        redis.get.return_value = None
        redis.lpop.return_value = None
        state = {"messages": [], "response": workflow_state.new_response(), "steps": 0}

        with patch("ai_assist.term_request_search.runner.run_term_request_or_search_agent_turn", side_effect=lambda messages, response, run_id=None: response.update(needs_user_input=True, question="Clarify")):
            runner.run_conversation("run-1", state)

        self.assertEqual(state["steps"], 1)
        save_state.assert_called_once_with("run-1", state)
        self.assertTrue(any(entry.args[0]["type"] == "question" for entry in emit.call_args_list))

    @patch("ai_assist.term_request_search.runner.run_conversation")
    @patch("ai_assist.term_request_search.runner.redis_client")
    def test_resume_task_loads_saved_state(self, redis, run_conversation):
        saved = {"messages": [], "response": workflow_state.new_response(), "steps": 3}
        redis.get.side_effect = [json.dumps(saved), None]

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

    @patch("ai_assist.consumers.redis_client")
    async def test_connect_rejects_when_assist_is_disabled(self, redis):
        consumer = self.make_consumer()

        with override_settings(AI_ASSIST_ENABLED=False):
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
