from os.path import join
import subprocess
from django.conf import settings
from django.test import TestCase


class TestValidHtml(TestCase):
    """
    Base class for tests that check W3C HTML and CSS validity
    """

    def assertValidCSS(self, path):
        """
        Check the CSS at the given path is valid by passing it through the W3C
        validator
        """

        # Command to run the W3C validator on CSS in a file
        command = [
            'java',
            '-jar',
            join(settings.VALIDATOR_DIR, 'vnu.jar'),
            '--css',
            path
        ]

        result = subprocess.run(
            command,
            capture_output=True
        )

        self.assertTrue(
            result.returncode == 0,
            msg="The CSS is not valid\n{0}\n{1}".format
            (
                path,
                result.stderr.decode('utf-8')
            )
        )

    def assertValid(self, url, status_code=200):
        """
        Navigate to the internal url and check the html is valid by passing it
        through the W3C validator
        """
        response = self.client.get(url)
        self.assertEqual(response.status_code, status_code)

        # Command to run the W3C validator from standard input
        command = [
            'java',
            '-jar',
            join(settings.VALIDATOR_DIR, 'vnu.jar'),
            '-'
        ]

        result = subprocess.run(
            command,
            input=response.content,
            capture_output=True
        )

        self.assertTrue(
            result.returncode == 0,
            msg="The HTML is not valid\n{0}\n{1}".format
            (
                url,
                result.stderr.decode('utf-8')
            )
        )
