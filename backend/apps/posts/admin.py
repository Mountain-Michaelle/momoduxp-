"""
Django Admin configuration for Posts app.
Production-ready with filters, search, actions, and detailed views.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone



class ScheduledPostAdmin(admin.ModelAdmin):
    """
    Admin for scheduled posts with advanced filtering and actions.
    """

    # List display configuration
    list_display = (
        'post_preview',
        'author_email',
        'platform_icon',
        'status_badge',
        'scheduled_for',
        'approval_status',
        'created_at',
    )

    # Fields to show in list view
    list_filter = (
        'status',
        'account__platform',
        'scheduled_for',
        'created_at',
        'author__subscription_plan',
    )

    # Search fields
    search_fields = (
        'content',
        'author__email',
        'author__username',
        'external_post_id',
    )

    # Default ordering
    ordering = ('-created_at',)

    # Raw ID fields for foreign keys
    raw_id_fields = ('author', 'account')

    # Fieldsets for edit page
    fieldsets = (
        ('Content', {
            'fields': ('content', 'media_urls'),
            'classes': ('VSCodeBlue',),
        }),
        ('Author & Account', {
            'fields': ('author', 'account'),
        }),
        ('Scheduling', {
            'fields': ('scheduled_for', 'approval_deadline'),
            'classes': ('VSCodeBlue',),
        }),
        ('Status', {
            'fields': ('status', 'approved_at'),
        }),
        ('Platform Metadata', {
            'fields': ('external_post_id', 'platform_id'),
            'classes': ('collapse',),
        }),
        ('Error Log', {
            'fields': ('error_log',),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    # Read-only fields
    readonly_fields = (
        'created_at',
        'updated_at',
    )

    # Custom methods
    def post_preview(self, obj):
        """Show truncated content preview."""
        preview = obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
        return format_html(
            '<span title="{}">{}</span>',
            obj.content.replace('\n', ' '),
            preview
        )
    post_preview.short_description = 'Content'

    def author_email(self, obj):
        """Display author's email."""
        return obj.author.email
    author_email.short_description = 'Author'
    author_email.admin_order_field = 'author__email'

    def platform_icon(self, obj):
        """Display platform with icon."""
        icons = {
            'linkedin': '🔗 LinkedIn',
            'twitter': '🐦 Twitter',
            'facebook': '📘 Facebook',
            'instagram': '📸 Instagram',
        }
        icon = icons.get(obj.account.platform, '📌')
        return format_html('{}', icon)
    platform_icon.short_description = 'Platform'

    def status_badge(self, obj):
        """Display status with color-coded badge."""
        colors = {
            'draft': '#9e9e9e',  # Grey
            'sent_for_approval': '#fbbf24',  # Orange
            'approved': '#a3e635',  # Green
            'published': '#4f46e5',  # Indigo-600
            'failed': '#f87171',  # Red
        }
        color = colors.get(obj.status, '#9e9e9e')
        status_text = obj.get_status_display()
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 4px; font-size: 12px;">{}</span>',
            color,
            status_text
        )
    status_badge.short_description = 'Status'

    def approval_status(self, obj):
        """Show approval deadline status."""
        if obj.status in ['draft', 'sent_for_approval']:
            if obj.approval_deadline:
                if obj.approval_deadline <= timezone.now():
                    color = '#f44336'  # Red - overdue
                    text = 'Overdue'
                else:
                    color = '#ff9800'  # Orange - pending
                    days_left = (obj.approval_deadline - timezone.now()).days
                    text = f'{days_left}d left'
            else:
                color = '#9e9e9e'
                text = 'No deadline'
        elif obj.approved_at:
            color = '#4caf50'  # Green
            text = f'Approved {obj.approved_at.strftime("%m/%d")}'
        else:
            color = '#9e9e9e'
            text = 'N/A'
        return format_html(
            '<span style="color: {};">● {}</span>',
            color,
            text
        )
    approval_status.short_description = 'Approval'

    # Custom admin actions
    actions = [
        'submit_for_approval',
        'approve_selected',
        'reject_selected',
        'mark_as_failed',
        'retry_failed',
        'reset_to_draft',
    ]

    def submit_for_approval(self, request, queryset):
        """Submit selected posts for approval."""
        updated = queryset.filter(status='draft').update(
            status='sent_for_approval'
        )
        self.message_user(request, f'{updated} posts submitted for approval.')
    submit_for_approval.short_description = 'Submit for approval'

    def approve_selected(self, request, queryset):
        """Approve selected posts."""
        now = timezone.now()
        updated = queryset.filter(
            status__in=['draft', 'sent_for_approval']
        ).update(status='approved', approved_at=now)
        self.message_user(request, f'{updated} posts approved.')
    approve_selected.short_description = 'Approve selected posts'

    def reject_selected(self, request, queryset):
        """Reject selected posts."""
        updated = queryset.filter(
            status='sent_for_approval'
        ).update(status='draft', approved_at=None)
        self.message_user(request, f'{updated} posts rejected.')
    reject_selected.short_description = 'Reject selected posts'

    def mark_as_failed(self, request, queryset):
        """Mark selected posts as failed."""
        updated = queryset.filter(
            status='published'
        ).update(status='failed', error_log='Manually marked as failed by admin')
        self.message_user(request, f'{updated} posts marked as failed.')
    mark_as_failed.short_description = 'Mark as failed'

    def retry_failed(self, request, queryset):
        """Retry failed posts."""
        updated = queryset.filter(
            status='failed'
        ).update(status='draft', error_log=None)
        self.message_user(request, f'{updated} posts reset for retry.')
    retry_failed.short_description = 'Retry failed posts'

    def reset_to_draft(self, request, queryset):
        """Reset posts to draft."""
        updated = queryset.exclude(
            status='published'
        ).update(status='draft', approved_at=None)
        self.message_user(request, f'{updated} posts reset to draft.')
    reset_to_draft.short_description = 'Reset to draft'

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related(
            'author', 'account'
        )
