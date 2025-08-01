import logging
import time
import socket
import struct
import re
from contextlib import contextmanager
from datetime import datetime
from django.conf import settings

logger = logging.getLogger('minecraft_app')


RANK_NAME_MAPPING = {
    'Divinité': 'deity',
    'Héros': 'hero',
    'Champion': 'champion',
    'Titan': 'titan',
    # Ajoutez d'autres mappings si nécessaire
    # 'Nom en français': 'nom_luckperms',
}



class SimpleRCON:
    """Implémentation RCON simple et fiable pour contourner les bugs de mcrcon"""
    
    def __init__(self, host, password, port=25575):
        self.host = host
        self.port = port
        self.password = password
        self.socket = None
        self.request_id = 0
    
    def connect(self):
        """Établit la connexion RCON"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(15)
            self.socket.connect((self.host, self.port))
            
            # Authentification RCON
            self.request_id += 1
            auth_packet = self._build_packet(self.request_id, 3, self.password)
            self.socket.send(auth_packet)
            
            # Lire la réponse d'authentification
            response = self._read_packet()
            if response[0] != self.request_id:
                raise Exception("Authentification RCON échouée")
            
            logger.info("Authentification RCON réussie")
            return True
            
        except Exception as e:
            logger.error(f"Erreur de connexion RCON: {e}")
            if self.socket:
                self.socket.close()
                self.socket = None
            raise
    
    def command(self, cmd):
        """Exécute une commande RCON"""
        if not self.socket:
            raise Exception("Non connecté au serveur RCON")
        
        try:
            self.request_id += 1
            cmd_packet = self._build_packet(self.request_id, 2, cmd)
            self.socket.send(cmd_packet)
            
            response = self._read_packet()
            return response[2].decode('utf-8', errors='ignore')
            
        except Exception as e:
            logger.error(f"Erreur commande RCON: {e}")
            raise
    
    def disconnect(self):
        """Ferme la connexion RCON"""
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None
    
    def _build_packet(self, request_id, packet_type, payload):
        """Construit un paquet RCON"""
        payload_bytes = payload.encode('utf-8')
        packet_size = 4 + 4 + len(payload_bytes) + 2
        
        packet = struct.pack('<i', packet_size)
        packet += struct.pack('<i', request_id)
        packet += struct.pack('<i', packet_type)
        packet += payload_bytes
        packet += b'\x00\x00'
        
        return packet
    
    def _read_packet(self):
        """Lit un paquet RCON"""
        # Lire la taille du paquet
        size_data = self.socket.recv(4)
        if len(size_data) < 4:
            raise Exception("Réponse RCON incomplète")
        
        packet_size = struct.unpack('<i', size_data)[0]
        
        # Lire le reste du paquet
        packet_data = b''
        while len(packet_data) < packet_size:
            chunk = self.socket.recv(packet_size - len(packet_data))
            if not chunk:
                raise Exception("Connexion RCON fermée")
            packet_data += chunk
        
        # Parser le paquet
        request_id = struct.unpack('<i', packet_data[0:4])[0]
        packet_type = struct.unpack('<i', packet_data[4:8])[0]
        payload = packet_data[8:-2]  # Enlever les deux null bytes
        
        return (request_id, packet_type, payload)

@contextmanager
def rcon_connection():
    """
    Context manager robuste pour les connexions RCON avec fallback
    """
    rcon = None
    try:
        host = getattr(settings, 'MINECRAFT_RCON_HOST', 'localhost')
        port = getattr(settings, 'MINECRAFT_RCON_PORT', 25575)
        password = getattr(settings, 'MINECRAFT_RCON_PASSWORD', '')
        timeout = getattr(settings, 'MINECRAFT_RCON_TIMEOUT', 15)
        
        logger.info(f"Connexion RCON à {host}:{port}")
        
        # Essayer d'abord avec mcrcon
        try:
            from mcrcon import MCRcon
            
            mcr = MCRcon(host, password, port, tlsmode=0)
            
            if mcr.socket is None:
                logger.warning("Socket mcrcon None, création manuelle")
                mcr.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            
            mcr.socket.settimeout(timeout)
            
            start_time = time.time()
            mcr.connect()
            connect_time = time.time() - start_time
            
            logger.info(f"Connexion RCON mcrcon OK en {connect_time:.3f}s")
            rcon = mcr
            yield rcon
            
        except Exception as mcrcon_error:
            logger.warning(f"mcrcon échoué: {mcrcon_error}, fallback vers RCON custom")
            
            # Fallback vers notre implémentation
            rcon = SimpleRCON(host, password, port)
            rcon.connect()
            logger.info("Connexion RCON custom établie")
            yield rcon
        
    except socket.timeout as e:
        logger.error(f"Timeout RCON après {timeout}s: {str(e)}")
        raise
    except socket.gaierror as e:
        logger.error(f"Erreur DNS pour {host}: {str(e)}")
        raise
    except ConnectionRefusedError as e:
        logger.error(f"Connexion refusée {host}:{port}: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Erreur RCON: {str(e)}", exc_info=True)
        raise
    finally:
        if rcon is not None:
            try:
                rcon.disconnect()
                logger.info("Déconnexion RCON effectuée")
            except Exception as e:
                logger.warning(f"Erreur déconnexion RCON: {str(e)}")


def apply_rank_to_player(username, rank_name, is_temporary=False, gifted_by=None):
    """
    Attribution de rang avec système H2 - notification admin optimisée.
    Version finale avec gestion robuste des erreurs RCON et messages de cadeaux.
    
    Args:
        username: Le joueur qui reçoit le grade
        rank_name: Le nom du grade
        is_temporary: Si le grade est temporaire
        gifted_by: Le pseudo du joueur qui offre le grade (None si achat normal)
    """
    if not username:
        logger.error("Cannot apply rank: No Minecraft username provided")
        return False
    
    # Convertir le nom du grade vers le nom LuckPerms
    luckperms_group = get_luckperms_group_name(rank_name)
    
    is_gift = gifted_by is not None
    logger.info(f"Attribution rang H2: {rank_name} (LuckPerms: {luckperms_group}) à {username} (temporaire: {is_temporary}, cadeau: {is_gift}, offert par: {gifted_by})")
    
    try:
        with rcon_connection() as rcon:
            duration_text = " (30 jours)" if is_temporary else ""
            
            # 1. Tentative d'attribution automatique LuckPerms avec le bon nom
            if is_temporary:
                lp_command = f"lp user {username} parent addtemp {luckperms_group} 720h"
            else:
                lp_command = f"lp user {username} parent add {luckperms_group}"
            
            logger.info(f"Commande LuckPerms: {lp_command}")
            try:
                lp_response = rcon.command(lp_command)
                logger.info(f"Réponse LuckPerms: '{lp_response}'")
                
                # Attendre un peu pour que LuckPerms traite la commande
                time.sleep(2)
                
                # Vérifier si l'attribution a fonctionné
                success = verify_rank_assignment(rcon, username, luckperms_group)
                if success:
                    logger.info(f"✅ Attribution automatique réussie pour {username}")
                    send_success_messages(rcon, username, rank_name, is_temporary, gifted_by)
                    return True
                else:
                    logger.warning(f"⚠️ Attribution automatique échouée, passage en mode admin")
                    
            except Exception as e:
                logger.warning(f"Commande LuckPerms échouée (normal avec H2): {e}")
            
            # 2. Mode admin : Messages optimisés même si l'attribution auto échoue
            
            # ✅ CORRECTION : Messages différenciés pour cadeaux et achats normaux
            if is_gift:
                # Message immédiat au joueur qui reçoit le cadeau
                player_message = f'tellraw {username} ["\\n",{{"text":"🎁 CADEAU REÇU ! 🎁","color":"gold","bold":true}},{{"text":"\\n\\n"}},{{"text":"💝 {gifted_by} vous a offert:","color":"green"}},{{"text":"\\n"}},{{"text":"🏆 Grade: ","color":"white"}},{{"text":"{rank_name}{duration_text}","color":"green","bold":true}},{{"text":"\\n\\n"}},{{"text":"⚡ Attribution en cours...","color":"yellow"}},{{"text":"\\n"}},{{"text":"Si le grade n\'apparaît pas immédiatement,","color":"gray"}},{{"text":"\\n"}},{{"text":"un administrateur vous l\'attribuera sous peu.","color":"gray"}},{{"text":"\\n\\n"}},{{"text":"💎 Merci {gifted_by} ! 💎","color":"aqua","bold":true}}]'
                
                # Notification aux admins pour les cadeaux avec informations complètes
                admin_notification = f'tellraw @a[permission=luckperms.user.parent.add] ["",{{"text":"\\n"}},{{"text":"🎁 [BOUTIQUE CADEAU] 🎁","color":"purple","bold":true}},{{"text":"\\n"}},{{"text":"Attribution de cadeau requise:","color":"yellow"}},{{"text":"\\n"}},{{"text":"💝 Offert par: ","color":"white"}},{{"text":"{gifted_by}","color":"gold","bold":true}},{{"text":"\\n"}},{{"text":"👤 Destinataire: ","color":"white"}},{{"text":"{username}","color":"green","bold":true}},{{"text":"\\n"}},{{"text":"🏆 Grade: ","color":"white"}},{{"text":"{rank_name}{duration_text}","color":"gold","bold":true}},{{"text":"\\n"}},{{"text":"🔧 Groupe LuckPerms: ","color":"white"}},{{"text":"{luckperms_group}","color":"aqua","bold":true}},{{"text":"\\n"}},{{"text":"💰 Achat confirmé et payé ✅","color":"green"}},{{"text":"\\n\\n"}},{{"text":"🔧 Cliquez pour attribuer: ","color":"gray"}},{{"text":"[EXÉCUTER MAINTENANT]","color":"aqua","bold":true,"underlined":true,"clickEvent":{{"action":"run_command","value":"{lp_command}"}},"hoverEvent":{{"action":"show_text","value":"Cliquez pour exécuter:\\n{lp_command}"}}}}]'
                
                # Broadcast public spécial pour les cadeaux
                public_broadcast = f'tellraw @a ["",{{"text":"🎁 [BOUTIQUE] ","color":"purple","bold":true}},{{"text":"{gifted_by} ","color":"gold","bold":true}},{{"text":"vient d\'offrir le grade ","color":"white"}},{{"text":"{rank_name}{duration_text}","color":"green","bold":true}},{{"text":" à ","color":"white"}},{{"text":"{username}","color":"yellow","bold":true}},{{"text":" ! 🎉","color":"gold"}},{{"text":"\\n"}},{{"text":"✨ Quel beau geste ! ✨","color":"aqua"}}]'
                
            else:
                # Messages pour les achats normaux
                player_message = f'tellraw {username} ["\\n",{{"text":"🎉 ACHAT CONFIRMÉ ! 🎉","color":"gold","bold":true}},{{"text":"\\n\\n"}},{{"text":"💳 Paiement traité avec succès","color":"green"}},{{"text":"\\n"}},{{"text":"🏆 Grade acheté: ","color":"white"}},{{"text":"{rank_name}{duration_text}","color":"green","bold":true}},{{"text":"\\n\\n"}},{{"text":"⚡ Attribution en cours...","color":"yellow"}},{{"text":"\\n"}},{{"text":"Si le grade n\'apparaît pas immédiatement,","color":"gray"}},{{"text":"\\n"}},{{"text":"un administrateur vous l\'attribuera sous peu.","color":"gray"}},{{"text":"\\n\\n"}},{{"text":"💎 Merci pour votre soutien ! 💎","color":"aqua","bold":true}}]'
                
                admin_notification = f'tellraw @a[permission=luckperms.user.parent.add] ["",{{"text":"\\n"}},{{"text":"🛒 [BOUTIQUE ADMIN] 🛒","color":"red","bold":true}},{{"text":"\\n"}},{{"text":"Attribution de rang requise:","color":"yellow"}},{{"text":"\\n"}},{{"text":"👤 Joueur: ","color":"white"}},{{"text":"{username}","color":"green","bold":true}},{{"text":"\\n"}},{{"text":"🏆 Grade: ","color":"white"}},{{"text":"{rank_name}{duration_text}","color":"gold","bold":true}},{{"text":"\\n"}},{{"text":"🔧 Groupe LuckPerms: ","color":"white"}},{{"text":"{luckperms_group}","color":"aqua","bold":true}},{{"text":"\\n"}},{{"text":"💰 Achat confirmé et payé ✅","color":"green"}},{{"text":"\\n\\n"}},{{"text":"🔧 Cliquez pour attribuer: ","color":"gray"}},{{"text":"[EXÉCUTER MAINTENANT]","color":"aqua","bold":true,"underlined":true,"clickEvent":{{"action":"run_command","value":"{lp_command}"}},"hoverEvent":{{"action":"show_text","value":"Cliquez pour exécuter:\\n{lp_command}"}}}}]'
                
                public_broadcast = f'tellraw @a ["",{{"text":"🛒 [BOUTIQUE] ","color":"aqua","bold":true}},{{"text":"{username} ","color":"yellow","bold":true}},{{"text":"vient d\'acheter le grade ","color":"white"}},{{"text":"{rank_name}{duration_text}","color":"green","bold":true}},{{"text":" ! 🎉","color":"gold"}},{{"text":"\\n"}},{{"text":"✨ Merci pour le soutien au serveur ! ✨","color":"aqua"}}]'
            
            # Envoyer tous les messages dans l'ordre
            rcon.command(player_message)
            logger.info("✅ Message de confirmation envoyé au joueur")
            
            rcon.command(admin_notification)
            logger.info("✅ Notification admin envoyée avec bouton cliquable")
            
            rcon.command(public_broadcast)
            logger.info("✅ Broadcast public envoyé")
            
            # ✅ CORRECTION : Effets sonores différenciés pour cadeaux et achats
            try:
                # Son pour le destinataire/acheteur
                player_sound = f"execute at {username} run playsound minecraft:entity.experience_orb.pickup master {username} ~ ~ ~ 1 1.8"
                rcon.command(player_sound)
                
                # Son global différent selon le type
                if is_gift:
                    # Son spécial cadeau pour tous (plus festif)
                    global_sound = "playsound minecraft:block.note_block.chime master @a ~ ~ ~ 0.3 1.8"
                    logger.info(f"✅ Son de cadeau joué pour {gifted_by} -> {username}")
                else:
                    # Son normal pour les achats
                    global_sound = "playsound minecraft:entity.experience_orb.pickup master @a ~ ~ ~ 0.2 1.2"
                    logger.info(f"✅ Son d'achat joué pour {username}")
                
                rcon.command(global_sound)
                logger.info("✅ Effets sonores joués")
                
            except Exception as e:
                logger.debug(f"Sons non joués: {e}")
            
            # Log administratif avec informations de cadeau
            log_purchase_for_admin_review(username, rank_name, is_temporary, gifted_by)
            
            if is_gift:
                logger.info(f"✅ Processus de cadeau de rang complété: {gifted_by} -> {username} (rang: {rank_name}, LuckPerms: {luckperms_group})")
            else:
                logger.info(f"✅ Processus d'achat de rang complété: {username} -> {rank_name} (LuckPerms: {luckperms_group})")
            
            return True
            
    except Exception as e:
        logger.error(f"Erreur critique lors du traitement d'achat: {str(e)}")
        
        # ✅ CORRECTION : Fallback avec messages différenciés
        try:
            with rcon_connection() as rcon:
                if is_gift:
                    fallback_message = f'tellraw {username} ["",{{"text":"⚠️ CADEAU ENREGISTRÉ ⚠️","color":"gold","bold":true}},{{"text":"\\n"}},{{"text":"{gifted_by} vous a offert un grade","color":"yellow"}},{{"text":"\\n"}},{{"text":"mais l\'attribution nécessite une intervention.","color":"yellow"}},{{"text":"\\n"}},{{"text":"Un admin vous contactera rapidement !","color":"green"}},{{"text":"\\n"}},{{"text":"Merci pour votre patience 💙","color":"aqua"}}]'
                    logger.info(f"✅ Message de fallback cadeau envoyé pour {gifted_by} -> {username}")
                else:
                    fallback_message = f'tellraw {username} ["",{{"text":"⚠️ ACHAT ENREGISTRÉ ⚠️","color":"gold","bold":true}},{{"text":"\\n"}},{{"text":"Votre paiement a été traité mais","color":"yellow"}},{{"text":"\\n"}},{{"text":"l\'attribution nécessite une intervention.","color":"yellow"}},{{"text":"\\n"}},{{"text":"Un admin vous contactera rapidement !","color":"green"}},{{"text":"\\n"}},{{"text":"Merci pour votre patience 💙","color":"aqua"}}]'
                    logger.info(f"✅ Message de fallback achat envoyé pour {username}")
                
                rcon.command(fallback_message)
                logger.info("✅ Message de fallback envoyé")
        except:
            logger.error("❌ Impossible d'envoyer le message de fallback")
        
        return False

def get_luckperms_group_name(django_rank_name):
    """
    Convertit le nom du grade Django vers le nom du groupe LuckPerms
    """
    return RANK_NAME_MAPPING.get(django_rank_name, django_rank_name.lower())

def verify_rank_assignment(rcon, username, lp_group):
    """
    Vérifie que le rang a bien été attribué au joueur.
    """
    try:
        check_command = f"lp user {username} info"
        resp = rcon.command(check_command)
        logger.info(f"Vérification pour {username}: {resp}")
        
        if lp_group.lower() in resp.lower():
            logger.info(f"✅ Confirmation: {username} a le groupe {lp_group}")
            return True
        else:
            logger.warning(f"❌ Groupe {lp_group} non trouvé pour {username}")
            return False
            
    except Exception as e:
        logger.error(f"Erreur vérification rang: {str(e)}")
        return False

# Dans minecraft_app/minecraft_service.py - REMPLACEZ la fonction send_success_messages par ceci :

def send_success_messages(rcon, username, rank_name, is_temporary, gifted_by=None):
    """
    Envoie les messages de succès quand l'attribution automatique fonctionne.
    CORRIGÉ pour ne pas envoyer les deux types de messages en même temps.
    """
    try:
        duration_text = " (30 jours)" if is_temporary else ""
        is_gift = gifted_by is not None
        
        logger.info(f"📢 send_success_messages: is_gift={is_gift}, gifted_by={gifted_by}")
        
        if is_gift:
            # ✅ SEULEMENT LES MESSAGES DE CADEAU
            logger.info(f"🎁 Envoi UNIQUEMENT des messages de cadeau : {gifted_by} -> {username}")
            
            # Message de succès au destinataire du cadeau
            success_message = f'tellraw {username} ["\\n",{{"text":"🎁 CADEAU REÇU ! 🎁","color":"gold","bold":true}},{{"text":"\\n\\n"}},{{"text":"✅ Attribution automatique réussie","color":"green"}},{{"text":"\\n"}},{{"text":"💝 {gifted_by} vous a offert:","color":"white"}},{{"text":"\\n"}},{{"text":"🏆 Vous avez maintenant: ","color":"white"}},{{"text":"{rank_name}{duration_text}","color":"green","bold":true}},{{"text":"\\n\\n"}},{{"text":"💎 Merci {gifted_by} ! 💎","color":"aqua","bold":true}}]'
            
            # Broadcast de cadeau SEULEMENT
            success_broadcast = f'tellraw @a ["",{{"text":"🎁 [BOUTIQUE] ","color":"purple","bold":true}},{{"text":"{gifted_by} ","color":"gold","bold":true}},{{"text":"vient d\'offrir le grade ","color":"white"}},{{"text":"{rank_name}{duration_text}","color":"green","bold":true}},{{"text":" à ","color":"white"}},{{"text":"{username}","color":"yellow","bold":true}},{{"text":" ! 🎉","color":"gold"}},{{"text":"\\n"}},{{"text":"✨ Quel beau geste ! ✨","color":"aqua"}}]'
            
            # Envoyer SEULEMENT les messages de cadeau
            try:
                rcon.command(success_message)
                logger.info(f"✅ Message personnel cadeau envoyé à {username}")
            except Exception as e:
                logger.warning(f"⚠️ Message personnel cadeau non envoyé: {e}")
            
            try:
                rcon.command(success_broadcast)
                logger.info(f"✅ BROADCAST CADEAU ENVOYÉ : {gifted_by} -> {username}")
            except Exception as e:
                logger.error(f"❌ ERREUR BROADCAST CADEAU : {e}")
            
            # Sons spéciaux pour cadeau
            try:
                player_sound = f"execute at {username} run playsound minecraft:entity.experience_orb.pickup master {username} ~ ~ ~ 1 1.8"
                rcon.command(player_sound)
                
                global_sound = "playsound minecraft:block.note_block.chime master @a ~ ~ ~ 0.3 1.8"
                rcon.command(global_sound)
                
                logger.info("✅ Sons de cadeau joués")
            except Exception as e:
                logger.debug(f"Sons de cadeau non joués: {e}")
                
        else:
            # ✅ SEULEMENT LES MESSAGES D'ACHAT NORMAL
            logger.info(f"🛒 Envoi UNIQUEMENT des messages d'achat normal pour {username}")
            
            # Messages pour achat normal
            success_message = f'tellraw {username} ["\\n",{{"text":"🎉 GRADE ATTRIBUÉ ! 🎉","color":"gold","bold":true}},{{"text":"\\n\\n"}},{{"text":"✅ Attribution automatique réussie","color":"green"}},{{"text":"\\n"}},{{"text":"🏆 Vous avez maintenant: ","color":"white"}},{{"text":"{rank_name}{duration_text}","color":"green","bold":true}},{{"text":"\\n\\n"}},{{"text":"💎 Merci pour votre achat ! 💎","color":"aqua","bold":true}}]'
            
            # Broadcast d'achat normal SEULEMENT
            success_broadcast = f'tellraw @a ["",{{"text":"🛒 [BOUTIQUE] ","color":"aqua","bold":true}},{{"text":"{username} ","color":"yellow","bold":true}},{{"text":"vient d\'acheter le grade ","color":"white"}},{{"text":"{rank_name}{duration_text}","color":"green","bold":true}},{{"text":" ! 🎉","color":"gold"}},{{"text":"\\n"}},{{"text":"✨ Merci pour le soutien au serveur ! ✨","color":"aqua"}}]'
            
            try:
                rcon.command(success_message)
                rcon.command(success_broadcast)
                logger.info(f"✅ Messages d'achat normal envoyés pour {username}")
            except Exception as e:
                logger.error(f"❌ Erreur messages achat normal: {e}")
            
            # Son normal pour achat
            try:
                player_sound = f"execute at {username} run playsound minecraft:entity.experience_orb.pickup master {username} ~ ~ ~ 1 1.8"
                rcon.command(player_sound)
                
                global_sound = "playsound minecraft:entity.experience_orb.pickup master @a ~ ~ ~ 0.2 1.2"
                rcon.command(global_sound)
                
                logger.info("✅ Sons d'achat joués")
            except Exception as e:
                logger.debug(f"Sons d'achat non joués: {e}")
        
        logger.info(f"✅ send_success_messages terminé avec succès (type: {'cadeau' if is_gift else 'achat'})")
        
    except Exception as e:
        logger.error(f"❌ Erreur dans send_success_messages: {e}")
        import traceback
        logger.error(f"❌ Traceback: {traceback.format_exc()}")

def give_store_item_to_player(username, item_name, quantity=1):
    """
    Don d'objet optimisé pour H2 avec excellent feedback utilisateur.
    """
    if not username:
        logger.error("Cannot give item: No Minecraft username provided")
        return False
    
    # Mappings des objets de la boutique
    item_command_templates = {
        # Coffres CrazyCrates
        'Coffre d\'Argent': 'cc give physical argentcrate {1} {0}',
        'Coffre de Bronze': 'cc give physical bronzecrate {1} {0}',
        'Coffre Doré': 'cc give physical goldencrate {1} {0}', 
        'Coffre Oros': 'cc give physical oroscrate {1} {0}',
        
        # Oeufs de mobs
        'Œuf de cheval squelette': 'give {0} minecraft:skeleton_horse_spawn_egg {1}',
        'Œuf d\'Allay': 'give {0} minecraft:allay_spawn_egg {1}',
        'Œuf de Villageois': 'give {0} minecraft:villager_spawn_egg {1}',
        'Œuf de Cheval': 'give {0} minecraft:horse_spawn_egg {1}',
        'Œuf de Loup': 'give {0} minecraft:wolf_spawn_egg {1}',
        
        # Objets rares
        'Élytre': 'give {0} minecraft:elytra {1}',
        'Pomme d\'or enchantée': 'give {0} minecraft:enchanted_golden_apple {1}',
        'Totem d\'immortalité': 'give {0} minecraft:totem_of_undying {1}',
        'Étoile du Nether': 'give {0} minecraft:nether_star {1}',
        'Netherite': 'give {0} minecraft:netherite_ingot {1}',
        'Beacon': 'give {0} minecraft:beacon {1}',
        
        # Têtes personnalisées
        'Tête de joueur': 'SPECIAL_HEAD'
    }
    
    if item_name not in item_command_templates:
        logger.error(f"Objet de boutique inconnu: {item_name}")
        return False
    
    logger.info(f"Don d'objet boutique: {quantity}x {item_name} à {username}")
    
    try:
        with rcon_connection() as rcon:
            # Traitement spécial pour les têtes personnalisées
            if item_name == 'Tête de joueur':
                head_notification = f'tellraw @a[permission=minecraft.command.give] ["",{{"text":"🎭 [BOUTIQUE ADMIN] 🎭","color":"purple","bold":true}},{{"text":"\\n"}},{{"text":"Tête personnalisée achetée:","color":"yellow"}},{{"text":"\\n"}},{{"text":"👤 Joueur: ","color":"white"}},{{"text":"{username}","color":"green","bold":true}},{{"text":"\\n"}},{{"text":"Quantité: ","color":"white"}},{{"text":"{quantity}","color":"gold"}},{{"text":"\\n"}},{{"text":"💰 Payé et confirmé ✅","color":"green"}}]'
                
                rcon.command(head_notification)
                
                player_msg = f'tellraw {username} ["",{{"text":"🎭 TÊTE PERSONNALISÉE !","color":"purple","bold":true}},{{"text":"\\n"}},{{"text":"Votre achat est confirmé !","color":"green"}},{{"text":"\\n"}},{{"text":"Un administrateur vous contactera","color":"white"}},{{"text":"\\n"}},{{"text":"pour personnaliser votre tête.","color":"white"}},{{"text":"\\n\\n"}},{{"text":"🎨 Préparez votre design ! 🎨","color":"aqua","bold":true}}]'
                
                rcon.command(player_msg)
                logger.info("✅ Tête personnalisée - notifications envoyées")
                return True
            
            # Don d'objet normal
            command = item_command_templates[item_name].format(username, quantity)
            logger.info(f"Commande d'objet: {command}")
            
            try:
                response = rcon.command(command)
                logger.info(f"Réponse commande: '{response}'")
            except Exception as e:
                logger.warning(f"Commande d'objet silencieuse: {e}")
            
            # Messages de confirmation
            quantity_text = f"{quantity}x " if quantity > 1 else ""
            
            # Message au joueur
            player_confirmation = f'tellraw {username} ["",{{"text":"✅ OBJET LIVRÉ !","color":"green","bold":true}},{{"text":"\\n\\n"}},{{"text":"📦 Vous avez reçu:","color":"white"}},{{"text":"\\n"}},{{"text":"{quantity_text}{item_name}","color":"yellow","bold":true}},{{"text":"\\n\\n"}},{{"text":"🎒 Vérifiez votre inventaire !","color":"gray"}},{{"text":"\\n"}},{{"text":"Si l\'objet n\'apparaît pas, contactez un admin.","color":"gray"}},{{"text":"\\n\\n"}},{{"text":"💎 Merci pour votre achat ! 💎","color":"aqua","bold":true}}]'
            
            rcon.command(player_confirmation)
            
            # Broadcast public
            public_message = f'tellraw @a ["",{{"text":"🛒 [BOUTIQUE] ","color":"aqua","bold":true}},{{"text":"{username} ","color":"yellow"}},{{"text":"vient d\'acheter ","color":"white"}},{{"text":"{quantity_text}{item_name}","color":"green","bold":true}},{{"text":" ! 🎉","color":"gold"}}]'
            
            rcon.command(public_message)
            
            # Son de livraison
            try:
                delivery_sound = f"execute at {username} run playsound minecraft:entity.item.pickup master {username} ~ ~ ~ 1 1.5"
                rcon.command(delivery_sound)
            except:
                pass
            
            logger.info(f"✅ Objet {item_name} livré à {username}")
            return True
            
    except Exception as e:
        logger.error(f"Erreur don d'objet: {str(e)}")
        
        # Message d'erreur au joueur
        try:
            with rcon_connection() as rcon:
                error_msg = f'tellraw {username} ["",{{"text":"⚠️ PROBLÈME DE LIVRAISON ⚠️","color":"gold","bold":true}},{{"text":"\\n"}},{{"text":"Votre achat est confirmé mais","color":"yellow"}},{{"text":"\\n"}},{{"text":"la livraison a échoué.","color":"yellow"}},{{"text":"\\n"}},{{"text":"Un admin va vous aider !","color":"green"}},{{"text":"\\n"}},{{"text":"Merci pour votre patience 💙","color":"aqua"}}]'
                rcon.command(error_msg)
        except:
            pass
        
        return False

def log_purchase_for_admin_review(username, rank_name, is_temporary, gifted_by=None):
    """
    Enregistre l'achat pour suivi administratif détaillé.
    """
    try:
        duration = "30 jours" if is_temporary else "permanent"
        timestamp = datetime.now().isoformat()
        is_gift = gifted_by is not None
        
        # Log détaillé pour les admins
        logger.info("="*60)
        if is_gift:
            logger.info("🎁 CADEAU BOUTIQUE - SUIVI ADMINISTRATIF")
            logger.info("="*60)
            logger.info(f"   💝 Offert par: {gifted_by}")
            logger.info(f"   👤 Destinataire: {username}")
        else:
            logger.info("🛒 ACHAT BOUTIQUE - SUIVI ADMINISTRATIF")
            logger.info("="*60)
            logger.info(f"   👤 Joueur: {username}")
        
        logger.info(f"   🏆 Grade: {rank_name}")
        logger.info(f"   ⏱️  Durée: {duration}")
        logger.info(f"   📅 Timestamp: {timestamp}")
        logger.info(f"   💰 Statut: Payé et confirmé")
        logger.info(f"   🔧 Action requise: /lp user {username} parent add {get_luckperms_group_name(rank_name)}")
        logger.info("="*60)
        
        # Enregistrement en base Django (optionnel)
        try:
            from minecraft_app.models import PurchaseLog
            PurchaseLog.objects.create(
                username=username,
                item_type='rank',
                item_name=rank_name,
                quantity=1,
                success=True,
                error_message=f"Attribution manuelle requise - {duration} - {timestamp}"
            )
            logger.info("✅ Achat enregistré en base Django")
        except Exception as e:
            logger.debug(f"Base Django non disponible: {e}")
            
    except Exception as e:
        logger.error(f"Erreur lors de l'enregistrement: {e}")

def check_server_status():
    """
    Vérifie si le serveur Minecraft est en ligne avec parsing robuste.
    """
    logger.info("Vérification du statut serveur")
    
    # Méthode 1: Test RCON
    try:
        with rcon_connection() as rcon:
            response = rcon.command("list")
            logger.info(f"Réponse RCON list: {response}")
            
            # Parser la réponse avec codes couleur Minecraft
            if "players online" in response and "out of maximum" in response:
                try:
                    # Pattern pour "§c60§6 out of maximum §c80§6"
                    pattern = r'§c(\d+)§6 out of maximum §c(\d+)§6'
                    match = re.search(pattern, response)
                    
                    if match:
                        current_players = int(match.group(1))
                        max_players = int(match.group(2))
                        logger.info(f"✅ Serveur en ligne: {current_players}/{max_players} joueurs")
                        return True, current_players, max_players
                    else:
                        # Fallback sans codes couleur
                        fallback_pattern = r'are (\d+) out of maximum (\d+) players'
                        fallback_match = re.search(fallback_pattern, response)
                        
                        if fallback_match:
                            current_players = int(fallback_match.group(1))
                            max_players = int(fallback_match.group(2))
                            logger.info(f"✅ Serveur en ligne (fallback): {current_players}/{max_players} joueurs")
                            return True, current_players, max_players
                        else:
                            logger.warning(f"Impossible de parser: {response}")
                            return True, 0, 100
                            
                except (ValueError, AttributeError) as e:
                    logger.warning(f"Erreur parsing: {e}")
                    return True, 0, 100
                    
            # Format standard Minecraft
            elif "There are" in response and "players online" in response:
                try:
                    pattern = r'There are (\d+) of a max of (\d+) players online'
                    match = re.search(pattern, response)
                    
                    if match:
                        current_players = int(match.group(1))
                        max_players = int(match.group(2))
                        logger.info(f"✅ Serveur en ligne (standard): {current_players}/{max_players} joueurs")
                        return True, current_players, max_players
                    else:
                        # Extraction brutale des nombres
                        numbers = re.findall(r'\d+', response)
                        if len(numbers) >= 2:
                            current_players = int(numbers[0])
                            max_players = int(numbers[1])
                            logger.info(f"✅ Serveur en ligne (extraction): {current_players}/{max_players} joueurs")
                            return True, current_players, max_players
                        else:
                            return True, 0, 100
                            
                except (ValueError, IndexError) as e:
                    logger.warning(f"Erreur parsing nombres: {e}")
                    return True, 0, 100
            else:
                # Serveur répond mais format inattendu
                logger.info(f"✅ Serveur en ligne (format inattendu): {response}")
                return True, 0, 100
                
    except Exception as e:
        logger.warning(f"Test RCON échoué: {str(e)}")
    
    # Méthode 2: Fallback socket
    try:
        host = getattr(settings, 'MINECRAFT_RCON_HOST', 'localhost')
        port = getattr(settings, 'MINECRAFT_RCON_PORT', 25575)
        
        logger.info(f"Fallback socket {host}:{port}")
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        
        try:
            result = sock.connect_ex((host, port))
            
            if result == 0:
                logger.info("✅ Serveur accessible via socket")
                return True, 0, 100
            else:
                logger.info(f"❌ Serveur non accessible, code: {result}")
                return False, 0, 0
                
        finally:
            sock.close()
            
    except Exception as e:
        logger.error(f"Erreur vérification socket: {str(e)}")
        return False, 0, 0

def test_rcon_connection():
    """
    Test simple de la connexion RCON
    """
    try:
        with rcon_connection() as rcon:
            response = rcon.command("list")
            logger.info(f"✅ Test RCON réussi: {response}")
            return True
    except Exception as e:
        logger.error(f"❌ Test RCON échoué: {str(e)}")
        return False

def test_h2_boutique_system():
    """
    Test complet du système boutique H2 optimisé.
    """
    logger.info("="*60)
    logger.info("🔍 TEST SYSTÈME BOUTIQUE H2 - VERSION FINALE")
    logger.info("="*60)
    
    success_count = 0
    total_tests = 4
    
    try:
        # Test 1: Connexion RCON de base
        print("🔍 Test 1: Connexion RCON...")
        if test_rcon_connection():
            print("✅ Test RCON: SUCCÈS")
            success_count += 1
        else:
            print("❌ Test RCON: ÉCHEC")
        
        # Test 2: Statut serveur
        print("🔍 Test 2: Statut serveur...")
        try:
            is_online, current, max_players = check_server_status()
            if is_online:
                print(f"✅ Test statut: SUCCÈS ({current}/{max_players} joueurs)")
                success_count += 1
            else:
                print("❌ Test statut: ÉCHEC")
        except Exception as e:
            print(f"❌ Test statut: ÉCHEC ({e})")
        
        # Test 3: Attribution de rang
        print("🔍 Test 3: Attribution de rang...")
        try:
            rank_success = apply_rank_to_player('SoCook', 'hero', False)
            if rank_success:
                print("✅ Test rang: SUCCÈS")
                success_count += 1
            else:
                print("❌ Test rang: ÉCHEC")
        except Exception as e:
            print(f"❌ Test rang: ÉCHEC ({e})")
        
        # Test 4: Don d'objet
        print("🔍 Test 4: Don d'objet...")
        try:
            item_success = give_store_item_to_player('SoCook', 'Coffre d\'Argent', 2)
            if item_success:
                print("✅ Test objet: SUCCÈS")
                success_count += 1
            else:
                print("❌ Test objet: ÉCHEC")
        except Exception as e:
            print(f"❌ Test objet: ÉCHEC ({e})")
        
        # Résultats finaux
        print("="*60)
        print(f"📊 RÉSULTATS FINAUX: {success_count}/{total_tests} tests réussis")
        print("="*60)
        
        if success_count >= 3:
            print("🎉 SYSTÈME BOUTIQUE H2 OPÉRATIONNEL !")
            print("✅ Votre boutique est prête à fonctionner !")
            print()
            print("📋 FONCTIONNALITÉS ACTIVÉES:")
            print("   • Messages de confirmation instantanés")
            print("   • Notifications admin avec boutons cliquables")
            print("   • Broadcasts communautaires")
            print("   • Effets sonores de célébration")
            print("   • Logs administratifs détaillés")
            print("   • Fallback robuste en cas d'erreur")
            print()
            print("🎯 POUR LES ADMINS:")
            print("   • Surveillez les notifications [BOUTIQUE ADMIN]")
            print("   • Cliquez sur [EXÉCUTER MAINTENANT] pour attribution")
            print("   • Consultez les logs Django pour le suivi")
            print()
            return True
        elif success_count >= 1:
            print("⚠️ SYSTÈME PARTIELLEMENT FONCTIONNEL")
            print("🔧 Certaines fonctionnalités peuvent être limitées")
            print("📞 Les joueurs recevront des notifications même en cas de problème")
            return True
        else:
            print("❌ PROBLÈMES CRITIQUES DÉTECTÉS")
            print("🚨 Vérifiez la configuration RCON")
            print("📝 Consultez les logs pour plus de détails")
            return False
        
    except Exception as e:
        logger.error(f"Erreur lors des tests: {e}")
        print(f"❌ Erreur critique: {e}")
        return False

# Fonctions utilitaires supplémentaires

def send_admin_alert(message):
    """
    Envoie une alerte aux administrateurs en ligne.
    """
    try:
        with rcon_connection() as rcon:
            alert_msg = f'tellraw @a[permission=luckperms.user.parent.add] ["",{{"text":"🚨 [ALERTE ADMIN] 🚨","color":"red","bold":true}},{{"text":"\\n"}},{{"text":"{message}","color":"yellow"}}]'
            rcon.command(alert_msg)
            logger.info(f"✅ Alerte admin envoyée: {message}")
            return True
    except Exception as e:
        logger.error(f"❌ Impossible d'envoyer l'alerte admin: {e}")
        return False

def send_maintenance_notice():
    """
    Envoie un message de maintenance pour la boutique.
    """
    try:
        with rcon_connection() as rcon:
            maintenance_msg = 'tellraw @a ["",{{"text":"🔧 [BOUTIQUE] 🔧","color":"gold","bold":true}},{{"text":"\\n"}},{{"text":"La boutique est temporairement en maintenance.","color":"yellow"}},{{"text":"\\n"}},{{"text":"Les achats sont suspendus.","color":"red"}},{{"text":"\\n"}},{{"text":"Merci de votre compréhension !","color":"aqua"}}]'
            rcon.command(maintenance_msg)
            logger.info("✅ Message de maintenance envoyé")
            return True
    except Exception as e:
        logger.error(f"❌ Impossible d'envoyer le message de maintenance: {e}")
        return False

def emergency_rank_attribution(username, rank_name):
    """
    Attribution d'urgence d'un rang avec méthodes multiples.
    Utilisé en cas d'échec répété du système normal.
    """
    logger.warning(f"🚨 Attribution d'urgence pour {username} -> {rank_name}")
    
    try:
        with rcon_connection() as rcon:
            # Tentative avec différentes syntaxes LuckPerms
            commands_to_try = [
                f"lp user {username} parent add {rank_name.lower()}",
                f"luckperms user {username} parent add {rank_name.lower()}",
                f"lp user {username} group add {rank_name.lower()}",
                f"perm user {username} group add {rank_name.lower()}"
            ]
            
            for cmd in commands_to_try:
                try:
                    logger.info(f"Tentative urgence: {cmd}")
                    response = rcon.command(cmd)
                    logger.info(f"Réponse: {response}")
                    
                    # Attendre et vérifier
                    time.sleep(3)
                    if verify_rank_assignment(rcon, username, rank_name.lower()):
                        logger.info(f"✅ Attribution d'urgence réussie avec: {cmd}")
                        
                        # Message de succès
                        success_msg = f'tellraw {username} ["",{{"text":"✅ GRADE ATTRIBUÉ !","color":"green","bold":true}},{{"text":"\\n"}},{{"text":"Attribution d\'urgence réussie","color":"yellow"}},{{"text":"\\n"}},{{"text":"Grade: ","color":"white"}},{{"text":"{rank_name}","color":"gold","bold":true}}]'
                        rcon.command(success_msg)
                        
                        return True
                except Exception as e:
                    logger.warning(f"Commande d'urgence échouée: {cmd} - {e}")
                    continue
            
            # Si toutes les tentatives échouent, alerter les admins
            emergency_alert = f'tellraw @a[permission=luckperms.user.parent.add] ["",{{"text":"🚨 URGENCE BOUTIQUE 🚨","color":"red","bold":true}},{{"text":"\\n"}},{{"text":"Attribution automatique impossible","color":"yellow"}},{{"text":"\\n"}},{{"text":"Joueur: {username}","color":"white"}},{{"text":"\\n"}},{{"text":"Grade: {rank_name}","color":"gold"}},{{"text":"\\n"}},{{"text":"INTERVENTION MANUELLE REQUISE","color":"red","bold":true}}]'
            
            rcon.command(emergency_alert)
            logger.error(f"❌ Toutes les tentatives d'urgence ont échoué pour {username}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Erreur critique attribution d'urgence: {e}")
        return False

def get_system_health():
    """
    Retourne l'état de santé du système boutique.
    """
    health_status = {
        'rcon_connection': False,
        'server_online': False,
        'luckperms_responsive': False,
        'overall_status': 'CRITICAL'
    }
    
    try:
        # Test connexion RCON
        if test_rcon_connection():
            health_status['rcon_connection'] = True
        
        # Test statut serveur
        is_online, _, _ = check_server_status()
        if is_online:
            health_status['server_online'] = True
        
        # Test LuckPerms (avec commande simple)
        try:
            with rcon_connection() as rcon:
                lp_response = rcon.command("lp info")
                if "LuckPerms" in lp_response or "running" in lp_response.lower():
                    health_status['luckperms_responsive'] = True
        except:
            pass
        
        # Déterminer le statut global
        if all(health_status[key] for key in ['rcon_connection', 'server_online']):
            if health_status['luckperms_responsive']:
                health_status['overall_status'] = 'EXCELLENT'
            else:
                health_status['overall_status'] = 'GOOD'  # Mode admin manual
        elif health_status['rcon_connection']:
            health_status['overall_status'] = 'LIMITED'
        else:
            health_status['overall_status'] = 'CRITICAL'
    
    except Exception as e:
        logger.error(f"Erreur lors de la vérification de santé: {e}")
    
    return health_status

def give_bundle_to_player(username, bundle):
    """
    Donne tous les objets d'un bundle à un joueur avec des messages optimisés.
    Utilise automatiquement le mapping des noms de grades français vers LuckPerms.
    """
    if not username:
        logger.error("Cannot give bundle: No Minecraft username provided")
        return False
    
    logger.info(f"Attribution du bundle {bundle.name} à {username}")
    
    try:
        with rcon_connection() as rcon:
            items = bundle.get_bundle_items()
            successful_items = []
            failed_items = []
            
            # Message d'ouverture du bundle
            bundle_start_msg = f'tellraw {username} ["",{{"text":"🎁 BUNDLE OUVERT ! 🎁","color":"gold","bold":true}},{{"text":"\\n\\n"}},{{"text":"📦 {bundle.name}","color":"yellow","bold":true}},{{"text":"\\n"}},{{"text":"Contenu en cours de livraison...","color":"gray"}},{{"text":"\\n"}}]'
            rcon.command(bundle_start_msg)
            
            # Attribution de chaque élément du bundle
            for item in items:
                item_type = item['type']
                item_name = item['name']
                quantity = item['quantity']
                
                logger.info(f"Attribution de {quantity}x {item_name} ({item_type}) du bundle {bundle.name}")
                
                try:
                    if item_type == 'rank':
                        # Attribution du rang - apply_rank_to_player gère automatiquement la conversion
                        success = apply_rank_to_player(username, item_name)
                        item_display = f"Grade {item_name}"
                        
                        # Log pour confirmer la conversion
                        luckperms_group = get_luckperms_group_name(item_name)
                        logger.info(f"Bundle - Grade {item_name} converti en groupe LuckPerms: {luckperms_group}")
                        
                    else:
                        # Attribution de l'objet
                        success = give_store_item_to_player(username, item_name, quantity)
                        item_display = f"{quantity}x {item_name}"
                    
                    if success:
                        successful_items.append(item_display)
                        logger.info(f"✅ {item_display} attribué avec succès")
                    else:
                        failed_items.append(item_display)
                        logger.error(f"❌ Échec de l'attribution de {item_display}")
                        
                    # Petit délai entre les attributions pour éviter le spam
                    time.sleep(1)
                    
                except Exception as e:
                    item_display = f"{quantity}x {item_name}" if item_type != 'rank' else f"Grade {item_name}"
                    failed_items.append(item_display)
                    logger.error(f"❌ Erreur lors de l'attribution de {item_display}: {e}")
            
            # Message de résumé du bundle
            if successful_items and not failed_items:
                # Tous les objets ont été attribués avec succès
                items_list = ", ".join(successful_items)
                success_msg = f'tellraw {username} ["",{{"text":"\\n🎉 BUNDLE COMPLET ! 🎉","color":"green","bold":true}},{{"text":"\\n\\n"}},{{"text":"✅ Tous les éléments ont été livrés :","color":"green"}},{{"text":"\\n"}},{{"text":"{items_list}","color":"yellow"}},{{"text":"\\n\\n"}},{{"text":"🎒 Vérifiez votre inventaire et vos permissions !","color":"aqua"}},{{"text":"\\n"}},{{"text":"💎 Merci pour votre achat ! 💎","color":"gold","bold":true}}]'
                rcon.command(success_msg)
                
                # Broadcast pour le bundle
                bundle_broadcast = f'tellraw @a ["",{{"text":"🎁 [BOUTIQUE] ","color":"purple","bold":true}},{{"text":"{username} ","color":"yellow"}},{{"text":"vient d\'ouvrir le ","color":"white"}},{{"text":"{bundle.name}","color":"gold","bold":true}},{{"text":" ! 🎉","color":"gold"}}]'
                rcon.command(bundle_broadcast)
                
                # Son de succès du bundle - CORRIGÉ (plus de spam)
                try:
                    # Son pour l'acheteur
                    success_sound = f"execute at {username} run playsound minecraft:entity.player.levelup master {username} ~ ~ ~ 1 1.2"
                    rcon.command(success_sound)
                    
                    # Son global discret pour le bundle - CORRIGÉ
                    bundle_sound = "playsound minecraft:block.note_block.chime master @a ~ ~ ~ 0.3 1.5"
                    rcon.command(bundle_sound)
                except:
                    pass
                
                logger.info(f"✅ Bundle {bundle.name} entièrement attribué à {username}")
                return True
                
            elif successful_items and failed_items:
                # Attribution partielle
                success_list = ", ".join(successful_items)
                failed_list = ", ".join(failed_items)
                
                partial_msg = f'tellraw {username} ["",{{"text":"⚠️ BUNDLE PARTIELLEMENT LIVRÉ ⚠️","color":"yellow","bold":true}},{{"text":"\\n\\n"}},{{"text":"✅ Éléments livrés :","color":"green"}},{{"text":"\\n"}},{{"text":"{success_list}","color":"yellow"}},{{"text":"\\n\\n"}},{{"text":"❌ Éléments en attente :","color":"red"}},{{"text":"\\n"}},{{"text":"{failed_list}","color":"red"}},{{"text":"\\n\\n"}},{{"text":"Un administrateur va vous aider !","color":"aqua"}}]'
                rcon.command(partial_msg)
                
                # Alerte aux admins avec détails des groupes LuckPerms
                failed_ranks = [item for item in failed_items if "Grade" in item]
                failed_ranks_luckperms = []
                for failed_rank in failed_ranks:
                    rank_name = failed_rank.replace("Grade ", "")
                    luckperms_group = get_luckperms_group_name(rank_name)
                    failed_ranks_luckperms.append(f"{rank_name} (LuckPerms: {luckperms_group})")
                
                admin_alert = f'tellraw @a[permission=minecraft.command.give] ["",{{"text":"⚠️ [BUNDLE ADMIN] ⚠️","color":"orange","bold":true}},{{"text":"\\n"}},{{"text":"Bundle partiellement livré :","color":"yellow"}},{{"text":"\\n"}},{{"text":"👤 Joueur: {username}","color":"white"}},{{"text":"\\n"}},{{"text":"📦 Bundle: {bundle.name}","color":"gold"}},{{"text":"\\n"}},{{"text":"❌ Éléments manquants: {failed_list}","color":"red"}},{{"text":"\\n"}},{{"text":"💰 Achat payé et confirmé ✅","color":"green"}}]'
                rcon.command(admin_alert)
                
                logger.warning(f"⚠️ Bundle {bundle.name} partiellement attribué à {username}")
                return False
                
            else:
                # Aucun élément n'a pu être attribué
                failed_list = ", ".join(failed_items) if failed_items else "Tous les éléments"
                
                error_msg = f'tellraw {username} ["",{{"text":"❌ PROBLÈME DE LIVRAISON ❌","color":"red","bold":true}},{{"text":"\\n\\n"}},{{"text":"Votre bundle a été acheté mais","color":"yellow"}},{{"text":"\\n"}},{{"text":"la livraison a échoué.","color":"yellow"}},{{"text":"\\n"}},{{"text":"Un admin va vous aider !","color":"green"}},{{"text":"\\n\\n"}},{{"text":"Bundle: {bundle.name}","color":"gold"}},{{"text":"\\n"}},{{"text":"Contenu: {failed_list}","color":"red"}}]'
                rcon.command(error_msg)
                
                # Alerte urgente aux admins avec groupes LuckPerms
                urgent_alert = f'tellraw @a[permission=minecraft.command.give] ["",{{"text":"🚨 [BUNDLE URGENT] 🚨","color":"red","bold":true}},{{"text":"\\n"}},{{"text":"Bundle non livré :","color":"red"}},{{"text":"\\n"}},{{"text":"👤 Joueur: {username}","color":"white"}},{{"text":"\\n"}},{{"text":"📦 Bundle: {bundle.name}","color":"gold"}},{{"text":"\\n"}},{{"text":"❌ Aucun élément livré","color":"red"}},{{"text":"\\n"}},{{"text":"💰 ACHAT PAYÉ - INTERVENTION REQUISE","color":"red","bold":true}}]'
                rcon.command(urgent_alert)
                
                logger.error(f"❌ Aucun élément du bundle {bundle.name} n'a pu être attribué à {username}")
                return False
            
    except Exception as e:
        logger.error(f"Erreur critique lors de l'attribution du bundle {bundle.name}: {str(e)}")
        
        # Message d'erreur de fallback
        try:
            with rcon_connection() as rcon:
                fallback_msg = f'tellraw {username} ["",{{"text":"⚠️ BUNDLE ACHETÉ ⚠️","color":"gold","bold":true}},{{"text":"\\n"}},{{"text":"Votre paiement a été traité mais","color":"yellow"}},{{"text":"\\n"}},{{"text":"l\'attribution nécessite une intervention.","color":"yellow"}},{{"text":"\\n"}},{{"text":"Un admin vous contactera rapidement !","color":"green"}},{{"text":"\\n"}},{{"text":"Bundle: {bundle.name}","color":"gold"}},{{"text":"\\n"}},{{"text":"Merci pour votre patience 💙","color":"aqua"}}]'
                rcon.command(fallback_msg)
        except:
            logger.error("❌ Impossible d'envoyer le message de fallback pour le bundle")
        
        return False

def send_bundle_notification_to_admins(username, bundle_name, items_list, status="purchased"):
    """
    Envoie une notification aux admins concernant un achat de bundle.
    """
    try:
        with rcon_connection() as rcon:
            if status == "purchased":
                status_text = "💰 BUNDLE ACHETÉ"
                color = "green"
            elif status == "failed":
                status_text = "❌ ÉCHEC BUNDLE"
                color = "red"
            else:
                status_text = "⚠️ BUNDLE PARTIEL"
                color = "yellow"
            
            admin_msg = f'tellraw @a[permission=minecraft.command.give] ["",{{"text":"{status_text}","color":"{color}","bold":true}},{{"text":"\\n"}},{{"text":"Joueur: {username}","color":"white"}},{{"text":"\\n"}},{{"text":"Bundle: {bundle_name}","color":"gold"}},{{"text":"\\n"}},{{"text":"Contenu: {items_list}","color":"gray"}}]'
            rcon.command(admin_msg)
            
    except Exception as e:
        logger.error(f"Erreur lors de l'envoi de notification bundle aux admins: {e}")

def log_bundle_purchase_for_admin_review(username, bundle_name, items_list):
    """
    Enregistre l'achat de bundle pour suivi administratif.
    """
    try:
        timestamp = datetime.now().isoformat()
        
        logger.info("="*60)
        logger.info("🎁 ACHAT BUNDLE - SUIVI ADMINISTRATIF")
        logger.info("="*60)
        logger.info(f"   👤 Joueur: {username}")
        logger.info(f"   📦 Bundle: {bundle_name}")
        logger.info(f"   📋 Contenu: {items_list}")
        logger.info(f"   📅 Timestamp: {timestamp}")
        logger.info(f"   💰 Statut: Payé et confirmé")
        logger.info("="*60)
        
    except Exception as e:
        logger.error(f"Erreur lors de l'enregistrement du bundle: {e}")

# Ajoutez ces fonctions à la fin de minecraft_app/minecraft_service.py

def remove_rank_from_player(username, rank_name):
    """
    Retire un grade d'un joueur (pour les subscriptions expirées).
    
    Args:
        username: Le joueur à qui retirer le grade
        rank_name: Le nom du grade à retirer
    
    Returns:
        bool: True si le retrait a réussi, False sinon
    """
    if not username:
        logger.error("Cannot remove rank: No Minecraft username provided")
        return False
    
    # Convertir le nom du grade vers le nom LuckPerms
    luckperms_group = get_luckperms_group_name(rank_name)
    
    logger.info(f"Retrait du grade mensuel expiré: {rank_name} (LuckPerms: {luckperms_group}) de {username}")
    
    try:
        with rcon_connection() as rcon:
            # Commande LuckPerms pour retirer le groupe
            lp_command = f"lp user {username} parent remove {luckperms_group}"
            
            logger.info(f"Commande LuckPerms: {lp_command}")
            try:
                lp_response = rcon.command(lp_command)
                logger.info(f"Réponse LuckPerms: '{lp_response}'")
                
                # Attendre un peu pour que LuckPerms traite la commande
                time.sleep(2)
                
                # Vérifier si le retrait a fonctionné
                success = verify_rank_removal(rcon, username, luckperms_group)
                if success:
                    logger.info(f"✅ Retrait automatique réussi pour {username}")
                    send_expiration_messages(rcon, username, rank_name)
                    return True
                else:
                    logger.warning(f"⚠️ Retrait automatique échoué, notification admin")
                    
            except Exception as e:
                logger.warning(f"Commande LuckPerms échouée: {e}")
            
            # Mode admin : Message si le retrait automatique échoue
            player_message = f'tellraw {username} ["\\n",{{"text":"⏰ GRADE MENSUEL EXPIRÉ ⏰","color":"orange","bold":true}},{{"text":"\\n\\n"}},{{"text":"Votre grade mensuel {rank_name} a expiré.","color":"yellow"}},{{"text":"\\n"}},{{"text":"Retrait en cours...","color":"gray"}},{{"text":"\\n"}},{{"text":"Vous pouvez le renouveler sur notre site !","color":"aqua"}},{{"text":"\\n\\n"}},{{"text":"💙 Merci pour votre soutien ! 💙","color":"blue","bold":true}}]'
            
            admin_notification = f'tellraw @a[permission=luckperms.user.parent.remove] ["",{{"text":"\\n"}},{{"text":"⏰ [SUBSCRIPTION EXPIRÉE] ⏰","color":"orange","bold":true}},{{"text":"\\n"}},{{"text":"Retrait de grade mensuel requis:","color":"yellow"}},{{"text":"\\n"}},{{"text":"👤 Joueur: ","color":"white"}},{{"text":"{username}","color":"yellow","bold":true}},{{"text":"\\n"}},{{"text":"🏆 Grade: ","color":"white"}},{{"text":"{rank_name}","color":"orange","bold":true}},{{"text":"\\n"}},{{"text":"🔧 Groupe LuckPerms: ","color":"white"}},{{"text":"{luckperms_group}","color":"aqua","bold":true}},{{"text":"\\n"}},{{"text":"📅 Subscription expirée","color":"red"}},{{"text":"\\n\\n"}},{{"text":"🔧 Cliquez pour retirer: ","color":"gray"}},{{"text":"[EXÉCUTER MAINTENANT]","color":"red","bold":true,"underlined":true,"clickEvent":{{"action":"run_command","value":"{lp_command}"}},"hoverEvent":{{"action":"show_text","value":"Cliquez pour exécuter:\\n{lp_command}"}}}}]'
            
            # Envoyer les messages
            rcon.command(player_message)
            logger.info("✅ Message d'expiration envoyé au joueur")
            
            rcon.command(admin_notification)
            logger.info("✅ Notification admin envoyée")
            
            # Log administratif
            log_expiration_for_admin_review(username, rank_name)
            
            logger.info(f"✅ Processus d'expiration complété: {rank_name} retiré de {username}")
            return True
            
    except Exception as e:
        logger.error(f"Erreur critique lors du retrait du grade: {str(e)}")
        
        # Fallback
        try:
            with rcon_connection() as rcon:
                fallback_message = f'tellraw {username} ["",{{"text":"⚠️ GRADE EXPIRÉ ⚠️","color":"orange","bold":true}},{{"text":"\\n"}},{{"text":"Votre grade mensuel a expiré mais","color":"yellow"}},{{"text":"\\n"}},{{"text":"le retrait nécessite une intervention.","color":"yellow"}},{{"text":"\\n"}},{{"text":"Un admin va s\'en occuper !","color":"green"}},{{"text":"\\n"}},{{"text":"Merci pour votre patience 💙","color":"aqua"}}]'
                rcon.command(fallback_message)
                logger.info("✅ Message de fallback expiration envoyé")
        except:
            logger.error("❌ Impossible d'envoyer le message de fallback d'expiration")
        
        return False

def verify_rank_removal(rcon, username, lp_group):
    """
    Vérifie que le rang a bien été retiré au joueur.
    """
    try:
        check_command = f"lp user {username} info"
        resp = rcon.command(check_command)
        logger.info(f"Vérification pour {username}: {resp}")
        
        if lp_group.lower() not in resp.lower():
            logger.info(f"✅ Confirmation: {username} n'a plus le groupe {lp_group}")
            return True
        else:
            logger.warning(f"❌ Groupe {lp_group} encore présent pour {username}")
            return False
            
    except Exception as e:
        logger.error(f"Erreur vérification retrait rang: {str(e)}")
        return False

def send_expiration_messages(rcon, username, rank_name):
    """
    Envoie les messages d'expiration quand le retrait automatique fonctionne.
    """
    try:
        # Message de confirmation au joueur
        success_message = f'tellraw {username} ["\\n",{{"text":"⏰ GRADE MENSUEL EXPIRÉ ⏰","color":"orange","bold":true}},{{"text":"\\n\\n"}},{{"text":"✅ Grade retiré automatiquement","color":"green"}},{{"text":"\\n"}},{{"text":"🏆 Grade expiré: ","color":"white"}},{{"text":"{rank_name}","color":"orange","bold":true}},{{"text":"\\n\\n"}},{{"text":"🔄 Vous pouvez le renouveler sur notre site !","color":"aqua"}},{{"text":"\\n"}},{{"text":"💙 Merci pour votre soutien passé ! 💙","color":"blue","bold":true}}]'
        
        rcon.command(success_message)
        logger.info(f"✅ Message d'expiration automatique envoyé à {username}")
        
        # Son d'expiration (discret)
        try:
            expiration_sound = f"execute at {username} run playsound minecraft:block.note_block.bass master {username} ~ ~ ~ 0.5 0.8"
            rcon.command(expiration_sound)
            logger.info("✅ Son d'expiration joué")
        except Exception as e:
            logger.debug(f"Son d'expiration non joué: {e}")
        
    except Exception as e:
        logger.error(f"❌ Erreur dans send_expiration_messages: {e}")

def log_expiration_for_admin_review(username, rank_name):
    """
    Enregistre l'expiration pour suivi administratif.
    """
    try:
        timestamp = datetime.now().isoformat()
        
        logger.info("="*60)
        logger.info("⏰ EXPIRATION GRADE MENSUEL - SUIVI ADMINISTRATIF")
        logger.info("="*60)
        logger.info(f"   👤 Joueur: {username}")
        logger.info(f"   🏆 Grade: {rank_name}")
        logger.info(f"   📅 Timestamp: {timestamp}")
        logger.info(f"   🔄 Statut: Grade mensuel expiré et retiré")
        logger.info(f"   💡 Action: Le joueur peut souscrire à nouveau")
        logger.info("="*60)
        
    except Exception as e:
        logger.error(f"Erreur lors de l'enregistrement d'expiration: {e}")