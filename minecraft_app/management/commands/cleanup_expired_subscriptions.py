# minecraft_app/management/commands/cleanup_expired_subscriptions.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from minecraft_app.models import UserSubscription
import logging

logger = logging.getLogger('minecraft_app')

class Command(BaseCommand):
    help = 'Nettoie les subscriptions expirées et retire les grades mensuels des joueurs'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Affiche ce qui serait fait sans effectuer les changements',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        now = timezone.now()
        
        if dry_run:
            self.stdout.write(self.style.WARNING("🔍 MODE DRY-RUN - Aucun changement ne sera effectué"))
        
        self.stdout.write(f"🕐 Recherche des subscriptions expirées avant {now}")
        
        # Trouver toutes les subscriptions actives mais expirées
        expired_subscriptions = UserSubscription.objects.filter(
            status='active',
            current_period_end__lt=now
        ).select_related('user', 'rank', 'user__profile')
        
        total_found = expired_subscriptions.count()
        self.stdout.write(f"📊 {total_found} subscription(s) expirée(s) trouvée(s)")
        
        if total_found == 0:
            self.stdout.write(self.style.SUCCESS("✅ Aucune subscription expirée à traiter"))
            return
        
        success_count = 0
        error_count = 0
        
        for subscription in expired_subscriptions:
            user = subscription.user
            rank = subscription.rank
            
            try:
                # Récupérer le nom d'utilisateur Minecraft
                try:
                    minecraft_username = user.profile.minecraft_username
                    if not minecraft_username:
                        minecraft_username = user.username
                        self.stdout.write(
                            self.style.WARNING(f"⚠️  {user.username} n'a pas de pseudo Minecraft, utilisation du username Django")
                        )
                except:
                    minecraft_username = user.username
                    self.stdout.write(
                        self.style.WARNING(f"⚠️  Impossible de récupérer le profil de {user.username}, utilisation du username Django")
                    )
                
                self.stdout.write(f"🔄 Traitement : {user.username} ({minecraft_username}) - Grade {rank.name}")
                self.stdout.write(f"   📅 Expiré le : {subscription.current_period_end}")
                self.stdout.write(f"   🆔 Stripe ID : {subscription.stripe_subscription_id or 'N/A'}")
                
                if not dry_run:
                    # Marquer la subscription comme expirée
                    subscription.status = 'expired'
                    subscription.save()
                    
                    # Retirer le grade du joueur via RCON
                    from minecraft_app.minecraft_service import remove_rank_from_player
                    
                    success = remove_rank_from_player(minecraft_username, rank.name)
                    
                    if success:
                        logger.info(f"✅ Grade mensuel {rank.name} retiré de {minecraft_username}")
                        self.stdout.write(
                            self.style.SUCCESS(f"   ✅ Grade {rank.name} retiré avec succès")
                        )
                        success_count += 1
                    else:
                        logger.error(f"❌ Échec du retrait du grade {rank.name} de {minecraft_username}")
                        self.stdout.write(
                            self.style.ERROR(f"   ❌ Échec du retrait du grade {rank.name}")
                        )
                        error_count += 1
                else:
                    self.stdout.write(f"   🔍 [DRY-RUN] Marquerait comme expiré et retirerait le grade {rank.name}")
                    success_count += 1
                    
            except Exception as e:
                error_count += 1
                error_msg = f"Erreur lors du traitement de {user.username}: {str(e)}"
                logger.error(error_msg)
                self.stdout.write(self.style.ERROR(f"   ❌ {error_msg}"))
        
        # Résumé final
        self.stdout.write("\n" + "="*60)
        if dry_run:
            self.stdout.write(self.style.SUCCESS("🔍 RÉSUMÉ DU DRY-RUN"))
        else:
            self.stdout.write(self.style.SUCCESS("📋 RÉSUMÉ DU NETTOYAGE"))
        self.stdout.write("="*60)
        
        self.stdout.write(f"📊 Total traité: {total_found}")
        self.stdout.write(f"✅ Succès: {success_count}")
        self.stdout.write(f"❌ Erreurs: {error_count}")
        
        if not dry_run and success_count > 0:
            self.stdout.write(f"\n💡 {success_count} grade(s) mensuel(s) ont été retirés des joueurs")
            self.stdout.write("🔄 Les joueurs peuvent maintenant souscrire à nouveau")
        
        if not dry_run:
            self.stdout.write(f"\n📝 Consultez les logs pour plus de détails")
        else:
            self.stdout.write(f"\n🚀 Exécutez sans --dry-run pour appliquer les changements")