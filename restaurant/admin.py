from django.contrib import admin
from .models import MenuItem, Order, OrderItem

@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'description')
    list_filter = ('category', 'price')
    search_fields = ('name', 'description')
    list_editable = ('category', 'price')

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('menu_item', 'quantity', 'price')

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'created_at', 'status', 'payment_status', 'payment_method', 'total')
    list_filter = ('status', 'payment_status', 'payment_method', 'created_at')
    search_fields = ('id',)
    readonly_fields = ('created_at', 'total')
    inlines = [OrderItemInline]

    def get_readonly_fields(self, request, obj=None):
        if obj:  # editing an existing object
            return self.readonly_fields + ('payment_method',)
        return self.readonly_fields

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('menu_item', 'order', 'quantity', 'price')
    list_filter = ('menu_item', 'order')
    search_fields = ('menu_item__name', 'order__order_uuid')
