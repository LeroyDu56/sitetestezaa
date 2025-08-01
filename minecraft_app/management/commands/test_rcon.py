# Créez ce fichier dans minecraft_app/management/commands/test_rcon.py

from django.core.management.base import BaseCommand
from minecraft_app.minecraft_service import test_rcon_connection, check_server_status, apply_rank_to_player
import logging

class Command(BaseCommand):
    help = 'Teste la connexion RCON au serveur Minecraft'

    def add_arguments(self, parser):
        parser.add_argument(
            '--test-rank',
            type=str,
            help='Teste l\'attribution d\'un rang à un joueur (format: joueur:rang)',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Mode verbose avec plus de détails',
        )

    def handle(self, *args, **options):
        if options['verbose']:
            logging.getLogger('minecraft_app').setLevel(logging.DEBUG)
        
        self.stdout.write("=== TEST DE CONNEXION RCON ===")
        
        # Test 1: Connexion de base
        self.stdout.write("\n1. Test de connexion RCON...")
        if test_rcon_connection():
            self.stdout.write(self.style.SUCCESS("✓ Connexion RCON réussie"))
        else:
            self.stdout.write(self.style.ERROR("✗ Connexion RCON échouée"))
            return
        
        # Test 2: Statut du serveur
        self.stdout.write("\n2. Test du statut du serveur...")
        is_online, player_count, max_players = check_server_status()
        if is_online:
            self.stdout.write(self.style.SUCCESS(f"✓ Serveur en ligne: {player_count}/{max_players} joueurs"))
        else:
            self.stdout.write(self.style.ERROR("✗ Serveur hors ligne"))
        
        # Test 3: Attribution de rang (optionnel)
        if options['test_rank']:
            try:
                player, rank = options['test_rank'].split(':')
                self.stdout.write(f"\n3. Test d'attribution du rang '{rank}' au joueur '{player}'...")
                
                if apply_rank_to_player(player, rank):
                    self.stdout.write(self.style.SUCCESS(f"✓ Rang '{rank}' attribué avec succès à '{player}'"))
                else:
                    self.stdout.write(self.style.ERROR(f"✗ Échec de l'attribution du rang '{rank}' à '{player}'"))
            except ValueError:
                self.stdout.write(self.style.ERROR("✗ Format invalide pour --test-rank. Utilisez: joueur:rang"))
        
        self.stdout.write(f"\n{self.style.SUCCESS('=== FIN DES TESTS ===')}")
        self.stdout.write("\nConsultez minecraft_rcon.log pour plus de détails.")