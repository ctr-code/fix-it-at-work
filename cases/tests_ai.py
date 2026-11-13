"""
Benchmark for the triage assistant in cases/ai.py.

Realistic reports, each with the category and priority a sensible case handler would choose.
Includes tricky ones: words with two meanings ("cold tap", "fire door"), danger words that aren't
dangers ("fire extinguisher missing", "not a fire"), misspellings, and Polish, Spanish and Urdu.
The last 16 were written after the rules were tuned, as a fairer check.

If a change to the AI makes these scores drop, this test fails. To try a real AI model later,
run it against the same reports and compare.
"""
from django.test import TestCase

from .management.commands.seed_demo import CATEGORIES, TEAMS
from . import ai
from .models import PRIORITY_RANK, Case, Category, Team

# (title, description, building, room, reporter urgency, impact, health and safety risk,
#  expected category, expected priority)
REPORTS = [
    ('Radiator cold', 'The radiator in room 4 has been cold since Monday and staff are wearing coats.', 'Main Office', 'Room 4', 'medium', 'team', False, 'Heating', 'high'),
    ('Office too hot', 'The air conditioning is not working and it is 30 degrees in the open plan office.', 'Main Office', 'Open plan', 'medium', 'team', False, 'Air Conditioning', 'medium'),
    ("Tap won't turn off", 'The cold tap in the kitchen will not turn off and keeps running.', 'Main Office', 'Kitchen', 'medium', 'team', False, 'Plumbing', 'medium'),
    ('Flickering light', 'One of the lights in the corridor flickers on and off all day.', 'Riverside House', 'Corridor', 'low', 'team', False, 'Lighting & Electrical', 'medium'),
    ('Broken chair', 'My office chair has a broken wheel and tips over when I sit down.', 'Main Office', 'Desk 14', 'low', 'single_user', False, 'Furniture', 'low'),
    ('Laptop screen cracked', 'I dropped my laptop this morning and the screen is now cracked.', 'Riverside House', '3rd floor', 'medium', 'single_user', False, 'Hardware', 'medium'),
    ('Outlook keeps crashing', 'Outlook crashes every time I open an attachment from a customer.', 'Main Office', '', 'low', 'single_user', False, 'Software', 'low'),
    ('Printer out of toner', 'The printer on the 2nd floor says it is out of toner and will not print.', 'Main Office', '2nd floor', 'low', 'team', False, 'Printing', 'low'),
    ('Account locked', 'I am locked out of my account after too many wrong password attempts.', 'Main Office', '', 'medium', 'single_user', False, 'Accounts & Access', 'medium'),
    ('Desk phone dead', 'My desk phone has no dial tone and I cannot make calls.', 'Riverside House', 'Desk 8', 'medium', 'single_user', False, 'Telephony', 'medium'),
    ('No internet', 'The internet is down for the whole floor and nobody can work.', 'Innovation Centre', '2nd floor', 'high', 'department', False, 'Network & Connectivity', 'high'),
    ('Badge not working', 'My badge does not open the main entrance door any more.', 'Warehouse B', 'Main entrance', 'medium', 'single_user', False, 'Access Control', 'high'),
    ('Lost keys', 'I have lost the keys to the stationery cupboard on the 1st floor.', 'Main Office', '1st floor', 'low', 'single_user', False, 'Keys & Fobs', 'medium'),
    ('Alarm going off at night', 'The intruder alarm keeps going off at night when no one is in the building.', 'Depot', '', 'medium', 'building_wide', False, 'Alarms', 'high'),
    ('Rain coming through ceiling', 'Rain water is coming through the ceiling tiles in the stairwell.', 'Riverside House', 'Stairwell', 'medium', 'team', True, 'Roof & Leaks', 'high'),
    ('Fire door wedged open', 'Someone keeps wedging the fire door open with a bin.', 'Main Office', '2nd floor', 'medium', 'team', True, 'Windows & Doors', 'high'),
    ('Crack in wall', 'There is a long crack in the wall by the stairs that is getting bigger.', 'Warehouse B', 'Stairs', 'medium', 'building_wide', False, 'Structural', 'high'),
    ('Hedge overgrown', 'The hedge by the car park is overgrown and starting to block the path.', 'Depot', 'Car park', 'low', 'team', False, 'Grounds', 'low'),
    ('Coffee spilt', 'Someone spilt coffee all over the corridor floor and it is slippery.', 'Innovation Centre', 'Corridor', 'medium', 'team', True, 'Spillages', 'high'),
    ('No soap', 'There is no soap left in the ladies toilets on the ground floor.', 'Main Office', 'Ground floor', 'low', 'team', False, 'Washroom Supplies', 'low'),
    ('Bins overflowing', 'The bins in the staff kitchen are overflowing again.', 'Main Office', 'Kitchen', 'low', 'team', False, 'Waste & Bins', 'low'),
    ('Mouse droppings', 'There are mouse droppings in the kitchen cupboard next to the food.', 'Riverside House', 'Kitchen', 'medium', 'team', False, 'Pest Control', 'high'),
    ('Needle in car park', 'I found a used needle on the ground in the car park.', 'Main Office', 'Car park', 'high', 'building_wide', True, 'Sharps', 'urgent'),
    ('Extinguisher missing', 'The fire extinguisher by the lift has gone missing.', 'Riverside House', 'Lift lobby', 'medium', 'building_wide', True, 'Fire Equipment', 'high'),
    ('Exit sign not lit', 'The emergency exit sign above the back door is not lit.', 'Depot', 'Back door', 'medium', 'building_wide', True, 'Emergency Lighting', 'high'),
    ('Fire exit blocked', 'Boxes are blocking the fire exit on the ground floor.', 'Warehouse B', 'Ground floor', 'high', 'building_wide', True, 'Escape Routes', 'urgent'),
    ('Trailing cable', 'There is a trailing cable across the walkway and someone nearly tripped.', 'Innovation Centre', 'Walkway', 'medium', 'team', True, 'Trip Hazards', 'high'),
    ('Van flat tyre', 'The pool van has a flat tyre and cannot be driven.', 'Depot', 'Yard', 'medium', 'team', False, 'Vans', 'medium'),
    ('Projector will not turn on', 'The projector in meeting room 2 will not turn on for my presentation.', 'Main Office', 'Meeting room 2', 'medium', 'team', False, 'Projectors & Displays', 'medium'),
    ('Teams camera', 'The camera in the Teams room is not working for video calls.', 'Riverside House', 'Teams room', 'medium', 'team', False, 'Video Conferencing', 'medium'),
    ('Smoke alarm chirping', 'Not a fire - the smoke alarm in the kitchen is chirping because it needs a new battery.', 'Main Office', 'Kitchen', 'low', 'team', False, 'Fire Alarm', 'medium'),
    ('Person trapped in lift', 'The lift is stuck between floors with someone trapped inside.', 'Innovation Centre', 'Main lift', 'urgent', 'building_wide', True, 'Structural', 'urgent'),
    ('Gas smell', 'There is a strong smell of gas in the kitchen.', 'Riverside House', 'Kitchen', 'high', 'building_wide', True, 'Heating', 'urgent'),
    ('Burst pipe', 'A pipe has burst and water is pouring through the ceiling onto computers.', 'Main Office', '1st floor', 'urgent', 'department', True, 'Plumbing', 'urgent'),
    ('Help', 'It does not work.', 'Main Office', '', 'medium', 'single_user', False, None, 'medium'),
    ('Brak ogrzewania', 'W biurze jest bardzo zimno, ogrzewanie nie działa od rana.', 'Warehouse B', 'Biuro', 'medium', 'team', False, 'Heating', 'high'),
    ('Fuga de agua', 'Hay una fuga de agua debajo del lavabo en el baño.', 'Riverside House', 'Baño', 'medium', 'team', False, 'Plumbing', 'high'),
    ('پانی کا رساؤ', 'باتھ روم میں نل سے پانی مسلسل بہہ رہا ہے', 'Main Office', '', 'medium', 'team', False, 'Plumbing', 'high'),
    ('Radiater broke', 'radiater not wokring its freezng in here', 'Depot', 'Office', 'medium', 'team', False, 'Heating', 'high'),
    ("Window won't close", 'The window in my office will not close and the rain is getting in.', 'Main Office', 'Office 12', 'medium', 'single_user', False, 'Windows & Doors', 'high'),
    ('Mouse not working', 'My wireless mouse has stopped working, I have tried new batteries.', 'Main Office', 'Desk 3', 'low', 'single_user', False, 'Hardware', 'low'),
    ('Dirty toilets', 'The toilets on the 3rd floor are filthy and smell awful.', 'Riverside House', '3rd floor', 'medium', 'team', False, 'Deep Clean', 'medium'),
    ('Wasp nest', 'There is a wasp nest above the entrance door and people are getting stung.', 'Depot', 'Entrance', 'high', 'building_wide', True, 'Pest Control', 'high'),
    ('Barrier stuck', 'The car park barrier will not lift and cars are queuing onto the road.', 'Main Office', 'Car park', 'high', 'building_wide', True, 'Access Control', 'high'),
    ('Drawer unit collapsed', 'The drawer unit under hot desk 7 has collapsed and the drawers will not open.', 'Depot', 'Hot desk 7', 'low', 'single_user', False, 'Furniture', 'low'),
    ('Pouring with rain - gutter', 'It is pouring with rain and the gutter outside reception is overflowing.', 'Riverside House', 'Reception', 'medium', 'team', False, 'Roof & Leaks', 'medium'),
    ('Everyone cold', 'Everyone in the team says the office is a bit chilly in the mornings.', 'Main Office', 'Open plan', 'low', 'team', False, 'Heating', 'medium'),
    ('Boiler making banging noise', 'The boiler in the plant room is making loud banging noises.', 'Depot', 'Plant room', 'medium', 'building_wide', False, 'Heating', 'high'),
    ('Fan heater not working', 'The heating in reception is off and visitors are cold.', 'Riverside House', 'Reception', 'medium', 'team', False, 'Heating', 'high'),
    ('Sink blocked', 'The sink in the 2nd floor kitchen is blocked and full of water.', 'Main Office', 'Kitchen', 'medium', 'team', False, 'Plumbing', 'medium'),
    ('Lights not working in toilets', 'None of the lights in the gents toilets come on.', 'Depot', 'Toilets', 'medium', 'team', True, 'Lighting & Electrical', 'high'),
    ('Fire door alarm sounding', 'The fire door at the back keeps setting off the exit alarm.', 'Warehouse B', 'Back door', 'medium', 'team', False, 'Alarms', 'high'),
    ('Not urgent - shelf loose', 'A shelf in the stationery room is loose. No injury, not urgent.', 'Main Office', 'Stationery room', 'low', 'single_user', False, 'Furniture', 'low'),
    ("Can't log in to laptop", 'I am locked out of my laptop after a password reset.', 'Riverside House', '', 'medium', 'single_user', False, 'Accounts & Access', 'medium'),
    ('WiFi slow', 'The wifi is very slow in the meeting rooms on the 3rd floor.', 'Innovation Centre', '3rd floor', 'low', 'team', False, 'Network & Connectivity', 'high'),
    ('Ceiling tile fell down', 'A ceiling tile fell down in the corridor, nobody was hurt.', 'Main Office', 'Corridor', 'high', 'team', True, 'Roof & Leaks', 'high'),
    ('Ants in kitchen', 'There are lots of ants in the kitchen near the sink.', 'Depot', 'Kitchen', 'low', 'team', False, 'Pest Control', 'high'),
    ('Broken glass in car park', 'There is broken glass all over the car park near the entrance.', 'Riverside House', 'Car park', 'high', 'building_wide', True, 'Sharps', 'urgent'),
    ('Defibrillator light flashing', 'The defibrillator by reception has a red light flashing.', 'Main Office', 'Reception', 'medium', 'building_wide', True, 'First Aid', 'high'),
    ('Microphone in council chamber', "The microphones in the council chamber are not working before tonight's meeting.", 'Main Office', 'Council chamber', 'high', 'department', False, 'Council Chamber', 'urgent'),
    ('Zimno w biurze', 'W biurze jest bardzo zimno, kaloryfer nie grzeje.', 'Warehouse B', 'Biuro', 'medium', 'team', False, 'Heating', 'high'),
    ('Sin luz en la oficina', 'No hay luz en la oficina del segundo piso.', 'Main Office', '2nd floor', 'medium', 'team', False, 'Lighting & Electrical', 'medium'),
    ('Tolet flodded', 'the tolet is flodded and watter on the flor', 'Riverside House', 'Toilets', 'medium', 'team', True, 'Plumbing', 'high'),
]

# The benchmark fails if either score drops below these
MIN_CATEGORY_SCORE = 0.95
MIN_PRIORITY_SCORE = 0.90


class TriageBenchmarkTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        teams = {n: Team.objects.create(name=n, contact_email=e, manager=m) for n, e, m in TEAMS}
        for name, team, pri, kw in CATEGORIES:
            Category.objects.create(name=name, default_team=teams[team], default_priority=pri, keywords=kw)

    def suggest(self, title, desc, building, room, urgency, impact, hs):
        return ai.triage(Case(title=title, description=desc, building=building, location_detail=room,
                              reported_urgency=urgency, impact=impact, hs_risk=hs,
                              reporter_name='Test Reporter', reporter_email='test@example.com'))

    def test_benchmark_scores(self):
        cat_ok = pri_ok = 0
        misses = []
        for *report, exp_cat, exp_pri in REPORTS:
            s = self.suggest(*report)
            got_cat = s['category'].name if s['category'] else None
            cat_ok += got_cat == exp_cat
            pri_ok += s['priority'] == exp_pri
            if got_cat != exp_cat or s['priority'] != exp_pri:
                misses.append(f'{report[0]}: category {got_cat} (expected {exp_cat}), '
                              f'priority {s["priority"]} (expected {exp_pri})')
        n = len(REPORTS)
        detail = '\n'.join(misses)
        self.assertGreaterEqual(cat_ok / n, MIN_CATEGORY_SCORE, f'Category {cat_ok}/{n}. Misses:\n{detail}')
        self.assertGreaterEqual(pri_ok / n, MIN_PRIORITY_SCORE, f'Priority {pri_ok}/{n}. Misses:\n{detail}')

    def test_danger_words_in_harmless_phrases_do_not_raise_priority(self):
        cases = [
            ('Extinguisher missing', 'The fire extinguisher by the lift has gone.', 'high'),
            ('Smoke alarm chirping', 'Not a fire, the smoke alarm needs a new battery.', 'high'),
            ('Account locked', 'I am locked out of my account after a password reset.', 'medium'),
            ('Gutter overflowing', 'It is pouring with rain and the gutter is overflowing.', 'medium'),
            ('Drawer broken', 'The drawer unit under my desk has collapsed.', 'low'),
        ]
        for title, desc, expected in cases:
            with self.subTest(title=title):
                s = self.suggest(title, desc, 'Main Office', '', 'low', 'single_user', False)
                self.assertEqual(s['priority'], expected, s['reasoning'])

    def test_real_dangers_are_still_urgent(self):
        for desc in ('There is smoke coming from the socket.', 'There is a fire in the bin store.',
                     'Water is pouring through the ceiling.', 'Someone collapsed in the kitchen.',
                     'There is a strong smell of gas.'):
            with self.subTest(desc=desc):
                s = self.suggest('Help', desc, 'Main Office', '', 'low', 'single_user', False)
                self.assertEqual(s['priority'], 'urgent', s['reasoning'])

    def test_specific_words_beat_generic_ones(self):
        for title, desc, expected in [
            ('Cold tap', 'The cold tap in the kitchen keeps running.', 'Plumbing'),
            ('Fire door', 'The fire door does not close by itself.', 'Windows & Doors'),
            ('No soap', 'There is no soap in the toilets.', 'Washroom Supplies'),
        ]:
            with self.subTest(title=title):
                s = self.suggest(title, desc, 'Main Office', '', 'low', 'single_user', False)
                self.assertEqual(s['category'].name, expected, s['reasoning'])

    def test_misspelling_is_matched_and_explained(self):
        s = self.suggest('Radiater broke', 'radiater not wokring', 'Depot', '', 'low', 'single_user', False)
        self.assertEqual(s['category'].name, 'Heating')
        self.assertIn('radiator (spelt "radiater")', s['reasoning'])


class TriageFairnessTests(TestCase):
    """The same problem written in clear English, poor English and another language. Measured 13 Nov 2026
    (see docs/responsible-design.md): danger is caught in every version, and nothing is ever suggested
    below the urgency the reporter chose. Categories and some priorities still differ, so a person checks."""

    setUpTestData = TriageBenchmarkTests.setUpTestData
    suggest = TriageBenchmarkTests.suggest

    SETS = [
        ('urgent', [('Socket sparking', 'The plug socket by my desk is sparking when I plug things in.'),
                    ('socket spark', 'plug thing at desk make sparks when i put plug'),
                    ('ساکٹ سے چنگاریاں', 'میری میز کے ساکٹ سے چنگاریاں نکل رہی ہیں اور آگ کا خطرہ ہے۔')]),
        ('high', [('No heating', 'There is no heating in the office and it is freezing.'),
                  ('heater no work', 'heater not work very cold all people cold'),
                  ('Sin calefacción', 'No hay calefacción en la oficina y hace mucho frío.')]),
        ('medium', [('Water leaking from ceiling', 'Water is leaking through the ceiling onto a desk in the office.'),
                    ('watter leek', 'water coming from celing on desk pls help'),
                    ('Przeciek z sufitu', 'Woda kapie z sufitu na biurko w biurze.')]),
        ('medium', [('Printer not working', 'The printer on the second floor is jammed and will not print.'),
                    ('printer broke', 'printer 2 floor paper stuck no print'),
                    ('Drukarka nie działa', 'Drukarka na drugim piętrze zacina papier i nie drukuje.')]),
    ]

    def test_poor_english_and_other_languages_are_never_under_prioritised(self):
        for at_least, versions in self.SETS:
            for title, desc in versions:
                with self.subTest(title=title):
                    s = self.suggest(title, desc, 'Main Office', '', 'medium', 'team', False)
                    # Never below the reporter's own "medium", and danger is caught in every language
                    self.assertGreaterEqual(PRIORITY_RANK[s['priority']], PRIORITY_RANK[at_least])

    def test_unrecognised_reports_are_flagged_for_a_person_to_check(self):
        s = self.suggest('Drukarka nie działa', 'Drukarka na drugim piętrze zacina papier i nie drukuje.',
                         'Main Office', '', 'medium', 'team', False)
        # Either it was understood, or it's marked as low confidence so the case handler checks it carefully
        self.assertTrue(s['category'] is not None or s['confidence'] <= 50)
