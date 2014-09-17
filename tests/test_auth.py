from django.test import TestCase, Client
import json


class AuthTestCase(TestCase):
    def test_config_json(self):
        response = self.client.get('/config.json')
        result = json.loads(response.content.decode('utf-8'))
        self.assertTrue("login" in result['pages'])