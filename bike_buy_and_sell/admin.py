from django.contrib import admin
from django.urls import path, include, reverse  # <-- added import
from django.shortcuts import render, redirect
from django.db.models import Sum, Count, F, ExpressionWrapper, DecimalField
from django.db.models.functions import Coalesce
from django.utils import timezone
from datetime import timedelta
from .models import *
from django.utils.safestring import mark_safe
from django.utils.html import format_html  # <-- to render link safely
from django.contrib.auth.models import User  # Import the User model
from django.http import HttpResponse
import csv


class CategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('id', 'name')


class BikeAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'price', 'description', 'category', 'user', 'status')
    search_fields = ('id', 'name', 'price', 'description', 'category', 'user', 'status')
    list_filter = ['status']
    list_editable = ['status']  # Allow editing the status directly in the list view

    actions = ['approve_listings']

    def approve_listings(self, request, queryset):
        queryset.update(status='Approved')
        self.message_user(request, "Selected listings have been approved.")
    approve_listings.short_description = "Approve selected listings"


class BikeBuyAndSellImageAdmin(admin.ModelAdmin):
    list_display = ('id', 'bike_buy_and_sell', 'image')


class OrdersAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'email', 'address', 'mobile', 'total_price', 'order_date', 'status', 'created_at')  # removed view_order_details
    list_editable = ('status',)  # added inline edit option for status
    search_fields = ('id', 'user__username', 'email', 'address', 'mobile', 'total_price', 'order_date', 'status', 'created_at')
    list_filter = ['status', 'order_date']
    actions = ['update_status']

    def update_status(self, request, queryset):
        for order in queryset:
            order.status = 'Order Confirmed'
            order.save()
        self.message_user(request, "Selected orders have been updated to 'Order Confirmed'.")
    update_status.short_description = "Update status to 'Order Confirmed'"


class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'bike_buy_and_sell', 'created_at', 'updated_at', 'price', 'quantity')
    search_fields = ('id', 'order', 'bike_buy_and_sell', 'created_at', 'updated_at', 'price', 'quantity')


class BannerAdmin(admin.ModelAdmin):
    list_display = ('id', 'banner_image')


class ReplyInline(admin.TabularInline):
    model = ChatMessage
    fields = ('message', 'is_admin')
    extra = 1

    def save_new(self, form, commit=True):
        obj = super().save_new(form, commit=False)
        obj.is_admin = True  # Mark as an admin message
        obj.user = self.parent_instance.user  # Set the user to the parent message's user
        obj.parent = self.parent_instance  # Associate the reply with the parent message
        if commit:
            obj.save()
        return obj

    def get_formset(self, request, obj=None, **kwargs):
        # Pass the parent instance to the formset
        self.parent_instance = obj
        return super().get_formset(request, obj, **kwargs)


class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('user', 'short_message', 'status', 'priority', 'timestamp', 'get_replies_count', 'reply_link')  # added reply_link
    list_filter = ('status', 'priority', 'is_admin')
    search_fields = ('user__username', 'message')
    readonly_fields = ('timestamp', 'user', 'get_chat_history')
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('reply/<int:message_id>/', self.admin_site.admin_view(self.reply_view), name='chat-reply'),
        ]
        return custom_urls + urls

    def reply_view(self, request, message_id):
        original_message = ChatMessage.objects.get(id=message_id)
        if request.method == 'POST':
            reply_text = request.POST.get('reply')
            if reply_text:
                ChatMessage.objects.create(
                    user=original_message.user,  # Ensure reply goes to the original sender
                    message=reply_text,
                    is_admin=True,
                    parent=original_message,
                    status='in_progress'
                )
                original_message.status = 'in_progress'
                original_message.save()
                self.message_user(request, 'Reply sent successfully')
                return redirect('admin:bike_buy_and_sell_chatmessage_changelist')
        
        context = {
            'title': 'Reply to Message',
            'original_message': original_message,
            'chat_history': ChatMessage.objects.filter(
                user=original_message.user
            ).order_by('timestamp'),
            'opts': self.model._meta,
            'app_label': self.model._meta.app_label,
        }
        return render(request, 'admin/chat_reply.html', context)

    def get_chat_history(self, obj):
        history = ChatMessage.objects.filter(
            user=obj.user
        ).order_by('timestamp')
        return mark_safe('<br>'.join([
            f'<strong>{"Admin" if msg.is_admin else msg.user.username}</strong> ({msg.timestamp.strftime("%Y-%m-%d %H:%M")}): {msg.message}'
            for msg in history
        ]))
    get_chat_history.short_description = 'Chat History'

    def short_message(self, obj):
        return obj.message[:50] + '...' if len(obj.message) > 50 else obj.message
    short_message.short_description = 'Message'

    def get_replies_count(self, obj):
        return obj.replies.count()
    get_replies_count.short_description = 'Replies'

    def reply_link(self, obj):
        # Only allow reply for messages not from admin
        if not obj.is_admin:
            url = reverse('admin:chat-reply', args=[obj.pk])
            return format_html('<a href="{}">Reply</a>', url)
        return ""
    reply_link.short_description = "Reply"

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['show_reply_button'] = True
        return super().change_view(request, object_id, form_url, extra_context)


def admin_dashboard(request):
    # Get date range for trends
    today = timezone.now()
    last_month = today - timedelta(days=30)
    
    # Calculate total sales and trend
    total_sales = Orders.objects.aggregate(
        total=Coalesce(Sum('total_price'), 0))['total']
    
    last_month_sales = Orders.objects.filter(
        created_at__gte=last_month
    ).aggregate(total=Coalesce(Sum('total_price'), 0))['total']
    
    sales_trend = (
        ((float(total_sales) - float(last_month_sales)) / float(last_month_sales) * 100) 
        if last_month_sales > 0 
        else 100 if total_sales > 0 else 0
    )

    # User statistics
    total_users = User.objects.count()
    active_users = User.objects.filter(is_active=True).count()

    # Order statistics
    total_orders = Orders.objects.count()
    pending_orders = Orders.objects.filter(status='Pending').count()

    # Bike statistics
    total_bikes = BikeBuyAndSell.objects.count()
    pending_bikes = BikeBuyAndSell.objects.filter(status='Pending').count()

    # Popular bikes
    popular_bikes = BikeBuyAndSell.objects.annotate(
        sales_count=Count('orderitem'),
        total_revenue=ExpressionWrapper(
            F('price') * Count('orderitem'),
            output_field=DecimalField()
        )
    ).order_by('-sales_count')[:5]

    # Recent orders
    recent_orders = Orders.objects.select_related('user').order_by('-created_at')[:10]

    context = {
        'total_sales': total_sales,
        'sales_trend': sales_trend,
        'total_users': total_users,
        'active_users': active_users,
        'total_orders': total_orders,
        'pending_orders': pending_orders,
        'total_bikes': total_bikes,
        'pending_bikes': pending_bikes,
        'popular_bikes': popular_bikes,
        'recent_orders': recent_orders,
    }
    return render(request, 'admin/dashboard.html', context)


# Create an AdminSite subclass to add custom views
class CustomAdminSite(admin.AdminSite):
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('dashboard/', self.admin_view(admin_dashboard), name='admin_dashboard'),
        ]
        return custom_urls + urls

# Replace the default admin site with our custom one
admin.site = CustomAdminSite()

# Update these registrations to use the new admin site
admin.site.register(Category, CategoryAdmin)
admin.site.register(BikeBuyAndSell, BikeAdmin)
admin.site.register(BikeBuyAndSellImage, BikeBuyAndSellImageAdmin)
admin.site.register(Orders, OrdersAdmin)
admin.site.register(OrderItem, OrderItemAdmin)
admin.site.register(Banner, BannerAdmin)
admin.site.register(ChatMessage, ChatMessageAdmin)
admin.site.register(User)  # Register the User model
