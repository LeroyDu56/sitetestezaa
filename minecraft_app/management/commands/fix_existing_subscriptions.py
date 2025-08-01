# minecraft_app/management/commands/fix_existing_subscriptions.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from minecraft_app.models import UserSubscription, UserPurchase
import stripe
from django.conf import settings
import logging

stripe.api_key = settings.STRIPE_SECRET_KEY
logger = logging.getLogger('minecraft_app')

class Command(BaseCommand):
    help = 'Corrige les subscriptions existantes en synchronisant avec Stripe'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Affiche ce qui serait fait sans effectuer les changements',
        )
        parser.add_argument(
            '--force-expire-old',
            action='store_true',
            help='Force l\'expiration des subscriptions anciennes sans Stripe ID',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        force_expire_old = options['force_expire_old']
        
        if dry_run:
            self.stdout.write(self.style.WARNING("🔍 MODE DRY-RUN - Aucun changement ne sera effectué"))
        
        self.stdout.write("🔧 Correction des subscriptions existantes...")
        
        # 1. Trouver toutes les subscriptions actives
        active_subscriptions = UserSubscription.objects.filter(status='active')
        
        self.stdout.write(f"📊 {active_subscriptions.count()} subscription(s) active(s) trouvée(s)")
        
        fixed_count = 0
        expired_count = 0
        error_count = 0
        
        for subscription in active_subscriptions:
            try:
                user = subscription.user
                rank = subscription.rank
                
                self.stdout.write(f"\n🔍 Vérification : {user.username} - {rank.name}")
                
                if subscription.stripe_subscription_id:
                    # Vérifier avec Stripe
                    try:
                        stripe_sub = stripe.Subscription.retrieve(subscription.stripe_subscription_id)
                        stripe_status = stripe_sub.status
                        
                        self.stdout.write(f"   📡 Stripe status: {stripe_status}")
                        
                        if stripe_status in ['canceled', 'unpaid', 'past_due']:
                            self.stdout.write(f"   ⚠️  Subscription Stripe annulée/expirée")
                            
                            if not dry_run:
                                subscription.status = 'expired'
                                subscription.save()
                                
                                # Retirer le grade
                                try:
                                    minecraft_username = user.profile.minecraft_username or user.username
                                    from minecraft_app.minecraft_service import remove_rank_from_player
                                    success = remove_rank_from_player(minecraft_username, rank.name)
                                    
                                    if success:
                                        self.stdout.write(f"   ✅ Grade {rank.name} retiré de {minecraft_username}")
                                        expired_count += 1
                                    else:
                                        self.stdout.write(f"   ❌ Échec du retrait du grade {rank.name}")
                                        error_count += 1
                                except Exception as e:
                                    self.stdout.write(f"   ❌ Erreur retrait: {str(e)}")
                                    error_count += 1
                            else:
                                self.stdout.write(f"   🔍 [DRY-RUN] Expirerait et retirerait le grade")
                                expired_count += 1
                        
                        elif stripe_status == 'active':
                            # Mettre à jour les dates si nécessaire
                            new_period_end = timezone.datetime.fromtimestamp(
                                stripe_sub.current_period_end, tz=timezone.utc
                            )
                            
                            if subscription.current_period_end != new_period_end:
                                self.stdout.write(f"   🔄 Mise à jour de la date d'expiration")
                                
                                if not dry_run:
                                    subscription.current_period_end = new_period_end
                                    subscription.current_period_start = timezone.datetime.fromtimestamp(
                                        stripe_sub.current_period_start, tz=timezone.utc
                                    )
                                    subscription.save()
                                    fixed_count += 1
                                else:
                                    self.stdout.write(f"   🔍 [DRY-RUN] Mettrait à jour les dates")
                                    fixed_count += 1
                            else:
                                self.stdout.write(f"   ✅ Subscription à jour")
                        
                    except stripe.error.StripeError as e:
                        self.stdout.write(f"   ❌ Erreur Stripe: {str(e)}")
                        
                        if "No such subscription" in str(e):
                            self.stdout.write(f"   🗑️  Subscription Stripe supprimée")
                            
                            if not dry_run:
                                subscription.status = 'expired'
                                subscription.save()
                                
                                # Retirer le grade
                                try:
                                    minecraft_username = user.profile.minecraft_username or user.username
                                    from minecraft_app.minecraft_service import remove_rank_from_player
                                    success = remove_rank_from_player(minecraft_username, rank.name)
                                    
                                    if success:
                                        expired_count += 1
                                    else:
                                        error_count += 1
                                except:
                                    error_count += 1
                            else:
                                expired_count += 1
                        else:
                            error_count += 1
                
                else:
                    # Pas de Stripe ID - ancienne subscription
                    self.stdout.write(f"   ⚠️  Aucun Stripe ID")
                    
                    # Vérifier l'âge de la subscription
                    age_days = (timezone.now() - subscription.created_at).days
                    self.stdout.write(f"   📅 Âge: {age_days} jours")
                    
                    if force_expire_old and age_days > 31:  # Plus d'un mois
                        self.stdout.write(f"   🔄 Expiration forcée (ancienne subscription)")
                        
                        if not dry_run:
                            subscription.status = 'expired'
                            subscription.save()
                            
                            # Retirer le grade
                            try:
                                minecraft_username = user.profile.minecraft_username or user.username
                                from minecraft_app.minecraft_service import remove_rank_from_player
                                success = remove_rank_from_player(minecraft_username, rank.name)
                                
                                if success:
                                    expired_count += 1
                                else:
                                    error_count += 1
                            except:
                                error_count += 1
                        else:
                            expired_count += 1
                    
                    elif subscription.current_period_end < timezone.now():
                        self.stdout.write(f"   ⏰ Période expirée selon les dates")
                        
                        if not dry_run:
                            subscription.status = 'expired'
                            subscription.save()
                            
                            # Retirer le grade
                            try:
                                minecraft_username = user.profile.minecraft_username or user.username
                                from minecraft_app.minecraft_service import remove_rank_from_player
                                success = remove_rank_from_player(minecraft_username, rank.name)
                                
                                if success:
                                    expired_count += 1
                                else:
                                    error_count += 1
                            except:
                                error_count += 1
                        else:
                            expired_count += 1
                    else:
                        self.stdout.write(f"   ✅ Subscription encore valide selon les dates")
                
            except Exception as e:
                error_count += 1
                self.stdout.write(f"   ❌ Erreur générale: {str(e)}")
        
        # 2. Vérifier les achats de grades mensuels orphelins
        self.stdout.write(f"\n🔍 Vérification des achats de grades mensuels orphelins...")
        
        monthly_purchases = UserPurchase.objects.filter(
            rank__duration_type='monthly',
            payment_status='completed'
        ).select_related('user', 'rank')
        
        orphan_count = 0
        
        for purchase in monthly_purchases:
            # Vérifier s'il y a une subscription correspondante
            existing_sub = UserSubscription.objects.filter(
                user=purchase.user,
                rank=purchase.rank
            ).first()
            
            if not existing_sub:
                self.stdout.write(f"🔍 Achat orphelin trouvé: {purchase.user.username} - {purchase.rank.name}")
                self.stdout.write(f"   📅 Acheté le: {purchase.created_at}")
                
                # Calculer si ça devrait être expiré (30 jours après achat)
                should_expire_at = purchase.created_at + timezone.timedelta(days=30)
                
                if timezone.now() > should_expire_at:
                    self.stdout.write(f"   ⏰ Devrait être expiré depuis: {should_expire_at}")
                    
                    # Retirer le grade
                    if not dry_run:
                        try:
                            minecraft_username = purchase.user.profile.minecraft_username or purchase.user.username
                            from minecraft_app.minecraft_service import remove_rank_from_player
                            success = remove_rank_from_player(minecraft_username, purchase.rank.name)
                            
                            if success:
                                self.stdout.write(f"   ✅ Grade orphelin retiré")
                                orphan_count += 1
                            else:
                                self.stdout.write(f"   ❌ Échec du retrait orphelin")
                                error_count += 1
                        except Exception as e:
                            self.stdout.write(f"   ❌ Erreur retrait orphelin: {str(e)}")
                            error_count += 1
                    else:
                        self.stdout.write(f"   🔍 [DRY-RUN] Retirerait le grade orphelin")
                        orphan_count += 1
                else:
                    self.stdout.write(f"   ✅ Encore valide jusqu'au: {should_expire_at}")
        
        # Résumé final
        self.stdout.write("\n" + "="*60)
        if dry_run:
            self.stdout.write(self.style.SUCCESS("🔍 RÉSUMÉ DU DRY-RUN"))
        else:
            self.stdout.write(self.style.SUCCESS("📋 RÉSUMÉ DE LA CORRECTION"))
        self.stdout.write("="*60)
        
        self.stdout.write(f"📊 Subscriptions vérifiées: {active_subscriptions.count()}")
        self.stdout.write(f"🔧 Mises à jour: {fixed_count}")
        self.stdout.write(f"⏰ Expirées: {expired_count}")
        self.stdout.write(f"🗑️  Orphelins nettoyés: {orphan_count}")
        self.stdout.write(f"❌ Erreurs: {error_count}")
        
        if not dry_run and (expired_count > 0 or orphan_count > 0):
            self.stdout.write(f"\n💡 {expired_count + orphan_count} grade(s) mensuel(s) ont été retirés")
            self.stdout.write("🔄 Les joueurs peuvent maintenant souscrire à nouveau")
        
        if not dry_run:
            self.stdout.write(f"\n📝 Consultez les logs pour plus de détails")
        else:
            self.stdout.write(f"\n🚀 Exécutez sans --dry-run pour appliquer les changements")
            if not force_expire_old:
                self.stdout.write(f"💡 Utilisez --force-expire-old pour forcer l'expiration des anciennes subscriptions")