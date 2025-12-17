# emails/admin.py
from django.contrib import admin
from .models import EmailCampaign, EmailRecipient
from .models import EmailUnsubscribe, EmailBounce


@admin.register(EmailCampaign)
class EmailCampaignAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'get_filters',
        'status',
        'total_recipients',
        'sent_count',
        'failed_count',
        'created_at'
    ]
    list_filter = [
        'status',
        'filter_active_year',
        'filter_teachers',
        'filter_students',
        'filter_school_managers',
        'use_custom_list',
        'created_at'
    ]
    search_fields = ['name', 'subject']
    readonly_fields = [
        'created_at',
        'sent_at',
        'sent_count',
        'failed_count',
        'emails_sent_today',
        'total_recipients'
    ]

    fieldsets = (
        ('Үндсэн мэдээлэл', {
            'fields': ('name', 'subject', 'message', 'html_message', 'created_by')
        }),
        ('Шүүлтүүр', {
            'fields': (
                'use_custom_list',
                'filter_active_year',
                'filter_teachers',
                'filter_students',
                'filter_school_managers',
                'specific_province',
                'specific_school',
            )
        }),
        ('Статус ба статистик', {
            'fields': (
                'status',
                'total_recipients',
                'sent_count',
                'failed_count',
                'created_at',
                'sent_at',
            )
        }),
        ('Rate Limiting', {
            'fields': (
                'daily_limit',
                'emails_sent_today',
                'last_reset_date',
            )
        }),
    )

    def get_filters(self, obj):
        """Идэвхжсэн шүүлтүүрийг харуулах"""
        filters = []
        if obj.use_custom_list:
            return "Custom жагсаалт"

        if obj.filter_active_year:
            filters.append("Идэвхитэй")
        if obj.filter_teachers:
            filters.append("Багш")
        if obj.filter_students:
            filters.append("Сурагч")
        if obj.filter_school_managers:
            filters.append("Менежер")
        if obj.specific_province:
            filters.append(f"Аймаг: {obj.specific_province.name}")
        if obj.specific_school:
            filters.append(f"Сургууль: {obj.specific_school.name}")

        return ", ".join(filters) if filters else "Бүх хэрэглэгч"

    get_filters.short_description = 'Шүүлтүүр'


@admin.register(EmailRecipient)
class EmailRecipientAdmin(admin.ModelAdmin):
    list_display = ['email', 'name', 'campaign', 'status', 'sent_at']
    list_filter = ['status', 'campaign', 'sent_at']
    search_fields = ['email', 'name', 'campaign__name']
    readonly_fields = ['sent_at', 'message_id']

    fieldsets = (
        ('Хүлээн авагч', {
            'fields': ('campaign', 'email', 'name', 'user')
        }),
        ('Статус', {
            'fields': ('status', 'sent_at', 'error_message', 'message_id')
        }),
    )

@admin.register(EmailUnsubscribe)
class EmailUnsubscribeAdmin(admin.ModelAdmin):
    list_display = ['email', 'user', 'unsubscribed_at', 'reason']
    search_fields = ['email', 'user__username']
    list_filter = ['unsubscribed_at']
    readonly_fields = ['unsubscribed_at']


@admin.register(EmailBounce)
class EmailBounceAdmin(admin.ModelAdmin):
    list_display = ['email', 'bounce_type', 'message_id', 'created_at']
    list_filter = ['bounce_type', 'created_at']
    search_fields = ['email', 'message_id']
    readonly_fields = ['created_at', 'notification_data']