"""
═══════════════════════════════════════════════════════════════════════════════
ENDPOINTS FASTAPI GOOGLE DRIVE - COMPLETS ET ROBUSTES
À ajouter dans votre backend principal
═══════════════════════════════════════════════════════════════════════════════
"""

from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import RedirectResponse
from typing import Optional

# Supposant que drive_manager est initialisé
# from backend_GOOGLE_DRIVE_ULTIME import drive_manager, drive_monitor

def add_google_drive_endpoints(app: FastAPI):
    """Ajouter tous les endpoints Google Drive"""
    
    # ═══════════════════════════════════════════════════════════════════════
    # OAUTH 2.0
    # ═══════════════════════════════════════════════════════════════════════
    
    @app.get("/auth/google/connect")
    async def google_connect(teacher_id: str):
        """
        Initier connexion Google OAuth
        Renvoie l'URL d'autorisation
        """
        try:
            auth_url = await drive_manager.get_oauth_authorization_url(teacher_id)
            return {"success": True, "authorization_url": auth_url}
        except HTTPException as e:
            raise e
        except Exception as e:
            raise HTTPException(500, f"Erreur: {str(e)}")
    
    @app.get("/auth/google/callback")
    async def google_callback(code: str, state: str):
        """
        Callback OAuth après autorisation
        """
        try:
            teacher_id = state
            
            # Échanger code
            token_data = await drive_manager.exchange_oauth_code(code, teacher_id)
            
            # Rediriger vers frontend
            frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
            return RedirectResponse(
                url=f"{frontend_url}/analyse?google_drive_connected=true"
            )
            
        except Exception as e:
            frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
            return RedirectResponse(
                url=f"{frontend_url}/analyse?google_drive_connected=false&error={str(e)}"
            )
    
    @app.get("/api/google-drive/status/{teacher_id}")
    async def google_drive_status(teacher_id: str):
        """
        Vérifier statut connexion Google Drive
        """
        try:
            # Tester OAuth
            credentials = await drive_manager.get_oauth_credentials(teacher_id)
            
            if credentials:
                # Tester accès
                service, auth_method, error = await drive_manager.get_drive_service(teacher_id)
                
                if service:
                    try:
                        about = service.about().get(fields="user").execute()
                        return {
                            "success": True,
                            "connected": True,
                            "auth_method": "oauth",
                            "user_email": about['user']['emailAddress'],
                            "user_name": about['user']['displayName'],
                            "message": "Connecté via Google OAuth"
                        }
                    except:
                        pass
            
            # Vérifier Service Account
            if drive_manager.service_account_email:
                return {
                    "success": True,
                    "connected": True,
                    "auth_method": "service_account",
                    "service_email": drive_manager.service_account_email,
                    "message": f"Service Account actif: {drive_manager.service_account_email}"
                }
            
            return {
                "success": True,
                "connected": False,
                "message": "Aucune connexion Google Drive active"
            }
            
        except Exception as e:
            return {
                "success": False,
                "connected": False,
                "message": str(e)
            }
    
    @app.post("/api/google-drive/disconnect")
    async def google_disconnect(teacher_id: str = Form(...)):
        """Déconnecter Google Drive"""
        try:
            success = await drive_manager.revoke_oauth_access(teacher_id)
            
            # Désactiver toutes les surveillances
            supabase_client.table('google_drive_monitors').update({
                'is_active': False
            }).eq('teacher_id', teacher_id).execute()
            
            return {
                "success": success,
                "message": "Déconnecté" if success else "Erreur"
            }
        except Exception as e:
            raise HTTPException(500, str(e))
    
    # ═══════════════════════════════════════════════════════════════════════
    # GESTION DOSSIERS
    # ═══════════════════════════════════════════════════════════════════════
    
    @app.get("/api/google-drive/folders/{teacher_id}")
    async def list_drive_folders(teacher_id: str):
        """Lister dossiers Google Drive accessibles"""
        try:
            service, auth_method, error = await drive_manager.get_drive_service(teacher_id)
            
            if not service:
                return {"success": False, "error": error, "folders": []}
            
            results = service.files().list(
                q="mimeType='application/vnd.google-apps.folder' and trashed=false",
                pageSize=50,
                fields="files(id, name, modifiedTime, webViewLink)",
                orderBy="modifiedTime desc"
            ).execute()
            
            return {
                "success": True,
                "folders": results.get('files', []),
                "auth_method": auth_method
            }
            
        except Exception as e:
            return {"success": False, "error": str(e), "folders": []}
    
    @app.post("/api/google-drive/test-folder-access")
    async def test_folder_access(
        teacher_id: str = Form(...),
        folder_id: str = Form(...)
    ):
        """
        Tester l'accès à un dossier AVANT de créer surveillance
        TRÈS IMPORTANT pour UX
        """
        try:
            result = await drive_manager.test_folder_access(folder_id, teacher_id)
            
            return {
                "success": result['success'],
                "auth_method": result['auth_method'],
                "error": result['error'],
                "folder_info": result['folder_info'],
                "message": "Accès OK" if result['success'] else result['error']
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Erreur test: {str(e)}"
            }
    
    # ═══════════════════════════════════════════════════════════════════════
    # SURVEILLANCE
    # ═══════════════════════════════════════════════════════════════════════
    
    @app.post("/api/google-drive/monitor")
    async def create_drive_monitor(
        teacher_id: str = Form(...),
        folder_id: str = Form(...),
        folder_name: str = Form(...),
        establishment_id: Optional[str] = Form(None),
        threshold: float = Form(15.0)
    ):
        """
        Créer surveillance Google Drive
        Test d'accès automatique avant création
        """
        try:
            # ÉTAPE 1: Tester l'accès d'abord
            access_test = await drive_manager.test_folder_access(folder_id, teacher_id)
            
            if not access_test['success']:
                raise HTTPException(403, access_test['error'])
            
            # ÉTAPE 2: Créer monitor
            monitor = supabase_client.table('google_drive_monitors').insert({
                'teacher_id': teacher_id,
                'drive_link': f"https://drive.google.com/drive/folders/{folder_id}",
                'drive_folder_id': folder_id,
                'folder_name': folder_name,
                'establishment_id': establishment_id,
                'similarity_threshold': threshold,
                'is_active': True,
                'last_check': datetime.now().isoformat(),
                'auth_method': access_test['auth_method']
            }).execute()
            
            monitor_id = monitor.data[0]['id']
            
            # ÉTAPE 3: Lancer surveillance
            asyncio.create_task(drive_monitor.start_monitoring(monitor_id))
            
            return {
                "success": True,
                "data": monitor.data[0],
                "message": f"Surveillance activée via {access_test['auth_method']}"
            }
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(500, str(e))
    
    @app.get("/api/google-drive/monitors/{teacher_id}")
    async def get_drive_monitors(teacher_id: str):
        """Lister surveillances"""
        try:
            result = supabase_client.table('google_drive_monitors').select('*').eq(
                'teacher_id', teacher_id
            ).order('created_at', desc=True).execute()
            
            return {"success": True, "data": result.data}
        except Exception as e:
            raise HTTPException(500, str(e))
    
    @app.put("/api/google-drive/monitors/{monitor_id}/toggle")
    async def toggle_drive_monitor(monitor_id: str):
        """Activer/Désactiver surveillance"""
        try:
            monitor = supabase_client.table('google_drive_monitors').select('*').eq('id', monitor_id).execute()
            
            if not monitor.data:
                raise HTTPException(404, "Monitor introuvable")
            
            new_status = not monitor.data[0]['is_active']
            
            result = supabase_client.table('google_drive_monitors').update({
                'is_active': new_status,
                'error_message': None if new_status else monitor.data[0].get('error_message'),
                'updated_at': datetime.now().isoformat()
            }).eq('id', monitor_id).execute()
            
            # Relancer si activé
            if new_status:
                asyncio.create_task(drive_monitor.start_monitoring(monitor_id))
            else:
                await drive_monitor.stop_monitoring(monitor_id)
            
            return {"success": True, "data": result.data[0]}
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(500, str(e))
    
    @app.delete("/api/google-drive/monitors/{monitor_id}")
    async def delete_drive_monitor(monitor_id: str):
        """Supprimer surveillance"""
        try:
            # Arrêter d'abord
            await drive_monitor.stop_monitoring(monitor_id)
            
            # Supprimer de BD
            supabase_client.table('google_drive_monitors').delete().eq('id', monitor_id).execute()
            
            return {"success": True, "message": "Surveillance supprimée"}
            
        except Exception as e:
            raise HTTPException(500, str(e))
    
    # ═══════════════════════════════════════════════════════════════════════
    # DIAGNOSTICS
    # ═══════════════════════════════════════════════════════════════════════
    
    @app.get("/api/google-drive/diagnostics")
    async def google_drive_diagnostics():
        """
        Diagnostics système Google Drive
        Utile pour debugging
        """
        return {
            "oauth_enabled": OAUTH_ENABLED,
            "oauth_client_id": CLIENT_CONFIG["web"]["client_id"][:20] + "..." if OAUTH_ENABLED else None,
            "service_account_configured": bool(drive_manager.service_account_email),
            "service_account_email": drive_manager.service_account_email,
            "active_monitors": len(drive_monitor.running),
            "backend_version": "3.0.0-ULTRA-ROBUST"
        }

print("✅ Endpoints Google Drive prêts à être ajoutés")
