from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
import logging
from decimal import Decimal
import random
import string

class TownyServer(models.Model):
    name = models.CharField(max_length=100, default="Novania - Earth Towny")
    ip_address = models.CharField(max_length=100, default="play.Novania.fr")
    description = models.TextField(default="Towny server on a 1:1000 scale Earth map")
    version = models.CharField(max_length=20, default="1.21.4+")
    player_count = models.IntegerField(default=0)
    max_players = models.IntegerField(default=100)
    status = models.BooleanField(default=True)  # True = online, False = offline
    discord_link = models.CharField(max_length=100, blank=True, null=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name_plural = "Towny Server"

class Nation(models.Model):
    name = models.CharField(max_length=100)
    leader = models.CharField(max_length=100)
    founded_date = models.DateField()
    description = models.TextField(blank=True)
    capital = models.CharField(max_length=100)
    flag_image = models.CharField(max_length=255, blank=True, null=True, help_text="URL of the flag image")
    real_world_country = models.CharField(max_length=100, blank=True, help_text="Real world country represented")
    
    def __str__(self):
        return self.name

class Town(models.Model):
    name = models.CharField(max_length=100)
    mayor = models.CharField(max_length=100)
    nation = models.ForeignKey(Nation, on_delete=models.SET_NULL, null=True, blank=True, related_name='towns')
    founded_date = models.DateField()
    description = models.TextField(blank=True)
    residents_count = models.IntegerField(default=1)
    location_x = models.IntegerField(help_text="X coordinate on the map")
    location_z = models.IntegerField(help_text="Z coordinate on the map")
    real_world_location = models.CharField(max_length=100, blank=True, help_text="Real world location represented")
    
    def __str__(self):
        return self.name

class StaffMember(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Administrator'),
        ('mod', 'Moderator'),
        ('helper', 'Helper'),
        ('builder', 'Builder'),
    ]
    
    name = models.CharField(max_length=100)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    minecraft_uuid = models.CharField(max_length=36, blank=True, null=True)
    description = models.TextField(blank=True)
    discord_username = models.CharField(max_length=100, blank=True)
    
    def __str__(self):
        return f"{self.name} ({self.get_role_display()})"

class Rank(models.Model):
    DURATION_CHOICES = [
        ('lifetime', 'À vie'),
        ('monthly', 'Mensuel'),
    ]
    
    name = models.CharField(max_length=100)
    description = models.TextField()
    price = models.DecimalField(max_digits=6, decimal_places=2)
    color_code = models.CharField(max_length=7, help_text="HEX color code (e.g.: #FF0000)")
    is_donation = models.BooleanField(default=True)
    features = models.TextField(blank=True, help_text="Enter features, one per line. These will be displayed as bullet points.")
    kit_image = models.CharField(max_length=255, blank=True, null=True, help_text="Path to the kit image in static/images folder (e.g.: ranks/vip_kit.png)")
    
    # Nouveaux champs pour gérer la durée
    duration_type = models.CharField(max_length=10, choices=DURATION_CHOICES, default='lifetime', help_text="Type de durée du grade")
    exclude_from_discounts = models.BooleanField(default=False, help_text="Exclure ce grade des réductions basées sur d'autres grades")
    
    def __str__(self):
        duration_suffix = " (Mensuel)" if self.duration_type == 'monthly' else ""
        return f"{self.name}{duration_suffix}"
    
    def get_features_list(self):
        """Return features as a list, separated by newlines"""
        if self.features:
            return [feature.strip() for feature in self.features.split('\n') if feature.strip()]
        return []
    
    def get_display_duration(self):
        """Return human readable duration"""
        if self.duration_type == 'monthly':
            return '/mois'
        return '/à vie'

class ServerRule(models.Model):
    title = models.CharField(max_length=100)
    description = models.TextField()
    order = models.IntegerField(default=0)
    
    def __str__(self):
        return self.title
    
    class Meta:
        ordering = ['order']

class DynamicMapPoint(models.Model):
    POINT_TYPE_CHOICES = [
        ('town', 'Town'),
        ('capital', 'Capital'),
        ('warp', 'Teleport Point'),
        ('shop', 'Shop'),
        ('pve', 'PvE Zone'),
        ('pvp', 'PvP Zone'),
    ]
    
    name = models.CharField(max_length=100)
    point_type = models.CharField(max_length=20, choices=POINT_TYPE_CHOICES)
    location_x = models.IntegerField(help_text="X coordinate on the map")
    location_z = models.IntegerField(help_text="Z coordinate on the map")
    description = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.name} ({self.get_point_type_display()})"
    
    # Ajoutez ceci à la fin de minecraft_app/models.py

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    minecraft_username = models.CharField(max_length=100, blank=True)
    minecraft_uuid = models.CharField(max_length=36, blank=True)
    bio = models.TextField(blank=True)
    discord_username = models.CharField(max_length=100, blank=True)
    
    def __str__(self):
        return f"Profil de {self.user.username}"
    
    def get_avatar_url(self):
        if self.minecraft_uuid:
            return f"https://mc-heads.net/avatar/{self.minecraft_uuid}/100"
        elif self.minecraft_username:
            return f"https://mc-heads.net/avatar/{self.minecraft_username}/100"
        else:
            return "https://mc-heads.net/avatar/MHF_Steve/100"  # Avatar par défaut
        
class UserPurchase(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='purchases')
    rank = models.ForeignKey(Rank, on_delete=models.SET_NULL, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    payment_id = models.CharField(max_length=100, unique=True)
    payment_status = models.CharField(max_length=20, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    is_gift = models.BooleanField(default=False)
    gifted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='gifts_given')
    
    def __str__(self):
        if self.is_gift and self.gifted_by:
            return f"{self.user.username} - {self.rank.name if self.rank else 'Rank supprimé'} (Gift from {self.gifted_by.username})"
        return f"{self.user.username} - {self.rank.name if self.rank else 'Rank supprimé'}"
    
# Dans minecraft_app/models.py - Modifiez la classe StoreItem

class StoreItem(models.Model):
    CATEGORY_CHOICES = [
        ('collectible', 'Collectible'),
        ('cosmetic', 'Cosmetic'),
        ('utility', 'Utility'),
        ('special', 'Special'),
        ('companion', 'Compagnon'),  # ✅ NOUVEAU : Catégorie pour les pets
    ]
    
    name = models.CharField(max_length=100)
    description = models.TextField()
    price = models.DecimalField(max_digits=6, decimal_places=2)
    image = models.CharField(max_length=255, help_text="URL of the item image", blank=True, null=True)
    color_code = models.CharField(max_length=7, help_text="HEX color code (e.g.: #FF0000)")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='collectible')
    quantity = models.IntegerField(default=1, help_text="Available quantity (-1 for unlimited)")
    
    # ✅ NOUVEAU : Champ spécifique pour les pets
    pet_permission = models.CharField(
        max_length=100, 
        blank=True, 
        null=True,
        help_text="Pour les compagnons: nom du pet (ex: dragon, chat, loup). La permission sera automatiquement: advancedpets.pet.<nom>"
    )
    
    def __str__(self):
        return self.name
    
    def get_pet_permission(self):
        """Retourne la permission complète pour les pets"""
        if self.category == 'companion' and self.pet_permission:
            return f"advancedpets.pet.{self.pet_permission.lower()}"
        return None

class Bundle(models.Model):
    BUNDLE_TYPES = [
        ('rank_items', 'Rang + Objets'),
        ('items_only', 'Objets seulement'),
    ]
    
    name = models.CharField(max_length=100)
    description = models.TextField()
    bundle_type = models.CharField(max_length=20, choices=BUNDLE_TYPES)
    
    # Relations
    rank = models.ForeignKey(Rank, on_delete=models.CASCADE, null=True, blank=True)
    
    # Prix et réductions
    price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_percentage = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    # ✅ NOUVEAU : Champ couleur
    color_code = models.CharField(
        max_length=7, 
        help_text="Code couleur HEX (ex: #FF0000)",
        default="#4CAF50"  # Vert par défaut
    )
    
    # Métadonnées
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    @property
    def total_value(self):
        """Valeur totale si achetés séparément"""
        total = Decimal('0.00')
        
        if self.rank:
            total += self.rank.price
        
        for bundle_item in self.items.all():
            total += bundle_item.store_item.price * bundle_item.quantity
        
        return total
    
    @property
    def savings(self):
        """Montant économisé"""
        return self.total_value - self.price
    
    @property
    def savings_percentage(self):
        """Pourcentage d'économie"""
        if self.total_value > 0:
            return round((self.savings / self.total_value) * 100, 1)
        return 0
    
    def get_total_value(self):
        """Alias pour la compatibilité template"""
        return self.total_value
    
    def get_savings(self):
        """Alias pour la compatibilité template"""
        return self.savings
    
    def get_savings_percentage(self):
        """Alias pour la compatibilité template"""
        return self.savings_percentage
    
    @property
    def discounted_price(self):
        """Prix avec réduction membre appliquée"""
        if self.discount_percentage > 0:
            reduction = self.price * (Decimal(self.discount_percentage) / 100)
            return self.price - reduction
        return None
    
    @property
    def original_price(self):
        """Prix original (sans réduction membre)"""
        return self.price
    
    def get_bundle_items(self):
        """
        Retourne la liste des objets du bundle avec leurs quantités
        """
        items = []
        
        # Ajouter le rang s'il y en a un
        if self.rank:
            items.append({
                'type': 'rank',
                'name': self.rank.name,
                'quantity': 1
            })
        
        # Ajouter tous les objets du bundle
        for bundle_item in self.items.all():
            items.append({
                'type': 'store_item',
                'name': bundle_item.store_item.name,
                'quantity': bundle_item.quantity
            })
        
        return items


# AJOUTEZ ce nouveau modèle APRÈS Bundle :
class BundleItem(models.Model):
    bundle = models.ForeignKey(Bundle, on_delete=models.CASCADE, related_name='items')
    store_item = models.ForeignKey(StoreItem, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    
    class Meta:
        unique_together = ['bundle', 'store_item']
    
    def __str__(self):
        return f"{self.bundle.name} - {self.store_item.name} x{self.quantity}"

class BundlePurchase(models.Model):
    """Modèle pour enregistrer les achats de bundles"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bundle_purchases')
    bundle = models.ForeignKey(Bundle, on_delete=models.SET_NULL, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_id = models.CharField(max_length=100)
    payment_status = models.CharField(max_length=20, default='completed')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.bundle.name if self.bundle else 'Bundle supprimé'}"
    
class CartItem(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cart_items')
    rank = models.ForeignKey(Rank, on_delete=models.SET_NULL, null=True, blank=True)
    store_item = models.ForeignKey(StoreItem, on_delete=models.SET_NULL, null=True, blank=True)
    bundle = models.ForeignKey(Bundle, on_delete=models.SET_NULL, null=True, blank=True)
    quantity = models.IntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    # NOUVEAUX CHAMPS POUR LES CADEAUX
    is_gift = models.BooleanField(default=False)
    gift_recipient_username = models.CharField(max_length=100, blank=True, null=True)
    gift_recipient_user = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='gifts_received_in_cart'
    )
    
    class Meta:
        unique_together = [
            ('user', 'rank'),
            ('user', 'store_item'),
            ('user', 'bundle'),
        ]

    
    def __str__(self):
        if self.rank:
            if self.is_gift:
                return f"{self.user.username} - CADEAU: {self.rank.name} pour {self.gift_recipient_username}"
            return f"{self.user.username} - {self.rank.name}"
        elif self.store_item:
            return f"{self.user.username} - {self.store_item.name} (x{self.quantity})"
        elif self.bundle:
            return f"{self.user.username} - {self.bundle.name}"
        return f"{self.user.username} - Unknown item"
    
    # Dans minecraft_app/models.py, remplacez la méthode get_subtotal() de CartItem par ceci :

    def get_subtotal(self):
        if self.rank:
            # Pour les cadeaux, utiliser le prix d'upgrade stocké dans metadata
            if self.is_gift and self.metadata and 'upgrade_price' in self.metadata:
                return Decimal(self.metadata['upgrade_price'])
            # Code existant pour les ranks normaux
            elif self.metadata and 'upgrade_price' in self.metadata:
                return Decimal(self.metadata['upgrade_price'])
            elif self.metadata and 'discounted_price' in self.metadata:
                return Decimal(self.metadata['discounted_price'])
            return self.rank.price
            
        elif self.store_item:
            # Code existant pour les store items
            discount_percentage = get_player_discount(self.user)
            item_price = self.store_item.price
            if discount_percentage > 0:
                discount_factor = Decimal(1 - discount_percentage / 100)
                item_price = round(item_price * discount_factor, 2)
            return item_price * self.quantity
            
        elif self.bundle:
            # Code existant pour les bundles
            discount_percentage = get_player_discount(self.user)
            bundle_price = self.bundle.price
            if discount_percentage > 0:
                discount_factor = Decimal(1 - discount_percentage / 100)
                bundle_price = round(bundle_price * discount_factor, 2)
            return bundle_price * self.quantity
            
        return Decimal('0.00')

    def get_item_name(self):
        """Retourne le nom de l'article"""
        if self.rank:
            return self.rank.name
        elif self.store_item:
            return self.store_item.name
        elif self.bundle:
            return self.bundle.name
        return "Article inconnu"
    
    def get_item_type(self):
        """Retourne le type d'article"""
        if self.rank:
            return "rank"
        elif self.store_item:
            return "store_item"
        elif self.bundle:
            return "bundle"
        return "unknown"
    
    def save(self, *args, **kwargs):
        logger = logging.getLogger(__name__)
        logger.debug("DEBUG: Saving CartItem %s: quantity=%s", self.id, self.quantity)
        super().save(*args, **kwargs)
        logger.debug("DEBUG: Saved CartItem %s: quantity=%s", self.id, self.quantity)
    

class StoreItemPurchase(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='store_item_purchases')
    store_item = models.ForeignKey(StoreItem, on_delete=models.SET_NULL, null=True)
    quantity = models.IntegerField(default=1)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_id = models.CharField(max_length=100)
    payment_status = models.CharField(max_length=20, default='completed')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.store_item.name if self.store_item else 'Deleted item'} x{self.quantity}"

class WebhookError(models.Model):
    event_type = models.CharField(max_length=100)
    session_id = models.CharField(max_length=100)
    error_message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.event_type} - {self.session_id} - {self.error_message[:50]}"
    


def get_player_discount(user):
    """
    Returns the discount percentage a player should receive based on their highest rank
    This applies ONLY to store items (treasures), NOT to rank upgrades
    Excludes ranks that have exclude_from_discounts=True
    """
    if not user or not user.is_authenticated:
        return 0
    
    # Get user's purchased ranks (lifetime only for discounts)
    purchased_ranks = UserPurchase.objects.filter(
        user=user,
        payment_status='completed',
        rank__duration_type='lifetime',  # Only lifetime ranks count for discounts
        rank__exclude_from_discounts=False  # Exclude ranks that shouldn't give discounts
    ).select_related('rank')
    
    if not purchased_ranks.exists():
        return 0
    
    # Get names of all purchased ranks (normalize to lowercase for comparison)
    rank_names = [purchase.rank.name.lower() for purchase in purchased_ranks if purchase.rank]
    
    # Define discount tiers with exact names from your database
    # Ces réductions s'appliquent UNIQUEMENT aux trésors exclusifs
    discount_mapping = {
        'divinité': 20,   # 20% discount pour Divinité
        'titan': 15,      # 15% discount pour Titan
        'champion': 10,   # 10% discount pour Champion
        'héros': 5,       # 5% discount pour Héros
    }
    
    # Find the highest discount the user is eligible for
    max_discount = 0
    for rank_name in rank_names:
        if rank_name in discount_mapping:
            max_discount = max(max_discount, discount_mapping[rank_name])
    
    return max_discount
    

class UserSubscription(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('cancelled', 'Annulée'),
        ('expired', 'Expirée'),
        ('pending', 'En attente'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='subscriptions')
    rank = models.ForeignKey(Rank, on_delete=models.CASCADE, limit_choices_to={'duration_type': 'monthly'})
    stripe_subscription_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    current_period_start = models.DateTimeField()
    current_period_end = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.rank.name} ({self.status})"
    
    def is_active(self):
        return self.status == 'active' and self.current_period_end > timezone.now()
    
    class Meta:
        unique_together = ['user', 'rank']

def get_rank_upgrade_price(user, target_rank):
    """
    Calculate the price for upgrading to a target rank
    Users only pay the difference between their highest rank and the target rank
    """
    if not user or not user.is_authenticated:
        return target_rank.price
    
    # Get user's highest purchased rank (lifetime only)
    purchased_ranks = UserPurchase.objects.filter(
        user=user,
        payment_status='completed',
        rank__duration_type='lifetime'
    ).select_related('rank')
    
    if not purchased_ranks.exists():
        return target_rank.price
    
    # Find the highest rank by price
    highest_owned_rank = max(
        [purchase.rank for purchase in purchased_ranks if purchase.rank],
        key=lambda rank: rank.price,
        default=None
    )
    
    if not highest_owned_rank:
        return target_rank.price
    
    # If user already has this rank or a higher rank, return 0
    if highest_owned_rank.price >= target_rank.price:
        return 0
    
    # Return the difference
    return target_rank.price - highest_owned_rank.price


class PromoCode(models.Model):
    DISCOUNT_TYPE_CHOICES = [
        ('fixed', 'Montant fixe (€)'),
        ('percentage', 'Pourcentage (%)'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Actif'),
        ('inactive', 'Inactif'),
        ('expired', 'Expiré'),
    ]
    
    code = models.CharField(max_length=50, unique=True, help_text="Code promo unique (ex: NOEL2024)")
    description = models.TextField(blank=True, help_text="Description du code promo")
    
    # Type et valeur de réduction
    discount_type = models.CharField(max_length=10, choices=DISCOUNT_TYPE_CHOICES, default='fixed')
    discount_value = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0.01)])
    
    # Limites d'utilisation
    max_uses = models.PositiveIntegerField(default=1, help_text="Nombre maximum d'utilisations (-1 pour illimité)")
    uses_count = models.PositiveIntegerField(default=0, help_text="Nombre d'utilisations actuelles")
    max_uses_per_user = models.PositiveIntegerField(default=1, help_text="Maximum par utilisateur")
    
    # Conditions d'application
    minimum_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Montant minimum du panier")
    maximum_discount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Réduction maximum (pour les %)")
    
    # Validité temporelle
    valid_from = models.DateTimeField(default=timezone.now)
    valid_until = models.DateTimeField(null=True, blank=True, help_text="Laissez vide pour pas d'expiration")
    
    # Restrictions
    applies_to_ranks = models.BooleanField(default=True, help_text="S'applique aux grades")
    applies_to_items = models.BooleanField(default=True, help_text="S'applique aux objets")
    specific_ranks = models.ManyToManyField(Rank, blank=True, help_text="Grades spécifiques (vide = tous)")
    specific_items = models.ManyToManyField(StoreItem, blank=True, help_text="Objets spécifiques (vide = tous)")
    
    # Métadonnées
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_promo_codes')
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Code Promo"
        verbose_name_plural = "Codes Promo"
    
    def __str__(self):
        return f"{self.code} ({self.get_discount_display()})"
    
    def get_discount_display(self):
        if self.discount_type == 'fixed':
            return f"-€{self.discount_value}"
        else:
            return f"-{self.discount_value}%"
    
    def is_valid(self):
        """Vérifie si le code promo est valide"""
        now = timezone.now()
        
        # Vérifier le statut
        if self.status != 'active':
            return False, "Code promo inactif"
        
        # Vérifier la date de début
        if self.valid_from > now:
            return False, "Code promo pas encore valide"
        
        # Vérifier la date d'expiration
        if self.valid_until and self.valid_until < now:
            return False, "Code promo expiré"
        
        # Vérifier le nombre d'utilisations
        if self.max_uses > 0 and self.uses_count >= self.max_uses:
            return False, "Code promo épuisé"
        
        return True, "Code valide"
    
    def can_user_use(self, user):
        """Vérifie si un utilisateur peut utiliser ce code"""
        if not user or not user.is_authenticated:
            return False, "Utilisateur non connecté"
        
        # Vérifier le nombre d'utilisations par utilisateur
        user_uses = PromoCodeUsage.objects.filter(promo_code=self, user=user).count()
        if user_uses >= self.max_uses_per_user:
            return False, f"Vous avez déjà utilisé ce code {self.max_uses_per_user} fois"
        
        return True, "Utilisateur peut utiliser le code"
    
    def calculate_discount(self, cart_total):
        """Calcule la réduction à appliquer"""
        if self.discount_type == 'fixed':
            discount = min(self.discount_value, cart_total)
        else:  # percentage
            discount = cart_total * (self.discount_value / 100)
            if self.maximum_discount:
                discount = min(discount, self.maximum_discount)
        
        return round(discount, 2)
    
    def applies_to_cart_item(self, cart_item):
        """Vérifie si le code s'applique à un article du panier"""
        if cart_item.rank:
            if not self.applies_to_ranks:
                return False
            if self.specific_ranks.exists() and cart_item.rank not in self.specific_ranks.all():
                return False
        
        if cart_item.store_item:
            if not self.applies_to_items:
                return False
            if self.specific_items.exists() and cart_item.store_item not in self.specific_items.all():
                return False
        
        return True
    
    @classmethod
    def generate_code(cls, length=8):
        """Génère un code promo aléatoire"""
        chars = string.ascii_uppercase + string.digits
        while True:
            code = ''.join(random.choice(chars) for _ in range(length))
            if not cls.objects.filter(code=code).exists():
                return code


class PromoCodeUsage(models.Model):
    """Historique d'utilisation des codes promo"""
    promo_code = models.ForeignKey(PromoCode, on_delete=models.CASCADE, related_name='usages')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='promo_usages')
    
    # Détails de l'utilisation
    cart_total_before = models.DecimalField(max_digits=10, decimal_places=2)
    discount_applied = models.DecimalField(max_digits=10, decimal_places=2)
    cart_total_after = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Référence au paiement
    payment_id = models.CharField(max_length=100, blank=True, help_text="ID de la session Stripe")
    
    # Métadonnées
    used_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    class Meta:
        ordering = ['-used_at']
        verbose_name = "Utilisation de Code Promo"
        verbose_name_plural = "Utilisations de Codes Promo"
    
    def __str__(self):
        return f"{self.user.username} - {self.promo_code.code} (-€{self.discount_applied})"
    
