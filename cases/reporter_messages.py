"""
Messages to the person who reported an issue, in the language they chose: received, sent to a team,
changes to the target date or team, an officer's visit, and the fix.

Each one is saved as a Communication (shown under "Messages to you" on the report, and counted as new
on "My reports" until they open it) and emailed to them. Email goes to the server window by default,
see MAILERS in settings.

The English texts are the originals. The Polish, Urdu and Spanish ones are fixed translations written
for this prototype, not produced by AI at run time; a native speaker should check them before real use.
Dates are written as numbers (14/11/2026 09:00) so they read the same in every language.
"""
from django.core.mail import send_mail
from django.utils import timezone

from .models import Communication

TEXTS = {
    'en': {
        'receipt': 'Thanks {name}, we have received your report "{title}". Your reference is {ref}. '
                   'You can track it at any time using this reference.',
        'routed': 'Your report {ref} has been passed to our {team} team as {priority} priority. '
                  'We aim to resolve it by {due}.',
        'duplicate': 'Thanks for your report. Someone has already reported this issue, so we have linked your '
                     'report to {other}. You can track progress there.',
        'update': 'Update on your report {ref}.',
        'new_due': 'We now aim to fix it by {due}.',
        'new_team': 'It is now being handled by our {team} team.',
        'follow_up': 'An officer visited on {date}. The problem needs another visit to fix it fully, '
                     'and we will keep you updated.',
        'fixed': 'Good news: an officer has fixed "{title}" ({ref}). We will send you a letter shortly '
                 'explaining what was done.',
        'priority': {'urgent': 'urgent', 'high': 'high', 'medium': 'medium', 'low': 'low'},
    },
    'pl': {
        'receipt': 'Dziękujemy, {name}. Otrzymaliśmy Twoje zgłoszenie „{title}”. Numer zgłoszenia: {ref}. '
                   'Możesz w każdej chwili sprawdzić jego status, używając tego numeru.',
        'routed': 'Twoje zgłoszenie {ref} zostało przekazane do zespołu {team} z priorytetem: {priority}. '
                  'Planujemy rozwiązać problem do {due}.',
        'duplicate': 'Dziękujemy za zgłoszenie. Ten problem został już zgłoszony, więc połączyliśmy Twoje '
                     'zgłoszenie ze zgłoszeniem {other}. Tam możesz śledzić postęp prac.',
        'update': 'Aktualizacja Twojego zgłoszenia {ref}.',
        'new_due': 'Planujemy teraz rozwiązać problem do {due}.',
        'new_team': 'Sprawą zajmuje się teraz zespół {team}.',
        'follow_up': 'Nasz pracownik był na miejscu {date}. Potrzebna jest kolejna wizyta, aby w pełni '
                     'rozwiązać problem. Będziemy Cię informować.',
        'fixed': 'Dobra wiadomość: nasz pracownik rozwiązał problem „{title}” ({ref}). Wkrótce wyślemy '
                 'list z informacją, co zostało zrobione.',
        'priority': {'urgent': 'pilny', 'high': 'wysoki', 'medium': 'średni', 'low': 'niski'},
    },
    'ur': {
        'receipt': 'شکریہ {name}، ہمیں آپ کی رپورٹ "{title}" موصول ہو گئی ہے۔ آپ کا حوالہ نمبر {ref} ہے۔ '
                   'آپ اس حوالہ نمبر سے کسی بھی وقت اس کی صورتحال دیکھ سکتے ہیں۔',
        'routed': 'آپ کی رپورٹ {ref} ہماری {team} ٹیم کو {priority} ترجیح کے ساتھ بھیج دی گئی ہے۔ '
                  'ہمارا ہدف ہے کہ اسے {due} تک حل کر دیا جائے۔',
        'duplicate': 'آپ کی رپورٹ کا شکریہ۔ یہ مسئلہ پہلے ہی رپورٹ ہو چکا ہے، اس لیے ہم نے آپ کی رپورٹ کو '
                     '{other} سے منسلک کر دیا ہے۔ آپ وہاں پیش رفت دیکھ سکتے ہیں۔',
        'update': 'آپ کی رپورٹ {ref} کے بارے میں تازہ معلومات۔',
        'new_due': 'اب ہمارا ہدف ہے کہ اسے {due} تک حل کر دیا جائے۔',
        'new_team': 'اب اس پر ہماری {team} ٹیم کام کر رہی ہے۔',
        'follow_up': 'ہمارا افسر {date} کو موقع پر آیا تھا۔ مسئلے کو مکمل طور پر حل کرنے کے لیے ایک اور دورہ '
                     'درکار ہے۔ ہم آپ کو باخبر رکھیں گے۔',
        'fixed': 'اچھی خبر: ہمارے افسر نے "{title}" ({ref}) کا مسئلہ حل کر دیا ہے۔ ہم جلد ہی آپ کو ایک خط '
                 'بھیجیں گے جس میں بتایا جائے گا کہ کیا کیا گیا۔',
        'priority': {'urgent': 'فوری', 'high': 'زیادہ', 'medium': 'درمیانی', 'low': 'کم'},
    },
    'es': {
        'receipt': 'Gracias, {name}. Hemos recibido su informe "{title}". Su referencia es {ref}. '
                   'Puede consultar su estado en cualquier momento con esta referencia.',
        'routed': 'Su informe {ref} se ha enviado a nuestro equipo de {team} con prioridad {priority}. '
                  'Nuestro objetivo es resolverlo antes del {due}.',
        'duplicate': 'Gracias por su informe. Otra persona ya ha informado de este problema, así que hemos '
                     'vinculado su informe a {other}. Puede seguir el progreso allí.',
        'update': 'Novedades sobre su informe {ref}.',
        'new_due': 'Ahora nuestro objetivo es resolverlo antes del {due}.',
        'new_team': 'Ahora lo gestiona nuestro equipo de {team}.',
        'follow_up': 'Un técnico lo visitó el {date}. Hace falta otra visita para solucionarlo por completo. '
                     'Le mantendremos informado/a.',
        'fixed': 'Buenas noticias: un técnico ha solucionado "{title}" ({ref}). En breve le enviaremos una '
                 'carta explicando lo que se hizo.',
        'priority': {'urgent': 'urgente', 'high': 'alta', 'medium': 'media', 'low': 'baja'},
    },
}


def _when(moment):
    return f'{timezone.localtime(moment):%d/%m/%Y %H:%M}' if moment else '-'


def _team(case):
    """The team's name without a trailing "Team", because every message adds its own word for team
    ("our Security & Access team", not "our Security & Access Team team")."""
    name = case.assigned_team.name if case.assigned_team else ''
    return name[:-5] if name.lower().endswith(' team') else name


def _text(case, key, **extra):
    t = TEXTS.get(case.preferred_language, TEXTS['en'])
    values = {
        'name': case.reporter_name.split()[0] if case.reporter_name else '',
        'title': case.title, 'ref': case.reference, 'due': _when(case.sla_due),
        'team': _team(case),
        'priority': t['priority'].get(case.priority, case.priority),
        **extra,
    }
    return t[key].format(**values)


def email_reporter(message):
    """Email a sent message to the reporter. A failed email never stops the work: the message is still
    on their report page."""
    case = message.case
    if not case.reporter_email:
        return
    subject = f'{case.reference}: {case.title}'
    try:
        send_mail(subject, message.draft_text, None, [case.reporter_email])
    except Exception:  # noqa: BLE001
        pass


def send(case, kind, text, approved_by='Automatic'):
    message = Communication.objects.create(case=case, kind=kind, language=case.preferred_language,
                                           draft_text=text, approved_by=approved_by, date_sent=timezone.now())
    email_reporter(message)
    return message


# ---------- One function for each moment the reporter hears from us ----------

def received(case):
    return send(case, Communication.Kind.RECEIPT, _text(case, 'receipt'))


def routed(case, approved_by):
    return send(case, Communication.Kind.ACKNOWLEDGEMENT, _text(case, 'routed'), approved_by)


def merged(case, approved_by):
    return send(case, Communication.Kind.ACKNOWLEDGEMENT,
                _text(case, 'duplicate', other=case.duplicate_of.reference), approved_by)


def changed(case, approved_by, new_due=False, new_team=False):
    """After a handler changes a case. Only what the reporter cares about: when, and who. Nothing is sent
    if neither changed (a new officer or category doesn't change anything for them)."""
    if not (new_due or new_team):
        return None
    parts = [_text(case, 'update')]
    if new_team:
        parts.append(_text(case, 'new_team'))
    if new_due:
        parts.append(_text(case, 'new_due'))
    return send(case, Communication.Kind.UPDATE, ' '.join(parts), approved_by)


def visited(case, visit):
    """After an officer's visit: either fixed, or a follow-up is needed."""
    if visit.fixed:
        return send(case, Communication.Kind.UPDATE, _text(case, 'fixed'))
    text = _text(case, 'update') + ' ' + _text(case, 'follow_up', date=_when(visit.visited_at))
    return send(case, Communication.Kind.UPDATE, text)


def unread_count(user):
    """Messages on this person's own reports that they haven't seen yet, for the badge on "My reports"."""
    if not user.is_authenticated:
        return 0
    return Communication.objects.filter(case__reporter_user=user, date_sent__isnull=False,
                                        read_at__isnull=True).count()
