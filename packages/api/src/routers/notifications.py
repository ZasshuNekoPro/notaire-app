"""
Routes WebSocket pour les notifications temps réel.
Connexions authentifiées JWT + Redis Pub/Sub pour diffusion alertes.
"""
import json
import logging
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException, status
from fastapi.responses import JSONResponse
import redis.asyncio as redis
import jwt
from pydantic import BaseModel

from src.auth.jwt import verify_jwt_token, JWT_SECRET, JWT_ALGORITHM
from src.models.auth import User
from src.models.veille import Alerte, NiveauImpact


router = APIRouter(prefix="/ws", tags=["WebSocket Notifications"])
logger = logging.getLogger(__name__)


# === Modèles de messages === #

class NotificationMessage(BaseModel):
    """Modèle de message de notification WebSocket."""
    type: str  # "alerte", "info", "warning", "error"
    alerte_id: str
    dossier_id: Optional[str] = None
    titre: str
    impact: str
    timestamp: str
    details: Optional[Dict] = None


# === Gestionnaire de connexions === #

class ConnectionManager:
    """
    Gestionnaire des connexions WebSocket actives.
    Maintient les connexions par user_id et gère la diffusion.
    """

    def __init__(self):
        # Connexions actives : user_id → WebSocket
        self.active_connections: Dict[UUID, WebSocket] = {}
        # Métadonnées des connexions : user_id → user_info
        self.user_metadata: Dict[UUID, Dict] = {}

    async def connect(self, user_id: UUID, websocket: WebSocket, user: User):
        """
        Établit une connexion WebSocket pour un utilisateur.

        Args:
            user_id: ID de l'utilisateur
            websocket: Connexion WebSocket
            user: Objet utilisateur avec rôles
        """
        await websocket.accept()

        # Fermer connexion existante si elle existe
        if user_id in self.active_connections:
            await self.disconnect(user_id)

        self.active_connections[user_id] = websocket
        self.user_metadata[user_id] = {
            "email": user.email,
            "role": user.role,
            "connected_at": "2025-03-13T15:00:00",  # datetime.now().isoformat()
            "ip": "127.0.0.1"  # websocket.client.host si disponible
        }

        logger.info(f"WebSocket connecté: user {user_id} ({user.email})")

        # Message de bienvenue
        await self.send_to_user(user_id, {
            "type": "info",
            "titre": "Connexion établie",
            "message": f"Notifications temps réel activées pour {user.email}",
            "timestamp": "2025-03-13T15:00:00"
        })

    async def disconnect(self, user_id: UUID):
        """
        Ferme la connexion WebSocket d'un utilisateur.

        Args:
            user_id: ID de l'utilisateur à déconnecter
        """
        if user_id in self.active_connections:
            websocket = self.active_connections[user_id]

            try:
                await websocket.close()
            except Exception as e:
                logger.warning(f"Erreur fermeture WebSocket {user_id}: {e}")

            del self.active_connections[user_id]
            del self.user_metadata[user_id]

            logger.info(f"WebSocket déconnecté: user {user_id}")

    async def send_to_user(self, user_id: UUID, message: Dict):
        """
        Envoie un message à un utilisateur spécifique.

        Args:
            user_id: ID de l'utilisateur destinataire
            message: Message JSON à envoyer
        """
        if user_id not in self.active_connections:
            logger.warning(f"Tentative envoi à user {user_id} non connecté")
            return False

        websocket = self.active_connections[user_id]

        try:
            await websocket.send_text(json.dumps(message))
            logger.debug(f"Message envoyé à {user_id}: {message.get('type', 'unknown')}")
            return True

        except Exception as e:
            logger.error(f"Erreur envoi WebSocket à {user_id}: {e}")
            # Nettoyer la connexion fermée
            await self.disconnect(user_id)
            return False

    async def broadcast_to_role(self, role: str, message: Dict):
        """
        Diffuse un message à tous les utilisateurs d'un rôle.

        Args:
            role: Rôle des destinataires ("notaire", "clerc", "admin")
            message: Message JSON à diffuser
        """
        sent_count = 0
        users_to_remove = []

        for user_id, metadata in self.user_metadata.items():
            if metadata.get("role") == role:
                success = await self.send_to_user(user_id, message)
                if success:
                    sent_count += 1
                else:
                    users_to_remove.append(user_id)

        # Nettoyer les connexions fermées
        for user_id in users_to_remove:
            if user_id in self.active_connections:
                await self.disconnect(user_id)

        logger.info(f"Broadcast role '{role}': {sent_count} utilisateurs")
        return sent_count

    async def broadcast_to_all(self, message: Dict):
        """
        Diffuse un message à toutes les connexions actives.

        Args:
            message: Message JSON à diffuser
        """
        sent_count = 0
        users_to_remove = []

        for user_id in list(self.active_connections.keys()):
            success = await self.send_to_user(user_id, message)
            if success:
                sent_count += 1
            else:
                users_to_remove.append(user_id)

        # Nettoyer les connexions fermées
        for user_id in users_to_remove:
            if user_id in self.active_connections:
                await self.disconnect(user_id)

        logger.info(f"Broadcast global: {sent_count} utilisateurs")
        return sent_count

    def get_active_users(self) -> List[Dict]:
        """
        Retourne la liste des utilisateurs connectés.

        Returns:
            Liste des métadonnées des utilisateurs connectés
        """
        return [
            {"user_id": str(user_id), **metadata}
            for user_id, metadata in self.user_metadata.items()
        ]

    def get_connection_count(self) -> int:
        """
        Retourne le nombre de connexions actives.

        Returns:
            Nombre de connexions WebSocket actives
        """
        return len(self.active_connections)


# === Instance globale du gestionnaire === #

connection_manager = ConnectionManager()


# === Authentification WebSocket === #

async def authenticate_websocket(token: str) -> Optional[User]:
    """
    Authentifie un token JWT pour WebSocket.

    Args:
        token: Token JWT depuis query parameter

    Returns:
        Utilisateur authentifié ou None si invalide
    """
    try:
        # Décoder le token JWT
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")

        if not user_id:
            return None

        # TODO: Récupérer l'utilisateur depuis la DB
        # Pour simulation, créer un user de test
        user = User(
            id=UUID(user_id),
            email=payload.get("email", "test@notaire.fr"),
            role=payload.get("role", "notaire"),
            is_active=True
        )

        return user

    except jwt.ExpiredSignatureError:
        logger.warning("Token JWT expiré pour WebSocket")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Token JWT invalide pour WebSocket: {e}")
        return None
    except Exception as e:
        logger.error(f"Erreur authentification WebSocket: {e}")
        return None


# === Routes WebSocket === #

@router.websocket("/notifications")
async def websocket_notifications(
    websocket: WebSocket,
    token: str = Query(..., description="Token JWT pour authentification")
):
    """
    WebSocket pour notifications temps réel.

    **Authentification** : Token JWT dans query parameter
    **Format messages** : JSON avec type, alerte_id, titre, impact, timestamp

    **Usage** :
    ```javascript
    const ws = new WebSocket(`ws://localhost:8000/ws/notifications?token=${jwt_token}`);
    ```
    """
    user = None
    user_id = None

    try:
        # Authentification JWT
        user = await authenticate_websocket(token)
        if not user:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        user_id = user.id

        # Établir la connexion
        await connection_manager.connect(user_id, websocket, user)

        # Boucle d'écoute des messages
        while True:
            try:
                # Recevoir message du client (heartbeat, acknowledgements, etc.)
                data = await websocket.receive_text()

                try:
                    message = json.loads(data)
                    message_type = message.get("type")

                    # Traiter les messages du client
                    if message_type == "ping":
                        # Heartbeat
                        await connection_manager.send_to_user(user_id, {
                            "type": "pong",
                            "timestamp": "2025-03-13T15:00:00"
                        })

                    elif message_type == "mark_read":
                        # Marquer une alerte comme lue
                        alerte_id = message.get("alerte_id")
                        logger.info(f"Alerte {alerte_id} marquée lue par {user_id}")
                        # TODO: Intégrer avec service alertes

                    else:
                        logger.debug(f"Message WebSocket non géré: {message_type}")

                except json.JSONDecodeError:
                    logger.warning(f"Message WebSocket invalide de {user_id}: {data}")

            except WebSocketDisconnect:
                logger.info(f"Client {user_id} déconnecté volontairement")
                break

    except Exception as e:
        logger.error(f"Erreur WebSocket {user_id}: {e}")

    finally:
        # Nettoyage de la connexion
        if user_id:
            await connection_manager.disconnect(user_id)


# === Fonctions utilitaires pour diffusion === #

async def diffuser_alerte_websocket(alerte: Alerte):
    """
    Diffuse une nouvelle alerte via WebSocket à tous les utilisateurs concernés.

    Args:
        alerte: Alerte à diffuser
    """
    try:
        # Construction du message de notification
        message = NotificationMessage(
            type="alerte",
            alerte_id=str(alerte.id),
            dossier_id=str(alerte.dossiers_impactes[0]) if alerte.dossiers_impactes else None,
            titre=alerte.titre,
            impact=alerte.niveau_impact.value,
            timestamp="2025-03-13T15:00:00",  # alerte.created_at.isoformat()
            details={
                "contenu": alerte.contenu,
                "source": alerte.veille_rule.type_source.value if alerte.veille_rule else "unknown",
                "url_source": alerte.url_source
            }
        ).model_dump()

        # Diffusion selon le niveau d'impact
        if alerte.niveau_impact == NiveauImpact.CRITIQUE:
            # Alertes critiques → tous les notaires et admins
            await connection_manager.broadcast_to_role("notaire", message)
            await connection_manager.broadcast_to_role("admin", message)

        elif alerte.niveau_impact == NiveauImpact.FORT:
            # Alertes fortes → notaires
            await connection_manager.broadcast_to_role("notaire", message)

        else:
            # Autres alertes → utilisateurs concernés ou tous
            await connection_manager.broadcast_to_all(message)

        logger.info(f"Alerte {alerte.id} diffusée via WebSocket ({alerte.niveau_impact})")

    except Exception as e:
        logger.error(f"Erreur diffusion WebSocket alerte {alerte.id}: {e}")


async def diffuser_message_info(titre: str, message: str, role: Optional[str] = None):
    """
    Diffuse un message d'information via WebSocket.

    Args:
        titre: Titre du message
        message: Contenu du message
        role: Rôle destinataire (None = tous)
    """
    try:
        notification = {
            "type": "info",
            "titre": titre,
            "message": message,
            "timestamp": "2025-03-13T15:00:00"
        }

        if role:
            await connection_manager.broadcast_to_role(role, notification)
        else:
            await connection_manager.broadcast_to_all(notification)

        logger.info(f"Message info diffusé: {titre}")

    except Exception as e:
        logger.error(f"Erreur diffusion message info: {e}")


# === Routes de gestion (admin) === #

@router.get("/admin/connections")
async def lister_connexions_actives():
    """
    Liste les connexions WebSocket actives.
    Route admin pour monitoring.
    """
    try:
        connexions = connection_manager.get_active_users()

        return {
            "total_connexions": connection_manager.get_connection_count(),
            "connexions": connexions,
            "timestamp": "2025-03-13T15:00:00"
        }

    except Exception as e:
        logger.error(f"Erreur liste connexions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération des connexions"
        )


@router.post("/admin/broadcast")
async def diffuser_message_admin(
    titre: str = Query(..., description="Titre du message"),
    message: str = Query(..., description="Contenu du message"),
    role: Optional[str] = Query(None, description="Rôle destinataire")
):
    """
    Diffuse un message administrateur via WebSocket.
    Route admin pour communication d'urgence.
    """
    try:
        await diffuser_message_info(titre, message, role)

        return {
            "success": True,
            "message": f"Message diffusé",
            "destinataires": role or "tous",
            "timestamp": "2025-03-13T15:00:00"
        }

    except Exception as e:
        logger.error(f"Erreur diffusion admin: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la diffusion du message"
        )


# === Intégration Redis Pub/Sub === #

class RedisNotificationHandler:
    """
    Gestionnaire Redis Pub/Sub pour les notifications entre services.
    Permet la diffusion d'alertes depuis d'autres services.
    """

    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.redis_url = redis_url
        self.redis_client = None
        self.subscriber = None

    async def start_listening(self):
        """
        Démarre l'écoute Redis Pub/Sub pour les nouvelles alertes.
        """
        try:
            self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
            self.subscriber = self.redis_client.pubsub()

            # S'abonner au canal des alertes
            await self.subscriber.subscribe("notaire_alertes")

            logger.info("Redis Pub/Sub démarré pour notifications")

            # Boucle d'écoute
            async for message in self.subscriber.listen():
                if message["type"] == "message":
                    await self._traiter_message_redis(message["data"])

        except Exception as e:
            logger.error(f"Erreur Redis Pub/Sub: {e}")

    async def _traiter_message_redis(self, data: str):
        """
        Traite un message Redis et le diffuse via WebSocket.

        Args:
            data: Message JSON depuis Redis
        """
        try:
            message_data = json.loads(data)

            # Vérifier le format du message
            if message_data.get("type") == "nouvelle_alerte":
                alerte_id = message_data.get("alerte_id")

                # TODO: Récupérer l'alerte complète depuis la DB
                # et la diffuser via diffuser_alerte_websocket()

                logger.info(f"Nouvelle alerte reçue via Redis: {alerte_id}")

        except json.JSONDecodeError:
            logger.warning(f"Message Redis invalide: {data}")
        except Exception as e:
            logger.error(f"Erreur traitement message Redis: {e}")

    async def publier_alerte(self, alerte_id: str):
        """
        Publie une nouvelle alerte sur Redis.

        Args:
            alerte_id: ID de l'alerte à publier
        """
        try:
            if not self.redis_client:
                self.redis_client = redis.from_url(self.redis_url, decode_responses=True)

            message = {
                "type": "nouvelle_alerte",
                "alerte_id": alerte_id,
                "timestamp": "2025-03-13T15:00:00"
            }

            await self.redis_client.publish("notaire_alertes", json.dumps(message))
            logger.info(f"Alerte {alerte_id} publiée sur Redis")

        except Exception as e:
            logger.error(f"Erreur publication Redis: {e}")

    async def stop(self):
        """Arrête proprement le gestionnaire Redis."""
        try:
            if self.subscriber:
                await self.subscriber.close()
            if self.redis_client:
                await self.redis_client.close()
            logger.info("Redis Pub/Sub arrêté")
        except Exception as e:
            logger.error(f"Erreur arrêt Redis: {e}")


# Instance globale du gestionnaire Redis
redis_handler = RedisNotificationHandler()