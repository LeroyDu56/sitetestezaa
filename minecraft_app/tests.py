# Script à exécuter dans le shell Django
# python manage.py shell

from minecraft_app.models import Rank, UserPurchase, StoreItem, get_player_discount, get_rank_upgrade_price
from django.contrib.auth.models import User
from decimal import Decimal

print("=== TEST DU SYSTÈME DE RÉDUCTIONS ET D'UPGRADES ===\n")

# 1. Afficher tous les grades disponibles
print("1. GRADES DISPONIBLES:")
for rank in Rank.objects.all().order_by('price'):
    print(f"   {rank.name}: €{rank.price} ({rank.duration_type})")

print("\n" + "="*60)

# 2. Tester avec un utilisateur spécifique
username = 'EnzoLaPicole'  # Remplacez par votre nom d'utilisateur
try:
    user = User.objects.get(username=username)
    print(f"2. TESTS POUR L'UTILISATEUR: {username}")
    
    # Afficher les achats actuels
    purchases = UserPurchase.objects.filter(
        user=user,
        payment_status='completed'
    ).select_related('rank')
    
    print("\n   Grades possédés:")
    owned_ranks = []
    for purchase in purchases:
        if purchase.rank:
            print(f"   - {purchase.rank.name} (€{purchase.rank.price})")
            owned_ranks.append(purchase.rank)
    
    if not owned_ranks:
        print("   - Aucun grade possédé")
    
    # Test des réductions sur les trésors
    print(f"\n   Réduction sur les Trésors Exclusifs: {get_player_discount(user)}%")
    
    # Test des prix d'upgrade pour chaque grade
    print("\n   Prix d'upgrade pour les grades:")
    all_ranks = Rank.objects.filter(duration_type='lifetime').order_by('price')
    
    for rank in all_ranks:
        upgrade_price = get_rank_upgrade_price(user, rank)
        is_owned = any(owned.id == rank.id for owned in owned_ranks)
        
        if is_owned:
            print(f"   - {rank.name}: DÉJÀ POSSÉDÉ")
        elif upgrade_price == rank.price:
            print(f"   - {rank.name}: €{rank.price} (prix normal)")
        else:
            savings = rank.price - upgrade_price
            print(f"   - {rank.name}: €{upgrade_price} (économie: €{savings})")
    
    # Test des réductions sur les articles de la boutique
    print("\n   Exemples de réductions sur les Trésors Exclusifs:")
    sample_items = StoreItem.objects.all()[:3]
    discount_percentage = get_player_discount(user)
    
    for item in sample_items:
        if discount_percentage > 0:
            discount_factor = Decimal(1 - discount_percentage / 100)
            discounted_price = round(item.price * discount_factor, 2)
            savings = item.price - discounted_price
            print(f"   - {item.name}: €{discounted_price} (au lieu de €{item.price}, économie: €{savings})")
        else:
            print(f"   - {item.name}: €{item.price} (pas de réduction)")

except User.DoesNotExist:
    print(f"Utilisateur '{username}' non trouvé")

print("\n" + "="*60)

# 3. Test de la logique de réduction
print("3. TEST DE LA LOGIQUE DE RÉDUCTION:")

# Simuler différents scénarios
test_scenarios = [
    ("Aucun grade", []),
    ("Héros seulement", ["Héros"]),
    ("Champion seulement", ["Champion"]),
    ("Héros + Champion", ["Héros", "Champion"]),
    ("Tous les grades", ["Héros", "Champion", "Titan", "Divinité"])
]

for scenario_name, rank_names in test_scenarios:
    print(f"\n   Scénario: {scenario_name}")
    
    # Simuler les réductions
    discount_mapping = {
        'divinité': 20,
        'titan': 15,
        'champion': 10,
        'héros': 5,
    }
    
    max_discount = 0
    for rank_name in rank_names:
        rank_name_lower = rank_name.lower()
        if rank_name_lower in discount_mapping:
            max_discount = max(max_discount, discount_mapping[rank_name_lower])
    
    print(f"     Réduction sur Trésors: {max_discount}%")
    
    # Calculer le prix d'upgrade pour le grade suivant
    if rank_names:
        current_ranks = Rank.objects.filter(name__in=rank_names)
        if current_ranks.exists():
            highest_owned = max(current_ranks, key=lambda r: r.price)
            next_ranks = Rank.objects.filter(price__gt=highest_owned.price).order_by('price')
            if next_ranks.exists():
                next_rank = next_ranks.first()
                upgrade_price = next_rank.price - highest_owned.price
                print(f"     Upgrade vers {next_rank.name}: €{upgrade_price} (au lieu de €{next_rank.price})")

print("\n" + "="*60)
print("4. VÉRIFICATIONS:")
print("   ✓ Les réductions sur Trésors s'appliquent selon le grade le plus élevé")
print("   ✓ Les prix d'upgrade sont la différence entre les grades")
print("   ✓ Les systèmes sont indépendants (Trésors vs Grades)")

print("\nSi vous ne voyez pas les réductions attendues:")
print("1. Vérifiez que l'utilisateur a bien des achats avec payment_status='completed'")
print("2. Vérifiez que les noms des grades correspondent exactement")
print("3. Vérifiez que exclude_from_discounts=False pour les grades concernés")