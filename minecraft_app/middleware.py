import time
import logging
import threading
from django.conf import settings

logger = logging.getLogger('minecraft_app')

class ServerStatusMiddleware:
    """
    Middleware qui vérifie périodiquement le statut du serveur Minecraft
    """
    def __init__(self, get_response):
        self.get_response = get_response
        self.status_check_interval = getattr(settings, 'SERVER_STATUS_CHECK_INTERVAL', 120) # 2 minutes par défaut
        self.last_check_time = 0
        self.checking = False
        logger.info(f"ServerStatusMiddleware initialisé avec intervalle de {self.status_check_interval} secondes")

    def __call__(self, request):
        # Vérifier si nous devons mettre à jour le statut
        current_time = time.time()
        
        # Si assez de temps est passé et qu'aucune vérification n'est en cours
        if not self.checking and current_time - self.last_check_time > self.status_check_interval:
            self.checking = True
            self.last_check_time = current_time
            
            # Lancer la vérification dans un thread pour ne pas bloquer la requête
            thread = threading.Thread(target=self._check_status)
            thread.daemon = True
            thread.start()
        
        response = self.get_response(request)
        return response
    
    def _check_status(self):
        """Vérifie le statut du serveur en arrière-plan"""
        try:
            from .services import update_server_status
            
            # Mettre à jour le statut
            is_online, player_count, max_players = update_server_status()
            logger.info(f"Middleware: Statut du serveur mis à jour, en ligne={is_online}, joueurs={player_count}/{max_players}")
            
        except Exception as e:
            logger.error(f"Middleware: Erreur lors de la vérification du statut: {str(e)}", exc_info=True)
        finally:
            self.checking = False