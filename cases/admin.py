from django.contrib import admin

from .models import Case, Category, Communication, Officer, SiteVisit, SLARule, Team


class VisitInline(admin.TabularInline):
    model = SiteVisit
    extra = 0


class CommunicationInline(admin.TabularInline):
    model = Communication
    extra = 0


@admin.register(Case)
class CaseAdmin(admin.ModelAdmin):
    list_display = ('reference', 'title', 'status', 'priority', 'assigned_team', 'date_reported', 'sla_due')
    list_filter = ('status', 'priority', 'assigned_team', 'category')
    search_fields = ('reference', 'title', 'description')
    inlines = [VisitInline, CommunicationInline]


admin.site.register([Team, Category, Officer, SLARule])
