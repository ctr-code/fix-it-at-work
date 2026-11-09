"""
AI assistant for the Request to Resolution journey.

Every AI feature lives in this one module so it can be swapped for a real
model (e.g. Azure OpenAI / Copilot / Claude) without touching the rest of the
app. This prototype version is rule-based so it runs offline with no keys and
no data leaves the machine.

Rules the rest of the app follows:
- AI only SUGGESTS. A person approves triage and every outgoing letter.
- Anything AI produced is labelled as such in the UI.
- Priority can never be set LOWER than the reporter asked for, so a report
  written in poor English or another language is not under-prioritised.
"""
import re
from difflib import SequenceMatcher
from datetime import timedelta

from django.utils import timezone

from .models import Case, Category, Priority, PRIORITY_RANK, OPEN_STATUSES

# Words that suggest a risk to people or property. Includes a few common
# words in Polish, Urdu and Spanish so non-English reports are not missed.
SAFETY_TERMS = {
    'urgent': [
        'fire', 'smoke', 'burning', 'sparks', 'sparking', 'gas smell', 'smell of gas', 'electric shock',
        'exposed wire', 'live wire', 'flood', 'flooding', 'pouring', 'gushing', 'trapped', 'stuck in lift',
        'injured', 'injury', 'collapsed', 'break-in', 'intruder', 'ceiling falling',
        'pożar', 'dym', 'gaz', 'zalanie', 'آگ', 'دھواں', 'گیس', 'fuego', 'humo', 'inundación',
    ],
    'high': [
        'leak', 'leaking', 'water on floor', 'no heating', 'freezing', 'no power', 'power cut', 'outage',
        'cannot access', "can't access", 'locked out', 'door won\'t lock', 'alarm', 'slip', 'trip hazard',
        'whole team', 'everyone', 'all staff', 'server', 'network down',
        'wyciek', 'przeciek', 'پانی', 'fuga', 'calefacción',
    ],
}


def _text(*parts):
    return ' '.join(p for p in parts if p).lower()


def _max_priority(*priorities):
    return max((p for p in priorities if p), key=lambda p: PRIORITY_RANK[p])


def triage(case):
    """
    Suggest category, priority, summary and a possible duplicate for a new case.
    Returns a dict; nothing is applied until a person approves it.
    """
    text = _text(case.title, case.description, case.location_detail)
    reasons = []

    # 1. Category: score each category by keyword hits
    scores = []
    for cat in Category.objects.select_related('default_team'):
        words = [w.strip().lower() for w in cat.keywords.split(',') if w.strip()]
        hits = [w for w in words if re.search(r'\b' + re.escape(w), text)]
        scores.append((len(hits), cat, hits))
    scores.sort(key=lambda s: s[0], reverse=True)
    best_score, category, hits = scores[0] if scores else (0, None, [])
    runner_up = scores[1][0] if len(scores) > 1 else 0

    if best_score == 0:
        category = Category.objects.filter(name='General / Other').first() or category
        confidence = 30
        reasons.append('No clear category words found, so a person should check this one carefully.')
    else:
        confidence = min(95, 50 + 15 * (best_score - runner_up) + 5 * best_score)
        reasons.append(f'Matched "{category.name}" because the report mentions: {", ".join(hits[:4])}.')

    # 2. Priority: highest of category default, safety words, and reporter's own view
    priority = category.default_priority if category else Priority.MEDIUM
    for level in ('urgent', 'high'):
        found = [t for t in SAFETY_TERMS[level] if re.search(r'\b' + re.escape(t) + r'\b', text)]
        if found:
            if PRIORITY_RANK[level] > PRIORITY_RANK[priority]:
                reasons.append(f'Raised to {level} because of: {", ".join(found[:3])}.')
            priority = _max_priority(priority, level)
            break
    if PRIORITY_RANK[case.reported_urgency] > PRIORITY_RANK[priority]:
        reasons.append(
            f'Kept at {case.reported_urgency} because that is what the reporter asked for '
            '(AI never lowers the reporter\'s urgency).')
        priority = case.reported_urgency

    if len(case.description.split()) < 8:
        confidence = min(confidence, 45)
        reasons.append('Short description - a person should check the details or the photo.')

    # 3. Duplicate check: similar open cases in the same building in the last 14 days.
    # Score = text similarity + bonus for same room + bonus for same category.
    duplicate = None
    since = timezone.now() - timedelta(days=14)
    candidates = Case.objects.filter(
        status__in=OPEN_STATUSES, building__iexact=case.building, date_reported__gte=since,
    ).exclude(pk=case.pk)
    best_ratio = 0
    for other in candidates:
        ratio = SequenceMatcher(None, text, _text(other.title, other.description, other.location_detail)).ratio()
        same_room = case.location_detail and other.location_detail.lower() == case.location_detail.lower()
        if same_room:
            ratio += 0.2
        if category and category.id in (other.category_id, other.ai_category_id):
            ratio += 0.2
        if ratio > best_ratio:
            best_ratio, duplicate = ratio, other
    if best_ratio < 0.65:
        duplicate = None
    else:
        reasons.append(f'Looks similar to {duplicate.reference} ("{duplicate.title}") in the same building.')

    return {
        'category': category,
        'priority': priority,
        'team': category.default_team if category else None,
        'summary': summarise_report(case),
        'reasoning': ' '.join(reasons),
        'confidence': confidence,
        'duplicate': duplicate,
    }


def _first_sentences(text, n=2, limit=220):
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    out = ' '.join(sentences[:n])
    return out if len(out) <= limit else out[:limit].rsplit(' ', 1)[0] + '...'


def summarise_report(case):
    where = case.building + (f', {case.location_detail}' if case.location_detail else '')
    return f'{case.title} at {where}. {_first_sentences(case.description)}'


def summarise_visit(note, fixed):
    """Turn an officer's typed or dictated note into a short case-note summary."""
    outcome = 'Fixed on this visit.' if fixed else 'Not fixed yet - follow-up visit needed.'
    return f'{_first_sentences(note, n=3, limit=300)} Outcome: {outcome}'


LETTERS = {
    'en': (
        'Dear {name},\n\n'
        'Thank you for reporting "{title}" (reference {ref}). Our {team} team has looked into it '
        'and the issue has now been resolved.\n\n'
        'What we did: {outcome}\n\n'
        'If the problem comes back, please reply quoting {ref} and we will pick it up straight away.\n\n'
        'Kind regards,\n{team} team'
    ),
    'pl': (
        'Szanowna Pani / Szanowny Panie {name},\n\n'
        'Dziękujemy za zgłoszenie „{title}” (numer {ref}). Nasz zespół {team} zajął się problemem '
        'i został on rozwiązany.\n\n'
        'Co zrobiliśmy: {outcome}\n\n'
        'Jeśli problem wróci, prosimy o odpowiedź z numerem {ref}.\n\n'
        'Z poważaniem,\nZespół {team}'
    ),
    'ur': (
        'محترم {name}،\n\n'
        '"{title}" کی رپورٹ کرنے کا شکریہ (حوالہ نمبر {ref})۔ ہماری {team} ٹیم نے اس مسئلے کو دیکھا '
        'اور اب یہ حل ہو گیا ہے۔\n\n'
        'ہم نے کیا کیا: {outcome}\n\n'
        'اگر مسئلہ دوبارہ پیش آئے تو براہ کرم {ref} کے حوالے سے جواب دیں۔\n\n'
        'شکریہ،\n{team} ٹیم'
    ),
    'es': (
        'Estimado/a {name}:\n\n'
        'Gracias por informar de "{title}" (referencia {ref}). Nuestro equipo de {team} lo ha revisado '
        'y el problema ya está resuelto.\n\n'
        'Qué hicimos: {outcome}\n\n'
        'Si el problema vuelve a ocurrir, responda indicando la referencia {ref}.\n\n'
        'Un saludo,\nEquipo de {team}'
    ),
}


def draft_outcome_letter(case):
    """Draft a plain-language outcome letter in the reporter's preferred language."""
    last_visit = case.visits.filter(fixed=True).last() or case.visits.last()
    outcome = last_visit.note if last_visit else 'The issue was resolved by our team.'
    outcome = _first_sentences(outcome, n=3, limit=300)
    template = LETTERS.get(case.preferred_language, LETTERS['en'])
    return template.format(
        name=case.reporter_name.split()[0],
        title=case.title,
        ref=case.reference,
        team=case.assigned_team.name if case.assigned_team else 'Facilities',
        outcome=outcome,
    )


def receipt_text(case):
    return (
        f'Thanks {case.reporter_name.split()[0]}, we have received your report "{case.title}". '
        f'Your reference is {case.reference}. You can track it at any time using this reference.'
    )
