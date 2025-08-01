# minecraft_app/views.py - Importations complètes en haut du fichier
# minecraft_app/views.py - Importations complètes en haut du fichier

from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.urls import reverse
from django.utils import timezone
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Count, Sum, F
from django.db import transaction
from django import forms
from decimal import Decimal
from io import BytesIO
import requests
import qrcode
import qrcode.image.svg
import json
import logging
import stripe
import time

# Importations depuis votre app
from .models import (
    TownyServer, Nation, Town, StaffMember, Rank, ServerRule, 
    DynamicMapPoint, UserProfile, UserPurchase, StoreItemPurchase, 
    StoreItem, CartItem, WebhookError, get_player_discount, 
    UserSubscription, get_rank_upgrade_price, PromoCode, PromoCodeUsage, 
    Bundle, BundlePurchase
)
from .services import fetch_minecraft_uuid, format_uuid_with_dashes
from .minecraft_service import apply_rank_to_player, give_bundle_to_player

# Configuration Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY
logger = logging.getLogger(__name__)

def home(request):
    server = TownyServer.objects.first()
    nations_count = Nation.objects.count()
    towns_count = Town.objects.count()
    
    # Get the top 3 nations for the home page display
    top_nations = Nation.objects.annotate(towns_count=Count('towns')).order_by('-towns_count')[:3]
    
    context = {
        'server': server,
        'nations_count': nations_count,
        'towns_count': towns_count,
        'nations': top_nations,  # Add nations for the home page
    }
    
    return render(request, 'minecraft_app/home.html', context)

def nations(request):
    # Get only the top 3 nations by number of towns
    nations_list = Nation.objects.annotate(towns_count=Count('towns')).order_by('-towns_count')[:3]
    
    # Calculate additional statistics for the nations page
    total_towns = Town.objects.count()
    total_residents = Town.objects.aggregate(total=Sum('residents_count'))['total'] or 0
    
    context = {
        'nations': nations_list,
        'total_towns': total_towns,
        'total_residents': total_residents,
    }
    
    return render(request, 'minecraft_app/nations.html', context)

def nation_detail(request, nation_id):
    nation = get_object_or_404(Nation, id=nation_id)
    towns = Town.objects.filter(nation=nation).order_by('-residents_count')
    
    context = {
        'nation': nation,
        'towns': towns,
    }
    
    return render(request, 'minecraft_app/nation_detail.html', context)

def dynmap(request):
    map_points = DynamicMapPoint.objects.all()
    towns = Town.objects.all()
    nations = Nation.objects.all()
    
    context = {
        'map_points': map_points,
        'towns': towns,
        'nations': nations,
    }
    
    return render(request, 'minecraft_app/dynmap.html', context)

def rules(request):
    rules_list = ServerRule.objects.all()
    
    context = {
        'rules': rules_list,
    }
    
    return render(request, 'minecraft_app/rules.html', context)

def map_view(request):
    server = TownyServer.objects.first()
    
    context = {
        'server': server,
    }
    
    return render(request, 'minecraft_app/map.html', context)

def server_status_api(request):
    """
    Vue API pour récupérer le statut du serveur en temps réel
    """
    from .services import update_server_status
    
    try:
        # Mettre à jour le statut du serveur
        is_online, player_count, max_players = update_server_status()
        
        # Mettre à jour l'objet TownyServer dans la base de données
        server = TownyServer.objects.first()
        if server:
            server.status = is_online
            server.player_count = player_count
            server.max_players = max_players
            server.save()
        
        return JsonResponse({
            'status': is_online,
            'player_count': player_count,
            'max_players': max_players,
            'version': server.version if server else "1.20.4"
        })
    except Exception as e:
        logger.error(f"Erreur API statut serveur: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
    
def contact(request):
    server = TownyServer.objects.first()
    
    if request.method == 'POST':
        # Get form data
        name = request.POST.get('name', '')
        discord_username = request.POST.get('discord_username', '')
        minecraft_username = request.POST.get('minecraft_username', '')
        subject = request.POST.get('subject', '')
        message = request.POST.get('message', '')
        
        # Log received data
        logging.debug(f"Contact form received - Name: {name}, Subject: {subject}")
        
        # Validate required fields
        if name and subject and message:
            # Log webhook URL from settings
            webhook_url = settings.DISCORD_WEBHOOK_URL
            logging.debug(f"Using webhook URL: {webhook_url}")
            
            if not webhook_url or webhook_url == '':
                logging.error("Discord webhook URL is empty or not set")
                messages.error(request, "Erreur de configuration du serveur : Le webhook Discord n'est pas configuré.")
                return redirect('contact')
                
            # Send the message to Discord webhook
            success = send_discord_webhook(name, discord_username, minecraft_username, subject, message)
            
            if success:
                messages.success(request, "Votre message a été envoyé avec succès. Nous vous répondrons dès que possible.")
            else:
                messages.error(request, "Une erreur s'est produite lors de l'envoi de votre message. Veuillez réessayer plus tard ou nous contacter sur Discord.")
            
            # Redirect to avoid form resubmission
            return redirect('contact')
        else:
            # If required fields are missing
            messages.error(request, "Veuillez remplir tous les champs obligatoires.")
    
    context = {
        'server': server,
    }
    
    return render(request, 'minecraft_app/contact.html', context)

def faq(request):
    return render(request, 'minecraft_app/faq.html')

def staff(request):
    # Check if staff members exist, if not create default administrators
    if StaffMember.objects.count() == 0:
        # Create administrators
        StaffMember.objects.create(
            name="EnzoLaPicole",
            role="admin",
            description="Fondateur et développeur principal du serveur Novania. Responsable des opérations techniques et de l'expérience de jeu globale.",
            discord_username="EnzoLaPicole#1234"
        )
        
        StaffMember.objects.create(
            name="karatoss",
            role="admin",
            description="Co-administrateur en charge de la gestion de la communauté et de la modération. Spécialiste du plugin Towny.",
            discord_username="karatoss#5678"
        )
        
        StaffMember.objects.create(
            name="Betaking",
            role="admin",
            description="Administrateur responsable des événements et des communications. Expert en construction et design des villes.",
            discord_username="Betaking#9012"
        )
    
    # Get staff members by role
    admins = StaffMember.objects.filter(role='admin')
    mods = StaffMember.objects.filter(role='mod')
    helpers = StaffMember.objects.filter(role='helper')
    builders = StaffMember.objects.filter(role='builder')
    
    context = {
        'admins': admins,
        'mods': mods,
        'helpers': helpers,
        'builders': builders,
    }
    
    return render(request, 'minecraft_app/staff.html', context)

# Custom registration form
class RegisterForm(UserCreationForm):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Entrez votre email'})
    )
    minecraft_username = forms.CharField(
        max_length=100, 
        required=False, 
        help_text="Votre nom d'utilisateur Minecraft",
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Entrez votre nom d\'utilisateur Minecraft (optionnel)',
            'autocomplete': 'off'
        })
    )
    
    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2', 'minecraft_username']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Choisissez un nom d\'utilisateur'}),
        }
    
    def __init__(self, *args, **kwargs):
        super(RegisterForm, self).__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Entrez votre mot de passe'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Confirmez votre mot de passe'})
    
    def clean_minecraft_username(self):
        minecraft_username = self.cleaned_data.get('minecraft_username')
        if minecraft_username and not is_minecraft_username_unique(minecraft_username):
            raise forms.ValidationError("Ce nom d'utilisateur Minecraft est déjà utilisé par un autre utilisateur.")
        return minecraft_username

# Modify register_view to retrieve UUID
def register_view(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            minecraft_username = form.cleaned_data.get('minecraft_username')
            
            # Create user profile
            profile = UserProfile.objects.create(
                user=user,
                minecraft_username=minecraft_username
            )
            
            # If a Minecraft username is provided, try to retrieve the UUID
            if minecraft_username:
                uuid = fetch_minecraft_uuid(minecraft_username)
                if uuid:
                    profile.minecraft_uuid = uuid
                    profile.save()
                
            # Log in the user
            login(request, user)
            messages.success(request, "Compte créé avec succès ! Bienvenue sur Novania !")
            return redirect('home')
    else:
        form = RegisterForm()
    
    return render(request, 'minecraft_app/register.html', {'form': form})

# Login view
def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.info(request, f"Vous êtes maintenant connecté en tant que {username}.")
                return redirect('home')
            else:
                messages.error(request, "Nom d'utilisateur ou mot de passe invalide.")
        else:
            messages.error(request, "Nom d'utilisateur ou mot de passe invalide.")
    else:
        form = AuthenticationForm()
    
    return render(request, 'minecraft_app/login.html', {'form': form})

# Logout view
def logout_view(request):
    logout(request)
    messages.info(request, "Vous avez été déconnecté.")
    return redirect('home')

# Profile view
@login_required
def profile_view(request):
    user = request.user
    try:
        profile = user.profile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=user)
    
    # Get user purchases for display
    purchases = UserPurchase.objects.filter(user=user).select_related('rank')
    
    # Get the server for global context
    server = TownyServer.objects.first()
    
    if request.method == 'POST':
        # Profile update form
        minecraft_username = request.POST.get('minecraft_username')
        discord_username = request.POST.get('discord_username')
        bio = request.POST.get('bio')
        
        # Vérifier si le pseudo Minecraft est unique avant de mettre à jour
        if minecraft_username and minecraft_username != profile.minecraft_username:
            if not is_minecraft_username_unique(minecraft_username, user):
                messages.error(request, "Ce nom d'utilisateur Minecraft est déjà utilisé par un autre utilisateur.")
                return redirect('profile')
        
        # Update profile
        old_minecraft_username = profile.minecraft_username
        
        profile.minecraft_username = minecraft_username
        profile.discord_username = discord_username
        profile.bio = bio
        
        # If Minecraft username changed, update UUID
        if minecraft_username != old_minecraft_username:
            if minecraft_username:
                uuid = fetch_minecraft_uuid(minecraft_username)
                if uuid:
                    profile.minecraft_uuid = uuid
                else:
                    # If UUID can't be retrieved, clear the old one
                    profile.minecraft_uuid = ''
            else:
                # If username is empty, clear UUID
                profile.minecraft_uuid = ''
        
        profile.save()
        
        messages.success(request, "Profil mis à jour avec succès !")
        return redirect('profile')
    
    context = {
        'profile': profile,
        'server': server,
        'purchases': purchases
    }
        
    return render(request, 'minecraft_app/profile.html', context)

def check_minecraft_username(request):
    """Vue API pour vérifier la disponibilité d'un pseudo Minecraft via AJAX"""
    if request.method == 'GET':
        username = request.GET.get('username', '')
        current_user = request.user if request.user.is_authenticated else None
        
        is_available = is_minecraft_username_unique(username, current_user)
        
        return JsonResponse({
            'available': is_available,
            'message': 'Nom d\'utilisateur disponible' if is_available else 'Ce nom d\'utilisateur Minecraft est déjà utilisé'
        })
    
    return JsonResponse({'error': 'Requête invalide'}, status=400)

@login_required
def gift_rank(request, rank_id):
    rank = get_object_or_404(Rank, id=rank_id)
    
    if request.method == 'POST':
        minecraft_username = request.POST.get('minecraft_username')
        
        if not minecraft_username:
            messages.error(request, "Veuillez entrer un nom d'utilisateur Minecraft.")
            return redirect('gift_rank', rank_id=rank_id)
        
        # Check if the user exists with this Minecraft username
        try:
            recipient_profile = UserProfile.objects.get(minecraft_username=minecraft_username)
            
            # Check if recipient is the same as buyer
            if recipient_profile.user == request.user:
                messages.error(request, "Vous ne pouvez pas offrir un grade à vous-même.")
                return redirect('gift_rank', rank_id=rank_id)
            
            # Check if recipient already has this rank
            existing_purchase = UserPurchase.objects.filter(
                user=recipient_profile.user,
                rank=rank,
                payment_status='completed'
            ).exists()
            
            if existing_purchase:
                messages.error(request, f"Le joueur {minecraft_username} possède déjà le grade {rank.name}.")
                return redirect('gift_rank', rank_id=rank_id)
            
            # Vérifier si l'acheteur a déjà ce cadeau dans SON panier
            existing_cart_item = CartItem.objects.filter(
                user=request.user,  # ✅ Panier de l'acheteur
                rank=rank,
                # ✅ Vérifier si c'est déjà un cadeau pour le même destinataire
                metadata__is_gift=True,
                metadata__recipient_minecraft_username=minecraft_username
            ).first()
            
            if existing_cart_item:
                messages.warning(request, f"Vous avez déjà ce cadeau pour {minecraft_username} dans votre panier.")
                return redirect('cart')
            
            # Calculer le prix d'upgrade pour le destinataire
            actual_price = get_rank_upgrade_price(recipient_profile.user, rank)
            
            # Si le destinataire a un rang plus élevé, on ne peut pas offrir un rang inférieur
            if actual_price == 0:
                messages.error(request, f"Le joueur {minecraft_username} possède déjà un grade égal ou supérieur à {rank.name}.")
                return redirect('gift_rank', rank_id=rank_id)
            
            # ✅ NOUVEAU : Ajouter au panier au lieu de créer une session Stripe
            metadata = {
                'is_gift': True,
                'recipient_minecraft_username': minecraft_username,
                'recipient_user_id': recipient_profile.user.id,
                'upgrade_price': str(actual_price),
                'original_price': str(rank.price),
                'is_upgrade': actual_price < rank.price
            }
            
            # Créer l'item dans le panier de l'acheteur avec les métadonnées de cadeau
            cart_item = CartItem.objects.create(
                user=request.user,  # ✅ L'acheteur possède l'item dans son panier
                rank=rank,
                quantity=1,
                metadata=metadata
            )
            
            messages.success(request, f"Cadeau {rank.name} pour {minecraft_username} ajouté au panier !")
            return redirect('cart')  # ✅ Rediriger vers le panier
                
        except UserProfile.DoesNotExist:
            messages.error(request, f"Aucun joueur trouvé avec le nom d'utilisateur Minecraft '{minecraft_username}'. Assurez-vous qu'il s'est inscrit sur notre site en premier.")
            return redirect('gift_rank', rank_id=rank_id)
    
    context = {
        'rank': rank,
        'server': TownyServer.objects.first(),
    }
    
    return render(request, 'minecraft_app/gift_rank.html', context)

@login_required
def calculate_gift_upgrade_price(request):
    """AJAX endpoint pour calculer le prix d'upgrade pour un cadeau"""
    username = request.GET.get('username', '').strip()
    rank_id = request.GET.get('rank_id')
    
    if not username or not rank_id:
        return JsonResponse({
            'success': False,
            'error': 'Paramètres manquants'
        })
    
    try:
        # Trouver le destinataire
        recipient_profile = UserProfile.objects.get(minecraft_username=username)
        recipient_user = recipient_profile.user
        
        # Trouver le rang
        rank = Rank.objects.get(id=rank_id)
        
        # Vérifier si le destinataire possède déjà ce rang exact
        existing_purchase = UserPurchase.objects.filter(
            user=recipient_user,
            rank=rank,
            payment_status='completed'
        ).exists()
        
        if existing_purchase:
            return JsonResponse({
                'success': False,
                'error': f'Ce joueur possède déjà le grade {rank.name}'
            })
        
        # Calculer le prix d'upgrade
        upgrade_price = get_rank_upgrade_price(recipient_user, rank)
        
        return JsonResponse({
            'success': True,
            'upgrade_price': float(upgrade_price),
            'original_price': float(rank.price),
            'is_upgrade': upgrade_price < rank.price,
            'recipient_username': username
        })
        
    except UserProfile.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Joueur non trouvé'
        })
    except Rank.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Rang non trouvé'
        })
    except Exception as e:
        logger.error(f"Erreur lors du calcul du prix d'upgrade cadeau: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Erreur lors du calcul du prix'
        })

@login_required
def verify_minecraft_username(request):
    """AJAX endpoint to verify Minecraft username exists in database"""
    minecraft_username = request.GET.get('username', '')
    
    try:
        profile = UserProfile.objects.get(minecraft_username=minecraft_username)
        return JsonResponse({
            'exists': True,
            'username': minecraft_username,
            'is_self': profile.user == request.user
        })
    except UserProfile.DoesNotExist:
        return JsonResponse({
            'exists': False,
            'message': 'Aucun joueur trouvé avec ce nom d\'utilisateur Minecraft'
        })

@login_required
def checkout(request, rank_id):
    rank = get_object_or_404(Rank, id=rank_id)
    user = request.user
    
    # Check if the user already has a rank and apply discount if necessary
    highest_owned_rank = None
    user_purchases = UserPurchase.objects.filter(
        user=user,
        payment_status='completed'
    ).select_related('rank')
    
    if user_purchases.exists():
        try:
            highest_owned_rank = max(
                [purchase.rank for purchase in user_purchases if purchase.rank],
                key=lambda rank: rank.price
            )
        except (ValueError, TypeError):
            highest_owned_rank = None
    
    # Apply discount if user has a rank and is buying a higher rank
    actual_price = rank.price
    if highest_owned_rank and highest_owned_rank.price < rank.price:
        actual_price = rank.price - highest_owned_rank.price
    
    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card', 'paypal'],  # ✅ AJOUT DE PAYPAL ICI
            line_items=[
                {
                    'price_data': {
                        'currency': 'eur',
                        'unit_amount': int(actual_price * 100),
                        'product_data': {
                            'name': f"Grade {rank.name}",
                            'description': f"{rank.description}",
                        },
                    },
                    'quantity': 1,
                }
            ],
            metadata={
                'user_id': user.id,
                'username': user.username,
                'rank_id': rank.id,
                'rank_name': rank.name,
                'original_price': str(rank.price),
                'discounted_price': str(actual_price),
                'previous_rank_id': str(highest_owned_rank.id) if highest_owned_rank else '',
            },
            mode='payment',
            success_url=request.build_absolute_uri(reverse('payment_success') + f'?session_id={{CHECKOUT_SESSION_ID}}'),
            cancel_url=request.build_absolute_uri(reverse('payment_cancel')),
        )
        return redirect(checkout_session.url, code=303)
    except Exception as e:
        logging.error(f"Error creating Stripe checkout session: {str(e)}")
        messages.error(request, f"Erreur lors de la création du paiement : {str(e)}")
        return redirect('store')


def payment_success(request):
    session_id = request.GET.get('session_id')
    
    if session_id:
        # Try to retrieve rank purchases
        rank_purchases = UserPurchase.objects.filter(payment_id=session_id)
        
        # Try to retrieve store item purchases
        store_item_purchases = StoreItemPurchase.objects.filter(payment_id=session_id)
        
        # Calculate total amount
        total_amount = 0
        for purchase in rank_purchases:
            total_amount += purchase.amount
        
        for purchase in store_item_purchases:
            total_amount += purchase.amount
        
        if rank_purchases.exists() or store_item_purchases.exists():
            return render(request, 'minecraft_app/payment_success.html', {
                'rank_purchases': rank_purchases,
                'store_item_purchases': store_item_purchases,
                'total_amount': total_amount,
                'server': TownyServer.objects.first()
            })
    
    # Fallback if purchase not found (can happen if webhook hasn't processed yet)
    return render(request, 'minecraft_app/payment_success.html', {
        'server': TownyServer.objects.first()
    })

@csrf_exempt
def stripe_webhook(request):
    logger.debug("Webhook received with payload: %s", request.body)
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    
    try:
        event = stripe.Webhook.construct_event(
            request.body, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
        logger.info("Webhook event received: %s", event['type'])
    except ValueError as e:
        logger.error("Invalid webhook payload: %s", str(e))
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        logger.error("Webhook signature verification failed: %s", str(e))
        return HttpResponse(status=400)

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        logger.info("Processing checkout.session.completed for session: %s", session['id'])
        try:
            process_successful_payment(session)
            logger.info("Successfully processed session: %s", session['id'])
        except Exception as e:
            logger.error("Error processing session %s: %s", session['id'], str(e))
    elif event['type'] == 'payment_intent.payment_failed':
        logger.warning("Payment failed for session: %s", event['data']['object']['id'])
        process_failed_payment(event['data']['object'])
    elif event['type'] == 'checkout.session.expired':
        logger.info("Checkout session expired: %s", event['data']['object']['id'])
        process_expired_session(event['data']['object'])
    elif event['type'] == 'customer.subscription.updated':
        subscription = event['data']['object']
        logger.info("Processing customer.subscription.updated for subscription: %s", subscription['id'])
        try:
            process_subscription_updated(subscription)
        except Exception as e:
            logger.error("Error processing subscription update %s: %s", subscription['id'], str(e))
    
    elif event['type'] == 'customer.subscription.deleted':
        subscription = event['data']['object']
        logger.info("Processing customer.subscription.deleted for subscription: %s", subscription['id'])
        try:
            process_subscription_cancelled(subscription)
        except Exception as e:
            logger.error("Error processing subscription cancellation %s: %s", subscription['id'], str(e))
    
    elif event['type'] == 'invoice.payment_failed':
        invoice = event['data']['object']
        logger.info("Processing invoice.payment_failed for invoice: %s", invoice['id'])
        try:
            process_failed_subscription_payment(invoice)
        except Exception as e:
            logger.error("Error processing failed payment %s: %s", invoice['id'], str(e))

    return HttpResponse(status=200)

def process_successful_payment(session):
    # Check if it's a gift purchase
    is_gift = session.get('metadata', {}).get('is_gift') == 'true'
    
    if is_gift:
        # ✅ SECTION CADEAUX DIRECTS (ancienne méthode, gardée pour compatibilité)
        user_id = session.get('metadata', {}).get('user_id')
        recipient_user_id = session.get('metadata', {}).get('recipient_user_id')
        recipient_minecraft_username = session.get('metadata', {}).get('recipient_minecraft_username')
        rank_id = session.get('metadata', {}).get('rank_id')
        actual_price = session.get('metadata', {}).get('actual_price')
        
        try:
            buyer = User.objects.get(id=user_id)
            recipient = User.objects.get(id=recipient_user_id)
            rank = Rank.objects.get(id=rank_id)
            
            # ✅ CORRECTION : Récupérer le pseudo Minecraft de l'acheteur de manière robuste
            try:
                buyer_profile = buyer.profile
                buyer_minecraft_username = buyer_profile.minecraft_username
                if not buyer_minecraft_username or buyer_minecraft_username.strip() == '':
                    buyer_minecraft_username = buyer.username
                    logger.warning(f"Acheteur {buyer.username} n'a pas de pseudo Minecraft défini, utilisation du username")
            except UserProfile.DoesNotExist:
                buyer_minecraft_username = buyer.username
                logger.warning(f"Acheteur {buyer.username} n'a pas de profil, utilisation du username")
            except Exception as e:
                buyer_minecraft_username = buyer.username
                logger.error(f"Erreur lors de la récupération du profil acheteur: {e}")
            
            # Vérifier le pseudo du destinataire
            if not recipient_minecraft_username:
                try:
                    recipient_profile = recipient.profile
                    recipient_minecraft_username = recipient_profile.minecraft_username
                    if not recipient_minecraft_username:
                        recipient_minecraft_username = recipient.username
                except:
                    recipient_minecraft_username = recipient.username
            
            # Utiliser le prix réel payé si disponible, sinon le prix du rang
            amount_paid = Decimal(actual_price) if actual_price else rank.price
            
            # Create purchase record for recipient
            purchase = UserPurchase.objects.create(
                user=recipient,
                rank=rank,
                amount=amount_paid,
                payment_id=session.id,
                payment_status='completed',
                is_gift=True,
                gifted_by=buyer
            )
            
            # ✅ CORRECTION PRINCIPALE : Appliquer le rang avec les bons pseudos
            success = apply_rank_to_player(
                recipient_minecraft_username, 
                rank.name, 
                is_temporary=False, 
                gifted_by=buyer_minecraft_username  # ✅ Pseudo Minecraft de l'acheteur
            )
            
            if success:
                logger.info(f"✅ Grade cadeau {rank.name} appliqué avec succès à {recipient_minecraft_username} par {buyer_minecraft_username} (montant: €{amount_paid})")
            else:
                logger.error(f"❌ Échec de l'application du grade cadeau {rank.name} à {recipient_minecraft_username}")
            
        except Exception as e:
            logger.error(f"Erreur lors du traitement du paiement cadeau : {str(e)}")
    else:
        # ✅ SECTION ACHATS PANIER (où se trouve le problème principal)
        cart_items_ids = session.get('metadata', {}).get('cart_items', '').split(',')
        
        if cart_items_ids and cart_items_ids[0]:  # Cart purchase
            user_id = session.get('metadata', {}).get('user_id')
            try:
                user = User.objects.get(id=user_id)
                logger.info("Utilisateur trouvé : %s", user.username)
                
                # ✅ CORRECTION : Récupérer le pseudo Minecraft de l'acheteur une seule fois
                try:
                    buyer_profile = user.profile
                    buyer_minecraft_username = buyer_profile.minecraft_username
                    if not buyer_minecraft_username or buyer_minecraft_username.strip() == '':
                        buyer_minecraft_username = user.username
                        logger.warning(f"Acheteur {user.username} n'a pas de pseudo Minecraft défini, utilisation du username")
                except UserProfile.DoesNotExist:
                    buyer_minecraft_username = user.username
                    logger.warning(f"Acheteur {user.username} n'a pas de profil, utilisation du username")
                except Exception as e:
                    buyer_minecraft_username = user.username
                    logger.error(f"Erreur lors de la récupération du profil acheteur: {e}")
                
                with transaction.atomic():
                    for item_id in cart_items_ids:
                        if not item_id:
                            logger.debug("Ignorer item_id vide")
                            continue
                        try:
                            cart_item = CartItem.objects.select_related('rank', 'store_item', 'bundle').get(id=item_id, user=user)
                            logger.debug("Traitement de l'article du panier %s : grade=%s, article=%s, bundle=%s", 
                                         item_id, cart_item.rank, cart_item.store_item, cart_item.bundle)
                            
                            if cart_item.rank:
                                # ✅ CORRECTION PRINCIPALE : Vérifier si c'est un cadeau DANS LE PANIER
                                if cart_item.is_gift and cart_item.gift_recipient_user:
                                    # ✅ TRAITEMENT DU CADEAU DEPUIS LE PANIER
                                    gift_recipient = cart_item.gift_recipient_user
                                    gift_recipient_username = cart_item.gift_recipient_username
                                    
                                    # Vérifier si le destinataire possède déjà ce grade
                                    if UserPurchase.objects.filter(user=gift_recipient, rank=cart_item.rank, payment_status='completed').exists():
                                        logger.warning("Le destinataire %s possède déjà le grade %s, ignoré", 
                                                     gift_recipient.username, cart_item.rank.name)
                                        cart_item.delete()
                                        continue
                                    
                                    # ✅ Créer l'achat pour le DESTINATAIRE
                                    purchase = UserPurchase.objects.create(
                                        user=gift_recipient,
                                        rank=cart_item.rank,
                                        amount=cart_item.get_subtotal(),
                                        payment_id=session.id,
                                        payment_status='completed',
                                        is_gift=True,
                                        gifted_by=user
                                    )
                                    logger.info("UserPurchase cadeau %s créé pour le grade %s (destinataire : %s, acheteur : %s)", 
                                               purchase.id, cart_item.rank.name, gift_recipient.username, user.username)
                                    
                                    # ✅ CORRECTION : Appliquer le rang au DESTINATAIRE avec le bon pseudo acheteur
                                    success = apply_rank_to_player(
                                        gift_recipient_username,
                                        cart_item.rank.name,
                                        is_temporary=False,
                                        gifted_by=buyer_minecraft_username  # ✅ Pseudo Minecraft de l'acheteur
                                    )
                                    
                                    logger.info("✅ Cadeau %s appliqué à %s par %s : %s", 
                                              cart_item.rank.name, gift_recipient_username, 
                                              buyer_minecraft_username, "Succès" if success else "Échec")
                                    
                                elif cart_item.metadata and cart_item.metadata.get('is_gift'):
                                    # ✅ CORRECTION : Gérer les cadeaux avec métadonnées (système actuel)
                                    gift_recipient_username = cart_item.metadata.get('recipient_minecraft_username')
                                    gift_recipient_user_id = cart_item.metadata.get('recipient_user_id')
                                    
                                    if gift_recipient_user_id and gift_recipient_username:
                                        try:
                                            gift_recipient = User.objects.get(id=gift_recipient_user_id)
                                            
                                            # Vérifier si le destinataire possède déjà ce grade
                                            if UserPurchase.objects.filter(user=gift_recipient, rank=cart_item.rank, payment_status='completed').exists():
                                                logger.warning("Le destinataire %s possède déjà le grade %s, ignoré", 
                                                             gift_recipient.username, cart_item.rank.name)
                                                cart_item.delete()
                                                continue
                                            
                                            # ✅ Créer l'achat pour le DESTINATAIRE
                                            purchase = UserPurchase.objects.create(
                                                user=gift_recipient,
                                                rank=cart_item.rank,
                                                amount=cart_item.get_subtotal(),
                                                payment_id=session.id,
                                                payment_status='completed',
                                                is_gift=True,
                                                gifted_by=user
                                            )
                                            logger.info("UserPurchase cadeau métadonnées %s créé pour le grade %s (destinataire : %s, acheteur : %s)", 
                                                       purchase.id, cart_item.rank.name, gift_recipient.username, user.username)
                                            
                                            # ✅ CORRECTION PRINCIPALE : Appliquer le rang au DESTINATAIRE avec le bon pseudo acheteur
                                            success = apply_rank_to_player(
                                                gift_recipient_username,
                                                cart_item.rank.name,
                                                is_temporary=False,
                                                gifted_by=buyer_minecraft_username  # ✅ Pseudo Minecraft de l'acheteur
                                            )
                                            
                                            logger.info("✅ Cadeau métadonnées %s appliqué à %s par %s : %s", 
                                                      cart_item.rank.name, gift_recipient_username, 
                                                      buyer_minecraft_username, "Succès" if success else "Échec")
                                                      
                                        except User.DoesNotExist:
                                            logger.error("Destinataire du cadeau introuvable avec l'ID %s", gift_recipient_user_id)
                                    else:
                                        logger.error("Informations de destinataire manquantes dans les métadonnées du cadeau")
                                    
                                else:
                                    # ✅ TRAITEMENT NORMAL D'UN RANG (achat personnel)
                                    # Vérifier si l'utilisateur a déjà ce grade
                                    if UserPurchase.objects.filter(user=user, rank=cart_item.rank, payment_status='completed').exists():
                                        logger.warning("L'utilisateur %s possède déjà le grade %s, ignoré", user.username, cart_item.rank.name)
                                        cart_item.delete()
                                        continue
                                    
                                    purchase = UserPurchase.objects.create(
                                        user=user,
                                        rank=cart_item.rank,
                                        amount=cart_item.get_subtotal(),
                                        payment_id=session.id,
                                        payment_status='completed'
                                    )
                                    logger.info("UserPurchase %s créé pour le grade %s (utilisateur : %s)", 
                                               purchase.id, cart_item.rank.name, user.username)
                                    
                                    # ✅ CORRECTION : Utiliser le pseudo Minecraft de l'acheteur
                                    if buyer_minecraft_username:
                                        success = apply_rank_to_player(
                                            buyer_minecraft_username,
                                            cart_item.rank.name, 
                                            is_temporary=False, 
                                            gifted_by=None  # ✅ Pas de cadeau
                                        )
                                        logger.info("Application du grade %s pour %s : %s", 
                                                   cart_item.rank.name, buyer_minecraft_username, 
                                                   "Succès" if success else "Échec")
                                    else:
                                        logger.warning("Pas de nom d'utilisateur Minecraft pour l'utilisateur %s, grade %s non appliqué", 
                                                      user.username, cart_item.rank.name)
                                
                                cart_item.delete()
                                logger.debug("Article du panier %s supprimé", item_id)
                                
                            elif cart_item.store_item:
                                purchase = StoreItemPurchase.objects.create(
                                    user=user,
                                    store_item=cart_item.store_item,
                                    quantity=cart_item.quantity,
                                    amount=cart_item.get_subtotal(),  # Utilise le prix avec réduction si applicable
                                    payment_id=session.id,
                                    payment_status='completed'
                                )
                                logger.info("StoreItemPurchase %s créé pour %s (x%s)", 
                                           purchase.id, cart_item.store_item.name, cart_item.quantity)
                                
                                # Application de l'objet acheté au joueur
                                minecraft_username = user.profile.minecraft_username
                                if minecraft_username:
                                    from .minecraft_service import give_store_item_to_player
                                    success = give_store_item_to_player(minecraft_username, cart_item.store_item.name, cart_item.quantity)
                                    logger.info("Attribution de %d %s pour %s: %s", 
                                              cart_item.quantity, cart_item.store_item.name, minecraft_username,
                                              "Succès" if success else "Échec")
                                else:
                                    logger.warning("Pas de nom d'utilisateur Minecraft pour l'utilisateur %s, objet(s) %s non appliqué(s)", 
                                                 user.username, cart_item.store_item.name)
                                
                                if cart_item.store_item.quantity > 0:
                                    cart_item.store_item.quantity -= cart_item.quantity
                                    cart_item.store_item.quantity = max(0, cart_item.store_item.quantity)
                                    cart_item.store_item.save()
                                cart_item.delete()

                            elif cart_item.bundle:
                                purchase = BundlePurchase.objects.create(
                                    user=user,
                                    bundle=cart_item.bundle,
                                    amount=cart_item.get_subtotal(),  # Utilise le prix avec réduction si applicable
                                    payment_id=session.id,
                                    payment_status='completed'
                                )
                                logger.info("BundlePurchase %s créé pour %s", 
                                           purchase.id, cart_item.bundle.name)
                                
                                # Appliquer le contenu du bundle au joueur
                                minecraft_username = user.profile.minecraft_username
                                if minecraft_username:
                                    success = give_bundle_to_player(minecraft_username, cart_item.bundle)
                                    logger.info("Attribution du bundle %s pour %s: %s", 
                                               cart_item.bundle.name, minecraft_username, 
                                               "Succès" if success else "Échec")
                                else:
                                    logger.warning("Pas de nom d'utilisateur Minecraft pour l'utilisateur %s, bundle %s non appliqué", 
                                                 user.username, cart_item.bundle.name)
                                cart_item.delete()

                            else:
                                logger.warning("L'article du panier %s n'a ni grade ni article ni bundle", item_id)

                        except CartItem.DoesNotExist:
                            error_msg = f"CartItem {item_id} introuvable pour l'utilisateur {user_id}"
                            logger.error(error_msg)
                            WebhookError.objects.create(
                                event_type='checkout.session.completed',
                                session_id=session.get('id'),
                                error_message=error_msg
                            )
                        except Exception as e:
                            error_msg = f"Erreur lors du traitement de l'article du panier {item_id} : {str(e)}"
                            logger.error(error_msg)
                            WebhookError.objects.create(
                                event_type='checkout.session.completed',
                                session_id=session.get('id'),
                                error_message=error_msg
                            )
                            
                    # Enregistrer l'utilisation du code promo
                    promo_code = session.get('metadata', {}).get('promo_code')
                    if promo_code:
                        try:
                            promo_obj = PromoCode.objects.get(code=promo_code)
                            promo_discount = Decimal(session.get('metadata', {}).get('promo_discount', '0'))
                            original_total = Decimal(session.get('metadata', {}).get('original_total', '0'))
                            final_total = original_total - promo_discount
                            
                            # Créer l'enregistrement d'utilisation
                            PromoCodeUsage.objects.create(
                                promo_code=promo_obj,
                                user=user,
                                cart_total_before=original_total,
                                discount_applied=promo_discount,
                                cart_total_after=final_total,
                                payment_id=session.id,
                                ip_address=None
                            )
                            
                            # Incrémenter le compteur d'utilisations
                            promo_obj.uses_count = F('uses_count') + 1
                            promo_obj.save(update_fields=['uses_count'])
                            
                            logger.info(f"Code promo {promo_code} utilisé par {user.username}, réduction: €{promo_discount}")
                            
                        except Exception as e:
                            logger.error(f"Erreur lors de l'enregistrement de l'utilisation du code promo: {str(e)}")
                            
            except User.DoesNotExist:
                error_msg = f"Utilisateur {user_id} introuvable pour la session {session.get('id')}"
                logger.error(error_msg)
                WebhookError.objects.create(
                    event_type='checkout.session.completed',
                    session_id=session.get('id'),
                    error_message=error_msg
                )
            except Exception as e:
                error_msg = f"Erreur inattendue dans process_successful_payment pour la session {session.get('id')} : {str(e)}"
                logger.error(error_msg)
                WebhookError.objects.create(
                    event_type='checkout.session.completed',
                    session_id=session.get('id'),
                    error_message=error_msg
                )
        else:  # Single rank purchase (direct purchase, not from cart)
            user_id = session.get('metadata', {}).get('user_id')
            rank_id = session.get('metadata', {}).get('rank_id')
            
            if user_id and rank_id:
                try:
                    user = User.objects.get(id=user_id)
                    rank = Rank.objects.get(id=rank_id)
                    
                    purchase = UserPurchase.objects.create(
                        user=user,
                        rank=rank,
                        amount=rank.price,
                        payment_id=session.id,
                        payment_status='completed'
                    )
                    
                    minecraft_username = user.profile.minecraft_username
                    if minecraft_username:
                        # ✅ CORRECTION : Ajouter le paramètre gifted_by=None pour les achats normaux
                        success = apply_rank_to_player(
                            minecraft_username, 
                            rank.name, 
                            is_temporary=False, 
                            gifted_by=None
                        )
                        if success:
                            logger.info(f"Grade {rank.name} appliqué avec succès à {minecraft_username}")
                        else:
                            logger.error(f"Échec de l'application du grade {rank.name} à {minecraft_username}")
                    else:
                        logger.warning(f"L'utilisateur {user.username} n'a pas défini de nom d'utilisateur Minecraft ; grade non appliqué")
                    
                except Exception as e:
                    logger.error(f"Erreur lors du traitement du paiement d'un grade : {str(e)}")
def recalculate_promo_discount(request):
    """
    Recalcule la réduction du code promo en fonction du contenu actuel du panier
    """
    promo_info = request.session.get('applied_promo_code')
    if not promo_info:
        return None, Decimal('0.00')
    
    try:
        # Récupérer le code promo
        promo_code_obj = PromoCode.objects.get(code=promo_info['code'])
        
        # Vérifier que le code est toujours valide
        is_valid, _ = promo_code_obj.is_valid()
        can_use, _ = promo_code_obj.can_user_use(request.user)
        
        if not is_valid or not can_use:
            # Supprimer le code promo invalide
            del request.session['applied_promo_code']
            return None, Decimal('0.00')
        
        # Recalculer le total éligible actuel
        cart_items = CartItem.objects.filter(user=request.user)
        eligible_total = Decimal('0.00')
        
        for item in cart_items:
            if promo_code_obj.applies_to_cart_item(item):
                eligible_total += item.get_subtotal()
        
        # Vérifier le montant minimum
        if eligible_total < promo_code_obj.minimum_amount:
            # Supprimer le code promo car le minimum n'est plus atteint
            del request.session['applied_promo_code']
            return None, Decimal('0.00')
        
        # Recalculer la réduction
        new_discount = promo_code_obj.calculate_discount(eligible_total)
        
        # Mettre à jour la session avec le nouveau montant
        request.session['applied_promo_code'] = {
            'code': promo_info['code'],
            'discount_amount': str(new_discount),
            'eligible_total': str(eligible_total)
        }
        
        return promo_code_obj, new_discount
        
    except PromoCode.DoesNotExist:
        # Supprimer le code promo inexistant
        del request.session['applied_promo_code']
        return None, Decimal('0.00')
    except Exception as e:
        logger.error(f"Erreur lors du recalcul du code promo: {str(e)}")
        return None, Decimal('0.00')
                       
def process_failed_payment(session):
    # Log failed payment
    user_id = session.get('metadata', {}).get('user_id')
    rank_id = session.get('metadata', {}).get('rank_id')
    
    if user_id and rank_id:
        try:
            user = User.objects.get(id=user_id)
            rank = Rank.objects.get(id=rank_id)
            
            # Record the failed purchase for tracking
            UserPurchase.objects.create(
                user=user,
                rank=rank,
                amount=rank.price,
                payment_id=session.id,
                payment_status='failed'
            )
            
            logging.warning(f"Échec du paiement pour {rank.name} par {user.username}")
        except (User.DoesNotExist, Rank.DoesNotExist):
            logging.error(f"Utilisateur ou Grade introuvable pour le paiement échoué. ID utilisateur : {user_id}, ID grade : {rank_id}")
    else:
        logging.error("Métadonnées d'utilisateur ou de grade manquantes dans le paiement échoué")

def process_expired_session(session):
    # Log expired session
    user_id = session.get('metadata', {}).get('user_id')
    
    if user_id:
        try:
            user = User.objects.get(id=user_id)
            logging.info(f"Session de paiement expirée pour l'utilisateur {user.username}")
        except User.DoesNotExist:
            logging.error(f"Utilisateur avec l'ID {user_id} introuvable pour la session expirée")
    else:
        logging.error("Métadonnées d'utilisateur manquantes dans la session expirée")

def payment_cancel(request):
    messages.warning(request, "Votre paiement a été annulé. Aucun montant n'a été prélevé.")
    return render(request, 'minecraft_app/payment_cancel.html')

def payment_failed(request):
    messages.error(request, "Votre paiement n'a pas pu être traité. Veuillez réessayer ou utiliser une autre méthode de paiement.")
    return render(request, 'minecraft_app/payment_failed.html')


def send_discord_webhook(name, discord_username, minecraft_username, subject, message):
    webhook_url = settings.DISCORD_WEBHOOK_URL
    
    # Debug log
    logging.debug(f"Envoi au webhook Discord : {webhook_url}")
    
    data = {
        "embeds": [{
            "title": f"Nouveau message de contact : {subject}",
            "description": message,
            "color": 3447003,  # Discord blue
            "fields": [
                {"name": "De", "value": name, "inline": True},
                {"name": "Discord", "value": discord_username or "Non fourni", "inline": True},
                {"name": "Minecraft", "value": minecraft_username or "Non fourni", "inline": True}
            ],
            "footer": {"text": "Message envoyé depuis le formulaire de contact du site web"}
        }]
    }
    
    # Debug log of data being sent
    logging.debug(f"Données du webhook : {json.dumps(data)}")
    
    try:
        response = requests.post(webhook_url, json=data)
        
        # Debug log of response
        logging.debug(f"Réponse du webhook Discord : Statut {response.status_code}, Contenu : {response.text}")
        
        return response.status_code == 204 or response.status_code == 200
    except Exception as e:
        logging.error(f"Erreur lors de l'envoi au webhook Discord : {str(e)}")
        return False


def store(request):
    # Check if user is authenticated
    if not request.user.is_authenticated:
        return redirect('store_nok')
    
    # Get all ranks ordered by price, separate lifetime and monthly
    lifetime_ranks = Rank.objects.filter(duration_type='lifetime').order_by('price')
    monthly_ranks = Rank.objects.filter(duration_type='monthly').order_by('price')
    store_items = StoreItem.objects.all().order_by('category', 'price')
    
    # Get user's active subscriptions (monthly ranks)
    active_subscriptions = UserSubscription.objects.filter(
        user=request.user,
        status='active',
        current_period_end__gt=timezone.now()
    ).select_related('rank')
    
    # Get ALL purchased ranks (for ownership check)
    all_purchased_ranks = UserPurchase.objects.filter(
        user=request.user,
        payment_status='completed'
    ).select_related('rank')
    
    # Get the IDs of ranks the user owns
    owned_lifetime_rank_ids = [purchase.rank.id for purchase in all_purchased_ranks if purchase.rank and purchase.rank.duration_type == 'lifetime']
    active_subscription_rank_ids = [sub.rank.id for sub in active_subscriptions if sub.rank]
    
    # Calculate discount percentage for STORE ITEMS ONLY
    store_discount_percentage = get_player_discount(request.user)
    
    # Debug: log the discount percentage
    logger.info(f"User {request.user.username} has store discount: {store_discount_percentage}%")
    
    # Prepare lifetime ranks with UPGRADE pricing (not discount)
    available_lifetime_ranks = []
    for rank in lifetime_ranks:
        # Create a copy to avoid modifying the original object
        rank_copy = {
            'id': rank.id,
            'name': rank.name,
            'description': rank.description,
            'price': rank.price,
            'color_code': rank.color_code,
            'is_donation': rank.is_donation,
            'features': rank.features,
            'kit_image': rank.kit_image,
            'duration_type': rank.duration_type,
            'get_features_list': rank.get_features_list(),
            'owned': rank.id in owned_lifetime_rank_ids,
            'original_price': rank.price
        }
        
        if not rank_copy['owned']:
            # Calculate upgrade price (difference from highest owned rank)
            upgrade_price = get_rank_upgrade_price(request.user, rank)
            
            if upgrade_price < rank.price:
                # Show both original and upgrade price
                rank_copy['discounted_price'] = upgrade_price
                rank_copy['discount_percentage'] = round(((rank.price - upgrade_price) / rank.price) * 100, 1)
                rank_copy['is_upgrade'] = True
                logger.info(f"Rank {rank.name}: Original price €{rank.price}, Upgrade price €{upgrade_price}")
            else:
                # No upgrade discount
                rank_copy['discounted_price'] = None
                rank_copy['discount_percentage'] = 0
                rank_copy['is_upgrade'] = False
        else:
            rank_copy['discounted_price'] = None
            rank_copy['discount_percentage'] = 0
            rank_copy['is_upgrade'] = False
        
        available_lifetime_ranks.append(rank_copy)
    
    # Prepare monthly ranks (no discounts or upgrades)
    available_monthly_ranks = []
    for rank in monthly_ranks:
        rank_copy = {
            'id': rank.id,
            'name': rank.name,
            'description': rank.description,
            'price': rank.price,
            'color_code': rank.color_code,
            'is_donation': rank.is_donation,
            'features': rank.features,
            'kit_image': rank.kit_image,
            'duration_type': rank.duration_type,
            'get_features_list': rank.get_features_list(),
            'owned': rank.id in active_subscription_rank_ids,
            'original_price': rank.price,
            'discounted_price': None,
            'discount_percentage': 0,
            'is_upgrade': False
        }
        available_monthly_ranks.append(rank_copy)
    
    # Combine all ranks for display
    all_ranks = available_monthly_ranks + available_lifetime_ranks
    
    # Get cart data
    cart_items = CartItem.objects.filter(user=request.user)
    cart_count = cart_items.count()
    cart_total = sum(item.get_subtotal() for item in cart_items)
    
    # Apply discount to store items if applicable
    for item in store_items:
        item.original_price = item.price
        if store_discount_percentage > 0:
            discount_factor = Decimal(1 - store_discount_percentage / 100)
            item.discounted_price = round(item.price * discount_factor, 2)
            item.discount_percentage = store_discount_percentage
            logger.info(f"Store item {item.name}: Original price €{item.price}, Discounted price €{item.discounted_price}")
        else:
            item.discounted_price = None
            item.discount_percentage = 0
    
    # Récupérer les bundles actifs
    bundles = Bundle.objects.filter(is_active=True).order_by('price')
    
    # Calculer les informations des bundles avec réductions si applicable
    bundles_with_discount = []
    for bundle in bundles:
        # Créer un dictionnaire avec toutes les informations calculées
        bundle_data = {
            'id': bundle.id,
            'name': bundle.name,
            'description': bundle.description,
            'bundle_type': bundle.bundle_type,
            'price': bundle.price,
            'original_price': bundle.price,  # Prix original
            'total_value': bundle.total_value,  # Utiliser la property
            'savings': bundle.savings,  # Utiliser la property
            'savings_percentage': bundle.savings_percentage,  # Utiliser la property
            'is_active': bundle.is_active,
            'rank': bundle.rank,
            'items': bundle.items.all(),  # Pour les BundleItem
            'discount_percentage': bundle.discount_percentage,
            'color_code': bundle.color_code,  # ✅ NOUVEAU : Ajouter la couleur
        }
        
        # Appliquer la réduction sur les bundles si l'utilisateur a un grade
        if store_discount_percentage > 0:
            discount_factor = Decimal(1 - store_discount_percentage / 100)
            bundle_data['discounted_price'] = round(bundle.price * discount_factor, 2)
            bundle_data['user_discount_percentage'] = store_discount_percentage
        else:
            bundle_data['discounted_price'] = None
            bundle_data['user_discount_percentage'] = 0
        
        bundles_with_discount.append(bundle_data)
    
    context = {
        'ranks': all_ranks,
        'store_items': store_items,
        'cart_count': cart_count,
        'cart_total': cart_total,
        'show_new_ranks_notice': False,
        'user_has_any_rank': all_purchased_ranks.exists() or active_subscriptions.exists(),
        'discount_percentage': store_discount_percentage,  # For store items only
        'bundles': bundles_with_discount,  # Ajouter bundles au contexte avec couleurs
    }
    
    return render(request, 'minecraft_app/store.html', context)

@login_required
def add_to_cart(request):
    if request.method == 'POST':
        item_type = request.POST.get('item_type')
        item_id = request.POST.get('item_id')
        quantity = int(request.POST.get('quantity', 1))
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

        try:
            # Ensure quantity is within bounds
            max_available = 99
            if quantity < 1:
                quantity = 1
                error_msg = "La quantité doit être d'au moins 1."
                if is_ajax:
                    return JsonResponse({'success': False, 'error': error_msg})
                else:
                    messages.warning(request, error_msg)
            
            if quantity > max_available:
                quantity = max_available
                warn_msg = f"Quantité limitée à {max_available}."
                if is_ajax:
                    return JsonResponse({'success': False, 'error': warn_msg})
                else:
                    messages.warning(request, warn_msg)

            if item_type == 'rank':
                rank = Rank.objects.get(id=item_id)
                
                # Vérifier si l'utilisateur possède déjà ce rang
                existing_purchase = UserPurchase.objects.filter(
                    user=request.user,
                    rank=rank,
                    payment_status='completed'
                ).exists()
                
                if existing_purchase:
                    error_msg = "Vous possédez déjà ce rang."
                    if is_ajax:
                        return JsonResponse({'success': False, 'error': error_msg})
                    else:
                        messages.warning(request, error_msg)
                        return redirect('cart')
                
                # Vérifier si déjà dans le panier
                existing_cart_item = CartItem.objects.filter(
                    user=request.user,
                    rank=rank
                ).first()
                
                if existing_cart_item:
                    error_msg = "Ce rang est déjà dans votre panier."
                    if is_ajax:
                        return JsonResponse({'success': False, 'error': error_msg})
                    else:
                        messages.warning(request, error_msg)
                        return redirect('cart')
                
                # Calculer le prix d'upgrade
                metadata = {}
                success_msg = f"Rang {rank.name} ajouté au panier"
                
                if rank.duration_type == 'lifetime':
                    upgrade_price = get_rank_upgrade_price(request.user, rank)
                    
                    if upgrade_price < rank.price:
                        # C'est un upgrade - sauvegarder le prix d'upgrade
                        metadata = {
                            'upgrade_price': str(upgrade_price),
                            'original_price': str(rank.price),
                            'is_upgrade': True
                        }
                        success_msg += f" (Upgrade: €{upgrade_price} au lieu de €{rank.price})"
                    else:
                        # Prix normal
                        metadata = {
                            'original_price': str(rank.price),
                            'is_upgrade': False
                        }
                else:
                    # Rang mensuel - prix normal
                    metadata = {
                        'original_price': str(rank.price),
                        'is_upgrade': False
                    }
                
                # Créer l'item dans le panier
                cart_item = CartItem.objects.create(
                    user=request.user,
                    rank=rank,
                    quantity=1,  # Les rangs sont toujours en quantité 1
                    metadata=metadata
                )
                
                logger.debug("Grade %s ajouté au panier avec métadonnées : %s", rank.name, metadata)
                
            elif item_type == 'store_item':
                store_item = StoreItem.objects.get(id=item_id)
                
                # Create or update cart item for store item
                cart_item, created = CartItem.objects.get_or_create(
                    user=request.user,
                    store_item=store_item,
                    defaults={'quantity': quantity}
                )
                
                if not created:
                    # If the item already exists, update the quantity
                    cart_item.quantity += quantity
                    if cart_item.quantity > max_available:
                        cart_item.quantity = max_available
                    cart_item.save()
                    success_msg = f"Quantité de {store_item.name} mise à jour dans le panier"
                else:
                    success_msg = f"{store_item.name} ajouté au panier"
                
                logger.debug("Article %s ajouté au panier avec une quantité de %d", item_id, quantity)
                

            elif item_type == 'bundle':
                bundle = Bundle.objects.get(id=item_id, is_active=True)
                
                # Vérifier si déjà dans le panier
                existing_cart_item = CartItem.objects.filter(
                    user=request.user,
                    bundle=bundle
                ).first()
                
                if existing_cart_item:
                    error_msg = "Ce bundle est déjà dans votre panier."
                    if is_ajax:
                        return JsonResponse({'success': False, 'error': error_msg})
                    else:
                        messages.warning(request, error_msg)
                        return redirect('cart')
                
                # Créer l'item dans le panier
                cart_item = CartItem.objects.create(
                    user=request.user,
                    bundle=bundle,
                    quantity=1,  # Les bundles sont toujours en quantité 1
                    metadata={'bundle_type': bundle.bundle_type}
                )
                
                success_msg = f"Bundle {bundle.name} ajouté au panier"
                logger.debug("Bundle %s ajouté au panier", bundle.name)

            else:
                error_msg = "Type d'article invalide."
                if is_ajax:
                    return JsonResponse({'success': False, 'error': error_msg})
                else:
                    messages.error(request, error_msg)
                    return redirect('store')

            # Calculate cart totals
            cart_items = CartItem.objects.filter(user=request.user)
            cart_count = cart_items.count()
            cart_total = sum(item.get_subtotal() for item in cart_items)

            if is_ajax:
                return JsonResponse({
                    'success': True,
                    'message': success_msg,
                    'status': 'success',
                    'cart_count': cart_count,
                    'cart_total': f"{cart_total:.2f}",
                    'current_quantity': cart_item.quantity
                })
            else:
                messages.success(request, success_msg)
                return redirect('cart')

        except (StoreItem.DoesNotExist, Rank.DoesNotExist):
            error_msg = "Article introuvable."
            if is_ajax:
                return JsonResponse({'success': False, 'error': error_msg})
            else:
                messages.error(request, error_msg)
        except Exception as e:
            error_msg = f"Erreur lors de l'ajout de l'article au panier : {str(e)}"
            logger.error(error_msg)
            if is_ajax:
                return JsonResponse({'success': False, 'error': error_msg})
            else:
                messages.error(request, error_msg)
        except Bundle.DoesNotExist:
            error_msg = "Bundle introuvable."
            if is_ajax:
                return JsonResponse({'success': False, 'error': error_msg})
            else:
                messages.error(request, error_msg)

    return redirect('store')

# View cart page
@login_required
def view_cart(request):
    cart_items = CartItem.objects.filter(user=request.user)
    
    total = 0
    for item in cart_items:
        total += item.get_subtotal()
    
    # ✅ CORRECTION : Recalculer automatiquement le code promo
    promo_code_obj, discount_amount = recalculate_promo_discount(request)
    promo_info = request.session.get('applied_promo_code')
    final_total = total - discount_amount
    
    context = {
        'cart_items': cart_items,
        'total': total,
        'promo_info': promo_info,
        'discount_amount': discount_amount,
        'final_total': final_total,
        'server': TownyServer.objects.first(),
    }
    
    return render(request, 'minecraft_app/cart.html', context)

# Dans minecraft_app/views.py, remplacez la fonction remove_from_cart par ceci :

@login_required
def remove_from_cart(request, item_id):
    try:
        cart_item = CartItem.objects.get(id=item_id, user=request.user)
        
        if cart_item.rank:
            item_name = cart_item.rank.name
        elif cart_item.store_item:
            item_name = cart_item.store_item.name
        elif cart_item.bundle:
            item_name = cart_item.bundle.name
        else:
            item_name = "Article inconnu"
        
        cart_item.delete()
        
        # ✅ AJOUT : Recalculer le code promo après suppression
        recalculate_promo_discount(request)
        
        messages.success(request, f"'{item_name}' a été retiré de votre panier.")
        
    except CartItem.DoesNotExist:
        messages.error(request, "Article introuvable dans votre panier.")
    
    return redirect('cart')

# Update cart item quantity
@login_required
def update_cart_quantity(request):
    logger.debug("DEBUG: update_cart_quantity appelé avec les données POST : %s", request.POST)
    if request.method == 'POST':
        item_id = request.POST.get('item_id')
        quantity = int(request.POST.get('quantity', 1))
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        
        try:
            cart_item = CartItem.objects.get(id=item_id, user=request.user)
            
            # Only store items can have quantities (not ranks)
            if cart_item.store_item:
                max_available = 99
                
                if quantity > max_available:
                    quantity = max_available
                    if is_ajax:
                        return JsonResponse({
                            'success': False,
                            'error': f'La quantité maximale est de {max_available}.',
                            'current_quantity': cart_item.quantity
                        })
                    else:
                        messages.warning(request, f"Quantité ajustée au maximum disponible ({max_available}).")
                
                cart_item.quantity = quantity
                cart_item.save()
                cart_item.refresh_from_db()
                
                # ✅ AJOUT : Recalculer le code promo après modification de quantité
                promo_code_obj, discount_amount = recalculate_promo_discount(request)
                
                if is_ajax:
                    item_subtotal = cart_item.get_subtotal()
                    cart_total = sum(item.get_subtotal() for item in CartItem.objects.filter(user=request.user))
                    final_total = cart_total - discount_amount
                    
                    response_data = {
                        'success': True,
                        'item_subtotal': f"{item_subtotal:.2f}",
                        'cart_total': f"{cart_total:.2f}",
                        'current_quantity': cart_item.quantity,
                        'final_total': f"{final_total:.2f}",
                        'discount_amount': f"{discount_amount:.2f}"
                    }
                    
                    # Ajouter les infos du code promo si présent
                    promo_info = request.session.get('applied_promo_code')
                    if promo_info:
                        response_data['promo_code'] = promo_info['code']
                        response_data['promo_active'] = True
                    else:
                        response_data['promo_active'] = False
                    
                    return JsonResponse(response_data)
            else:
                if is_ajax:
                    return JsonResponse({
                        'success': False,
                        'error': 'Les grades ne peuvent pas avoir de quantité mise à jour'
                    })
                
        except CartItem.DoesNotExist:
            if is_ajax:
                return JsonResponse({'success': False, 'error': 'Article introuvable'})
            else:
                messages.error(request, "Article introuvable dans votre panier.")
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour du panier : %s", str(e))
            if is_ajax:
                return JsonResponse({'success': False, 'error': str(e)})
            else:
                messages.error(request, f"Erreur lors de la mise à jour du panier : {str(e)}")
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': False, 'error': 'Requête invalide'})
    
    return redirect('cart')

@login_required
def checkout_cart(request):
    cart_items = CartItem.objects.filter(user=request.user)
    
    if not cart_items.exists():
        messages.error(request, "Votre panier est vide.")
        return redirect('cart')
    
    # Calculate total
    total_amount = 0
    items_description = []
    
    for item in cart_items:
        subtotal = item.get_subtotal()
        total_amount += subtotal
        
        if item.rank:
            items_description.append(f"Grade : {item.rank.name}")
        elif item.store_item:
            items_description.append(f"{item.store_item.name} x{item.quantity}")
        elif item.bundle:
            bundle_desc = f"Bundle : {item.bundle.name}"
            if item.bundle.description and item.bundle.description.strip():
                bundle_desc += f" - {item.bundle.description[:50]}"
            items_description.append(bundle_desc)
        else:
            items_description.append("Article boutique")
    
    # ✅ CORRECTION : Utiliser la fonction de recalcul pour le code promo
    promo_code_obj, discount_amount = recalculate_promo_discount(request)
    promo_info = request.session.get('applied_promo_code')
    
    if promo_info and discount_amount > 0:
        total_amount = max(total_amount - discount_amount, Decimal('0.00'))
        items_description.append(f"Code promo: {promo_info['code']} (-€{discount_amount})")
    
    # Create Stripe session
    try:
        # Déterminer les méthodes de paiement en fonction du choix de l'utilisateur
        is_qr_code = request.GET.get('qr_code') == 'true'
        
        # Configuration commune pour tous les types de sessions
        metadata = {
            'user_id': request.user.id,
            'username': request.user.username,
            'cart_items': ",".join([str(item.id) for item in cart_items]),
        }
        
        # ✅ CORRECTION : Ajouter les informations du code promo recalculées aux métadonnées
        if promo_code_obj and discount_amount > 0:
            metadata.update({
                'promo_code': promo_code_obj.code,
                'promo_discount': str(discount_amount),
                'original_total': str(total_amount + discount_amount)
            })
        
        session_params = {
            'line_items': [
                {
                    'price_data': {
                        'currency': 'eur',
                        'unit_amount': int(total_amount * 100),
                        'product_data': {
                            'name': "Achat sur la boutique Novania",
                            'description': ", ".join(items_description) if items_description else "Achat boutique Novania",
                        },
                    },
                    'quantity': 1,
                }
            ],
            'metadata': metadata,
            'mode': 'payment',
            'success_url': request.build_absolute_uri(reverse('payment_success') + f'?session_id={{CHECKOUT_SESSION_ID}}'),
            'cancel_url': request.build_absolute_uri(reverse('payment_cancel')),
        }
        
        # Ajouter des paramètres spécifiques en fonction du mode de paiement
        if is_qr_code:
            session_params.update({
                'payment_method_types': ['bancontact']
            })
        else:
            session_params.update({
                'payment_method_types': ['card', 'paypal'],
                'payment_method_options': {
                    'card': {
                        'request_three_d_secure': 'any',
                    }
                }
            })
        
        # Créer la session avec tous les paramètres
        checkout_session = stripe.checkout.Session.create(**session_params)
        
        # Si c'est un paiement par QR code
        if is_qr_code:
            return render(request, 'minecraft_app/payment_qr.html', {
                'session_id': checkout_session.id,
                'qr_code_url': reverse('payment_qr_code', args=[checkout_session.id]),
                'checkout_url': checkout_session.url,
                'payment_method': 'Bancontact',
                'server': TownyServer.objects.first(),
            })
        else:
            return redirect(checkout_session.url, code=303)
            
    except stripe.error.StripeError as e:
        logging.error(f"Stripe error: {str(e)}")
        error_message = f"Erreur de paiement: {e.user_message if hasattr(e, 'user_message') else str(e)}"
        messages.error(request, error_message)
        return redirect('cart')
    except Exception as e:
        logging.error(f"Erreur lors de la création de la session de paiement: {str(e)}")
        messages.error(request, f"Erreur lors de la création du paiement: {str(e)}")
        return redirect('cart')


def legal_notices(request):
    """Vue pour afficher les mentions légales"""
    server = TownyServer.objects.first()
    
    context = {
        'server': server,
    }
    
    return render(request, 'minecraft_app/legal_notices.html', context)

def terms_of_service(request):
    """Vue pour afficher les conditions d'utilisation"""
    server = TownyServer.objects.first()
    
    context = {
        'server': server,
    }
    
    return render(request, 'minecraft_app/terms_of_service.html', context)

def is_minecraft_username_unique(username, current_user=None):
    """
    Vérifie si un pseudo Minecraft est unique dans la base de données
    Exclut l'utilisateur actuel si fourni (pour la mise à jour du profil)
    """
    if not username:
        return True
    
    existing_profiles = UserProfile.objects.filter(minecraft_username=username)
    if current_user:
        existing_profiles = existing_profiles.exclude(user=current_user)
    
    return not existing_profiles.exists()

@login_required
def payment_qr_code(request, session_id):
    try:
        # Récupérer la session Stripe
        checkout_session = stripe.checkout.Session.retrieve(session_id)
        
        # Générer le QR code pour l'URL de la session
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(checkout_session.url)
        qr.make(fit=True)
        
        # Créer une image SVG du QR code
        img = qr.make_image(fill_color="black", back_color="white", image_factory=qrcode.image.svg.SvgImage)
        
        # Convertir l'image en bytes pour la réponse HTTP
        output = BytesIO()
        img.save(output)
        output.seek(0)
        
        # Retourner l'image SVG
        return HttpResponse(output.read(), content_type='image/svg+xml')
    except Exception as e:
        logger.error(f"Erreur lors de la génération du QR code : {str(e)}")
        return HttpResponse(status=404)

def store_nok(request):
    """
    Page d'accès requis pour la boutique - pour les utilisateurs non connectés
    """
    if request.user.is_authenticated:
        return redirect('store')
    
    server = TownyServer.objects.first()
    
    context = {
        'server': server,
    }
    
    return render(request, 'minecraft_app/store_nok.html', context)

def rcon_health_check(request):
    """API endpoint pour vérifier la santé RCON"""
    from .minecraft_service import test_rcon_connection
    
    try:
        is_healthy = test_rcon_connection()
        return JsonResponse({
            'rcon_healthy': is_healthy,
            'timestamp': timezone.now().isoformat()
        })
    except Exception as e:
        return JsonResponse({
            'rcon_healthy': False,
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }, status=500)
    
def get_client_ip(request):
    """Récupère l'IP du client"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

@login_required
def apply_promo_code(request):
    """AJAX endpoint pour appliquer un code promo"""
    if request.method == 'POST':
        promo_code = request.POST.get('promo_code', '').strip().upper()
        
        if not promo_code:
            return JsonResponse({
                'success': False,
                'error': 'Veuillez entrer un code promo'
            })
        
        try:
            # Récupérer le code promo
            code_obj = PromoCode.objects.get(code=promo_code)
            
            # Vérifier la validité du code
            is_valid, message = code_obj.is_valid()
            if not is_valid:
                return JsonResponse({
                    'success': False,
                    'error': message
                })
            
            # Vérifier si l'utilisateur peut utiliser ce code
            can_use, user_message = code_obj.can_user_use(request.user)
            if not can_use:
                return JsonResponse({
                    'success': False,
                    'error': user_message
                })
            
            # Récupérer les articles du panier
            cart_items = CartItem.objects.filter(user=request.user)
            if not cart_items.exists():
                return JsonResponse({
                    'success': False,
                    'error': 'Votre panier est vide'
                })
            
            # Calculer le total éligible
            eligible_total = Decimal('0.00')
            for item in cart_items:
                if code_obj.applies_to_cart_item(item):
                    eligible_total += item.get_subtotal()
            
            if eligible_total == 0:
                return JsonResponse({
                    'success': False,
                    'error': 'Ce code promo ne s\'applique à aucun article de votre panier'
                })
            
            # Vérifier le montant minimum
            if eligible_total < code_obj.minimum_amount:
                return JsonResponse({
                    'success': False,
                    'error': f'Montant minimum requis: €{code_obj.minimum_amount}'
                })
            
            # Calculer la réduction
            discount_amount = code_obj.calculate_discount(eligible_total)
            new_total = eligible_total - discount_amount
            
            # Stocker le code promo dans la session
            request.session['applied_promo_code'] = {
                'code': promo_code,
                'discount_amount': str(discount_amount),
                'eligible_total': str(eligible_total)
            }
            
            return JsonResponse({
                'success': True,
                'message': f'Code promo appliqué: -{code_obj.get_discount_display()}',
                'discount_amount': f"{discount_amount:.2f}",
                'new_total': f"{new_total:.2f}",
                'promo_code': promo_code
            })
            
        except PromoCode.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Code promo invalide'
            })
        except Exception as e:
            logger.error(f"Erreur lors de l'application du code promo: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Erreur lors de l\'application du code promo'
            })
    
    return JsonResponse({'success': False, 'error': 'Méthode non autorisée'})

@login_required
def remove_promo_code(request):
    """AJAX endpoint pour supprimer un code promo"""
    if request.method == 'POST':
        # Supprimer le code promo de la session
        if 'applied_promo_code' in request.session:
            del request.session['applied_promo_code']
        
        # Recalculer le total
        cart_items = CartItem.objects.filter(user=request.user)
        cart_total = sum(item.get_subtotal() for item in cart_items)
        
        return JsonResponse({
            'success': True,
            'message': 'Code promo supprimé',
            'new_total': f"{cart_total:.2f}"
        })
    
    return JsonResponse({'success': False, 'error': 'Méthode non autorisée'})

# Modifiez également la vue view_cart pour inclure les informations de code promo
@login_required
def view_cart(request):
    cart_items = CartItem.objects.filter(user=request.user)
    
    total = 0
    for item in cart_items:
        total += item.get_subtotal()
    
    # Gestion du code promo
    promo_info = request.session.get('applied_promo_code')
    discount_amount = Decimal('0.00')
    final_total = total
    
    if promo_info:
        try:
            discount_amount = Decimal(promo_info['discount_amount'])
            final_total = total - discount_amount
        except (KeyError, ValueError, TypeError):
            # Supprimer le code promo invalide de la session
            if 'applied_promo_code' in request.session:
                del request.session['applied_promo_code']
            promo_info = None
    
    context = {
        'cart_items': cart_items,
        'total': total,
        'promo_info': promo_info,
        'discount_amount': discount_amount,
        'final_total': final_total,
        'server': TownyServer.objects.first(),
    }
    
    return render(request, 'minecraft_app/cart.html', context)

def process_subscription_updated(subscription):
    """Traite les mises à jour de subscription (annulations, renouvellements, etc.)"""
    stripe_subscription_id = subscription['id']
    status = subscription['status']
    
    try:
        user_subscription = UserSubscription.objects.get(stripe_subscription_id=stripe_subscription_id)
        
        # Mettre à jour le statut
        if status in ['canceled', 'unpaid', 'past_due']:
            user_subscription.status = 'cancelled'
            user_subscription.cancelled_at = timezone.now()
            
            # Marquer pour retrait immédiat si c'est une annulation
            if status == 'canceled':
                logger.info(f"Subscription {stripe_subscription_id} annulée, grade sera retiré lors du prochain nettoyage")
        
        elif status == 'active':
            user_subscription.status = 'active'
            # Mettre à jour les dates de période
            user_subscription.current_period_start = timezone.datetime.fromtimestamp(
                subscription['current_period_start'], tz=timezone.utc
            )
            user_subscription.current_period_end = timezone.datetime.fromtimestamp(
                subscription['current_period_end'], tz=timezone.utc
            )
        
        user_subscription.save()
        logger.info(f"Subscription {stripe_subscription_id} mise à jour : statut {status}")
        
    except UserSubscription.DoesNotExist:
        logger.error(f"UserSubscription avec Stripe ID {stripe_subscription_id} introuvable")

def process_subscription_cancelled(subscription):
    """Traite l'annulation définitive d'une subscription"""
    stripe_subscription_id = subscription['id']
    
    try:
        user_subscription = UserSubscription.objects.get(stripe_subscription_id=stripe_subscription_id)
        user_subscription.status = 'cancelled'
        user_subscription.cancelled_at = timezone.now()
        user_subscription.save()
        
        # Optionnel : Retirer le grade immédiatement
        user = user_subscription.user
        rank = user_subscription.rank
        
        try:
            minecraft_username = user.profile.minecraft_username or user.username
            from .minecraft_service import remove_rank_from_player
            success = remove_rank_from_player(minecraft_username, rank.name)
            
            if success:
                logger.info(f"Grade mensuel {rank.name} retiré immédiatement suite à l'annulation de {user.username}")
            else:
                logger.warning(f"Échec du retrait immédiat du grade {rank.name} pour {user.username}")
        except Exception as e:
            logger.error(f"Erreur lors du retrait immédiat du grade: {str(e)}")
        
        logger.info(f"Subscription {stripe_subscription_id} annulée définitivement")
        
    except UserSubscription.DoesNotExist:
        logger.error(f"UserSubscription avec Stripe ID {stripe_subscription_id} introuvable")

def process_failed_subscription_payment(invoice):
    """Traite les échecs de paiement de subscription"""
    subscription_id = invoice.get('subscription')
    
    if not subscription_id:
        return
    
    try:
        user_subscription = UserSubscription.objects.get(stripe_subscription_id=subscription_id)
        
        # Marquer comme en échec de paiement
        user_subscription.status = 'past_due'
        user_subscription.save()
        
        # Optionnel : Notifier le joueur en jeu
        user = user_subscription.user
        rank = user_subscription.rank
        
        try:
            minecraft_username = user.profile.minecraft_username or user.username
            
            with rcon_connection() as rcon:
                payment_failed_msg = f'tellraw {minecraft_username} ["",{{"text":"⚠️ ÉCHEC DE PAIEMENT ⚠️","color":"red","bold":true}},{{"text":"\\n"}},{{"text":"Votre grade mensuel {rank.name}","color":"yellow"}},{{"text":"\\n"}},{{"text":"risque d\'être suspendu.","color":"orange"}},{{"text":"\\n"}},{{"text":"Vérifiez votre méthode de paiement !","color":"red"}},{{"text":"\\n\\n"}},{{"text":"💳 Mettez à jour sur notre site 💳","color":"aqua","bold":true}}]'
                rcon.command(payment_failed_msg)
                
                logger.info(f"Notification d'échec de paiement envoyée à {minecraft_username}")
                
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi de la notification d'échec de paiement: {str(e)}")
        
        logger.info(f"Échec de paiement traité pour la subscription {subscription_id}")
        
    except UserSubscription.DoesNotExist:
        logger.error(f"UserSubscription avec Stripe ID {subscription_id} introuvable")