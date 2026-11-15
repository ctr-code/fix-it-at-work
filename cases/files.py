"""
Private links for uploaded photos and voice notes.

Every file is reached through /files/<name> (views.case_file), never a public address. That view finds the
case the file belongs to and only sends it to someone allowed to see that case (permissions.can_view_case):
the reporter, staff, or officers in the case's team. Anyone else gets "not found", so a copied link is
useless to them.

- Files on this server (local development) are sent by the view itself. /media/ is no longer served.
- Files in Cloudinary (production) are uploaded as "authenticated", so Cloudinary refuses its plain links,
  and the view redirects to a signed link that expires after a few minutes (project/storage.py).
"""
from .models import Case, ReportPhoto, SiteVisit, VisitPhoto

# Where each kind of upload lives: (model, field, how to get from a row to its case)
FILE_FIELDS = [
    (Case, 'photo', lambda row: row),
    (ReportPhoto, 'image', lambda row: row.case),
    (SiteVisit, 'photo', lambda row: row.case),
    (SiteVisit, 'audio', lambda row: row.case),
    (VisitPhoto, 'image', lambda row: row.visit.case),
]


def case_for_file(name):
    """The case an uploaded file belongs to, or None if no case has a file by that name."""
    if not name:
        return None
    for model, field, to_case in FILE_FIELDS:
        row = model.objects.filter(**{field: name}).first()
        if row is not None:
            return to_case(row)
    return None


def all_file_names():
    """Every stored upload, for the command that makes older Cloudinary files private."""
    names = []
    for model, field, _ in FILE_FIELDS:
        names += [n for n in model.objects.exclude(**{field: ''}).values_list(field, flat=True) if n]
    return names
