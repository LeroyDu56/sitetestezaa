# Créez ce fichier : minecraft_app/management/commands/manage_promo_codes.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from minecraft_app.models import PromoCode
from datetime import timedelta

class Command(BaseCommand):
    help = 'Gère les codes promo (nettoyage, statistiques, etc.)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--cleanup-expired',
            action='store_true',
            help='Marque les codes expirés comme "expired"',
        )
        parser.add_argument(
            '--stats',
            action='store_true',
            help='Affiche les statistiques des codes promo',
        )
        parser.add_argument(
            '--create-sample',
            action='store_true',
            help='Crée des codes promo d\'exemple',
        )

    def handle(self, *args, **options):
        if options['cleanup_expired']:
            self.cleanup_expired_codes()
        
        if options['stats']:
            self.show_stats()
        
        if options['create_sample']:
            self.create_sample_codes()

    def cleanup_expired_codes(self):
        """Marque les codes expirés comme 'expired'"""
        now = timezone.now()
        expired_codes = PromoCode.objects.filter(
            status='active',
            valid_until__lt=now
        )
        
        count = expired_codes.update(status='expired')
        self.stdout.write(
            self.style.SUCCESS(f'✅ {count} code(s) promo marqué(s) comme expirés')
        )

    def show_stats(self):
        """Affiche les statistiques des codes promo"""
        self.stdout.write(self.style.SUCCESS('📊 STATISTIQUES DES CODES PROMO'))
        self.stdout.write('=' * 50)
        
        # Statistiques générales
        total_codes = PromoCode.objects.count()
        active_codes = PromoCode.objects.filter(status='active').count()
        expired_codes = PromoCode.objects.filter(status='expired').count()
        inactive_codes = PromoCode.objects.filter(status='inactive').count()
        
        self.stdout.write(f"📋 Total des codes: {total_codes}")
        self.stdout.write(f"✅ Codes actifs: {active_codes}")
        self.stdout.write(f"❌ Codes expirés: {expired_codes}")
        self.stdout.write(f"⏸️  Codes inactifs: {inactive_codes}")
        
        # Statistiques d'utilisation
        from minecraft_app.models import PromoCodeUsage
        total_uses = PromoCodeUsage.objects.count()
        total_discount = sum(
            usage.discount_applied 
            for usage in PromoCodeUsage.objects.all()
        )
        
        self.stdout.write(f"\n💰 UTILISATION:")
        self.stdout.write(f"🎫 Total utilisations: {total_uses}")
        self.stdout.write(f"💸 Total réductions accordées: €{total_discount:.2f}")
        
        # Top 5 des codes les plus utilisés
        top_codes = PromoCode.objects.filter(uses_count__gt=0).order_by('-uses_count')[:5]
        if top_codes:
            self.stdout.write(f"\n🏆 TOP 5 DES CODES LES PLUS UTILISÉS:")
            for i, code in enumerate(top_codes, 1):
                self.stdout.write(f"{i}. {code.code}: {code.uses_count} utilisations")

    def create_sample_codes(self):
        """Crée des codes promo d'exemple"""
        sample_codes = [
            {
                'code': 'BIENVENUE10',
                'description': 'Code de bienvenue - 10€ de réduction',
                'discount_type': 'fixed',
                'discount_value': 10.00,
                'max_uses': 100,
                'minimum_amount': 20.00,
                'valid_until': timezone.now() + timedelta(days=30)
            },
            {
                'code': 'REDUCTION25',
                'description': '25% de réduction sur tout',
                'discount_type': 'percentage',
                'discount_value': 25.00,
                'max_uses': 50,
                'minimum_amount': 15.00,
                'maximum_discount': 50.00,
                'valid_until': timezone.now() + timedelta(days=14)
            },
            {
                'code': 'WEEKEND5',
                'description': 'Code weekend - 5€ de réduction',
                'discount_type': 'fixed',
                'discount_value': 5.00,
                'max_uses': 200,
                'max_uses_per_user': 1,
                'minimum_amount': 10.00,
                'applies_to_items': False,  # Uniquement sur les grades
                'valid_until': timezone.now() + timedelta(days=7)
            }
        ]
        
        created_count = 0
        for code_data in sample_codes:
            code, created = PromoCode.objects.get_or_create(
                code=code_data['code'],
                defaults=code_data
            )
            
            if created:
                created_count += 1
                self.stdout.write(f"✅ Code '{code.code}' créé")
            else:
                self.stdout.write(f"⚠️  Code '{code.code}' existe déjà")
        
        self.stdout.write(
            self.style.SUCCESS(f'\n🎉 {created_count} nouveaux codes promo créés !')
        )