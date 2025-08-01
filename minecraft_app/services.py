import requests
import json
import logging

logger = logging.getLogger(__name__)

def fetch_minecraft_uuid(username):
    """
    Récupère l'UUID Minecraft d'un utilisateur à partir de son nom d'utilisateur.
    Utilise l'API Mojang.
    
    Args:
        username (str): Nom d'utilisateur Minecraft
        
    Returns:
        str: UUID de l'utilisateur (sans tirets) ou None si non trouvé
    """
    if not username:
        return None
        
    try:
        url = f"https://api.mojang.com/users/profiles/minecraft/{username}"
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            return data.get('id')  # UUID sans tirets
        elif response.status_code == 204 or response.status_code == 404:
            logger.warning(f"Utilisateur Minecraft non trouvé: {username}")
            return None
        else:
            logger.error(f"Erreur lors de la récupération de l'UUID: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"Exception lors de la récupération de l'UUID: {str(e)}")
        return None

def format_uuid_with_dashes(uuid):
    """
    Ajoute des tirets à l'UUID au format standard.
    
    Args:
        uuid (str): UUID sans tirets
        
    Returns:
        str: UUID avec tirets au format standard
    """
    if not uuid or len(uuid) != 32:
        return uuid
        
    return f"{uuid[0:8]}-{uuid[8:12]}-{uuid[12:16]}-{uuid[16:20]}-{uuid[20:32]}"

def update_server_status():
    """
    Met à jour le statut du serveur dans la base de données.
    """
    from .models import TownyServer
    from .minecraft_service import check_server_status
    import logging
    
    logger = logging.getLogger('minecraft_app')
    
    try:
        # Vérifier le statut du serveur
        is_online, player_count, max_players = check_server_status()
        
        # Mettre à jour le modèle
        server = TownyServer.objects.first()
        if not server:
            server = TownyServer.objects.create(
                name="Novania - Earth Towny",
                ip_address="play.Novania.fr",
                description="Towny server on a 1:1000 scale Earth map"
            )
        
        server.status = is_online
        server.player_count = player_count
        server.max_players = max_players
        server.save()
        logger.info(f"Statut du serveur mis à jour: En ligne={is_online}, Joueurs={player_count}/{max_players}")
        
        return is_online, player_count, max_players
        
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour du statut du serveur: {str(e)}", exc_info=True)
        return False, 0, 0