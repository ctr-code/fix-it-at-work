from django.urls import reverse
from django.conf import settings
from django.contrib.auth.models import User
from core.common_test import TestValidHtml


class TestValidPages(TestValidHtml):
    """
    Check that all the core pages have valid HTML and check style.css
    """

    def test_validate_css(self):
        self.assertValidCSS(settings.BASE_DIR / 'static/css/style.css')

    def test_validate_page_home(self):
        self.assertValid(reverse('index'))

    def test_validate_page_contact(self):
        self.assertValid(reverse('contact'))

    def test_validate_404(self):
        self.assertValid('a_bogus_url', 404)

    # Also validate allauth views here

    def test_validate_signup(self):
        self.assertValid(reverse('account_signup'))

    def test_validate_login(self):
        self.assertValid(reverse('account_login'))

    def test_validate_profile(self):
        User.objects.create_user(
            username="regularJoe",
            password="myPassword",
            email="test@test.com"
        )
        self.client.login(
            username="regularJoe", password="myPassword")
        self.assertValid(reverse('profile'))
