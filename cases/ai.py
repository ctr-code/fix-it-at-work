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

from .models import Case, Category, Impact, Priority, PRIORITY_RANK, OPEN_STATUSES

# Words that suggest a risk to people or property. Includes a few common
# words in Polish, Urdu and Spanish so non-English reports are not missed.
SAFETY_TERMS = {
    'urgent': [
        'fire', 'smoke', 'burning', 'sparks', 'sparking', 'gas smell', 'smell of gas', 'gas leak', 'electric shock',
        'exposed wire', 'live wire', 'flood', 'flooding', 'water pouring', 'pouring through', 'pouring in',
        'pouring out', 'pouring from', 'gushing', 'trapped', 'stuck in lift',
        'injured', 'injury', 'someone collapsed', 'person collapsed', 'has collapsed on', 'ceiling collapsed',
        'ceiling has collapsed', 'wall has collapsed', 'roof has collapsed', 'break-in', 'intruder', 'ceiling falling',
        'pożar', 'dym', 'gaz', 'zalanie', 'آگ', 'دھواں', 'گیس', 'fuego', 'humo', 'inundación',
    ],
    'high': [
        'leak', 'leaking', 'water on floor', 'no heating', 'freezing', 'no power', 'power cut', 'outage',
        'cannot access', "can't access", 'locked out', 'door won\'t lock', 'alarm', 'slip', 'trip hazard',
        'whole team', 'everyone', 'all staff', 'server', 'network down',
        'wyciek', 'przeciek', 'پانی', 'fuga', 'calefacción',
    ],
}

# Phrases that contain a danger word but aren't a danger in themselves. They're blanked out before
# the danger words are checked, so "fire extinguisher missing" or "locked out of my account" doesn't
# jump the queue. The category's own default priority still applies (e.g. Fire Equipment is high).
HARMLESS_PHRASES = [
    r'fire doors?', r'fire extinguishers?', r'fire blankets?', r'fire exits? signs?', r'fire alarm tests?',
    r'fire (?:safety )?(?:checks?|drills?|training)', r'smoke (?:alarm|detector)s?', r'intruder alarms?',
    r'burglar alarms?', r'pouring (?:with )?rain', r'locked out of (?:my |the |our )?'
    r'(?:account|laptop|computer|pc|email|e-mail|outlook|teams|system|phone|app)',
]
# A danger word just after one of these is being ruled out ("not a fire", "no smoke").
NEGATIONS = {'no', 'not', 'without', 'never', 'isn\'t', 'wasn\'t', 'nothing'}

# Keywords that turn up in reports about many different things ("cold tap", "fire door", "rain"). They
# still count, but less than specific words, so "the cold tap won't turn off" goes to Plumbing, not Heating.
GENERIC_KEYWORDS = {'cold', 'door', 'entrance', 'toilet', 'rain', 'smell', 'power', 'lift', 'camera', 'display'}
PHRASE_WEIGHT, WORD_WEIGHT, GENERIC_WEIGHT, NEAR_MISS_WEIGHT = 2, 1, 0.5, 0.75


def _text(*parts):
    return ' '.join(p for p in parts if p).lower()


def _max_priority(*priorities):
    return max((p for p in priorities if p), key=lambda p: PRIORITY_RANK[p])


def _near_miss(word, tokens):
    """A token that looks like a misspelling of word ("radiater" for "radiator"), or None.
    Only for longer words, and the first letter must match, to keep false matches rare."""
    if len(word) < 6 or ' ' in word:
        return None
    for tok in tokens:
        # "lift" isn't a misspelling of "lifted": a shorter or longer form of the word is a different word
        if tok.startswith(word) or word.startswith(tok):
            continue
        if (tok[0] == word[0] and abs(len(tok) - len(word)) <= 2
                and SequenceMatcher(None, tok, word).ratio() >= 0.8):
            return tok
    return None


def _score_category(cat, text, tokens):
    """Weighted keyword score: specific phrases count most, generic words least,
    near-miss spellings a little less than a correct spelling."""
    score, hits = 0, []
    for w in (w.strip().lower() for w in cat.keywords.split(',')):
        if not w:
            continue
        if re.search(r'\b' + re.escape(w), text):
            score += PHRASE_WEIGHT if ' ' in w else GENERIC_WEIGHT if w in GENERIC_KEYWORDS else WORD_WEIGHT
            hits.append(w)
        else:
            tok = _near_miss(w, tokens)
            if tok:
                score += NEAR_MISS_WEIGHT
                hits.append(f'{w} (spelt "{tok}")')
    return score, hits


FILLERS = {'a', 'an', 'any', 'sign', 'signs', 'of', 'real', 'actual'}


def _danger_terms(terms, text):
    """Danger words in text, skipping harmless phrases and ones that are ruled out ("not a fire")."""
    for phrase in HARMLESS_PHRASES:
        text = re.sub(r'\b' + phrase + r'\b', ' ', text)
    found = []
    for term in terms:
        for m in re.finditer(r'\b' + re.escape(term) + r'\b', text):
            negated = False
            for word in reversed(text[:m.start()].split()[-3:]):
                word = word.strip('.,;:!?-"\'')
                if word in NEGATIONS:
                    negated = True
                    break
                if word not in FILLERS:
                    break
            if not negated:
                found.append(term)
                break
    return found


def triage(case):
    """
    Suggest team, category, priority, summary and a possible duplicate for a new case.
    Every category belongs to one team, so picking the category also picks the team.
    Returns a dict; nothing is applied until a person approves it.
    """
    text = _text(case.title, case.description, case.location_detail)
    reasons = []

    # 1. Category (and so team): score each category by its keywords (see _score_category)
    tokens = re.findall(r'\w+', text)
    scores = []
    for cat in Category.objects.select_related('default_team'):
        score, hits = _score_category(cat, text, tokens)
        scores.append((score, cat, hits))
    scores.sort(key=lambda s: s[0], reverse=True)
    best_score, category, hits = scores[0] if scores else (0, None, [])
    runner_up = scores[1][0] if len(scores) > 1 else 0

    if best_score == 0:
        category = None
        confidence = 30
        reasons.append('No clear category words found, so a person needs to choose the team and category.')
    else:
        confidence = min(95, round(50 + 15 * (best_score - runner_up) + 5 * best_score))
        reasons.append(f'Matched {category.default_team} / {category.name} because the report mentions: '
                       f'{", ".join(hits[:4])}.')

    # 2. Priority: highest of category default, safety words, and reporter's own view
    priority = category.default_priority if category else Priority.MEDIUM
    for level in ('urgent', 'high'):
        found = _danger_terms(SAFETY_TERMS[level], text)
        if found:
            if PRIORITY_RANK[level] > PRIORITY_RANK[priority]:
                reasons.append(f'Raised to {level} because of: {", ".join(found[:3])}.')
            priority = _max_priority(priority, level)
            break
    if case.hs_risk and PRIORITY_RANK[priority] < PRIORITY_RANK['high']:
        reasons.append('Raised to high because the reporter flagged a health and safety risk.')
        priority = 'high'
    if case.impact == Impact.BUILDING_WIDE and PRIORITY_RANK[priority] < PRIORITY_RANK['high']:
        reasons.append('Raised to high because it affects the whole building.')
        priority = 'high'
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


def summarise_visit(note, fixed, action=''):
    """Turn an officer's typed or dictated answers into a short case-note summary.
    note is what they found; action is what they did (blank on visits recorded before the two were split)."""
    outcome = 'Fixed on this visit.' if fixed else 'Not fixed yet - follow-up visit needed.'
    if not action:
        return f'{_first_sentences(note, n=3, limit=300)} Outcome: {outcome}'
    return (f'Found: {_first_sentences(note, n=2, limit=200)} '
            f'Done: {_first_sentences(action, n=3, limit=300)} Outcome: {outcome}')


LETTERS = {
    'en': (
        'Dear {name},\n\n'
        'Thank you for reporting "{title}" (reference {ref}). Our {team} team has looked into it '
        'and the issue has now been resolved.\n\n'
        'What we did: {outcome}\n\n'
        'If the problem comes back, please reply quoting {ref} and we will pick it up straight away.\n\n'
        'Let us know how we did: open {ref} in Fix It at Work and rate the fix within 14 days.\n\n'
        'Kind regards,\n{team} team'
    ),
    'pl': (
        'Szanowna Pani / Szanowny Panie {name},\n\n'
        'Dziękujemy za zgłoszenie „{title}” (numer {ref}). Nasz zespół {team} zajął się problemem '
        'i został on rozwiązany.\n\n'
        'Co zrobiliśmy: {outcome}\n\n'
        'Jeśli problem wróci, prosimy o odpowiedź z numerem {ref}.\n\n'
        'Prosimy o ocenę naszej pracy: otwórz zgłoszenie {ref} w Fix It at Work w ciągu 14 dni.\n\n'
        'Z poważaniem,\nZespół {team}'
    ),
    'ur': (
        'محترم {name}،\n\n'
        '"{title}" کی رپورٹ کرنے کا شکریہ (حوالہ نمبر {ref})۔ ہماری {team} ٹیم نے اس مسئلے کو دیکھا '
        'اور اب یہ حل ہو گیا ہے۔\n\n'
        'ہم نے کیا کیا: {outcome}\n\n'
        'اگر مسئلہ دوبارہ پیش آئے تو براہ کرم {ref} کے حوالے سے جواب دیں۔\n\n'
        'ہمیں بتائیں کہ ہم نے کیسا کام کیا: 14 دن کے اندر Fix It at Work میں {ref} کھول کر اپنی رائے دیں۔\n\n'
        'شکریہ،\n{team} ٹیم'
    ),
    'es': (
        'Estimado/a {name}:\n\n'
        'Gracias por informar de "{title}" (referencia {ref}). Nuestro equipo de {team} lo ha revisado '
        'y el problema ya está resuelto.\n\n'
        'Qué hicimos: {outcome}\n\n'
        'Si el problema vuelve a ocurrir, responda indicando la referencia {ref}.\n\n'
        'Díganos qué tal lo hicimos: abra {ref} en Fix It at Work y valore la reparación en un plazo de 14 días.\n\n'
        'Un saludo,\nEquipo de {team}'
    ),
}


def draft_outcome_letter(case):
    """Draft a plain-language outcome letter in the reporter's preferred language."""
    last_visit = case.visits.filter(fixed=True).last() or case.visits.last()
    # "What we did" comes from what the officer did; older visits only have the combined note
    if last_visit:
        outcome = last_visit.action or last_visit.note
    else:
        outcome = 'The issue was resolved by our team.'
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
    """The "we've got it" message, in the reporter's language (kept here for seed_demo)."""
    from .reporter_messages import _text
    return _text(case, 'receipt')
