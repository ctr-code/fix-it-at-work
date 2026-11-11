import shutil
import tempfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from .models import Case, ReportPhoto

# A real 1x1 PNG, so the upload looks like a phone photo would to the server
PNG_1PX = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde'
    b'\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
)

MEDIA = tempfile.mkdtemp()


@override_settings(
    MEDIA_ROOT=MEDIA, ALLOWED_HOSTS=['testserver'],
    # Plain static storage, so tests don't need collectstatic to have been run
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
)
class ReportPhotoTests(TestCase):
    """The report form saves the photo chosen in the upload area with the right case."""

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(MEDIA, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.user = User.objects.create_user('reporter1', 'reporter1@example.com', 'not-a-real-password-1')
        self.client.force_login(self.user)

    def report(self, **extra):
        data = {
            'title': 'Water leaking from ceiling', 'description': 'Dripping onto a desk since this morning.',
            'building': 'Main Office', 'location_detail': '2nd floor kitchen',
            'reported_urgency': 'high', 'impact': 'team',
            'preferred_language': 'en', 'preferred_contact': 'email',
        }
        data.update(extra)
        return self.client.post('/report/', data)

    def png(self, name='leak.png'):
        return SimpleUploadedFile(name, PNG_1PX, content_type='image/png')

    def test_report_with_photo_saves_it_on_that_case(self):
        response = self.report(photo=self.png())
        case = Case.objects.get()
        self.assertRedirects(response, f'/track/{case.reference}/', fetch_redirect_response=False)
        self.assertEqual(case.reporter_user, self.user)
        photo = case.photos.get()
        self.assertTrue(photo.image.name.startswith('reports/leak'))
        with photo.image.open('rb') as f:
            self.assertEqual(f.read(), PNG_1PX)

    def test_report_with_five_photos_saves_all_in_order(self):
        names = [f'photo{i}.png' for i in range(1, 6)]
        self.report(photo=[self.png(n) for n in names])
        case = Case.objects.get()
        saved = [p.image.name.split('/')[-1] for p in case.photos.all()]
        self.assertEqual(len(saved), 5)
        for name, stored in zip(names, saved):
            self.assertTrue(stored.startswith(name[:-4]))
        self.assertEqual(len(case.all_photos()), 5)

    def test_more_than_five_photos_is_refused(self):
        response = self.report(photo=[self.png(f'p{i}.png') for i in range(6)])
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Case.objects.exists())
        self.assertFalse(ReportPhoto.objects.exists())
        self.assertContains(response, 'Please choose up to 5 photos. You chose 6.')

    def test_wrong_type_is_refused_with_its_name(self):
        pdf = SimpleUploadedFile('scan.pdf', b'%PDF-1.4', content_type='application/pdf')
        response = self.report(photo=[self.png(), pdf])
        self.assertFalse(Case.objects.exists())
        self.assertContains(response, 'scan.pdf is not a JPG, PNG or WEBP image.')

    def test_photo_over_10mb_is_refused_with_its_name(self):
        big = SimpleUploadedFile('huge.jpg', b'0' * (10 * 1024 * 1024 + 1), content_type='image/jpeg')
        response = self.report(photo=big)
        self.assertFalse(Case.objects.exists())
        self.assertContains(response, 'huge.jpg is 10.0MB. Each photo must be 10MB or less.')

    def test_older_single_photo_still_shows_with_new_ones(self):
        self.report(photo=self.png('new.png'))
        case = Case.objects.get()
        case.photo = 'reports/old.png'
        case.save()
        self.assertEqual([f.name for f in case.all_photos()][0], 'reports/old.png')
        self.assertEqual(len(case.all_photos()), 2)

    def test_report_without_photo_still_works(self):
        response = self.report()
        case = Case.objects.get()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(case.all_photos(), [])

    def test_urgency_impact_and_safety_values_are_saved(self):
        self.report(reported_urgency='urgent', impact='building_wide', hs_risk='on')
        case = Case.objects.get()
        self.assertEqual((case.reported_urgency, case.impact, case.hs_risk), ('urgent', 'building_wide', True))

    def test_form_errors_ask_for_the_photo_again(self):
        response = self.report(title='', photo=self.png())
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Case.objects.exists())
        self.assertContains(response, 'Please add your photos again')

    def test_upload_area_keeps_field_name_and_id(self):
        response = self.client.get('/report/')
        self.assertContains(response, 'name="photo" id="id_photo" class="dropzone-input" multiple')
        self.assertContains(response, 'data-max-files="5" data-max-mb="10"')
        self.assertContains(response, 'enctype="multipart/form-data"')
        self.assertNotContains(response, 'capture=')


@override_settings(
    ALLOWED_HOSTS=['testserver'],
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
)
class HeaderTests(TestCase):
    """The shared header shows each role its own links, marks the current page and signs out."""

    def user_with_role(self, role):
        user = User.objects.create_user(f'{role}1', f'{role}1@example.com', 'not-a-real-password-1')
        user.profile.role = role
        user.profile.save()
        self.client.force_login(user)
        return user

    def nav_links(self, response):
        html = response.content.decode()
        return [label for label in ('Report an issue', 'Case queue', 'My jobs', 'Dashboard', 'People')
                if f'aria-hidden="true"></i> {label}</a>' in html]

    def test_each_role_sees_its_links(self):
        expected = {
            'reporter': ['Report an issue'],
            'handler': ['Report an issue', 'Case queue'],
            'manager': ['Report an issue', 'Case queue', 'Dashboard', 'People'],
        }
        for role, links in expected.items():
            with self.subTest(role=role):
                self.user_with_role(role)
                self.assertEqual(self.nav_links(self.client.get('/')), links)
                self.client.logout()

    def test_current_page_is_marked(self):
        self.user_with_role('manager')
        for path, label in [('/report/', 'Report an issue'), ('/triage/', 'Case queue'),
                            ('/dashboard/', 'Dashboard'), ('/people/', 'People')]:
            with self.subTest(path=path):
                html = self.client.get(path).content.decode()
                self.assertEqual(html.count('aria-current="page"'), 1)
                marked = html.split('aria-current="page"')[1].split('</a>')[0]
                self.assertIn(label, marked)
        home = self.client.get('/').content.decode()
        self.assertNotIn('aria-current="page"', home)

    def test_sign_out_still_works(self):
        self.user_with_role('reporter')
        html = self.client.get('/').content.decode()
        self.assertIn('<form method="post" action="/accounts/logout/">', html)
        self.client.post('/accounts/logout/')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_signed_out_header_offers_sign_in(self):
        html = self.client.get('/accounts/login/').content.decode()
        self.assertIn('Create account', html)
        self.assertIn('nav-cta active" aria-current="page"', html)


@override_settings(
    ALLOWED_HOSTS=['testserver'],
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
)
class CaseQueueSortTests(TestCase):
    """The case queue gives the sorting script what it needs: headings and sortable values."""

    def test_queue_has_sortable_headings_and_values(self):
        user = User.objects.create_user('handler1', 'handler1@example.com', 'not-a-real-password-1')
        user.profile.role = 'handler'
        user.profile.save()
        self.client.force_login(user)
        case = Case.objects.create(title='Lift making grinding noise', description='Noisy lift.',
                                   building='Main Office', reporter_name='A Reporter',
                                   reporter_email='reporter@example.com', ai_priority='urgent')
        html = self.client.get('/triage/').content.decode()
        self.assertEqual(html.count('class="sort-btn"'), 19)
        self.assertIn('js/sort-table.js', html)
        self.assertIn('data-label="AI suggests" data-sort-value="4"', html)  # urgent ranks highest
        self.assertIn(f'data-sort-value="{case.date_reported.isoformat()[:19]}', html)
