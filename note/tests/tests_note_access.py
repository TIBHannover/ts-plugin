from django.test import TestCase
from user_service.libs.test_config import BaseTest
from user_service.libs.test_helpers import TestHelper


class TestNoteAccess(TestCase, BaseTest):

    @classmethod
    def setUpTestData(self) -> None:
        self.orcidUser, _ = TestHelper.createOrcidUser()
        self.gitHubUser, _ = TestHelper.createGitHubUser()
        self.public_note = TestHelper.createNote(self.gitHubUser, "public")
        self.note_for_class = TestHelper.createNote(user=self.gitHubUser, parent_ontology_id="bfo", visibility="public", component_type="class")
        self.internal_note = TestHelper.createNote(self.gitHubUser, "internal")
        self.private_note = TestHelper.createNote(self.gitHubUser, 'me')
        self.note_for_another_ontology = TestHelper.createNote(user=self.gitHubUser, ontology_id="chmo")
        self.public_note_comment = TestHelper.createCommentForNote(self.gitHubUser, self.public_note)
        self.private_note_comment = TestHelper.createCommentForNote(self.gitHubUser, self.private_note)


    
    def test_note_list_should_only_contains_public_note_for_guest_user(self):
        params = {"ontology": self.test_ontology_id}
        note_list_url = "/note/list/"
        response = self.client.get(note_list_url, headers=self.guest_request_headers, data=params)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["_result"]["notes"]), 2)
        self.assertEqual(response.json()["_result"]["notes"][0]["visibility"], "public")



    def test_note_list_should_only_contains_public_and_internal_for_another_user(self):
        """
        The Github user were used to create the internal note. ORCID user is used for test.
        """

        params = {"ontology": self.test_ontology_id}
        note_list_url = "/note/list/"
        response = self.client.get(note_list_url, headers=self.orcid_request_headers, data=params)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["_result"]["notes"]), 3)
        for note in response.json()["_result"]["notes"]:
            self.assertIn(note["visibility"], ["public", "internal"])




    def test_note_list_should_contains_everything_for_a_owner_user(self):
        """
        The Github user were used to create the private note.
        """

        params = {"ontology": self.test_ontology_id}
        note_list_url = "/note/list/"
        response = self.client.get(note_list_url, headers=self.github_request_headers, data=params)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["_result"]["notes"]), 4)
        for note in response.json()["_result"]["notes"]:
            self.assertIn(note["visibility"], ["public", "internal", "me"])




    def test_note_list_should_contains_only_the_ontology_notes(self):
        params = {"ontology": self.test_ontology_id}
        note_list_url = "/note/list/"
        response = self.client.get(
            note_list_url, headers=self.github_request_headers, data=params
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["_result"]["notes"]), 4)
        for note in response.json()["_result"]["notes"]:
            self.assertEqual(note["ontology_id"], self.test_ontology_id)




    def test_note_list_should_contains_child_notes_for_parent_ontology(self):
        '''
            Vibso ontology published a note to bfo. now bfo should contain that note
        '''
        params = {"ontology": self.test_parent_ontology_id}
        note_list_url = "/note/list/"
        response = self.client.get(note_list_url, headers=self.github_request_headers, data=params)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["_result"]["notes"]), 1)
        for note in response.json()["_result"]["notes"]:
            self.assertEqual(note["ontology_id"], self.test_ontology_id)
            self.assertEqual(note["parent_ontology"], self.test_parent_ontology_id)
            self.assertEqual(note["imported"], True)



    def test_note_list_should_not_contains_child_notes_for_parent_ontology_when_onlyOriginalNotes_is_given(self):
        params = {"ontology": self.test_parent_ontology_id, "onlyOriginalNotes": True}
        note_list_url = "/note/list/"
        response = self.client.get(note_list_url, headers=self.github_request_headers, data=params)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["_result"]["notes"]), 0)



    def test_note_list_stats(self):
        params = {"ontology": self.test_ontology_id}
        note_list_url = "/note/list/"
        response = self.client.get(note_list_url, headers=self.github_request_headers, data=params)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["_result"]["stats"]["page"], 1)
        self.assertEqual(response.json()["_result"]["stats"]["size"], 10)
        self.assertEqual(response.json()["_result"]["stats"]["total_number_of_records"], 4)
        self.assertEqual(response.json()["_result"]["stats"]["totalPageCount"], 1)




    def test_get_note_should_fail_with_wrong_note_id(self):
        params = {"ontology": self.test_ontology_id}
        get_a_note_url = "/note/get/12345/"
        response = self.client.get(get_a_note_url, headers=self.github_request_headers, data=params)
        self.assertEqual(response.status_code, 404)
        self.assertIn("Note does not exist", response.content.decode())



    def test_guest_user_cannot_access_private_note(self):
        params = {"ontology": self.test_ontology_id}
        get_a_note_url = "/note/get/" + str(self.private_note.id) + '/'
        response = self.client.get(get_a_note_url, headers=self.guest_request_headers, data=params)
        self.assertEqual(response.status_code, 404)
        self.assertIn("Note does not exist", response.content.decode())



    def test_guest_user_cannot_access_internal_note(self):
        params = {"ontology": self.test_ontology_id}
        get_a_note_url = "/note/get/" + str(self.internal_note.id) + '/'
        response = self.client.get(get_a_note_url, headers=self.guest_request_headers, data=params)
        self.assertEqual(response.status_code, 404)
        self.assertIn("Note does not exist", response.content.decode())



    def test_guest_user_can_access_public_note(self):
        params = {"ontology": self.test_ontology_id}
        get_a_note_url = "/note/get/" + str(self.public_note.id) + '/'
        response = self.client.get(get_a_note_url, headers=self.guest_request_headers, data=params)
        self.assertEqual(response.status_code, 200)



    def test_user_can_access_internal_note(self):
        params = {"ontology": self.test_ontology_id}
        get_a_note_url = "/note/get/" + str(self.internal_note.id) + '/'
        response = self.client.get(get_a_note_url, headers=self.orcid_request_headers, data=params)
        self.assertEqual(response.status_code, 200)



    def test_user_can_access_public_note(self):
        params = {"ontology": self.test_ontology_id}
        get_a_note_url = "/note/get/" + str(self.public_note.id) + '/'
        response = self.client.get(get_a_note_url, headers=self.orcid_request_headers, data=params)
        self.assertEqual(response.status_code, 200)



    def test_user_cannot_access_another_user_private_note(self):
        params = {"ontology": self.test_ontology_id}
        get_a_note_url = "/note/get/" + str(self.private_note.id) + '/'
        response = self.client.get(get_a_note_url, headers=self.orcid_request_headers, data=params)
        self.assertEqual(response.status_code, 404)



    def test_user_can_access_her_own_private_note(self):
        params = {"ontology": self.test_ontology_id}
        get_a_note_url = "/note/get/" + str(self.private_note.id) + '/'
        response = self.client.get(get_a_note_url, headers=self.github_request_headers, data=params)
        self.assertEqual(response.status_code, 200)



    def test_note_list_filtering_based_on_artifact_type(self):
        params = {"ontology": self.test_ontology_id, "artifact_type": "class"}
        note_list_url = "/note/list/"
        response = self.client.get(note_list_url, headers=self.github_request_headers, data=params)
        self.assertEqual(response.status_code, 200)
        for note in response.json()["_result"]["notes"]:
            self.assertEqual(note["semantic_component_type"], "class")
        
