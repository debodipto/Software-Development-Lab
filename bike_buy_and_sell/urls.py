from django.urls import path
from bike_buy_and_sell import views

app_name = 'bike_buy_and_sell'

urlpatterns = [
    path('', views.index, name='bike_index'),  # Changed from 'index' to 'bike_index'
    path('login/', views.user_login, name='login'),
    path('registration/', views.SignUpView.as_view(), name='registration'),
    path('change-password/', views.change_password, name='change_password'),
    path('profile/', views.profile, name='profile'),
    path('update-profile/', views.update_profile, name='update_profile'),
    path('logout/', views.logout_view, name='logout'),
    path('about/', views.about_view, name='about'),
    path('contact-us/', views.contact_view, name='contact'),
    path('booking_list/', views.booking_list, name='booking_list'),
    path('buy-list/', views.buy_list, name='buy_list'),  # Keep only this one
    path('sell/', views.sell_views, name='sell'),
    path('sell_list/', views.sell_list, name='sell_list'),
    path('add-to-cart/<int:product_id>/', views.add_to_cart_view, name='cart_add'),
    path('bike-details/<int:id>/', views.product_detail, name='product_detail'),
    path('cart-details/', views.cart_detail, name='cart_detail'),
    path('remove/<int:product_id>/', views.cart_remove, name='cart_remove'),
    path('update/<int:product_id>/', views.cart_update, name='cart_update'),
    path('checkout/', views.order_create, name='order_create'),
    path('my-order-details/<int:order_id>/', views.order_details, name='order_details'),
    path('admin/order-details/<int:order_id>/', views.admin_order_details, name='admin_order_details'),
    path('search/', views.search_view, name='search'),
    path('category_based_bike/<int:category_id>/', views.category_based_bike, name='category_based_bike'),
    path('chat-support/', views.user_chat_support, name='chat_support'),
    path('admin-chat-support/', views.admin_chat_support, name='admin_chat_support'),
    path('edit-bike/<int:bike_id>/', views.edit_bike, name='edit_bike'),
    path('delete-bike/<int:bike_id>/', views.delete_bike, name='delete_bike'),
    path('delete-bike-image/<int:image_id>/', views.delete_bike_image, name='delete_bike_image'),
    path('chat-support-redirect/', views.chat_support_redirect, name='chat_support_redirect'),
    path('activate/<uidb64>/<token>/', views.activate_account, name='activate'),
    path('chat-support-popup/', views.chat_support_popup, name='chat_support_popup'),
]
