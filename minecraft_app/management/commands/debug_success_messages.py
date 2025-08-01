# Créez le fichier minecraft_app/management/commands/debug_success_messages.py

from django.core.management.base import BaseCommand
from minecraft_app.minecraft_service import rcon_connection

class Command(BaseCommand):
    help = 'Debug direct de send_success_messages'

    def handle(self, *args, **options):
        self.stdout.write("="*70)
        self.stdout.write("🔍 DEBUG SEND_SUCCESS_MESSAGES")
        self.stdout.write("="*70)
        
        try:
            with rcon_connection() as rcon:
                self.stdout.write("✅ Connexion RCON établie")
                
                # Test direct de la fonction send_success_messages
                self.stdout.write("\n🧪 Test 1: Message d'achat normal (gifted_by=None)")
                
                try:
                    from minecraft_app.minecraft_service import send_success_messages
                    send_success_messages(rcon, "SoCook", "Héros", False, None)
                    self.stdout.write("✅ send_success_messages achat normal appelée")
                except Exception as e:
                    self.stdout.write(f"❌ Erreur achat normal: {e}")
                
                self.stdout.write("\n🧪 Test 2: Message de cadeau (gifted_by='SoCook')")
                
                try:
                    send_success_messages(rcon, "karatoss", "Héros", False, "SoCook")
                    self.stdout.write("✅ send_success_messages cadeau appelée")
                except Exception as e:
                    self.stdout.write(f"❌ Erreur cadeau: {e}")
                
                self.stdout.write("\n🧪 Test 3: Message direct forcé")
                
                # Test direct du message broadcast
                try:
                    direct_msg = 'tellraw @a ["",{"text":"🧪 TEST DIRECT: SoCook offre Héros à karatoss !","color":"purple"}]'
                    rcon.command(direct_msg)
                    self.stdout.write("✅ Message direct envoyé")
                except Exception as e:
                    self.stdout.write(f"❌ Erreur message direct: {e}")
                    
        except Exception as e:
            self.stdout.write(f"❌ Erreur connexion RCON: {e}")
        
        self.stdout.write("\n" + "="*70)
        self.stdout.write("🔍 Regardez dans le jeu quel test a fonctionné !")
        self.stdout.write("="*70)