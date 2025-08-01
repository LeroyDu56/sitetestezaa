from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('map/', views.map_view, name='dynmap'),
    path('staff/', views.staff, name='staff'),
    path('store/', views.store, name='store'),
    path('store/require_access/', views.store_nok, name='store_nok'),
    path('rules/', views.rules, name='rules'),
    path('contact/', views.contact, name='contact'),
    path('faq/', views.faq, name='faq'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    path('profile/', views.profile_view, name='profile'),
    path('checkout/<int:rank_id>/', views.checkout, name='checkout'),
    path('payment/success/', views.payment_success, name='payment_success'),
    path('payment/cancel/', views.payment_cancel, name='payment_cancel'),
    path('webhook/stripe/', views.stripe_webhook, name='stripe_webhook'),
    path('payment/failed/', views.payment_failed, name='payment_failed'),
    path('cart/', views.view_cart, name='cart'),
    path('cart/add/', views.add_to_cart, name='add_to_cart'),
    path('cart/remove/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('cart/update/', views.update_cart_quantity, name='update_cart_quantity'),
    path('cart/checkout/', views.checkout_cart, name='checkout_cart'),
    path('check-minecraft-username/', views.check_minecraft_username, name='check_minecraft_username'),
    path('store/gift/<int:rank_id>/', views.gift_rank, name='gift_rank'),
    path('verify-minecraft-username/', views.verify_minecraft_username, name='verify_minecraft_username'),
    path('api/server-status/', views.server_status_api, name='server_status_api'),
    path('payment/qr-code/<str:session_id>/', views.payment_qr_code, name='payment_qr_code'),
    path('legal/', views.legal_notices, name='legal'),
    path('terms/', views.terms_of_service, name='terms'),
    path('cart/apply-promo/', views.apply_promo_code, name='apply_promo_code'),
    path('cart/remove-promo/', views.remove_promo_code, name='remove_promo_code'),
    path('api/calculate-gift-upgrade/', views.calculate_gift_upgrade_price, name='calculate_gift_upgrade_price'),
    # Routes de réinitialisation de mot de passe
    path('password_reset/', 
         auth_views.PasswordResetView.as_view(
             template_name='minecraft_app/password_reset.html',
             email_template_name='minecraft_app/password_reset_email.html',
             success_url='/password_reset/done/'
         ), 
         name='password_reset'),
    
    path('password_reset/done/', 
         auth_views.PasswordResetDoneView.as_view(
             template_name='minecraft_app/password_reset_done.html'
         ), 
         name='password_reset_done'),
    
    path('reset/<uidb64>/<token>/', 
         auth_views.PasswordResetConfirmView.as_view(
             template_name='minecraft_app/password_reset_confirm.html',
             success_url='/reset/done/'
         ), 
         name='password_reset_confirm'),
    
    path('reset/done/', 
         auth_views.PasswordResetCompleteView.as_view(
             template_name='minecraft_app/password_reset_complete.html'
         ), 
         name='password_reset_complete'),
]