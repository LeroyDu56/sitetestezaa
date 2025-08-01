from django.contrib import admin
from .models import TownyServer, Nation, Town, StaffMember, Rank, ServerRule, DynamicMapPoint, UserProfile, UserPurchase, StoreItem, CartItem, StoreItemPurchase, UserSubscription, PromoCode, PromoCodeUsage,BundlePurchase,Bundle,BundleItem

# Basic admin registration for existing models
admin.site.register(TownyServer)
admin.site.register(Nation)
admin.site.register(Town)
admin.site.register(ServerRule)
admin.site.register(DynamicMapPoint)
admin.site.register(UserProfile)

# Enhanced admin configuration for StaffMember
class StaffMemberAdmin(admin.ModelAdmin):
    list_display = ('name', 'role', 'discord_username')
    list_filter = ('role',)
    search_fields = ('name', 'discord_username')

admin.site.register(StaffMember, StaffMemberAdmin)

# Enhanced admin configuration for Rank
class RankAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'duration_type', 'color_code', 'is_donation', 'exclude_from_discounts')
    list_filter = ('is_donation', 'duration_type', 'exclude_from_discounts')
    search_fields = ('name',)
    
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'price', 'color_code')
        }),
        ('Configuration', {
            'fields': ('is_donation', 'duration_type', 'exclude_from_discounts')
        }),
        ('Content', {
            'fields': ('features', 'kit_image')
        }),
    )

admin.site.register(Rank, RankAdmin)

# Admin configuration for UserSubscription
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'rank', 'status', 'current_period_start', 'current_period_end', 'created_at')
    list_filter = ('status', 'rank', 'created_at')
    search_fields = ('user__username', 'rank__name', 'stripe_subscription_id')
    date_hierarchy = 'created_at'
    readonly_fields = ('stripe_subscription_id', 'created_at')

admin.site.register(UserSubscription, UserSubscriptionAdmin)

# Enhanced admin configuration for UserPurchase
class UserPurchaseAdmin(admin.ModelAdmin):
    list_display = ('user', 'rank', 'amount', 'payment_status', 'created_at')
    list_filter = ('payment_status', 'created_at')
    search_fields = ('user__username', 'rank__name', 'payment_id')
    date_hierarchy = 'created_at'

admin.site.register(UserPurchase, UserPurchaseAdmin)

class StoreItemPurchaseAdmin(admin.ModelAdmin):
    list_display = ('user', 'get_item_name', 'quantity', 'amount', 'payment_status', 'created_at')
    list_filter = ('payment_status', 'created_at')
    search_fields = ('user__username', 'store_item__name', 'payment_id')
    date_hierarchy = 'created_at'
    
    def get_item_name(self, obj):
        if obj.store_item:
            return obj.store_item.name
        return "Objet supprimé"
    
    get_item_name.short_description = 'Item'

# Ajoutez cette ligne après admin.site.register(UserPurchase, UserPurchaseAdmin)
admin.site.register(StoreItemPurchase, StoreItemPurchaseAdmin)

# New admin configuration for StoreItem
class StoreItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'quantity', 'color_code', 'get_pet_permission_display')
    list_filter = ('category',)
    search_fields = ('name', 'description', 'pet_permission')
    
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'price')
        }),
        ('Apparence', {
            'fields': ('image', 'color_code')
        }),
        ('Classification', {
            'fields': ('category', 'quantity')
        }),
        ('Configuration Compagnon', {
            'fields': ('pet_permission',),
            'description': 'Pour les compagnons seulement: entrez le nom du pet (ex: dragon, chat, loup)',
            'classes': ('collapse',)
        }),
    )
    
    def get_pet_permission_display(self, obj):
        """Affiche la permission complète dans la liste admin"""
        if obj.category == 'companion' and obj.pet_permission:
            return f"advancedpets.pet.{obj.pet_permission.lower()}"
        return "-"
    get_pet_permission_display.short_description = 'Permission Pet'
    
    def save_model(self, request, obj, form, change):
        # Si c'est un compagnon mais pas de permission définie, utiliser le nom
        if obj.category == 'companion' and not obj.pet_permission:
            obj.pet_permission = obj.name.lower()
        super().save_model(request, obj, form, change)

admin.site.register(StoreItem, StoreItemAdmin)

# New admin configuration for CartItem
class CartItemAdmin(admin.ModelAdmin):
    list_display = ('user', 'get_item_name', 'quantity', 'added_at')
    list_filter = ('added_at',)
    search_fields = ('user__username',)
    date_hierarchy = 'added_at'
    
    def get_item_name(self, obj):
        if obj.rank:
            return f"Rank: {obj.rank.name}"
        elif obj.store_item:
            return f"Item: {obj.store_item.name}"
        return "Unknown item"
    
    get_item_name.short_description = 'Item'

admin.site.register(CartItem, CartItemAdmin)

class PromoCodeUsageInline(admin.TabularInline):
    model = PromoCodeUsage
    extra = 0
    readonly_fields = ['user', 'cart_total_before', 'discount_applied', 'cart_total_after', 'payment_id', 'used_at', 'ip_address']
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False

@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = [
        'code', 
        'get_discount_display', 
        'status', 
        'uses_count', 
        'max_uses', 
        'valid_from', 
        'valid_until',
        'minimum_amount',
        'created_at'
    ]
    
    list_filter = [
        'status', 
        'discount_type', 
        'applies_to_ranks', 
        'applies_to_items',
        'created_at',
        'valid_from'
    ]
    
    search_fields = ['code', 'description']
    
    readonly_fields = ['uses_count', 'created_at', 'created_by']
    
    fieldsets = (
        ('Informations de base', {
            'fields': ('code', 'description', 'status', 'created_by', 'created_at')
        }),
        ('Configuration de réduction', {
            'fields': ('discount_type', 'discount_value', 'maximum_discount'),
            'description': 'Configurez le type et la valeur de la réduction'
        }),
        ('Limites d\'utilisation', {
            'fields': ('max_uses', 'uses_count', 'max_uses_per_user', 'minimum_amount'),
            'description': 'Gérez les limites d\'utilisation du code'
        }),
        ('Validité temporelle', {
            'fields': ('valid_from', 'valid_until'),
            'description': 'Définissez la période de validité du code'
        }),
        ('Restrictions d\'application', {
            'fields': ('applies_to_ranks', 'applies_to_items', 'specific_ranks', 'specific_items'),
            'description': 'Choisissez à quoi le code s\'applique',
            'classes': ['collapse']
        }),
    )
    
    filter_horizontal = ['specific_ranks', 'specific_items']
    
    inlines = [PromoCodeUsageInline]
    
    actions = ['activate_codes', 'deactivate_codes', 'generate_usage_report']
    
    def save_model(self, request, obj, form, change):
        if not change:  # Nouveau code
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    def activate_codes(self, request, queryset):
        updated = queryset.update(status='active')
        self.message_user(request, f'{updated} code(s) promo activé(s).')
    activate_codes.short_description = "Activer les codes sélectionnés"
    
    def deactivate_codes(self, request, queryset):
        updated = queryset.update(status='inactive')
        self.message_user(request, f'{updated} code(s) promo désactivé(s).')
    deactivate_codes.short_description = "Désactiver les codes sélectionnés"
    
    def generate_usage_report(self, request, queryset):
        total_uses = sum(code.uses_count for code in queryset)
        total_discount = sum(
            usage.discount_applied 
            for code in queryset 
            for usage in code.usages.all()
        )
        
        self.message_user(
            request, 
            f'Rapport: {queryset.count()} codes, {total_uses} utilisations, €{total_discount:.2f} de réductions accordées.'
        )
    generate_usage_report.short_description = "Générer un rapport d'utilisation"
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        
        # Ajouter un bouton pour générer un code automatiquement
        if not obj:  # Nouveau code
            form.base_fields['code'].help_text = 'Laissez vide pour générer automatiquement'
        
        return form

@admin.register(PromoCodeUsage)
class PromoCodeUsageAdmin(admin.ModelAdmin):
    list_display = [
        'promo_code', 
        'user', 
        'discount_applied', 
        'cart_total_before', 
        'cart_total_after',
        'used_at',
        'payment_id'
    ]
    
    list_filter = [
        'promo_code__code',
        'used_at',
        'promo_code__discount_type'
    ]
    
    search_fields = [
        'user__username', 
        'promo_code__code', 
        'payment_id'
    ]
    
    readonly_fields = [
        'promo_code', 'user', 'cart_total_before', 'discount_applied', 
        'cart_total_after', 'payment_id', 'used_at', 'ip_address'
    ]
    
    date_hierarchy = 'used_at'
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False
    

# REMPLACEZ votre BundleAdmin par ceci dans admin.py :

from .models import BundleItem  # Ajoutez cet import en haut du fichier

class BundleItemInline(admin.TabularInline):
    model = BundleItem
    extra = 1  # Affiche 1 ligne vide par défaut
    fields = ['store_item', 'quantity']
    autocomplete_fields = ['store_item']  # Recherche facile des objets
    
    def get_extra(self, request, obj=None, **kwargs):
        # Si c'est un nouveau bundle, affiche 3 lignes vides
        if obj is None:
            return 3
        return 1

class BundleAdmin(admin.ModelAdmin):
    list_display = ('name', 'bundle_type', 'price', 'get_total_value', 'get_savings', 'get_savings_percentage', 'get_items_count', 'is_active', 'created_at')
    list_filter = ('bundle_type', 'is_active', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at', 'get_total_value', 'get_savings', 'get_savings_percentage', 'get_items_preview')
    
    # ✅ AJOUT DE L'INLINE POUR LES OBJETS
    inlines = [BundleItemInline]
    
    fieldsets = (
        ('Informations de base', {
            'fields': ('name', 'description', 'bundle_type')
        }),
        ('Apparence', {
            'fields': ('color_code',),
            'description': 'Couleur du bundle (utilisée pour l\'affichage)'
        }),
        ('Contenu', {
            'fields': ('rank', 'get_items_preview'),
            'description': 'Le rang inclus et un aperçu des objets (configurés en bas de page)'
        }),
        ('Tarification', {
            'fields': ('price', 'discount_percentage')
        }),
        ('Statut', {
            'fields': ('is_active', 'created_at', 'updated_at')
        }),
        ('Statistiques', {
            'fields': ('get_total_value', 'get_savings', 'get_savings_percentage'),
            'classes': ['collapse']
        }),
    )
    
    def get_total_value(self, obj):
        return f"€{obj.total_value:.2f}"
    get_total_value.short_description = 'Valeur totale'
    
    def get_savings(self, obj):
        return f"€{obj.savings:.2f}"
    get_savings.short_description = 'Économies'
    
    def get_savings_percentage(self, obj):
        return f"{obj.savings_percentage}%"
    get_savings_percentage.short_description = '% d\'économies'
    
    def get_items_count(self, obj):
        return obj.items.count()
    get_items_count.short_description = 'Nb objets'
    
    def get_items_preview(self, obj):
        if obj.pk:
            items = obj.items.all()
            if items:
                items_list = []
                for bundle_item in items:
                    items_list.append(f"• {bundle_item.quantity}x {bundle_item.store_item.name}")
                return "\n".join(items_list)
            return "Aucun objet ajouté"
        return "Sauvegardez d'abord le bundle pour ajouter des objets"
    get_items_preview.short_description = 'Objets inclus'
    
    actions = ['activate_bundles', 'deactivate_bundles']
    
    def activate_bundles(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} bundle(s) activé(s).')
    activate_bundles.short_description = "Activer les bundles sélectionnés"
    
    def deactivate_bundles(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} bundle(s) désactivé(s).')
    deactivate_bundles.short_description = "Désactiver les bundles sélectionnés"
# ✅ AJOUTEZ CETTE LIGNE :
admin.site.register(Bundle, BundleAdmin)

# Configuration admin pour BundlePurchase
class BundlePurchaseAdmin(admin.ModelAdmin):
    list_display = ('user', 'get_bundle_name', 'amount', 'payment_status', 'created_at')
    list_filter = ('payment_status', 'created_at', 'bundle__bundle_type')
    search_fields = ('user__username', 'bundle__name', 'payment_id')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at',)
    
    def get_bundle_name(self, obj):
        if obj.bundle:
            return obj.bundle.name
        return "Bundle supprimé"
    
    get_bundle_name.short_description = 'Bundle'

admin.site.register(BundlePurchase, BundlePurchaseAdmin)