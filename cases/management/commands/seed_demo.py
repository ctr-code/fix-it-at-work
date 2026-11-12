"""
Load fictional demo data. All names, emails and places are made up.

    python manage.py seed_demo          # wipe cases and reload everything

Also creates one demo login per role. The password comes from DEMO_PASSWORD in
your local .env (never commit it). If it is not set, a random one is printed.
"""
import os
import random
import secrets
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from cases import ai
from cases.models import (
    PRIORITY_RANK, Case, Category, Communication, Officer, Profile, Role, SiteVisit, SLARule, Status, Team,
)

# Demo logins: (username, first name, last name, role)
DEMO_USERS = [
    ('alex', 'Alex', 'Morgan', Role.REPORTER),
    ('jo', 'Jo', 'Clarke', Role.HANDLER),
    ('rob', 'Rob', 'Turner', Role.MANAGER),
] + [(name.split()[0].lower(), *name.split(), Role.OFFICER) for name in [
    'Sam Okafor', 'Priya Shah', 'Tom Becker', 'Aisha Rahman', 'Dan Walsh', 'Mei Lin', 'Grace Mensah', 'Owen Price',
]] + [('serena', 'Serena', '', Role.OFFICER)]

# Teams and categories follow the "Mock data v3" spreadsheet: its Assigned Team column is the team,
# and its Sub-Category column is the category. Each category belongs to exactly one team.
TEAMS = [
    ('Facilities Helpdesk', 'facilities@example.com', 'Rob Turner'),
    ('IT Service Desk', 'it.servicedesk@example.com', 'Nadia Karim'),
    ('IT Network Team', 'it.network@example.com', 'Nadia Karim'),
    ('Security & Access Team', 'security@example.com', 'Chris Hall'),
    ('Estates Maintenance', 'estates@example.com', 'Helen Ward'),
    ('Cleaning Services', 'cleaning@example.com', 'Bev Hughes'),
    ('Health & Safety Team', 'health.safety@example.com', 'Martin Shaw'),
    ('Fleet Services', 'fleet@example.com', 'Lorraine Webb'),
    ('AV & Meeting Room Support', 'av.support@example.com', 'Nadia Karim'),
]

# (category, team, default priority, comma separated keywords for the triage assistant).
# Keywords match the start of a word, so "light" also matches "lights". Default priorities are the
# most common priority for that sub-category in the spreadsheet.
CATEGORIES = [
    ('Heating', 'Facilities Helpdesk', 'high',
     'heating, radiator, cold, freezing, boiler, thermostat, gas, gas smell, smell of gas, gas leak, '
     'ogrzewanie, zimno, calefacción, frío, ہیٹنگ, ٹھنڈ'),
    ('Air Conditioning', 'Facilities Helpdesk', 'medium',
     'air con, air conditioning, aircon, ac unit, hot air, overheating, too hot, ventilation, degrees, stuffy'),
    ('Plumbing', 'Facilities Helpdesk', 'medium',
     'pipe, tap, toilet, sink, washbasin, drain, blocked, burst, hot water, leaking pipe, drip, '
     'inodoro, atascado, grifo, lavabo, rura, kran, przeciek, fuga, نل, رساؤ, باتھ روم'),
    ('Lighting & Electrical', 'Facilities Helpdesk', 'medium',
     'light, bulb, socket, power, electric, wire, flicker, sparking, sparks, plug, burning, fuse, '
     'światło, prąd, luz, enchufe, بجلی, لائٹ'),
    ('Furniture', 'Facilities Helpdesk', 'low', 'chair, furniture, drawer, cabinet, shelf, shelves'),

    ('Hardware', 'IT Service Desk', 'medium',
     'laptop, computer, pc, monitor, keyboard, mouse, docking, charger, charging, charge, not starting'),
    ('Software', 'IT Service Desk', 'low', 'software, outlook, excel, application, crashing, crashes, install'),
    ('Printing', 'IT Service Desk', 'low', 'printer, printing, prints, toner, paper jam, jam, copier, scanner'),
    ('Accounts & Access', 'IT Service Desk', 'medium',
     'password, account, login, log in, shared drive, permissions, mfa'),
    ('Telephony', 'IT Service Desk', 'medium', 'phone, telephone, handset, voicemail, headset'),

    ('Network & Connectivity', 'IT Network Team', 'high',
     'wifi, wi-fi, wireless, network, internet, connectivity, connection, vpn, ethernet, sieć'),

    ('Access Control', 'Security & Access Team', 'high',
     'door, badge, card reader, access door, barrier, gate, entrance, turnstile, not locking'),
    ('Keys & Fobs', 'Security & Access Team', 'medium', 'keys, lost key, fob, lanyard, key safe'),
    ('Alarms', 'Security & Access Team', 'high',
     'intruder alarm, burglar alarm, alarm sounding, alarm going off, false activation, exit alarm'),
    ('CCTV', 'Security & Access Team', 'medium',
     'cctv, security camera, suspicious, stranger, theft, stolen, break-in, intruder, tailgating, recognise'),

    ('Roof & Leaks', 'Estates Maintenance', 'medium',
     'roof, ceiling, damp, gutter, rain, water coming in, stain, sagging, water damage, mould, dripping from, '
     'wilgoć, humedad'),
    ('Windows & Doors', 'Estates Maintenance', 'high',
     'window, cracked window, crack in the window, blind, fire door, door closer, hinge, glazing, not closing, does not close, okno, ventana'),
    ('Structural', 'Estates Maintenance', 'high', 'crack, wall, floor tile, lifted, subsidence, stairs, lift'),
    ('Grounds', 'Estates Maintenance', 'low', 'hedge, grass, path, grounds, tree, pothole, gritting, weeds, overgrown'),

    ('Spillages', 'Cleaning Services', 'high', 'spill, spilt, spilled, sticky, wet floor, liquid on'),
    ('Washroom Supplies', 'Cleaning Services', 'low',
     'soap, paper towel, toilet roll, hand towel, sanitiser, out of supplies'),
    ('Waste & Bins', 'Cleaning Services', 'low', 'bin, rubbish, waste, overflowing, litter, recycling'),
    ('Deep Clean', 'Cleaning Services', 'medium', 'deep clean, dirty, filthy, smell, hygiene, vomit, unclean'),
    ('Pest Control', 'Cleaning Services', 'high',
     'mice, mouse droppings, rats, pest, cockroach, ants, wasp, nest, bees, hornet, stung, droppings, flies'),
    ('Sharps', 'Cleaning Services', 'urgent', 'needle, syringe, sharps, broken glass'),

    ('Fire Equipment', 'Health & Safety Team', 'high', 'fire extinguisher, extinguisher, fire blanket, hose reel'),
    ('Emergency Lighting', 'Health & Safety Team', 'high', 'emergency light, exit sign'),
    ('First Aid', 'Health & Safety Team', 'low', 'first aid, defibrillator, defib, eyewash, bandage'),
    ('Fire Alarm', 'Health & Safety Team', 'high', 'fire alarm, call point, smoke detector, smoke alarm, alarm panel'),
    ('Escape Routes', 'Health & Safety Team', 'urgent',
     'fire exit, escape route, exit blocked, blocked exit, emergency exit, fire escape'),
    ('Trip Hazards', 'Health & Safety Team', 'high',
     'trip, trailing cable, cable across, uneven, catching their feet, slippery, carpet'),

    ('Refuse Vehicles', 'Fleet Services', 'high',
     'refuse vehicle, refuse truck, bin lorry, bin lift, hydraulic, compactor, lorry'),
    ('Pool Cars', 'Fleet Services', 'medium', 'pool car, warning light, car service'),
    ('Vans', 'Fleet Services', 'medium', 'van, flat tyre, tyre, puncture'),
    ('Telematics', 'Fleet Services', 'low', 'tracker, telematics, gps, vehicle tracking, dashcam'),
    ('EV Charging', 'Fleet Services', 'medium', 'ev charger, ev charging, electric vehicle, charge point, charging point'),

    ('Projectors & Displays', 'AV & Meeting Room Support', 'medium',
     'projector, display, meeting room screen, hdmi, smartboard, presentation'),
    ('Video Conferencing', 'AV & Meeting Room Support', 'medium',
     'teams room, video call, webcam, camera, video conferencing, speakerphone'),
    ('Council Chamber', 'AV & Meeting Room Support', 'urgent',
     'council chamber, chamber, webcast, microphone, voting system, livestream'),
    ('Hearing Loops', 'AV & Meeting Room Support', 'high', 'hearing loop, induction loop, hearing aid'),
]

# Officers with a demo login are listed first. Teams the demo logins don't cover use officer names from
# the spreadsheet; they have no login until a manager gives them one on the People page.
OFFICERS = [
    ('Sam Okafor', 'Facilities Helpdesk'), ('Priya Shah', 'Facilities Helpdesk'),
    ('Tom Becker', 'IT Service Desk'), ('Aisha Rahman', 'IT Network Team'),
    ('Dan Walsh', 'Security & Access Team'), ('Mei Lin', 'Security & Access Team'),
    ('Grace Mensah', 'Estates Maintenance'), ('Owen Price', 'Estates Maintenance'),
    ('Kevin Brooks', 'Cleaning Services'), ('Maria Silva', 'Cleaning Services'),
    ('Sunita Rao', 'Health & Safety Team'), ('Alan Whitfield', 'Health & Safety Team'),
    ('Darren Cole', 'Fleet Services'), ('Mick Fraser', 'Fleet Services'),
    ('Jordan Ellis', 'AV & Meeting Room Support'),
]

# Serena: a field officer with a fixed set of five open jobs, so "My jobs" always has a full list to show.
# She joins her team after the other cases are made, so random assignment never gives her extra jobs.
SERENA_TEAM = 'Facilities Helpdesk'
# Same fields as REPORTS, plus the category and priority the handler chose at triage.
# One job per Facilities category, each in a different building, with a mix of priorities and stages.
SERENA_JOBS = [
    ('Desk drawer unit collapsed', 'The drawer unit under hot desk 7 has collapsed and the drawers will not open.',
     'Depot', 'Hot desk 7', 'low', 'en', 'Ellie Watson', 3, 'assigned', 'Furniture', 'low'),
    ('Air con dripping onto desks', 'Water is dripping from the air conditioning unit onto two desks by the window. '
     'We have moved the laptops.', 'Warehouse B', 'Upstairs office', 'high', 'en', 'Oscar Bennett', 2.5,
     'in_progress', 'Air Conditioning', 'high'),
    ('Radiator stuck on full in finance office', 'The radiator in the finance office is stuck on full heat and the '
     'valve will not turn. The room is uncomfortably hot.', 'Innovation Centre', '2nd floor finance office', 'medium',
     'en', 'Nina Gallagher', 1.2, 'assigned', 'Heating', 'medium'),
    ('No hot water in 3rd floor kitchen', 'The hot water tap in the 3rd floor kitchen only runs cold. Staff cannot '
     'wash up.', 'Main Office', '3rd floor kitchen', 'medium', 'en', 'Priyanka Desai', 0.6, 'assigned', 'Plumbing',
     'medium'),
    ('Lights out in basement corridor', 'Half the lights in the basement corridor have gone out and it is very dark '
     'by the stairs.', 'Riverside House', 'Basement corridor', 'urgent', 'en', 'Tariq Malik', 0.1, 'assigned',
     'Lighting & Electrical', 'urgent'),
]

# (priority, response target hours, resolution target hours), from the mock data's SLA Settings sheet.
# Calendar hours: the clock runs 24/7.
SLA = [('urgent', 1, 4), ('high', 4, 24), ('medium', 8, 72), ('low', 24, 120)]

# (title, description, building, room, reporter urgency, language, reporter, days ago, stage)
REPORTS = [
    ('Leaking pipe under kitchen sink', 'Water dripping from the pipe under the sink in the 2nd floor kitchen. '
     'There is a puddle forming on the floor.', 'Main Office', '2nd floor kitchen', 'high', 'en', 'Alex Morgan', 25, 'closed'),
    ('Radiator not working', 'The radiator in meeting room 3 is cold all day. The room is freezing for morning meetings.',
     'Riverside House', 'Meeting room 3', 'medium', 'en', 'Jordan Hale', 22, 'closed'),
    ('Printer jammed and showing error', 'The big printer by reception keeps jamming and now shows error E-204. '
     'Nobody on the floor can print.', 'Main Office', 'Ground floor reception', 'medium', 'en', 'Casey Patel', 20, 'closed'),
    ('Badge reader on side door not working', 'My badge does not open the side entrance door. I have to walk round '
     'to the front every time.', 'Warehouse B', 'Side entrance', 'medium', 'en', 'Riley Brooks', 18, 'closed'),
    ('Flickering lights in open office', 'Two ceiling lights flicker constantly near desks 40-48, giving people headaches.',
     'Innovation Centre', '1st floor open plan', 'medium', 'en', 'Sam Taylor', 16, 'closed'),
    ('Leak in staff toilets', 'Water is dripping from the pipe under the washbasin in the staff toilets. '
     'The floor is wet.', 'Warehouse B', 'Staff toilets', 'high', 'en', 'Marta Nowak', 14, 'closed'),
    ('Bin store overflowing', 'The bins outside the loading bay are overflowing and rubbish is blowing around the yard.',
     'Warehouse B', 'Loading bay', 'low', 'en', 'Lee Johnson', 12, 'closed'),
    ('Laptop will not charge', 'My laptop stopped charging this morning. I tried two different chargers.',
     'Riverside House', '3rd floor', 'low', 'en', 'Morgan Price', 10, 'closed'),
    ('Cracked window in stairwell', 'There is a large crack in the window on the stairwell between floors 1 and 2.',
     'Main Office', 'Stairwell B', 'medium', 'en', 'Taylor Reid', 9, 'closed'),
    ('Wifi keeps dropping', 'The wifi drops every few minutes in the east wing. It affects the whole team on calls.',
     'Innovation Centre', 'East wing', 'high', 'en', 'Alex Morgan', 6, 'closed'),
    ('Toilet blocked', 'The toilet in the ground floor loos is blocked and there is water on the floor.',
     'Riverside House', 'Ground floor toilets', 'medium', 'en', 'Lucía Fernández', 4, 'closed'),
    ('Air conditioning blowing hot air', 'The air con in the training room is blowing hot air and it is 28 degrees.',
     'Main Office', 'Training room', 'medium', 'en', 'Alex Morgan', 3, 'resolved'),
    ('Monitor screen flickering', 'My second monitor keeps flickering and going black every few minutes.',
     'Riverside House', '2nd floor desk 21', 'low', 'en', 'Imran Hussain', 2, 'resolved'),
    ('Ceiling tile stained and sagging', 'A ceiling tile above the photocopier is stained brown and sagging. '
     'Looks like water damage from above.', 'Main Office', '1st floor print area', 'high', 'en', 'Robin Hayes', 6, 'in_progress'),
    ('Fire door not closing properly', 'The fire door on the 3rd floor does not close on its own anymore, it stays open.',
     'Riverside House', '3rd floor corridor', 'high', 'en', 'Charlie Evans', 5, 'in_progress'),
    ('Projector not connecting', 'The projector in the boardroom will not connect to laptops using HDMI.',
     'Innovation Centre', 'Boardroom', 'medium', 'en', 'Drew Wilson', 8, 'in_progress'),
    ('No heating in warehouse office', 'Heating has stopped in the warehouse office. It is very cold and staff are '
     'wearing coats.', 'Warehouse B', 'Office', 'high', 'en', 'Kai Murphy', 7, 'assigned'),
    ('Car park barrier stuck', 'The car park barrier is stuck in the down position and cars are queuing on the road.',
     'Main Office', 'Car park', 'high', 'en', 'Alex Morgan', 1, 'assigned'),
    ('Socket sparking', 'The wall socket by desk 12 made a sparking noise and there is a smell of burning.',
     'Riverside House', '2nd floor desk 12', 'urgent', 'en', 'Quinn Foster', 0.3, 'assigned'),
    ('Carpet ripped by lift', 'Carpet is ripped by the lift on the ground floor and people keep catching their feet. '
     'Trip hazard.', 'Innovation Centre', 'Ground floor lift lobby', 'medium', 'en', 'Harper Lewis', 2, 'assigned'),
    ('Window blind broken', 'The blind in meeting room 5 is broken and cannot be lowered. Sun glare on all the screens.',
     'Riverside House', 'Meeting room 5', 'medium', 'en', 'Rowan King', 16, 'assigned'),
    ('Pool car warning light', 'The pool car has an orange engine warning light on the dashboard since this morning.',
     'Depot', 'Pool car bay 2', 'medium', 'en', 'Casey Patel', 11, 'closed'),
    ('Fire extinguisher missing', 'The fire extinguisher by the kitchen door has gone, only the bracket is left.',
     'Riverside House', '2nd floor kitchen', 'high', 'en', 'Sam Taylor', 1.5, 'assigned'),
    # New - waiting for triage (shows AI suggestions, duplicates and fairness rules)
    ('Water dripping from ceiling', 'Water is dripping from the ceiling near the photocopier on the 1st floor. '
     'Someone has put a bucket there.', 'Main Office', '1st floor print area', 'high', 'en', 'Alex Morgan', 0.08, 'new'),
    ('Suspicious person in car park', 'Someone I did not recognise was trying car door handles in the car park '
     'about 10 minutes ago.', 'Main Office', 'Car park', 'high', 'en', 'Frankie Moss', 0.04, 'new'),
    ('Lift making grinding noise', 'The lift makes a loud grinding noise between floors 2 and 3.',
     'Innovation Centre', 'Main lift', 'medium', 'en', 'Reese Cooper', 0.2, 'new'),
    ('Heating not working', 'It is very cold in the warehouse office. The heating has not worked since this morning.',
     'Warehouse B', 'Office', 'medium', 'en', 'Piotr Kowalski', 0.1, 'new'),
    ('Broken', 'It is broken again.', 'Riverside House', '', 'medium', 'en', 'Billie Ward', 0.4, 'new'),
]

# What the reporter told us about each report: (who is affected, health and safety risk, asset tag)
REPORT_DETAILS = {
    'Leaking pipe under kitchen sink': ('team', True, ''),
    'Radiator not working': ('team', False, ''),
    'Printer jammed and showing error': ('department', False, 'PRN-MO-G01'),
    'Badge reader on side door not working': ('single_user', False, 'ACR-WB-03'),
    'Flickering lights in open office': ('team', False, ''),
    'Leak in staff toilets': ('team', True, ''),
    'Bin store overflowing': ('building_wide', False, ''),
    'Laptop will not charge': ('single_user', False, 'LT-04512'),
    'Cracked window in stairwell': ('building_wide', True, ''),
    'Wifi keeps dropping': ('team', False, 'AP-IC-E02'),
    'Toilet blocked': ('team', True, ''),
    'Air conditioning blowing hot air': ('team', False, 'AC-MO-TR1'),
    'Monitor screen flickering': ('single_user', False, 'MON-RH-221'),
    'Ceiling tile stained and sagging': ('team', True, ''),
    'Fire door not closing properly': ('building_wide', True, 'FD-RH-3-02'),
    'Projector not connecting': ('team', False, 'PRJ-IC-BR1'),
    'No heating in warehouse office': ('team', False, 'BLR-WB-01'),
    'Car park barrier stuck': ('building_wide', True, 'BAR-MO-01'),
    'Socket sparking': ('team', True, ''),
    'Carpet ripped by lift': ('building_wide', True, ''),
    'Window blind broken': ('team', False, ''),
    'Pool car warning light': ('department', False, 'VEH-PC14'),
    'Fire extinguisher missing': ('building_wide', True, 'FE-RH-2K'),
    'Water dripping from ceiling': ('team', True, ''),
    'Suspicious person in car park': ('building_wide', True, ''),
    'Lift making grinding noise': ('building_wide', True, 'LIFT-IC-01'),
    'Heating not working': ('team', False, 'BLR-WB-01'),
    'Broken': ('single_user', False, ''),
    # Serena's jobs
    'Desk drawer unit collapsed': ('single_user', False, 'FUR-DP-HD7'),
    'Air con dripping onto desks': ('team', True, 'AC-WB-U01'),
    'Radiator stuck on full in finance office': ('team', False, 'RAD-IC-2F3'),
    'No hot water in 3rd floor kitchen': ('department', False, ''),
    'Lights out in basement corridor': ('building_wide', True, ''),
}

# Reporter feedback on closed cases. Weights follow the spreadsheet's spread of scores (mostly 4s and 5s);
# a fix that took more than one visit, or missed its SLA, shifts the weights down.
SATISFACTION_WEIGHTS = {'good': [2, 4, 12, 30, 52], 'poor': [10, 20, 35, 25, 10]}  # for scores 1..5
# Fixed feedback so the demo always has an unhappy reporter for the case handler to follow up
FIXED_FEEDBACK = {'Toilet blocked': (2, 'Took two visits and the floor was left wet the first time.')}
# The demo reporter's own closed cases get no made-up feedback, so their home page asks them to rate the fix
DEMO_REPORTER = 'Alex Morgan'

SATISFACTION_COMMENTS = {
    5: ['Really quick response and the engineer explained what had happened.', 'Sorted the same day, thank you.',
        'Great service, kept me updated throughout.'],
    4: ['Fixed well, took a little longer than I expected.', 'Good job, would have liked an update sooner.'],
    3: ['Fixed in the end but I had to chase.', 'OK, but nobody told me when someone was coming.'],
    2: ['Took several visits to fix.', 'Slow, and the problem came back once.'],
    1: ['Took far too long and nobody kept me informed.'],
}

# What the officer wrote when they fixed it, by team: (what they found, what they did)
VISIT_NOTES = {
    'Facilities Helpdesk': ('A worn part was causing the fault.',
                            'Replaced the worn part. Tested and checked again after 20 minutes, all working.'),
    'IT Service Desk': ('Hardware fault in the unit.',
                        'Swapped the unit for a tested spare and confirmed it works with the user.'),
    'IT Network Team': ('One access point was failing and dropping connections.',
                        'Replaced the access point and checked signal strength across the area. Connection stable.'),
    'Security & Access Team': ('The reader and lock had lost their settings.',
                               'Re-set and tested the reader and lock. Reviewed CCTV and logged with the site '
                               'security lead.'),
    'Estates Maintenance': ('The area was unsafe to use.',
                            'Made safe and taped off the area, then carried out the repair. Checked the '
                            'surrounding area.'),
    'Cleaning Services': ('The area needed a full clean.', 'Cleared and cleaned the area. Added it to the weekly check list.'),
    'Health & Safety Team': ('A hazard was in a walkway.', 'Made the area safe and removed the hazard. Recorded in the H&S log.'),
    'Fleet Services': ('A faulty part on the vehicle.',
                       'Replaced the faulty part and road tested the vehicle. Back in service.'),
    'AV & Meeting Room Support': ('A faulty cable was stopping the system connecting.',
                                  'Reset the system and replaced the cable. Tested with a laptop and a Teams call.'),
}
FOLLOW_UP = ('Part needed that is not in the van.', 'Ordered the part and booked a return visit.')

HANDLER = 'Jo Clarke'


class Command(BaseCommand):
    help = 'Load fictional demo data (deletes existing cases)'

    def handle(self, *args, **options):
        rng = random.Random(7)
        now = timezone.now()

        Case.objects.all().delete()
        Officer.objects.all().delete()
        Category.objects.all().delete()
        Team.objects.all().delete()
        SLARule.objects.all().delete()

        teams = {n: Team.objects.create(name=n, contact_email=e, manager=m) for n, e, m in TEAMS}
        for name, team, pri, kw in CATEGORIES:
            Category.objects.create(name=name, default_team=teams[team], default_priority=pri, keywords=kw)
        users = self.make_users()
        for name, team in OFFICERS:
            Officer.objects.create(name=name, team=teams[team], user=users.get(name.split()[0].lower()),
                                   contact_email=name.lower().replace(' ', '.') + '@example.com')
        for p, ack, res in SLA:
            SLARule.objects.create(priority=p, acknowledge_hours=ack, resolve_hours=res)

        # Oldest first, so references follow the order things were reported
        for spec in sorted(REPORTS, key=lambda r: -r[7]):
            self.make_case(spec, rng, now)

        # The demo reporter can see their own reports on their home page
        Case.objects.filter(reporter_name='Alex Morgan').update(reporter_user=users['alex'])

        self.make_serena(teams[SERENA_TEAM], users['serena'], rng, now)

        self.stdout.write(self.style.SUCCESS(f'Loaded {Case.objects.count()} fictional cases.'))
        self.stdout.write('Demo logins: ' + ', '.join(f'{u} ({r.label})' for u, _, _, r in DEMO_USERS[:4]) +
                          ' ... plus one per field officer.')

    def make_users(self):
        User = get_user_model()
        password = os.getenv('DEMO_PASSWORD')
        if not password:
            password = secrets.token_urlsafe(9)
            self.stdout.write(self.style.WARNING(f'DEMO_PASSWORD not set in .env - using: {password}'))
        users = {}
        for username, first, last, role in DEMO_USERS:
            User.objects.filter(username=username).delete()
            user = User.objects.create_user(username, f'{username}@example.com', password,
                                            first_name=first, last_name=last)
            Profile.objects.update_or_create(user=user, defaults={'role': role})
            users[username] = user
        return users

    def make_serena(self, team, user, rng, now):
        """Add Serena to her team and give her the five jobs in SERENA_JOBS. Safe to run again."""
        Case.objects.filter(title__in=[j[0] for j in SERENA_JOBS]).delete()
        Officer.objects.filter(name='Serena').delete()
        officer = Officer.objects.create(name='Serena', team=team, user=user, contact_email='serena@example.com')
        for spec in sorted(SERENA_JOBS, key=lambda r: -r[7]):
            *report, category, priority = spec
            self.make_case(report, rng, now, officer=officer, category=category, priority=priority)
        return officer

    def make_case(self, spec, rng, now, officer=None, category=None, priority=None):
        """Create one case and walk it to its stage. officer, category and priority, when given,
        replace the random officer and the AI's suggestions at triage."""
        title, desc, building, room, urgency, lang, name, days_ago, stage = spec
        reported = now - timedelta(days=days_ago)
        impact, hs_risk, asset_tag = REPORT_DETAILS[title]
        case = Case.objects.create(
            title=title, description=desc, building=building, location_detail=room,
            reported_urgency=urgency, impact=impact, hs_risk=hs_risk, asset_tag=asset_tag,
            preferred_language=lang, reporter_name=name,
            reporter_email=name.split()[0].lower() + '@example.com', date_reported=reported,
        )
        s = ai.triage(case)
        case.ai_category, case.ai_priority = s['category'], s['priority']
        case.ai_summary, case.ai_reasoning = s['summary'], s['reasoning']
        case.ai_confidence, case.ai_duplicate_candidate = s['confidence'], s['duplicate']
        case.save()
        Communication.objects.create(case=case, kind='receipt', language=lang, draft_text=ai.receipt_text(case),
                                     approved_by='Automatic', date_sent=reported)
        if stage == 'new':
            return

        # Triage: the handler accepts most AI suggestions, sometimes raises priority
        case.category = Category.objects.get(name=category) if category else s['category']
        if priority:
            case.priority = priority
        else:
            case.priority = s['priority']
            if rng.random() < 0.2 and case.priority != 'urgent':
                case.priority = {1: 'medium', 2: 'high', 3: 'urgent'}[PRIORITY_RANK[case.priority]]
        case.ai_suggestion_accepted = case.priority == s['priority'] and case.category == s['category']
        case.assigned_team = case.category.default_team
        case.assigned_officer = officer or rng.choice(list(case.assigned_team.officers.all()))
        case.triaged_by = HANDLER
        # Response and fix times scale with the priority's SLA targets, so most meet them and a few don't
        rule = SLARule.objects.get(priority=case.priority)
        case.date_acknowledged = reported + timedelta(hours=rule.acknowledge_hours * rng.uniform(0.1, 1.3))
        case.status = Status.ASSIGNED
        case.apply_sla()
        case.save()
        Communication.objects.create(
            case=case, kind='ack', language=lang, approved_by=HANDLER, date_sent=case.date_acknowledged,
            draft_text=f'Your report {case.reference} has been passed to our {case.assigned_team} team.')
        if stage == 'assigned':
            return

        found, did = VISIT_NOTES[case.assigned_team.name]
        first_visit = min(case.date_acknowledged + timedelta(hours=rule.resolve_hours * rng.uniform(0.1, 0.7)),
                          now - timedelta(hours=2))
        if stage == 'in_progress':
            SiteVisit.objects.create(case=case, officer=case.assigned_officer, visited_at=first_visit,
                                     note=FOLLOW_UP[0], action=FOLLOW_UP[1],
                                     ai_summary=ai.summarise_visit(FOLLOW_UP[0], False, FOLLOW_UP[1]))
            case.status = Status.IN_PROGRESS
            case.save()
            return

        two_visits = rng.random() < 0.3
        visit_time = first_visit
        if two_visits:
            SiteVisit.objects.create(case=case, officer=case.assigned_officer, visited_at=first_visit,
                                     note=FOLLOW_UP[0], action=FOLLOW_UP[1],
                                     ai_summary=ai.summarise_visit(FOLLOW_UP[0], False, FOLLOW_UP[1]))
            visit_time = min(first_visit + timedelta(hours=rule.resolve_hours * rng.uniform(0.2, 0.6)),
                             now - timedelta(hours=1))
        SiteVisit.objects.create(case=case, officer=case.assigned_officer, visited_at=visit_time, note=found,
                                 action=did, fixed=True, transcript_used=rng.random() < 0.4,
                                 ai_summary=ai.summarise_visit(found, True, did))
        case.status = Status.RESOLVED
        case.date_resolved = visit_time
        case.first_time_fix = not two_visits
        case.save()
        if stage == 'resolved':
            return

        sent = min(visit_time + timedelta(hours=rng.uniform(1, 6)), now)
        Communication.objects.create(case=case, kind='outcome', language=lang, ai_drafted=True,
                                     draft_text=ai.draft_outcome_letter(case), approved_by=HANDLER, date_sent=sent)
        case.status = Status.CLOSED
        case.date_closed = sent
        if title in FIXED_FEEDBACK:
            case.satisfaction, case.satisfaction_comments = FIXED_FEEDBACK[title]
        elif name != DEMO_REPORTER and rng.random() < 0.75:  # about three in four reporters leave feedback
            weights = SATISFACTION_WEIGHTS['good' if case.first_time_fix and not case.is_overdue else 'poor']
            case.satisfaction = rng.choices([1, 2, 3, 4, 5], weights)[0]
            if rng.random() < 0.6:
                case.satisfaction_comments = rng.choice(SATISFACTION_COMMENTS[case.satisfaction])
        case.save()
