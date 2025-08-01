def server_status(request):
    """
    Context processor pour inclure le statut du serveur Minecraft dans tous les templates.
    """
    from minecraft_app.models import TownyServer
    import logging
    
    logger = logging.getLogger('minecraft_app')
    
    try:
        server = TownyServer.objects.first()
        if not server:
            server = TownyServer.objects.create(
                name="Novania - Earth Towny",
                ip_address="play.Novania.fr",
                description="Towny server on a 1:1000 scale Earth map"
            )
            logger.info("Objet TownyServer créé dans le context processor")
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du statut du serveur: {str(e)}", exc_info=True)
        # Créer un objet temporaire pour éviter les erreurs de template
        from django.db.models.base import ModelBase
        server = type('TempServer', (object,), {
            'name': "Novania - Earth Towny",
            'ip_address': "play.Novania.fr",
            'description': "Towny server on a 1:1000 scale Earth map",
            'status': False,
            'player_count': 0,
            'max_players': 100,
            'version': "1.20.4"
        })
    
    return {
        'server': server,
    }