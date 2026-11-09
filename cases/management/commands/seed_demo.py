"""
Load fictional demo data. All names, emails and places are made up.

    python manage.py seed_demo          # wipe cases and reload everything
"""
import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from cases import ai
from cases.models import (
    PRIORITY_RANK, Case, Category, Communication, Officer, SiteVisit, SLARule, Status, Team,
)

TEAMS = [
    ('Facilities', 'facilities@example.com', 'Rob Turner'),
    ('IT', 'it.support@example.com', 'Nadia Karim'),
    ('Security', 'security@example.com', 'Chris Hall'),
    ('Estates', 'estates@example.com', 'Helen Ward'),
]

CATEGORIES = [
    ('Plumbing & leaks', 'Leaks, blocked toilets, taps', 'Facilities', 'high',
     'leak, leaking, water, pipe, drip, toilet, sink, tap, burst, blocked, drain, inodoro, atascado, '
     'wyciek, przeciek, woda, rura, agua, fuga'),
    ('Heating & air con', 'Too hot, too cold, ventilation', 'Facilities', 'medium',
     'heating, radiator, cold, hot air, temperature, air con, boiler, freezing, ventilation, degrees, '
     'ogrzewanie, zimno, calefacción, frío'),
    ('Electrical & lighting', 'Lights, sockets, power', 'Facilities', 'high',
     'light, lights, bulb, socket, power, electric, wire, flicker, sparking, sparks, plug, burning'),
    ('IT equipment', 'Laptops, printers, wifi, AV', 'IT', 'medium',
     'laptop, computer, monitor, printer, screen, keyboard, mouse, wifi, network, internet, login, '
     'projector, hdmi, charging, charge, jam'),
    ('Access & doors', 'Doors, badges, barriers, lifts', 'Security', 'high',
     'door, lock, badge, pass, card reader, access, key, gate, barrier, entrance, fire door'),
    ('Security concern', 'Suspicious activity, theft', 'Security', 'high',
     'suspicious, stranger, theft, stolen, break-in, intruder, cctv, alarm, tailgating, recognise'),
    ('Building fabric', 'Walls, ceilings, floors, windows, lifts', 'Estates', 'medium',
     'ceiling, wall, roof, window, crack, cracked, tile, carpet, damp, mould, stairs, blind, '
     'lift, trip'),
    ('Cleaning & waste', 'Bins, spills, hygiene', 'Facilities', 'low',
     'bin, bins, rubbish, spill, dirty, clean, smell, waste'),
    ('General / Other', 'Anything else', 'Facilities', 'low', ''),
]

OFFICERS = [
    ('Sam Okafor', 'Facilities'), ('Priya Shah', 'Facilities'),
    ('Tom Becker', 'IT'), ('Aisha Rahman', 'IT'),
    ('Dan Walsh', 'Security'), ('Mei Lin', 'Security'),
    ('Grace Mensah', 'Estates'), ('Owen Price', 'Estates'),
]

SLA = [('urgent', 1, 1), ('high', 4, 3), ('medium', 24, 10), ('low', 48, 20)]

# (title, description, building, room, reporter urgency, language, reporter, days ago, stage)
REPORTS = [
    ('Leaking pipe under kitchen sink', 'Water dripping from the pipe under the sink in the 2nd floor kitchen. '
     'There is a puddle forming on the floor.', 'Main Office', '2nd floor kitchen', 'high', 'en', 'Alex Morgan', 25, 'closed'),
    ('Radiator not working', 'The radiator in meeting room 3 is cold all day. The room is freezing for morning meetings.',
     'Riverside House', 'Meeting room 3', 'medium', 'en', 'Jordan Ellis', 22, 'closed'),
    ('Printer jammed and showing error', 'The big printer by reception keeps jamming and now shows error E-204. '
     'Nobody on the floor can print.', 'Main Office', 'Ground floor reception', 'medium', 'en', 'Casey Patel', 20, 'closed'),
    ('Badge reader on side door not working', 'My badge does not open the side entrance door. I have to walk round '
     'to the front every time.', 'Warehouse B', 'Side entrance', 'medium', 'en', 'Riley Brooks', 18, 'closed'),
    ('Flickering lights in open office', 'Two ceiling lights flicker constantly near desks 40-48, giving people headaches.',
     'Innovation Centre', '1st floor open plan', 'medium', 'en', 'Sam Taylor', 16, 'closed'),
    ('Przeciek w łazience', 'Woda kapie z rury pod umywalką w łazience dla pracowników. Podłoga jest mokra.',
     'Warehouse B', 'Staff toilets', 'high', 'pl', 'Marta Nowak', 14, 'closed'),
    ('Bin store overflowing', 'The bins outside the loading bay are overflowing and rubbish is blowing around the yard.',
     'Warehouse B', 'Loading bay', 'low', 'en', 'Lee Johnson', 12, 'closed'),
    ('Laptop will not charge', 'My laptop stopped charging this morning. I tried two different chargers.',
     'Riverside House', '3rd floor', 'low', 'en', 'Morgan Price', 10, 'closed'),
    ('Cracked window in stairwell', 'There is a large crack in the window on the stairwell between floors 1 and 2.',
     'Main Office', 'Stairwell B', 'medium', 'en', 'Taylor Reid', 9, 'closed'),
    ('Wifi keeps dropping', 'The wifi drops every few minutes in the east wing. It affects the whole team on calls.',
     'Innovation Centre', 'East wing', 'high', 'en', 'Jamie Clarke', 6, 'closed'),
    ('Inodoro atascado', 'El inodoro del baño de la planta baja está atascado y hay agua en el suelo.',
     'Riverside House', 'Ground floor toilets', 'medium', 'es', 'Lucía Fernández', 4, 'closed'),
    ('Air conditioning blowing hot air', 'The air con in the training room is blowing hot air and it is 28 degrees.',
     'Main Office', 'Training room', 'medium', 'en', 'Avery Scott', 3, 'resolved'),
    ('Monitor screen flickering', 'My second monitor keeps flickering and going black every few minutes.',
     'Riverside House', '2nd floor desk 21', 'low', 'ur', 'Imran Hussain', 2, 'resolved'),
    ('Ceiling tile stained and sagging', 'A ceiling tile above the photocopier is stained brown and sagging. '
     'Looks like water damage from above.', 'Main Office', '1st floor print area', 'high', 'en', 'Robin Hayes', 6, 'in_progress'),
    ('Fire door not closing properly', 'The fire door on the 3rd floor does not close on its own anymore, it stays open.',
     'Riverside House', '3rd floor corridor', 'high', 'en', 'Charlie Evans', 5, 'in_progress'),
    ('Projector not connecting', 'The projector in the boardroom will not connect to laptops using HDMI.',
     'Innovation Centre', 'Boardroom', 'medium', 'en', 'Drew Wilson', 8, 'in_progress'),
    ('No heating in warehouse office', 'Heating has stopped in the warehouse office. It is very cold and staff are '
     'wearing coats.', 'Warehouse B', 'Office', 'high', 'en', 'Kai Murphy', 7, 'assigned'),
    ('Car park barrier stuck', 'The car park barrier is stuck in the down position and cars are queuing on the road.',
     'Main Office', 'Car park', 'high', 'en', 'Sky Bennett', 1, 'assigned'),
    ('Socket sparking', 'The wall socket by desk 12 made a sparking noise and there is a smell of burning.',
     'Riverside House', '2nd floor desk 12', 'urgent', 'en', 'Quinn Foster', 0.3, 'assigned'),
    ('Carpet ripped by lift', 'Carpet is ripped by the lift on the ground floor and people keep catching their feet. '
     'Trip hazard.', 'Innovation Centre', 'Ground floor lift lobby', 'medium', 'en', 'Harper Lewis', 2, 'assigned'),
    ('Window blind broken', 'The blind in meeting room 5 is broken and cannot be lowered. Sun glare on all the screens.',
     'Riverside House', 'Meeting room 5', 'medium', 'en', 'Rowan King', 16, 'assigned'),
    # New - waiting for triage (shows AI suggestions, duplicates and fairness rules)
    ('Water dripping from ceiling', 'Water is dripping from the ceiling near the photocopier on the 1st floor. '
     'Someone has put a bucket there.', 'Main Office', '1st floor print area', 'high', 'en', 'Elliot Grant', 0.08, 'new'),
    ('Suspicious person in car park', 'Someone I did not recognise was trying car door handles in the car park '
     'about 10 minutes ago.', 'Main Office', 'Car park', 'high', 'en', 'Frankie Moss', 0.04, 'new'),
    ('Lift making grinding noise', 'The lift makes a loud grinding noise between floors 2 and 3.',
     'Innovation Centre', 'Main lift', 'medium', 'en', 'Reese Cooper', 0.2, 'new'),
    ('Nie działa ogrzewanie', 'W biurze magazynu jest bardzo zimno, ogrzewanie nie działa od rana.',
     'Warehouse B', 'Office', 'medium', 'pl', 'Piotr Kowalski', 0.1, 'new'),
    ('Broken', 'It is broken again.', 'Riverside House', '', 'medium', 'en', 'Billie Ward', 0.4, 'new'),
]

VISIT_NOTES = {
    'Plumbing & leaks': ('Found a loose compression joint on the waste pipe. Tightened and replaced the washer. '
                         'Dried the area and checked for further leaks, none found.'),
    'Heating & air con': ('Thermostatic valve was stuck. Freed the pin and bled the system. '
                          'Unit now heating up correctly, checked after 20 minutes.'),
    'Electrical & lighting': ('Replaced two faulty LED drivers. Tested all fittings in the area, all working.'),
    'IT equipment': ('Diagnosed hardware fault. Swapped the unit for a tested spare and confirmed it works with the user.'),
    'Access & doors': ('Door closer arm had come loose. Re-fixed and adjusted closing speed. Tested 10 times.'),
    'Security concern': ('Reviewed CCTV and spoke to reception. Logged with site security lead.'),
    'Building fabric': ('Made safe and taped off the area. Measured up for a replacement part.'),
    'Cleaning & waste': ('Arranged an extra collection and cleared the area. Added the bay to the weekly check list.'),
    'General / Other': ('Inspected and resolved on site.'),
}
FOLLOW_UP = 'Part needed that is not in the van. Ordered and booked a return visit.'

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
        for name, desc, team, pri, kw in CATEGORIES:
            Category.objects.create(name=name, description=desc, default_team=teams[team],
                                    default_priority=pri, keywords=kw)
        for name, team in OFFICERS:
            Officer.objects.create(name=name, team=teams[team],
                                   contact_email=name.lower().replace(' ', '.') + '@example.com')
        for p, ack, res in SLA:
            SLARule.objects.create(priority=p, acknowledge_hours=ack, resolve_working_days=res)

        # Oldest first, so references follow the order things were reported
        for spec in sorted(REPORTS, key=lambda r: -r[7]):
            self.make_case(spec, rng, now)

        self.stdout.write(self.style.SUCCESS(f'Loaded {Case.objects.count()} fictional cases.'))

    def make_case(self, spec, rng, now):
        title, desc, building, room, urgency, lang, name, days_ago, stage = spec
        reported = now - timedelta(days=days_ago)
        case = Case.objects.create(
            title=title, description=desc, building=building, location_detail=room,
            reported_urgency=urgency, preferred_language=lang, reporter_name=name,
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
        case.category = s['category']
        case.priority = s['priority']
        if rng.random() < 0.2 and case.priority != 'urgent':
            case.priority = {1: 'medium', 2: 'high', 3: 'urgent'}[PRIORITY_RANK[case.priority]]
        case.ai_suggestion_accepted = case.priority == s['priority']
        case.assigned_team = case.category.default_team
        case.assigned_officer = rng.choice(list(case.assigned_team.officers.all()))
        case.triaged_by = HANDLER
        case.date_acknowledged = reported + timedelta(hours=rng.uniform(0.2, 5))
        case.status = Status.ASSIGNED
        case.apply_sla()
        case.save()
        Communication.objects.create(
            case=case, kind='ack', language=lang, approved_by=HANDLER, date_sent=case.date_acknowledged,
            draft_text=f'Your report {case.reference} has been passed to our {case.assigned_team} team.')
        if stage == 'assigned':
            return

        note = VISIT_NOTES.get(case.category.name, VISIT_NOTES['General / Other'])
        first_visit = min(case.date_acknowledged + timedelta(days=rng.uniform(0.1, 1.5)), now - timedelta(hours=2))
        if stage == 'in_progress':
            SiteVisit.objects.create(case=case, officer=case.assigned_officer, visited_at=first_visit, note=FOLLOW_UP,
                                     ai_summary=ai.summarise_visit(FOLLOW_UP, False))
            case.status = Status.IN_PROGRESS
            case.save()
            return

        two_visits = rng.random() < 0.3
        visit_time = first_visit
        if two_visits:
            SiteVisit.objects.create(case=case, officer=case.assigned_officer, visited_at=first_visit, note=FOLLOW_UP,
                                     ai_summary=ai.summarise_visit(FOLLOW_UP, False))
            visit_time = min(first_visit + timedelta(days=rng.uniform(1, 4)), now - timedelta(hours=1))
        SiteVisit.objects.create(case=case, officer=case.assigned_officer, visited_at=visit_time, note=note,
                                 fixed=True, transcript_used=rng.random() < 0.4,
                                 ai_summary=ai.summarise_visit(note, True))
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
        case.save()
