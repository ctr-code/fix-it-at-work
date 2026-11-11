from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

from .models import Case, Category, Communication, Officer, Profile, ReportPhoto, SiteVisit, SLARule, Team, get_role


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'Role in Fix It at Work'
    help_text = 'To make someone a field officer, use the People page in the app so they also get a team.'


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role')
    list_filter = ('role',)
    search_fields = ('user__username', 'user__email')


admin.site.unregister(User)


@admin.register(User)
class UserWithRoleAdmin(UserAdmin):
    """The standard user admin, plus each user's Fix It at Work role."""
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_staff')
    list_filter = ('profile__role',) + UserAdmin.list_filter
    list_select_related = ('profile',)
    inlines = [ProfileInline]

    @admin.display(description='Role', ordering='profile__role')
    def role(self, obj):
        # Superusers are always treated as managers, whatever their profile says
        label = dict(Profile._meta.get_field('role').choices).get(get_role(obj), '-')
        return f'{label} (superuser)' if obj.is_superuser else label

    def get_inlines(self, request, obj):
        # A new user's profile is created automatically when they are saved,
        # so only show the role editor once the user exists
        return self.inlines if obj else []


class ReportPhotoInline(admin.TabularInline):
    model = ReportPhoto
    extra = 0


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
    inlines = [ReportPhotoInline, VisitInline, CommunicationInline]


admin.site.register([Team, Category, Officer, SLARule])
