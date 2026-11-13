import re
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
        # The link text follows its icon, sometimes wrapped with a count badge and a hidden "3 cases waiting"
        return [label for label in ('Report an issue', 'Case queue', 'My jobs', 'Dashboard', 'People')
                if re.search(rf'</(?:i|span)> {re.escape(label)}(?:<span class="visually-hidden">[^<]*</span>)?</a>', html)]

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
        self.assertIn('data-priority="3" data-building="Main Office">', html)
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
        self.assertIn('data-reporter="Lucía Fernández">', html)

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
        self.assertIn('data-team="IT Service Desk" data-language="pl">', html)

    def test_every_tab_has_a_title_and_reference_search(self):
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
                self.assertIn(f'data-search-rows="#{tab} tbody" data-search-key="title ref"', html)
                pane = html.split(f'id="{tab}" role="tabpanel"')[1].split('role="tabpanel"')[0]
                ref = Case.objects.get(title=title).reference
                self.assertIn(f'<tr data-title="{title}" data-ref="{ref}"', pane)
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


@override_settings(
    MEDIA_ROOT=MEDIA, ALLOWED_HOSTS=['testserver'],
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
)
class ReportUpdateTests(TestCase):
    """A reporter adding more details and photos to their report after sending it."""

    def make_user(self, username, role):
        user = User.objects.create_user(username, f'{username}@example.com', 'not-a-real-password-1')
        user.profile.role = role
        user.profile.save()
        return user

    def setUp(self):
        self.reporter = self.make_user('reporter1', 'reporter')
        self.case = Case.objects.create(
            title='Radiator stuck on full', description='Valve will not turn.', building='Innovation Centre',
            reporter_name='Nina Gallagher', reporter_email='nina@example.com', reporter_user=self.reporter,
            status=Status.ASSIGNED)
        self.url = f'/track/{self.case.reference}/'
        self.client.force_login(self.reporter)

    def png(self, name):
        return SimpleUploadedFile(name, PNG_1PX, content_type='image/png')

    def add(self, **data):
        return self.client.post(self.url, {'add_details': '', **data})

    def test_reporter_adds_details_and_photos(self):
        response = self.add(text='Now the radiator is leaking too.', photo=[self.png('leak1.png'), self.png('leak2.png')])
        self.assertRedirects(response, self.url + '#updates', fetch_redirect_response=False)
        update = self.case.updates.get()
        self.assertEqual((update.text, update.author), ('Now the radiator is leaking too.', self.reporter))
        self.assertEqual(update.photos.count(), 2)
        self.assertTrue(all(p.case == self.case for p in update.photos.all()))
        # Added photos belong to the update, not to the original report
        self.assertEqual(self.case.all_photos(), [])

    def test_text_only_and_photo_only_updates_work(self):
        self.add(text='It started making a banging noise.')
        self.add(photo=self.png('valve.png'))
        self.assertEqual(self.case.updates.count(), 2)

    def test_empty_update_is_refused(self):
        response = self.add(text='   ')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Add some details or at least one photo.')
        self.assertFalse(self.case.updates.exists())

    def test_photo_limits_apply(self):
        response = self.add(photo=[self.png(f'p{i}.png') for i in range(6)])
        self.assertContains(response, 'Please choose up to 5 photos. You chose 6.')
        self.assertFalse(self.case.updates.exists())

    def test_only_the_reporter_can_add(self):
        self.client.force_login(self.make_user('handler1', 'handler'))
        self.assertEqual(self.add(text='Not mine').status_code, 403)
        self.assertNotContains(self.client.get(self.url), 'Add more details')
        self.assertFalse(self.case.updates.exists())

    def test_closed_or_merged_case_cannot_be_added_to(self):
        for status in (Status.CLOSED, Status.DUPLICATE):
            with self.subTest(status=status):
                Case.objects.filter(pk=self.case.pk).update(status=status)
                self.assertEqual(self.add(text='Still broken').status_code, 403)
                self.assertNotContains(self.client.get(self.url), 'Add more details')
        self.assertFalse(self.case.updates.exists())

    def test_updates_show_to_reporter_handler_and_officer(self):
        self.add(text='Now the radiator is leaking too.', photo=self.png('leak.png'))
        self.assertContains(self.client.get(self.url), 'Now the radiator is leaking too.')
        team = Team.objects.create(name='Facilities Helpdesk', contact_email='f@example.com', manager='R Turner')
        officer_user = self.make_user('officer1', 'officer')
        officer = Officer.objects.create(name='Serena', team=team, contact_email='s@example.com', user=officer_user)
        Case.objects.filter(pk=self.case.pk).update(assigned_team=team, assigned_officer=officer)
        for user, url in [(self.make_user('handler2', 'handler'), f'/cases/{self.case.reference}/'),
                          (officer_user, f'/officer/{self.case.reference}/')]:
            with self.subTest(user=user.username):
                self.client.force_login(user)
                html = self.client.get(url).content.decode()
                self.assertIn('Added later by the reporter', html)
                self.assertIn('Now the radiator is leaking too.', html)
                self.assertIn('reports/leak', html)

    def test_feedback_still_works_on_closed_case(self):
        from django.utils import timezone
        Case.objects.filter(pk=self.case.pk).update(status=Status.CLOSED, date_closed=timezone.now())
        self.client.post(self.url, {'satisfaction': 5, 'satisfaction_comments': 'Great'})
        self.case.refresh_from_db()
        self.assertEqual(self.case.satisfaction, 5)


@override_settings(
    ALLOWED_HOSTS=['testserver'],
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
)
class MyReportsTests(TestCase):
    """The My reports page lists the signed-in user's own reports."""

    def make_user(self, username, role):
        user = User.objects.create_user(username, f'{username}@example.com', 'not-a-real-password-1')
        user.profile.role = role
        user.profile.save()
        return user

    def report(self, user, title, **extra):
        return Case.objects.create(title=title, description='x', building='Main Office', reporter_name=user.username,
                                   reporter_email=user.email, reporter_user=user, **extra)

    def setUp(self):
        self.me = self.make_user('reporter1', 'reporter')
        self.client.force_login(self.me)

    def test_lists_only_my_reports_with_links(self):
        mine = self.report(self.me, 'Tap dripping')
        self.report(self.make_user('reporter2', 'reporter'), 'Someone else broke this')
        html = self.client.get('/my-reports/').content.decode()
        self.assertIn('Tap dripping', html)
        self.assertNotIn('Someone else broke this', html)
        self.assertIn(f'href="/track/{mine.reference}/"', html)
        self.assertIn("You've made 1 report, 1 still open.", html)

    def test_status_filter_lists_only_statuses_i_have(self):
        self.report(self.me, 'Tap dripping')
        self.report(self.me, 'Bin overflowing', status=Status.CLOSED)
        html = self.client.get('/my-reports/').content.decode()
        options = html.split('id="mine-status"')[1].split('</select>')[0]
        self.assertIn('<option value="new">New - awaiting triage</option>', options)
        self.assertIn('<option value="closed">Closed</option>', options)
        self.assertNotIn('value="assigned"', options)
        self.assertIn('data-search-key="title ref"', html)

    def test_closed_report_waiting_for_a_rating_is_flagged(self):
        from django.utils import timezone
        case = self.report(self.me, 'Bin overflowing', status=Status.CLOSED, date_closed=timezone.now())
        self.assertContains(self.client.get('/my-reports/'), f'/track/{case.reference}/#feedback')

    def test_staff_see_reports_they_made(self):
        handler = self.make_user('handler1', 'handler')
        self.report(handler, 'Projector broken')
        self.client.force_login(handler)
        self.assertContains(self.client.get('/my-reports/'), 'Projector broken')

    def test_empty_state(self):
        self.assertContains(self.client.get('/my-reports/'), 'No reports yet')

    def test_sign_in_needed(self):
        self.client.logout()
        self.assertEqual(self.client.get('/my-reports/').status_code, 302)

    def test_header_link_and_current_page(self):
        case = self.report(self.me, 'Tap dripping')
        for path in ('/my-reports/', f'/track/{case.reference}/'):
            with self.subTest(path=path):
                html = self.client.get(path).content.decode()
                marked = html.split('aria-current="page"')[1].split('</a>')[0]
                self.assertIn('My reports', marked)
        report_page = self.client.get('/report/').content.decode()
        self.assertIn('Report an issue', report_page.split('aria-current="page"')[1].split('</a>')[0])


@override_settings(
    ALLOWED_HOSTS=['testserver'],
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
)
class ReassignCaseTests(TestCase):
    """Case handlers and managers can change the priority, team, category or officer of a triaged case."""

    def make_user(self, username, role, first=''):
        user = User.objects.create_user(username, f'{username}@example.com', 'not-a-real-password-1',
                                        first_name=first)
        user.profile.role = role
        user.profile.save()
        return user

    def setUp(self):
        from .models import Category, SLARule
        self.facilities = Team.objects.create(name='Facilities Helpdesk', contact_email='fac@example.com',
                                              manager='R Turner')
        self.it = Team.objects.create(name='IT Service Desk', contact_email='it@example.com', manager='K Osei')
        self.heating = Category.objects.create(name='Heating', default_team=self.facilities)
        self.network = Category.objects.create(name='Network', default_team=self.it)
        self.serena = Officer.objects.create(name='Serena', team=self.facilities, contact_email='s@example.com')
        self.tom = Officer.objects.create(name='Tom', team=self.facilities, contact_email='t@example.com')
        self.priya = Officer.objects.create(name='Priya', team=self.it, contact_email='p@example.com')
        SLARule.objects.create(priority='medium', acknowledge_hours=8, resolve_hours=72)
        SLARule.objects.create(priority='high', acknowledge_hours=4, resolve_hours=24)
        self.handler = self.make_user('handler1', 'handler', 'Jo')
        self.manager = self.make_user('manager1', 'manager', 'Ade')
        self.case = Case.objects.create(
            title='Radiator stuck on full', description='Valve will not turn.', building='Innovation Centre',
            reporter_name='Nina Gallagher', reporter_email='nina@example.com', priority='medium',
            status=Status.ASSIGNED, category=self.heating, assigned_team=self.facilities,
            assigned_officer=self.serena)
        self.case.apply_sla()
        self.case.save()
        self.url = f'/cases/{self.case.reference}/change/'

    def post(self, user=None, **changes):
        data = {'team': self.facilities.pk, 'category': self.heating.pk, 'priority': 'medium',
                'officer': self.serena.pk, 'reason': ''}
        data.update(changes)
        self.client.force_login(user or self.handler)
        response = self.client.post(self.url, data)
        self.case.refresh_from_db()
        return response

    def test_handler_and_manager_can_open_the_page(self):
        for user in (self.handler, self.manager):
            self.client.force_login(user)
            response = self.client.get(self.url)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'Change priority or assignment')
            self.assertContains(response, 'js/team-filter.js')

    def test_officers_and_reporters_cannot(self):
        for role in ('officer', 'reporter'):
            self.client.force_login(self.make_user(f'someone_{role}', role))
            self.assertNotEqual(self.client.get(self.url).status_code, 200)
            self.client.post(self.url, {'team': self.it.pk, 'category': self.network.pk, 'priority': 'high'})
            self.case.refresh_from_db()
            self.assertEqual(self.case.assigned_team, self.facilities)

    def test_raising_priority_moves_the_sla_and_is_recorded(self):
        old_due = self.case.sla_due
        response = self.post(priority='high', reason='Water now reaching the server room')
        self.assertRedirects(response, f'/cases/{self.case.reference}/')
        self.assertEqual(self.case.priority, 'high')
        self.assertLess(self.case.sla_due, old_due)
        change = self.case.changes.get()
        self.assertEqual(change.changed_by, 'Jo')
        self.assertIn('Priority: Medium → High', change.lines())
        self.assertTrue(any(line.startswith('SLA due:') for line in change.lines()))
        self.assertEqual(change.reason, 'Water now reaching the server room')
        page = self.client.get(f'/cases/{self.case.reference}/')
        self.assertContains(page, 'Change history')
        self.assertContains(page, 'Water now reaching the server room')

    def test_change_officer_and_unassign(self):
        self.post(officer=self.tom.pk)
        self.assertEqual(self.case.assigned_officer, self.tom)
        self.assertEqual(self.case.status, Status.ASSIGNED)
        self.post(officer='')
        self.assertIsNone(self.case.assigned_officer)
        self.assertEqual([c.lines() for c in self.case.changes.order_by('pk')],
                         [['Officer: Serena → Tom'], ['Officer: Tom → Unassigned']])

    def test_move_to_another_team(self):
        self.post(user=self.manager, team=self.it.pk, category=self.network.pk, officer=self.priya.pk)
        self.assertEqual((self.case.assigned_team, self.case.category, self.case.assigned_officer),
                         (self.it, self.network, self.priya))
        self.assertEqual(self.case.changes.get().changed_by, 'Ade')

    def test_officer_or_category_from_another_team_is_refused(self):
        response = self.post(team=self.it.pk, category=self.heating.pk, officer=self.serena.pk)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Heating is not handled by IT Service Desk')
        self.assertContains(response, 'Serena is not in IT Service Desk')
        self.assertEqual(self.case.assigned_team, self.facilities)
        self.assertFalse(self.case.changes.exists())

    def test_saving_without_changes_records_nothing(self):
        old_due = self.case.sla_due
        self.post()
        self.assertEqual(self.case.sla_due, old_due)
        self.assertFalse(self.case.changes.exists())

    def test_in_progress_case_keeps_its_status(self):
        self.case.status = Status.IN_PROGRESS
        self.case.save()
        self.post(officer=self.tom.pk)
        self.assertEqual(self.case.status, Status.IN_PROGRESS)
        self.assertEqual(self.case.assigned_officer, self.tom)

    def test_only_triaged_open_cases_can_be_changed(self):
        for status in (Status.RESOLVED, Status.CLOSED, Status.DUPLICATE):
            self.case.status = status
            self.case.save()
            self.client.force_login(self.handler)
            self.assertRedirects(self.client.get(self.url), f'/cases/{self.case.reference}/')
            self.post(priority='high')
            self.assertEqual(self.case.priority, 'medium')
            page = self.client.get(f'/cases/{self.case.reference}/')
            self.assertNotContains(page, 'Change priority or assignment')
        self.case.status = Status.NEW
        self.case.save()
        self.assertRedirects(self.client.get(self.url), f'/triage/{self.case.reference}/',
                             fetch_redirect_response=False)

    def test_case_page_shows_the_button(self):
        self.client.force_login(self.handler)
        page = self.client.get(f'/cases/{self.case.reference}/')
        self.assertContains(page, f'href="{self.url}"')


@override_settings(
    ALLOWED_HOSTS=['testserver'],
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
)
class TeamAlertTests(TestCase):
    """The team (and officer) a case is sent to are emailed automatically, and each alert is kept on the case."""

    # Same teams, officers and case as the reassignment tests
    make_user = ReassignCaseTests.make_user
    setUp = ReassignCaseTests.setUp
    post = ReassignCaseTests.post

    def team_mail(self):
        """Emails to staff only; the reporter is now emailed too (see ReporterMessageTests)."""
        from django.core import mail
        return [m for m in mail.outbox if 'nina@example.com' not in m.to]

    def triage(self, **choices):
        self.case.status = Status.NEW
        self.case.assigned_team = self.case.assigned_officer = None
        self.case.ai_summary = 'Radiator valve seized, room too hot.'
        self.case.save()
        data = {'team': self.facilities.pk, 'category': self.heating.pk, 'priority': 'medium',
                'officer': '', 'duplicate_of': ''}
        data.update(choices)
        self.client.force_login(self.handler)
        response = self.client.post(f'/triage/{self.case.reference}/', data, follow=True)
        self.case.refresh_from_db()
        return response

    def test_triage_emails_the_team_and_officer(self):
        from django.core import mail
        response = self.triage(officer=self.serena.pk)
        self.assertEqual(len(self.team_mail()), 1)
        email = self.team_mail()[0]
        self.assertEqual(email.to, ['fac@example.com', 's@example.com'])
        self.assertEqual(email.subject, f'[Medium] {self.case.reference} Radiator stuck on full')
        self.assertIn('Serena, you have a new medium priority job.', email.body)
        self.assertIn('Radiator valve seized, room too hot.', email.body)
        self.assertIn(f'http://testserver/officer/{self.case.reference}/', email.body)
        alert = self.case.alerts.get()
        self.assertTrue(alert.delivered)
        self.assertEqual(alert.recipients, 'fac@example.com, s@example.com')
        self.assertContains(response, 'Alert sent to fac@example.com, s@example.com.')

    def test_triage_without_officer_alerts_the_team_inbox(self):
        from django.core import mail
        self.triage()
        self.assertEqual(self.team_mail()[0].to, ['fac@example.com'])
        self.assertIn('Facilities Helpdesk has a new medium priority job.', self.team_mail()[0].body)
        self.assertIn('anyone in the team can take it', self.team_mail()[0].body)

    def test_urgent_and_safety_cases_are_flagged(self):
        from django.core import mail
        self.case.hs_risk = True
        self.case.save()
        self.triage(priority='urgent')
        self.assertTrue(self.team_mail()[0].subject.startswith('[Urgent] '))
        self.assertTrue(self.team_mail()[0].subject.endswith(' - health and safety risk'))
        self.assertIn('HEALTH AND SAFETY RISK', self.team_mail()[0].body)

    def test_merging_a_duplicate_alerts_nobody(self):
        from django.core import mail
        other = Case.objects.create(title='Radiator on full again', description='Same radiator.',
                                    building='Innovation Centre', reporter_name='Sam', reporter_email='sam@example.com',
                                    status=Status.ASSIGNED, assigned_team=self.facilities)
        self.triage(duplicate_of=other.pk)
        self.assertEqual(self.case.status, Status.DUPLICATE)
        self.assertEqual(self.team_mail(), [])

    def test_reassigning_alerts_new_team_and_both_officers(self):
        from django.core import mail
        self.post(team=self.it.pk, category=self.network.pk, officer=self.priya.pk)
        self.assertEqual(self.team_mail()[0].to, ['it@example.com', 'p@example.com', 's@example.com'])
        body = self.team_mail()[0].body
        self.assertIn('- Team: Facilities Helpdesk → IT Service Desk', body)
        self.assertIn('Serena no longer needs to attend.', body)
        self.assertEqual(self.case.alerts.get().kind, 'changed')

    def test_priority_change_alerts_the_current_team(self):
        from django.core import mail
        self.post(priority='high')
        self.assertEqual(self.team_mail()[0].to, ['fac@example.com', 's@example.com'])
        self.assertIn('- Priority: Medium → High', self.team_mail()[0].body)
        self.assertNotIn('no longer needs to attend', self.team_mail()[0].body)

    def test_no_change_sends_nothing(self):
        from django.core import mail
        self.post()
        self.assertEqual(self.team_mail(), [])

    def test_a_mail_failure_is_recorded_and_routing_still_happens(self):
        from unittest import mock
        with mock.patch('cases.alerts.send_mail', side_effect=OSError('Mail server unreachable')):
            response = self.triage()
        self.assertEqual(self.case.status, Status.ASSIGNED)
        alert = self.case.alerts.get()
        self.assertFalse(alert.delivered)
        self.assertEqual(alert.error, 'Mail server unreachable')
        self.assertContains(response, 'could not be sent')
        page = self.client.get(f'/cases/{self.case.reference}/')
        self.assertContains(page, 'Not sent')

    def test_case_page_lists_alerts(self):
        self.triage(officer=self.serena.pk)
        page = self.client.get(f'/cases/{self.case.reference}/')
        self.assertContains(page, 'Team alerts')
        self.assertContains(page, 'Emailed')
        self.assertContains(page, 'fac@example.com, s@example.com')


@override_settings(
    ALLOWED_HOSTS=['testserver'],
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
)
class AlertInboxTests(TestCase):
    """Officers see alerts sent to them or their team on the Alerts page, with an unread count in the navbar."""

    make_user = ReassignCaseTests.make_user
    post = ReassignCaseTests.post
    triage = TeamAlertTests.triage

    def setUp(self):
        ReassignCaseTests.setUp(self)
        # Serena and Tom are in Facilities, Priya is in IT; each gets a sign-in
        for officer in (self.serena, self.tom, self.priya):
            officer.user = self.make_user(officer.name.lower(), 'officer')
            officer.save()

    def page(self, officer, url='/alerts/'):
        self.client.force_login(officer.user)
        return self.client.get(url)

    def unread(self, officer):
        from .alerts import unread_count
        return unread_count(officer.user)

    def test_new_job_reaches_the_officer_and_their_team(self):
        self.triage(officer=self.serena.pk)
        self.assertEqual((self.unread(self.serena), self.unread(self.tom), self.unread(self.priya)), (1, 1, 0))
        page = self.page(self.serena)
        self.assertContains(page, 'Sent to you')
        self.assertContains(page, 'Serena, you have a new medium priority job.')
        self.assertContains(page, 'class="alert-new"')
        self.assertContains(self.page(self.tom), 'Sent to Facilities Helpdesk')
        self.assertContains(self.page(self.priya), 'No alerts yet')

    def test_navbar_shows_the_unread_count(self):
        self.triage(officer=self.serena.pk)
        self.client.force_login(self.serena.user)
        home = self.client.get('/')
        self.assertContains(home, 'href="/alerts/"')
        self.assertContains(home, '<span class="nav-badge" aria-hidden="true">1</span>', html=False)
        self.assertContains(home, ', 1 unread</span>')
        # On phones the menu button carries the count too
        self.assertContains(home, 'aria-label="Open menu, 1 needs your attention"')
        self.assertContains(home, 'toggler-badge')
        # No badge when there's nothing unread
        self.client.force_login(self.priya.user)
        home = self.client.get('/')
        self.assertContains(home, 'href="/alerts/"')
        self.assertNotContains(home, 'nav-badge')

    def test_mark_as_read_is_per_person(self):
        self.triage(officer=self.serena.pk)
        alert = self.case.alerts.get()
        self.client.force_login(self.serena.user)
        self.assertRedirects(self.client.post('/alerts/', {'read': alert.pk}), '/alerts/')
        self.assertEqual((self.unread(self.serena), self.unread(self.tom)), (0, 1))
        self.assertNotContains(self.page(self.serena), 'class="alert-new"')

    def test_opening_the_job_marks_it_read(self):
        self.triage(officer=self.serena.pk)
        self.client.force_login(self.serena.user)
        response = self.client.post('/alerts/', {'open': self.case.alerts.get().pk})
        self.assertRedirects(response, f'/officer/{self.case.reference}/')
        self.assertEqual(self.unread(self.serena), 0)

    def test_mark_all_as_read(self):
        self.triage(officer=self.serena.pk)
        self.post(priority='high')
        self.assertEqual(self.unread(self.serena), 2)
        self.client.force_login(self.serena.user)
        self.client.post('/alerts/', {'all': '1'})
        self.assertEqual(self.unread(self.serena), 0)

    def test_unread_filter(self):
        self.triage(officer=self.serena.pk)
        self.post(priority='high')
        first = self.case.alerts.order_by('pk').first()
        self.client.force_login(self.serena.user)
        self.client.post('/alerts/?show=unread', {'read': first.pk})
        page = self.page(self.serena, '/alerts/?show=unread')
        self.assertContains(page, 'Priority: Medium → High')
        self.assertNotContains(page, 'you have a new medium priority job')
        self.assertContains(self.page(self.serena), 'you have a new medium priority job')

    def test_other_teams_alerts_cannot_be_marked_or_seen(self):
        self.triage(officer=self.serena.pk)
        alert = self.case.alerts.get()
        self.client.force_login(self.priya.user)
        self.client.post('/alerts/', {'read': alert.pk})
        self.client.post('/alerts/', {'all': '1'})
        self.assertFalse(alert.reads.exists())
        self.assertNotContains(self.page(self.priya), alert.subject)

    def test_officer_taken_off_a_job_is_told_but_cannot_open_it(self):
        self.triage(officer=self.serena.pk)
        self.post(team=self.it.pk, category=self.network.pk, officer=self.priya.pk)
        page = self.page(self.serena)
        self.assertContains(page, 'Serena no longer needs to attend.')
        self.assertContains(page, f'{self.case.reference} is no longer with you.')
        self.assertEqual(page.content.decode().count('name="open"'), 0)
        # Priya, the new officer, can open it
        self.assertContains(self.page(self.priya), 'name="open"')

    def test_only_officers_have_an_alerts_page(self):
        self.client.force_login(self.handler)
        self.assertEqual(self.client.get('/alerts/').status_code, 403)
        self.assertNotContains(self.client.get('/'), 'href="/alerts/"')


@override_settings(
    ALLOWED_HOSTS=['testserver'],
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
)
class ReporterMessageTests(TestCase):
    """The reporter hears from us at each stage, in their language, and sees new messages counted on My reports."""

    make_user = ReassignCaseTests.make_user
    post = ReassignCaseTests.post
    triage = TeamAlertTests.triage

    def setUp(self):
        ReassignCaseTests.setUp(self)
        self.nina = self.make_user('nina', 'reporter', 'Nina')
        self.case.reporter_user = self.nina
        self.case.save()
        self.serena.user = self.make_user('serena', 'officer')
        self.serena.save()

    def messages_to_nina(self):
        return list(self.case.communications.filter(date_sent__isnull=False).order_by('pk'))

    def nina_mail(self):
        from django.core import mail
        return [m for m in mail.outbox if m.to == ['nina@example.com']]

    def unread(self):
        from .reporter_messages import unread_count
        return unread_count(self.nina)

    def visit(self, fixed):
        self.client.force_login(self.serena.user)
        data = {'note': 'Valve seized.', 'action': 'Freed the valve.'}
        if fixed:
            data['fixed'] = 'on'
        self.client.post(f'/officer/{self.case.reference}/', data)
        self.case.refresh_from_db()

    def test_triage_tells_the_reporter_and_emails_them(self):
        self.triage()
        message = self.messages_to_nina()[-1]
        self.assertEqual(message.kind, 'ack')
        self.assertIn('passed to our Facilities Helpdesk team as medium priority. We aim to resolve it by',
                      message.draft_text)
        self.assertEqual(len(self.nina_mail()), 1)
        self.assertEqual(self.nina_mail()[0].body, message.draft_text)
        self.assertEqual(self.unread(), 1)

    def test_messages_use_the_reporters_language(self):
        from . import reporter_messages
        self.case.preferred_language = 'es'
        self.case.save()
        self.triage()
        self.assertIn('con prioridad media', self.messages_to_nina()[-1].draft_text)
        self.case.preferred_language = 'pl'
        self.assertIn('Otrzymaliśmy Twoje zgłoszenie', reporter_messages.received(self.case).draft_text)
        self.case.preferred_language = 'ur'
        receipt = reporter_messages.received(self.case)
        self.assertIn('موصول', receipt.draft_text)
        self.assertEqual(receipt.language, 'ur')

    def test_new_target_date_or_team_is_explained(self):
        self.post(priority='high')
        update = self.messages_to_nina()[-1]
        self.assertEqual(update.kind, 'update')
        self.assertIn('We now aim to fix it by', update.draft_text)
        self.assertNotIn('now being handled', update.draft_text)
        self.post(priority='high', team=self.it.pk, category=self.network.pk, officer=self.priya.pk)
        self.assertIn('It is now being handled by our IT Service Desk team.', self.messages_to_nina()[-1].draft_text)

    def test_team_names_ending_in_team_are_not_doubled(self):
        self.it.name = 'IT Network Team'
        self.it.save()
        self.post(team=self.it.pk, category=self.network.pk, officer=self.priya.pk)
        self.assertIn('handled by our IT Network team.', self.messages_to_nina()[-1].draft_text)

    def test_a_new_officer_alone_does_not_message_the_reporter(self):
        self.post(officer=self.tom.pk)
        self.assertEqual(self.messages_to_nina(), [])

    def test_visits_are_reported(self):
        self.visit(fixed=False)
        self.assertIn('An officer visited on', self.messages_to_nina()[-1].draft_text)
        self.assertIn('needs another visit', self.messages_to_nina()[-1].draft_text)
        self.visit(fixed=True)
        self.assertIn('Good news: an officer has fixed "Radiator stuck on full"', self.messages_to_nina()[-1].draft_text)
        self.assertEqual(self.unread(), 2)

    def test_approved_outcome_letter_is_emailed_and_draft_is_not_counted(self):
        self.visit(fixed=True)
        self.client.force_login(self.handler)
        self.client.get(f'/cases/{self.case.reference}/letter/')  # makes the AI draft
        self.assertEqual(self.unread(), 1)  # the "fixed" update only, not the draft letter
        draft = self.case.communications.get(kind='outcome').draft_text
        self.client.post(f'/cases/{self.case.reference}/letter/', {'draft_text': draft})
        self.assertEqual(self.unread(), 2)
        self.assertEqual(self.nina_mail()[-1].body, draft)

    def test_opening_the_report_marks_messages_read(self):
        self.triage()
        self.post(priority='high')
        # Staff looking at the report don't mark the reporter's messages as read
        self.client.force_login(self.handler)
        self.client.get(f'/track/{self.case.reference}/')
        self.assertEqual(self.unread(), 2)
        self.client.force_login(self.nina)
        page = self.client.get(f'/track/{self.case.reference}/')
        self.assertEqual(page.content.decode().count('<span class="alert-new">New</span>'), 2)
        self.assertEqual(self.unread(), 0)
        page = self.client.get(f'/track/{self.case.reference}/')
        self.assertNotContains(page, '<span class="alert-new">New</span>')
        # Newest first
        text = page.content.decode()
        self.assertLess(text.index('We now aim to fix it by'), text.index('passed to our Facilities Helpdesk'))

    def test_my_reports_and_navbar_show_new_messages(self):
        self.triage()
        self.client.force_login(self.nina)
        page = self.client.get('/my-reports/')
        self.assertContains(page, '1 new message.')
        self.assertContains(page, f'href="/track/{self.case.reference}/#your-messages"')
        self.assertContains(page, ', 1 new message</span>')
        self.assertContains(page, 'aria-label="Open menu, 1 needs your attention"')
        self.client.get(f'/track/{self.case.reference}/')
        page = self.client.get('/my-reports/')
        self.assertNotContains(page, 'new message')
        self.assertNotContains(page, 'nav-badge')


@override_settings(
    ALLOWED_HOSTS=['testserver'],
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
)
class CaseQueueCountTests(TestCase):
    """Case handlers and managers see how many cases are waiting for them on "Case queue" in the navbar."""

    make_user = ReassignCaseTests.make_user
    triage = TeamAlertTests.triage

    def setUp(self):
        ReassignCaseTests.setUp(self)  # one assigned case, which isn't waiting for a handler

    def add_case(self, status, **extra):
        return Case.objects.create(title=f'{status} case', description='Test.', building='Main Office',
                                   reporter_name='Sam', reporter_email='sam@example.com', status=status, **extra)

    def nav(self, user):
        self.client.force_login(user)
        return self.client.get('/').content.decode()

    def test_counts_cases_to_triage_and_reply_to(self):
        from django.utils import timezone
        self.add_case(Status.NEW)
        self.add_case(Status.NEW)
        self.add_case(Status.RESOLVED)
        # Not waiting for a handler: with a team, closed (even with an unhappy reporter), merged
        self.add_case(Status.IN_PROGRESS)
        self.add_case(Status.CLOSED, satisfaction=1, date_closed=timezone.now())
        self.add_case(Status.DUPLICATE)
        for user in (self.handler, self.manager):
            page = self.nav(user)
            self.assertIn('<span class="nav-badge" aria-hidden="true">3</span></span> Case queue', page)
            self.assertIn('Case queue<span class="visually-hidden">, 3 cases waiting</span>', page)
            self.assertIn('aria-label="Open menu, 3 need your attention"', page)

    def test_count_goes_down_when_a_case_is_triaged(self):
        self.add_case(Status.NEW)
        self.case.status = Status.NEW  # triage() resets this case to new as well
        self.case.save()
        self.assertIn(', 2 cases waiting', self.nav(self.handler))
        self.triage()
        page = self.nav(self.handler)
        self.assertIn(', 1 case waiting', page)
        self.assertIn('aria-label="Open menu, 1 needs your attention"', page)

    def test_no_badge_when_nothing_is_waiting(self):
        page = self.nav(self.handler)
        self.assertIn('Case queue', page)
        self.assertNotIn('nav-badge', page)
        self.assertNotIn('your attention', page)

    def test_only_handlers_and_managers_get_the_count(self):
        self.add_case(Status.NEW)
        for role in ('officer', 'reporter'):
            page = self.nav(self.make_user(f'someone_{role}', role))
            self.assertNotIn('cases waiting', page)
            self.assertNotIn('case waiting', page)


@override_settings(
    ALLOWED_HOSTS=['testserver'],
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
)
class DashboardAttentionTests(TestCase):
    """The manager dashboard opens with the cases that need acting on now, grouped by what's wrong."""

    make_user = ReassignCaseTests.make_user

    def setUp(self):
        from datetime import timedelta

        from django.utils import timezone

        from .models import SLARule
        self.now = timezone.now()
        self.hours = lambda h: self.now + timedelta(hours=h)
        self.team = Team.objects.create(name='Facilities Helpdesk', contact_email='fac@example.com', manager='R Turner')
        self.officer = Officer.objects.create(name='Serena', team=self.team, contact_email='s@example.com')
        SLARule.objects.create(priority='high', acknowledge_hours=4, resolve_hours=24)
        SLARule.objects.create(priority='medium', acknowledge_hours=8, resolve_hours=72)
        self.manager = self.make_user('manager1', 'manager', 'Ade')

    def add(self, title, status=Status.ASSIGNED, **extra):
        extra.setdefault('assigned_team', self.team if status != Status.NEW else None)
        extra.setdefault('priority', 'medium')
        return Case.objects.create(title=title, description='Test.', building='Main Office', reporter_name='Sam',
                                   reporter_email='sam@example.com', status=status, **extra)

    def dashboard(self):
        self.client.force_login(self.manager)
        return self.client.get('/dashboard/').content.decode()

    def group(self, page, key):
        """The HTML of one group, or '' if it isn't shown."""
        start = page.find(f'id="attention-{key}"')
        return '' if start < 0 else page[start:page.find('</section>', start)]

    def test_each_kind_of_problem_has_its_group(self):
        self.add('Overdue leak', sla_due=self.hours(-2), assigned_officer=self.officer)
        self.add('Due soon heating', sla_due=self.hours(5), assigned_officer=self.officer)
        self.add('Plenty of time', sla_due=self.hours(24 * 5), assigned_officer=self.officer)
        self.add('Urgent with nobody', priority='urgent', sla_due=self.hours(48))
        self.add('Unsafe with nobody', hs_risk=True, sla_due=self.hours(48))
        self.add('Medium with nobody', sla_due=self.hours(48))
        self.add('Slow triage', status=Status.NEW, ai_priority='high', date_reported=self.hours(-6))
        self.add('Fresh report', status=Status.NEW, ai_priority='high', date_reported=self.hours(-1))
        self.add('Letter waiting', status=Status.RESOLVED, date_resolved=self.hours(-30))
        self.add('Just fixed', status=Status.RESOLVED, date_resolved=self.hours(-2))
        self.add('Grumpy', status=Status.CLOSED, satisfaction=1, satisfaction_comments='Took ages',
                 date_closed=self.hours(-24))
        page = self.dashboard()
        expected = {
            'overdue': ['Overdue leak'], 'due-soon': ['Due soon heating'],
            'no-officer': ['Urgent with nobody', 'Unsafe with nobody'], 'slow-triage': ['Slow triage'],
            'slow-reply': ['Letter waiting'], 'unhappy': ['Grumpy'],
        }
        for key, titles in expected.items():
            with self.subTest(group=key):
                html = self.group(page, key)
                for title in titles:
                    self.assertIn(title, html)
        for title in ('Plenty of time', 'Medium with nobody', 'Fresh report', 'Just fixed'):
            self.assertNotIn(title, self.group(page, 'overdue') + self.group(page, 'due-soon')
                             + self.group(page, 'no-officer') + self.group(page, 'slow-triage')
                             + self.group(page, 'slow-reply'))
        self.assertIn('target 4 hours', self.group(page, 'slow-triage'))
        self.assertIn('Rated 1/5', self.group(page, 'unhappy'))
        self.assertIn('health and safety risk', self.group(page, 'no-officer'))
        self.assertIn('Facilities Helpdesk · Serena', self.group(page, 'overdue'))
        self.assertIn('7 cases across 6 areas', page)

    def test_long_groups_show_five_and_link_to_the_rest(self):
        for i in range(7):
            self.add(f'Late job {i}', sla_due=self.hours(-10 + i), assigned_officer=self.officer)
        html = self.group(self.dashboard(), 'overdue')
        self.assertEqual(html.count('<li>'), 5)
        self.assertIn('Late job 0', html)  # most overdue first
        self.assertNotIn('Late job 6', html)
        self.assertIn('and 2 more in the Case queue', html)
        self.assertIn('href="/triage/#teams"', html)

    def test_empty_groups_are_left_out(self):
        self.add('Overdue leak', sla_due=self.hours(-2), assigned_officer=self.officer)
        page = self.dashboard()
        self.assertIn('id="attention-overdue"', page)
        self.assertNotIn('id="attention-unhappy"', page)
        self.assertIn('1 case across 1 area', page)

    def test_all_clear(self):
        page = self.dashboard()
        self.assertIn('Nothing needs attention right now', page)
        self.assertNotIn('Overdue cases - act now', page)


@override_settings(
    ALLOWED_HOSTS=['testserver'],
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
)
class DashboardTrendTests(TestCase):
    """The dashboard shows reports in vs fixes out each week, and the median time at each stage."""

    make_user = ReassignCaseTests.make_user
    add = DashboardAttentionTests.add

    def setUp(self):
        from datetime import datetime, timedelta

        from django.utils import timezone
        self.team = Team.objects.create(name='Facilities Helpdesk', contact_email='fac@example.com', manager='R Turner')
        self.manager = self.make_user('manager1', 'manager', 'Ade')
        # A fixed "now": Wednesday 11 November 2026, midday, so the weeks are predictable
        self.now = timezone.make_aware(datetime(2026, 11, 11, 12, 0))
        self.at = lambda days, hours=0: self.now - timedelta(days=days, hours=hours)

    def trends(self):
        from .views import _trends
        return _trends(self.now)

    def test_weeks_run_monday_to_sunday_with_this_week_last(self):
        weeks = self.trends()['weeks']
        self.assertEqual(len(weeks), 8)
        self.assertEqual(weeks[0]['start'], '2026-09-21')
        self.assertEqual(weeks[-1]['start'], '2026-11-09')
        self.assertEqual(weeks[-1]['label'], 'This week')
        self.assertTrue(weeks[-1]['partial'])
        self.assertEqual(weeks[-2]['label'], '2 Nov')

    def test_reports_and_fixes_are_counted_in_their_week(self):
        self.add('This week A', status=Status.NEW, date_reported=self.at(1))            # Tue 10 Nov
        self.add('This week B', status=Status.NEW, date_reported=self.at(2))            # Mon 9 Nov
        self.add('Last week', status=Status.RESOLVED, date_reported=self.at(4),         # Sat 7 Nov
                 date_resolved=self.at(1))
        self.add('Merged', status=Status.DUPLICATE, date_reported=self.at(3), date_resolved=self.at(3))
        self.add('Too old', status=Status.NEW, date_reported=self.at(70))
        t = self.trends()
        self.assertEqual((t['weeks'][-1]['reported'], t['weeks'][-1]['resolved']), (2, 1))
        self.assertEqual((t['weeks'][-2]['reported'], t['weeks'][-2]['resolved']), (2, 0))  # merged counts as reported only
        self.assertEqual((t['reported_total'], t['resolved_total']), (4, 1))

    def test_median_time_at_each_stage(self):
        for triage_h, fix_h, reply_h in [(1, 10, 2), (3, 20, 4), (2, 30, 6)]:
            reported = self.at(5)
            from datetime import timedelta
            acked = reported + timedelta(hours=triage_h)
            fixed = acked + timedelta(hours=fix_h)
            self.add('Done', status=Status.CLOSED, date_reported=reported, date_acknowledged=acked,
                     date_resolved=fixed, date_closed=fixed + timedelta(hours=reply_h))
        self.add('Waiting', status=Status.NEW, date_reported=self.at(1))
        stages = {st['name']: st for st in self.trends()['stages']}
        self.assertEqual(stages['Waiting for triage']['text'], '2.0 hours')
        self.assertEqual(stages['Being fixed']['text'], '20.0 hours')
        self.assertEqual(stages['Waiting for the reply']['text'], '4.0 hours')
        self.assertEqual(stages['Waiting for triage']['now'], 1)
        self.assertEqual(self.trends()['longest_stage']['name'], 'Being fixed')

    def test_durations_read_naturally(self):
        from .views import _duration
        self.assertEqual([_duration(h) for h in (None, 0.5, 6.25, 72)], ['-', '30 min', '6.2 hours', '3.0 days'])

    def test_dashboard_shows_the_charts_and_a_table(self):
        self.add('Recent', status=Status.NEW)
        self.client.force_login(self.manager)
        page = self.client.get('/dashboard/').content.decode()
        self.assertIn('Reported and resolved each week', page)
        self.assertIn('id="trend-data"', page)
        self.assertIn('js/trend-chart.js', page)
        self.assertIn('Show as a table', page)
        self.assertIn('This week (so far)', page)
        self.assertIn('Where the time goes', page)


@override_settings(
    ALLOWED_HOSTS=['testserver'],
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
)
class CaseLocationTests(TestCase):
    """Each case has an address and a map point: from the building directory, or from the reporter's phone."""

    report = ReportPhotoTests.report

    def setUp(self):
        from decimal import Decimal

        from .models import Building
        self.user = User.objects.create_user('reporter1', 'reporter1@example.com', 'not-a-real-password-1')
        self.client.force_login(self.user)
        Building.objects.create(name='Main Office', address='10 Example Square, Birmingham',
                                latitude=Decimal('52.481000'), longitude=Decimal('-1.899000'))

    def latest(self):
        return Case.objects.latest('pk')

    def test_a_known_building_fills_in_the_address_and_map_point(self):
        self.report(building='main office')  # any capitals
        case = self.latest()
        self.assertEqual(case.address, '10 Example Square, Birmingham')
        self.assertEqual((str(case.latitude), str(case.longitude)), ('52.481000', '-1.899000'))
        self.assertEqual(case.location_source, 'building')

    def test_a_shared_location_is_kept_and_rounded(self):
        self.report(latitude='52.4799991234', longitude='-1.9012345678')
        case = self.latest()
        self.assertEqual((str(case.latitude), str(case.longitude)), ('52.480000', '-1.901230'))
        self.assertEqual(case.location_source, 'device')
        self.assertEqual(case.address, '10 Example Square, Birmingham')  # the address still comes from the building

    def test_somewhere_else_with_a_typed_address(self):
        self.report(building='Car park next door', address='Behind 12 Example Road')
        case = self.latest()
        self.assertEqual(case.address, 'Behind 12 Example Road')
        self.assertFalse(case.has_map_point)
        self.assertEqual(case.map_url, '')

    def test_bad_locations_are_refused(self):
        for extra, message in [({'latitude': '52.48'}, 'only got half of your location'),
                               ({'latitude': '95', 'longitude': '1'}, 'not a real place')]:
            with self.subTest(extra=extra):
                response = self.report(**extra)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, message)
        self.assertFalse(Case.objects.exists())

    def test_form_offers_use_my_location(self):
        page = self.client.get('/report/')
        self.assertContains(page, 'Use my current location')
        self.assertContains(page, 'js/locate.js')
        self.assertContains(page, 'name="latitude"')
        self.assertContains(page, '<option value="Main Office">')

    def test_staff_and_reporter_see_the_map_link(self):
        self.report()
        case = self.latest()
        url = 'https://www.openstreetmap.org/?mlat=52.481000&amp;mlon=-1.899000#map=18/52.481000/-1.899000'
        self.assertContains(self.client.get(f'/track/{case.reference}/'), url)
        handler = User.objects.create_user('handler1', 'h@example.com', 'not-a-real-password-1')
        handler.profile.role = 'handler'
        handler.profile.save()
        self.client.force_login(handler)
        page = self.client.get(f'/cases/{case.reference}/')
        self.assertContains(page, '10 Example Square, Birmingham')
        self.assertContains(page, url)
        self.assertContains(page, 'rel="noopener noreferrer"')
        self.assertContains(page, 'building location')

    def test_sync_buildings_fills_old_cases_but_keeps_shared_locations(self):
        from decimal import Decimal

        from django.core.management import call_command
        old = Case.objects.create(title='Old', description='x', building='Riverside House', reporter_name='Sam',
                                  reporter_email='sam@example.com')
        mine = Case.objects.create(title='Mine', description='x', building='Riverside House', reporter_name='Sam',
                                   reporter_email='sam@example.com', latitude=Decimal('52.1'),
                                   longitude=Decimal('-1.5'), location_source='device')
        from io import StringIO
        call_command('sync_buildings', stdout=StringIO())
        old.refresh_from_db()
        mine.refresh_from_db()
        self.assertEqual(old.address, '5 Demo Wharf, Birmingham')
        self.assertEqual(old.location_source, 'building')
        self.assertEqual((mine.latitude, mine.location_source), (Decimal('52.100000'), 'device'))
        self.assertEqual(mine.address, '5 Demo Wharf, Birmingham')
