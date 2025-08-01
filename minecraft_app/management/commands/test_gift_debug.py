# Créez le fichier minecraft_app/management/commands/test_gift_debug.py

from django.core.management.base import BaseCommand
from minecraft_app.minecraft_service import rcon_connection, get_luckperms_group_name
import time

class Command(BaseCommand):
    help = 'Test debug des messages de cadeaux avec affichage console'

    def add_arguments(self, parser):
        # Valeurs par défaut pour votre test
        parser.add_argument('--buyer', type=str, default='SoCook', help='Pseudo de l\'acheteur')
        parser.add_argument('--recipient', type=str, default='karatoss', help='Pseudo du destinataire')
        parser.add_argument('--rank', type=str, default='Divinité', help='Nom du rang')

    def handle(self, *args, **options):
        buyer = options.get('buyer', 'SoCook')
        recipient = options.get('recipient', 'karatoss') 
        rank = options.get('rank', 'Divinité')
        
        self.stdout.write("="*70)
        self.stdout.write(self.style.SUCCESS("🧪 TEST DEBUG MESSAGES CADEAUX"))
        self.stdout.write("="*70)
        self.stdout.write("🎁 Acheteur: SoCook")
        self.stdout.write("👤 Destinataire: karatoss")
        self.stdout.write("🏆 Rang: Divinité")
        self.stdout.write("-"*70)
        
        # Étape 1: Test connexion RCON
        self.stdout.write("1️⃣ Test de connexion RCON...")
        try:
            with rcon_connection() as rcon:
                self.stdout.write(self.style.SUCCESS("   ✅ Connexion RCON établie"))
                
                # Étape 2: Test commande list
                self.stdout.write("\n2️⃣ Test commande list...")
                list_response = rcon.command("list")
                self.stdout.write(f"   📋 Réponse: {list_response}")
                
                if 'karatoss' in list_response.lower():
                    self.stdout.write(self.style.SUCCESS("   ✅ karatoss est en ligne"))
                else:
                    self.stdout.write(self.style.WARNING("   ⚠️ karatoss ne semble pas en ligne"))
                
                # Étape 3: Test message simple au destinataire
                self.stdout.write("\n3️⃣ Test message simple à karatoss...")
                simple_msg = 'tellraw karatoss ["",{"text":"🧪 TEST 1: Vous recevez ce message ?","color":"yellow"}]'
                self.stdout.write(f"   📤 Commande: {simple_msg}")
                
                try:
                    rcon.command(simple_msg)
                    self.stdout.write(self.style.SUCCESS("   ✅ Message simple envoyé"))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"   ❌ Erreur: {e}"))
                
                time.sleep(1)
                
                # Étape 4: Test broadcast à tous
                self.stdout.write("\n4️⃣ Test broadcast à tous les joueurs...")
                broadcast_msg = 'tellraw @a ["",{"text":"🧪 TEST 2: Broadcast visible par tous","color":"green"}]'
                self.stdout.write(f"   📤 Commande: {broadcast_msg}")
                
                try:
                    rcon.command(broadcast_msg)
                    self.stdout.write(self.style.SUCCESS("   ✅ Broadcast envoyé"))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"   ❌ Erreur: {e}"))
                
                time.sleep(1)
                
                # Étape 5: Test message de cadeau au destinataire
                self.stdout.write("\n5️⃣ Test message cadeau à karatoss...")
                gift_msg = 'tellraw karatoss ["\\n",{"text":"🎁 CADEAU REÇU ! 🎁","color":"gold","bold":true},{"text":"\\n\\n"},{"text":"💝 SoCook vous a offert:","color":"green"},{"text":"\\n"},{"text":"🏆 Grade: ","color":"white"},{"text":"Divinité","color":"green","bold":true},{"text":"\\n\\n"},{"text":"💎 Merci SoCook ! 💎","color":"aqua","bold":true}]'
                self.stdout.write(f"   📤 Longueur du message: {len(gift_msg)} caractères")
                
                try:
                    rcon.command(gift_msg)
                    self.stdout.write(self.style.SUCCESS("   ✅ Message cadeau destinataire envoyé"))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"   ❌ Erreur: {e}"))
                
                time.sleep(1)
                
                # Étape 6: Test broadcast cadeau public
                self.stdout.write("\n6️⃣ Test broadcast cadeau public...")
                public_msg = 'tellraw @a ["",{"text":"🎁 [BOUTIQUE] ","color":"purple","bold":true},{"text":"SoCook ","color":"gold","bold":true},{"text":"vient d\'offrir le grade ","color":"white"},{"text":"Divinité","color":"green","bold":true},{"text":" à ","color":"white"},{"text":"karatoss","color":"yellow","bold":true},{"text":" ! 🎉","color":"gold"},{"text":"\\n"},{"text":"✨ Quel beau geste ! ✨","color":"aqua"}]'
                self.stdout.write(f"   📤 Longueur du message: {len(public_msg)} caractères")
                
                try:
                    rcon.command(public_msg)
                    self.stdout.write(self.style.SUCCESS("   ✅ Broadcast cadeau public envoyé"))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"   ❌ Erreur: {e}"))
                
                time.sleep(1)
                
                # Étape 7: Test sons
                self.stdout.write("\n7️⃣ Test effets sonores...")
                try:
                    player_sound = "execute at karatoss run playsound minecraft:entity.experience_orb.pickup master karatoss ~ ~ ~ 1 1.8"
                    rcon.command(player_sound)
                    self.stdout.write(self.style.SUCCESS("   ✅ Son destinataire envoyé"))
                    
                    global_sound = "playsound minecraft:block.note_block.chime master @a ~ ~ ~ 0.3 1.8"
                    rcon.command(global_sound)
                    self.stdout.write(self.style.SUCCESS("   ✅ Son global cadeau envoyé"))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"   ❌ Erreur sons: {e}"))
                
                # Étape 8: Test attribution LuckPerms
                self.stdout.write("\n8️⃣ Test attribution LuckPerms...")
                luckperms_group = get_luckperms_group_name("Divinité")  # Devrait retourner "deity"
                lp_command = f"lp user karatoss parent add {luckperms_group}"
                self.stdout.write(f"   📤 Commande LuckPerms: {lp_command}")
                self.stdout.write(f"   📝 Note: 'Divinité' → '{luckperms_group}' (mapping automatique)")
                
                try:
                    lp_response = rcon.command(lp_command)
                    self.stdout.write(f"   📥 Réponse: {lp_response}")
                    self.stdout.write(self.style.SUCCESS("   ✅ Commande LuckPerms envoyée"))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"   ❌ Erreur LuckPerms: {e}"))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Erreur connexion RCON: {e}"))
            return
        
        # Résumé
        self.stdout.write("\n" + "="*70)
        self.stdout.write(self.style.SUCCESS("📋 RÉSUMÉ DU TEST"))
        self.stdout.write("="*70)
        self.stdout.write("Si vous voyez dans le jeu Minecraft:")
        self.stdout.write("  🧪 TEST 1: Message jaune → RCON fonctionne")
        self.stdout.write("  🧪 TEST 2: Message vert → Broadcast fonctionne")  
        self.stdout.write("  🎁 Message de cadeau → Messages cadeaux fonctionnent")
        self.stdout.write("  🎁 Broadcast public → Annonces publiques fonctionnent")
        self.stdout.write("  🔊 Sons → Effets sonores fonctionnent")
        self.stdout.write("")
        self.stdout.write("Si AUCUN message n'apparaît:")
        self.stdout.write("  → Problème de connexion RCON ou joueur hors ligne")
        self.stdout.write("")
        self.stdout.write("Si seulement certains messages apparaissent:")
        self.stdout.write("  → Problème dans le formatage des messages complexes")
        self.stdout.write("="*70)