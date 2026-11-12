import shutil
import tempfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from .models import Case, Communication, Officer, ReportPhoto, SiteVisit, Status, Team

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

    def test_people_page_sorts_by_name_and_email(self):
        manager = self.user_with_role('manager')
        html = self.client.get('/people/').content.decode()
        self.assertIn('table-sortable', html)
        self.assertIn('js/sort-table.js', html)
        self.assertIn('data-sort="text"><button type="button" class="sort-btn">Name', html)
        self.assertIn('data-sort="text"><button type="button" class="sort-btn">Email', html)
        self.assertIn(f'data-sort-value="{manager.email}"', html)

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

    def test_queue_lists_are_tabs_that_links_can_open(self):
        user = User.objects.create_user('handler2', 'handler2@example.com', 'not-a-real-password-1')
        user.profile.role = 'handler'
        user.profile.save()
        self.client.force_login(user)
        html = self.client.get('/triage/').content.decode()
        self.assertIn('js/tabs.js', html)
        for pane, label in [('triage', 'Needs triage'), ('reply', 'Fixed - reply needed'),
                            ('unhappy', 'Unhappy reporters'), ('teams', 'With teams')]:
            with self.subTest(pane=pane):
                self.assertIn(f'data-bs-target="#{pane}"', html)
                self.assertIn(f'id="{pane}" role="tabpanel" aria-labelledby="tab-{pane}"', html)
                self.assertIn(f'>{label} <span class="tab-count">', html)
        self.assertEqual(html.count('class="tab-pane fade show active"'), 1)

    def test_needs_triage_filters_list_only_whats_in_the_queue(self):
        user = User.objects.create_user('handler3', 'handler3@example.com', 'not-a-real-password-1')
        user.profile.role = 'handler'
        user.profile.save()
        self.client.force_login(user)
        Case.objects.create(title='Tap dripping', description='x', building='Main Office', reporter_name='R',
                            reporter_email='r@example.com', ai_priority='high')
        html = self.client.get('/triage/').content.decode()
        self.assertIn('id="triage-priority"', html)
        self.assertIn('js/table-filter.js', html)
        options = html.split('id="triage-priority"')[1].split('</select>')[0]
        self.assertIn('<option value="3">High</option>', options)
        self.assertNotIn('Urgent', options)
        self.assertIn('<tr data-title="Tap dripping" data-priority="3" data-building="Main Office">', html)
        places = html.split('id="triage-location"')[1].split('</select>')[0]
        self.assertIn('<option value="Main Office">Main Office</option>', places)
        self.assertEqual(places.count('<option'), 2)  # "All locations" plus the one building with a case

    def test_with_teams_filters_list_priorities_teams_and_officers(self):
        user = User.objects.create_user('handler4', 'handler4@example.com', 'not-a-real-password-1')
        user.profile.role = 'handler'
        user.profile.save()
        self.client.force_login(user)
        team = Team.objects.create(name='Health & Safety Team', contact_email='hs@example.com', manager='M Shaw')
        officer = Officer.objects.create(name='Sunita Rao', team=team, contact_email='sr@example.com')
        common = dict(description='x', building='Depot', reporter_name='R', reporter_email='r@example.com',
                      status=Status.ASSIGNED, assigned_team=team)
        Case.objects.create(title='Exit blocked', priority='urgent', assigned_officer=officer, **common)
        Case.objects.create(title='Trailing cable', priority='high', **common)
        html = self.client.get('/triage/').content.decode()
        options = lambda sid: html.split(f'id="{sid}"')[1].split('</select>')[0]
        self.assertIn('<option value="4">Urgent</option>', options('teams-priority'))
        self.assertNotIn('Medium', options('teams-priority'))
        self.assertIn('<option value="Health &amp; Safety Team">', options('teams-team'))
        self.assertIn('<option value="-">Unassigned</option>', options('teams-officer'))
        self.assertIn('<option value="Sunita Rao">Sunita Rao</option>', options('teams-officer'))
        self.assertIn('data-team="Health &amp; Safety Team" data-officer="Sunita Rao"', html)
        self.assertIn('data-officer="-"', html)

    def test_unhappy_reporters_filter_lists_their_names(self):
        from django.utils import timezone
        user = User.objects.create_user('handler5', 'handler5@example.com', 'not-a-real-password-1')
        user.profile.role = 'handler'
        user.profile.save()
        self.client.force_login(user)
        Case.objects.create(title='Toilet blocked', description='x', building='Depot', reporter_name='Lucía Fernández',
                            reporter_email='l@example.com', status=Status.CLOSED, date_closed=timezone.now(),
                            satisfaction=2)
        html = self.client.get('/triage/').content.decode()
        options = html.split('id="unhappy-reporter"')[1].split('</select>')[0]
        self.assertIn('<option value="Lucía Fernández">Lucía Fernández</option>', options)
        self.assertIn('<tr data-title="Toilet blocked" data-reporter="Lucía Fernández">', html)

    def test_reply_needed_filters_list_teams_and_languages(self):
        user = User.objects.create_user('handler6', 'handler6@example.com', 'not-a-real-password-1')
        user.profile.role = 'handler'
        user.profile.save()
        self.client.force_login(user)
        team = Team.objects.create(name='IT Service Desk', contact_email='it@example.com', manager='N Karim')
        common = dict(description='x', building='Depot', reporter_name='R', reporter_email='r@example.com',
                      status=Status.RESOLVED, assigned_team=team)
        Case.objects.create(title='Monitor flickering', preferred_language='en', **common)
        Case.objects.create(title='Brak internetu', preferred_language='pl', **common)
        html = self.client.get('/triage/').content.decode()
        teams = html.split('id="reply-team"')[1].split('</select>')[0]
        languages = html.split('id="reply-language"')[1].split('</select>')[0]
        self.assertIn('<option value="IT Service Desk">IT Service Desk</option>', teams)
        self.assertIn('<option value="en">English</option>', languages)
        self.assertIn('<option value="pl">Polski (Polish)</option>', languages)
        self.assertNotIn('value="es"', languages)
        self.assertIn('<tr data-title="Brak internetu" data-team="IT Service Desk" data-language="pl">', html)

    def test_every_tab_has_a_title_search(self):
        user = User.objects.create_user('handler7', 'handler7@example.com', 'not-a-real-password-1')
        user.profile.role = 'handler'
        user.profile.save()
        self.client.force_login(user)
        from django.utils import timezone
        team = Team.objects.create(name='Facilities Helpdesk', contact_email='f@example.com', manager='R Turner')
        common = dict(description='x', building='Depot', reporter_name='R', reporter_email='r@example.com')
        Case.objects.create(title='Lift noisy', **common)
        Case.objects.create(title='Monitor flickering', status=Status.RESOLVED, assigned_team=team, **common)
        Case.objects.create(title='Toilet blocked', status=Status.CLOSED, date_closed=timezone.now(), satisfaction=1,
                            **common)
        Case.objects.create(title='Window blind broken', status=Status.ASSIGNED, assigned_team=team, **common)
        html = self.client.get('/triage/').content.decode()
        for tab, title in [('triage', 'Lift noisy'), ('reply', 'Monitor flickering'),
                           ('unhappy', 'Toilet blocked'), ('teams', 'Window blind broken')]:
            with self.subTest(tab=tab):
                self.assertIn(f'id="{tab}-search"', html)
                self.assertIn(f'data-search-rows="#{tab} tbody" data-search-key="title"', html)
                pane = html.split(f'id="{tab}" role="tabpanel"')[1].split('role="tabpanel"')[0]
                self.assertIn(f'<tr data-title="{title}"', pane)
        self.assertNotIn('{#', html)


@override_settings(
    ALLOWED_HOSTS=['testserver'],
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
)
class OfficerJobPageTests(TestCase):
    """An officer only gets the visit form once the job is theirs."""

    def setUp(self):
        user = User.objects.create_user('officer1', 'officer1@example.com', 'not-a-real-password-1')
        user.profile.role = 'officer'
        user.profile.save()
        self.client.force_login(user)
        team = Team.objects.create(name='Estates Maintenance', contact_email='estates@example.com', manager='H Ward')
        self.officer = Officer.objects.create(name='Officer One', team=team, contact_email='o1@example.com', user=user)
        self.case = Case.objects.create(title='Leaking tap', description='Drips.', building='Main Office',
                                        reporter_name='A Reporter', reporter_email='reporter@example.com',
                                        priority='medium', status=Status.ASSIGNED, assigned_team=team)
        self.url = f'/officer/{self.case.reference}/'

    def test_unassigned_job_offers_take_but_not_visit_form(self):
        html = self.client.get(self.url).content.decode()
        self.assertIn('Assign this job to me', html)
        self.assertNotIn('Record your visit', html)

    def test_visit_form_shows_once_taken(self):
        self.client.post(self.url, {'take': ''})
        html = self.client.get(self.url).content.decode()
        self.assertNotIn('Assign this job to me', html)
        self.assertIn('Record your visit', html)

    def test_job_list_gives_sort_values(self):
        self.client.post(self.url, {'take': ''})
        Case.objects.filter(pk=self.case.pk).update(priority='urgent')
        html = self.client.get('/officer/').content.decode()
        self.assertIn('id="job-sort"', html)
        self.assertIn('js/sort-cards.js', html)
        self.assertIn('data-building="Main Office" data-title="Leaking tap"', html)
        self.assertIn('data-priority="4"', html)
        self.assertIn('data-overdue="0"', html)

    def test_location_filter_lists_only_this_officers_buildings(self):
        self.client.post(self.url, {'take': ''})
        other_team = Team.objects.create(name='IT Service Desk', contact_email='it@example.com', manager='N Karim')
        Case.objects.create(title='Laptop broken', description='x', building='Depot', reporter_name='R',
                            reporter_email='r@example.com', status=Status.ASSIGNED, assigned_team=other_team)
        html = self.client.get('/officer/').content.decode()
        self.assertIn('id="job-location"', html)
        self.assertIn('<option value="Main Office">Main Office</option>', html)
        self.assertNotIn('<option value="Depot">', html)

    def test_priority_filter_lists_only_this_officers_priorities(self):
        self.client.post(self.url, {'take': ''})  # the job set up for this officer is medium
        html = self.client.get('/officer/').content.decode()
        self.assertIn('id="job-priority"', html)
        self.assertIn('data-search-cards=".job-list" data-search-key="title"', html)
        self.assertIn('data-clear-filters hidden', html)  # shown by the script once something is filtered
        self.assertIn('<option value="2">Medium</option>', html)
        for absent in ('Urgent', 'High', 'Low'):
            self.assertNotIn(f'">{absent}</option>', html)


@override_settings(
    MEDIA_ROOT=MEDIA, ALLOWED_HOSTS=['testserver'],
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
)
class VisitRecordingTests(TestCase):
    """What happens when a field officer records a visit on one of their jobs."""

    def make_user(self, username, role):
        user = User.objects.create_user(username, f'{username}@example.com', 'not-a-real-password-1')
        user.profile.role = role
        user.profile.save()
        return user

    def setUp(self):
        self.team = Team.objects.create(name='Facilities Helpdesk', contact_email='fac@example.com', manager='R Turner')
        self.user = self.make_user('officer1', 'officer')
        self.officer = Officer.objects.create(name='Officer One', team=self.team, contact_email='o1@example.com',
                                              user=self.user)
        self.case = Case.objects.create(
            title='Radiator stuck on full', description='Valve will not turn.', building='Innovation Centre',
            reporter_name='A Reporter', reporter_email='reporter@example.com', priority='medium',
            status=Status.ASSIGNED, assigned_team=self.team, assigned_officer=self.officer)
        self.url = f'/officer/{self.case.reference}/'
        self.client.force_login(self.user)

    def visit(self, note='The radiator valve was seized on full.',
              action='Replaced the valve head and bled the radiator. Tested for 20 minutes.', **extra):
        return self.client.post(self.url, {'note': note, 'action': action, **extra})

    def test_fixed_on_first_visit_resolves_the_case(self):
        response = self.visit(fixed='on')
        self.assertRedirects(response, '/officer/', fetch_redirect_response=False)
        self.case.refresh_from_db()
        visit = self.case.visits.get()
        self.assertEqual((visit.officer, visit.fixed), (self.officer, True))
        self.assertIn('Outcome: Fixed on this visit.', visit.ai_summary)
        self.assertEqual(self.case.status, Status.RESOLVED)
        self.assertIsNotNone(self.case.date_resolved)
        self.assertTrue(self.case.first_time_fix)

    def test_not_fixed_keeps_the_case_open(self):
        self.visit(note='Valve seized. Part ordered, return visit booked.')
        self.case.refresh_from_db()
        visit = self.case.visits.get()
        self.assertFalse(visit.fixed)
        self.assertIn('Not fixed yet - follow-up visit needed.', visit.ai_summary)
        self.assertEqual(self.case.status, Status.IN_PROGRESS)
        self.assertIsNone(self.case.date_resolved)
        self.assertIsNone(self.case.first_time_fix)

    def test_fixed_on_second_visit_is_not_a_first_time_fix(self):
        self.visit(note='Valve seized. Part ordered.')
        self.visit(note='Fitted the new valve. Working.', fixed='on')
        self.case.refresh_from_db()
        self.assertEqual(self.case.visits.count(), 2)
        self.assertEqual(self.case.status, Status.RESOLVED)
        self.assertFalse(self.case.first_time_fix)

    def test_fixed_case_moves_to_handler_reply_list(self):
        self.visit(fixed='on')
        self.client.force_login(self.make_user('handler1', 'handler'))
        html = self.client.get('/triage/').content.decode()
        reply_section = html.split('id="reply" role="tabpanel"')[1].split('role="tabpanel"')[0]
        self.assertIn(self.case.reference, reply_section)

    def test_visit_photo_and_dictation_flag_are_saved(self):
        photo = SimpleUploadedFile('valve.png', PNG_1PX, content_type='image/png')
        self.visit(photo=photo, transcript_used='True')
        visit = self.case.visits.get()
        self.assertTrue(visit.photo.name.startswith('visits/valve'))
        self.assertTrue(visit.transcript_used)

    def test_missing_action_is_refused(self):
        response = self.visit(action='', fixed='on')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'This field is required.')
        self.assertFalse(self.case.visits.exists())

    def test_empty_note_is_refused(self):
        response = self.visit(note='', fixed='on')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.case.visits.exists())
        self.case.refresh_from_db()
        self.assertEqual(self.case.status, Status.ASSIGNED)

    def test_other_officer_cannot_record_a_visit(self):
        other = self.make_user('officer2', 'officer')
        Officer.objects.create(name='Officer Two', team=self.team, contact_email='o2@example.com', user=other)
        self.client.force_login(other)
        response = self.visit(fixed='on')
        self.assertEqual(response.status_code, 403)
        self.assertFalse(self.case.visits.exists())

    def test_reporter_cannot_record_a_visit(self):
        self.client.force_login(self.make_user('reporter1', 'reporter'))
        self.visit(fixed='on')
        self.assertFalse(self.case.visits.exists())

    def test_fixed_or_closed_job_refuses_a_visit(self):
        for status in (Status.RESOLVED, Status.CLOSED, Status.DUPLICATE):
            with self.subTest(status=status):
                resolved_at = self.case.date_resolved
                Case.objects.filter(pk=self.case.pk).update(status=status, first_time_fix=True)
                response = self.visit(note='Popped back to check.')
                self.assertRedirects(response, '/officer/', fetch_redirect_response=False)
                self.case.refresh_from_db()
                self.assertEqual(self.case.status, status)
                self.assertTrue(self.case.first_time_fix)
                self.assertEqual(self.case.date_resolved, resolved_at)
                self.assertFalse(self.case.visits.exists())

    def test_second_click_on_fixed_does_not_spoil_first_time_fix(self):
        self.visit(fixed='on')
        response = self.visit(fixed='on')  # e.g. Save pressed twice
        self.case.refresh_from_db()
        self.assertEqual(self.case.visits.count(), 1)
        self.assertEqual(self.case.status, Status.RESOLVED)
        self.assertTrue(self.case.first_time_fix)
        messages = [str(m) for m in response.wsgi_request._messages]
        self.assertIn(f'{self.case.reference} is already marked as fixed, so no visit was recorded.', messages)


@override_settings(
    ALLOWED_HOSTS=['testserver'],
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
)
class VisitOutcomeFlowTests(TestCase):
    """An officer's answers (what they found, what they did, whether it's fixed) followed through to the
    handler's case page, the outcome letter and the reporter's tracking page."""

    FOUND = 'The radiator valve was seized and the room was at 29 degrees.'
    DID = 'Replaced the valve head and bled the radiator.'
    CHECKED = 'Room back to 21 degrees after 20 minutes.'

    def make_user(self, username, role, first=''):
        user = User.objects.create_user(username, f'{username}@example.com', 'not-a-real-password-1',
                                        first_name=first)
        user.profile.role = role
        user.profile.save()
        return user

    def setUp(self):
        team = Team.objects.create(name='Facilities Helpdesk', contact_email='fac@example.com', manager='R Turner')
        self.officer_user = self.make_user('officer1', 'officer')
        self.officer = Officer.objects.create(name='Serena', team=team, contact_email='s@example.com',
                                              user=self.officer_user)
        self.handler = self.make_user('handler1', 'handler', 'Jo')
        self.reporter = self.make_user('reporter1', 'reporter', 'Nina')
        self.case = Case.objects.create(
            title='Radiator stuck on full', description='Valve will not turn.', building='Innovation Centre',
            reporter_name='Nina Gallagher', reporter_email='nina@example.com', reporter_user=self.reporter,
            priority='medium', status=Status.ASSIGNED, assigned_team=team, assigned_officer=self.officer)
        self.ref = self.case.reference

    def record(self, found, did, fixed):
        self.client.force_login(self.officer_user)
        data = {'note': found, 'action': did}
        if fixed:
            data['fixed'] = 'on'
        self.client.post(f'/officer/{self.ref}/', data)
        self.case.refresh_from_db()
        return self.case.visits.last()

    def draft_letter(self):
        self.client.force_login(self.handler)
        self.client.get(f'/cases/{self.ref}/letter/')
        return Communication.objects.get(case=self.case, kind=Communication.Kind.OUTCOME).draft_text

    def test_both_answers_are_saved_with_a_summary(self):
        visit = self.record(self.FOUND, f'{self.DID} {self.CHECKED}', fixed=True)
        self.assertEqual((visit.note, visit.action, visit.fixed), (self.FOUND, f'{self.DID} {self.CHECKED}', True))
        self.assertEqual(visit.ai_summary,
                         f'Found: {self.FOUND} Done: {self.DID} {self.CHECKED} Outcome: Fixed on this visit.')

    def test_handler_sees_outcome_summary_and_both_answers(self):
        self.record(self.FOUND, self.DID, fixed=True)
        self.client.force_login(self.handler)
        visits = self.client.get(f'/cases/{self.ref}/').content.decode().split('Site visits')[1]
        self.assertIn('Serena &middot; Fixed', visits)
        self.assertIn('Outcome: Fixed on this visit.', visits)
        self.assertIn(f'<strong>Found:</strong> {self.FOUND}', visits)
        self.assertIn(f'<strong>Did:</strong> {self.DID}', visits)

    def test_letter_says_what_was_done_not_what_was_found(self):
        self.record(self.FOUND, f'{self.DID} {self.CHECKED}', fixed=True)
        letter = self.draft_letter()
        self.assertIn('Dear Nina', letter)
        self.assertIn(f'What we did: {self.DID} {self.CHECKED}', letter)
        self.assertNotIn(self.FOUND, letter)

    def test_long_description_of_the_fault_does_not_hide_the_action(self):
        found = ('Arrived at 9am. The finance office was very hot, about 29 degrees. Staff had opened the windows. '
                 'The radiator valve was seized on full.')
        self.record(found, self.DID, fixed=True)
        self.assertIn(f'What we did: {self.DID}', self.draft_letter())
        self.assertIn(f'Done: {self.DID}', self.case.visits.get().ai_summary)

    def test_older_visit_with_one_note_still_drafts_a_letter(self):
        SiteVisit.objects.create(case=self.case, officer=self.officer, fixed=True,
                                 note='Found the valve seized and replaced it.')
        Case.objects.filter(pk=self.case.pk).update(status=Status.RESOLVED)
        self.assertIn('What we did: Found the valve seized and replaced it.', self.draft_letter())

    def test_fixed_job_reaches_reporter_through_approved_letter(self):
        self.record(self.FOUND, f'{self.DID} {self.CHECKED}', fixed=True)
        # Before the handler approves a letter, the reporter only sees the status
        self.client.force_login(self.reporter)
        html = self.client.get(f'/track/{self.ref}/').content.decode()
        self.assertIn('Resolved - reply being prepared', html)
        self.assertNotIn(self.DID, html)

        # Approving the AI draft sends it and closes the case
        letter = self.draft_letter()
        self.client.post(f'/cases/{self.ref}/letter/', {'draft_text': letter})
        self.case.refresh_from_db()
        self.assertEqual(self.case.status, Status.CLOSED)
        self.assertTrue(self.case.first_time_fix)

        # Now the reporter sees the letter, including what was done
        self.client.force_login(self.reporter)
        html = self.client.get(f'/track/{self.ref}/').content.decode()
        self.assertIn('Closed', html)
        self.assertIn(self.DID, html)

    def test_not_fixed_keeps_reporter_informed_and_no_letter_yet(self):
        self.record('Valve seized solid.', 'Ordered a new valve. Return visit booked for Thursday.', fixed=False)
        self.assertEqual(self.case.status, Status.IN_PROGRESS)
        self.client.force_login(self.handler)
        html = self.client.get(f'/cases/{self.ref}/').content.decode()
        self.assertIn('Serena &middot; Follow-up needed', html)
        self.assertIn('Done: Ordered a new valve. Return visit booked for Thursday. '
                      'Outcome: Not fixed yet - follow-up visit needed.', html)
        response = self.client.get(f'/cases/{self.ref}/letter/')
        self.assertRedirects(response, f'/cases/{self.ref}/', fetch_redirect_response=False)
        self.client.force_login(self.reporter)
        self.assertIn('In progress - follow-up needed', self.client.get(f'/track/{self.ref}/').content.decode())
