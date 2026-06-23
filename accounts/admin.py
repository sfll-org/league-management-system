from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Coach, CoachSeason, User, UserRole


class UserRoleInline(admin.TabularInline):
    model = UserRole
    extra = 0
    fk_name = 'user'


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'first_name', 'last_name', 'phone', 'is_staff', 'is_active', 'power_user_mode')
    list_filter = ('is_staff', 'is_active', 'power_user_mode')
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('email',)
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal', {'fields': ('first_name', 'last_name', 'phone')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Power-user features (SFLL-117)', {'fields': ('power_user_mode',)}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'password1', 'password2'),
        }),
    )
    inlines = [UserRoleInline]


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'league', 'division', 'is_active', 'assigned_at')
    list_filter = ('role', 'is_active', 'league')
    search_fields = ('user__email', 'user__first_name', 'user__last_name')


class CoachSeasonInline(admin.TabularInline):
    model = CoachSeason
    extra = 0


@admin.register(Coach)
class CoachAdmin(admin.ModelAdmin):
    list_display = ('user', 'league', 'phone')
    list_filter = ('league',)
    search_fields = ('user__email', 'user__first_name', 'user__last_name')
    inlines = [CoachSeasonInline]


@admin.register(CoachSeason)
class CoachSeasonAdmin(admin.ModelAdmin):
    list_display = ('coach', 'team_season', 'season', 'role', 'is_drafter')
    list_filter = ('role', 'is_drafter', 'season')
    search_fields = ('coach__user__email', 'coach__user__first_name', 'coach__user__last_name')
