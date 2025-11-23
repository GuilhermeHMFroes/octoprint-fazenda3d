# -*- coding: utf-8 -*-
from __future__ import absolute_import
import os
import requests
import flask
import octoprint.plugin
import octoprint.util
from flask import jsonify

import octoprint.filemanager.destinations
from octoprint.filemanager.util import StreamWrapper


# --- CORREÇÃO 1: ADICIONAR O AssetPlugin DE VOLTA ---
class Fazenda3DPlugin(octoprint.plugin.SettingsPlugin,
                      octoprint.plugin.TemplatePlugin,
                      octoprint.plugin.StartupPlugin,
                      octoprint.plugin.SimpleApiPlugin,
                      octoprint.plugin.AssetPlugin):  # <-- DEVE ESTAR AQUI

    def __init__(self):
        super(Fazenda3DPlugin, self).__init__()
        self._timer = None

    def on_after_startup(self):
        self._logger.info("Fazenda3DPlugin iniciado.")
        interval = 5.0  # segundos
        self._timer = octoprint.util.RepeatedTimer(interval, self._loop_status)
        self._timer.start()

    def get_settings_defaults(self):
        return dict(
            servidor_url="",
            token="",
            nome_impressora=""
        )

    def get_template_vars(self):
        return dict(
            servidor_url=self._settings.get(["servidor_url"]),
            token=self._settings.get(["token"]),
            nome_impressora=self._settings.get(["nome_impressora"])
        )

    def get_template_configs(self):
        return [
            dict(type="tab", name="Fazenda 3D", template="fazenda3d_tab.jinja2")
        ]

    # --- CORREÇÃO 2: USAR O get_assets (O MÉTODO OFICIAL) ---
    # Isto diz ao OctoPrint para carregar o seu script em TODAS as páginas.
    def get_assets(self):
        return dict(js=["js/octoprint_fazenda3d.js"])

    # ======== SimpleApiPlugin ========
    
    def get_api_commands(self):
        # A API espera 'servidor_url' e 'token'
        return dict(connect=["servidor_url", "token"])

    # --- CORREÇÃO 3: ADICIONAR A FUNÇÃO DE PERMISSÕES ---
    # Isto corrige o aviso de "is_api_protected" que você viu.
    # Estamos a dizer que qualquer utilizador logado pode usar esta API.
    def is_api_protected(self):
        return True # Exige que o utilizador esteja logado

    def on_api_command(self, command, data):
        if command == "connect":
            server_url = data.get("servidor_url")
            # "api_key" vem do JavaScript, mas o seu servidor espera "token"
            api_key = data.get("token") 

            if not server_url or not api_key:
                return jsonify(success=False, error="URL ou Token não fornecidos")

            # Adiciona "http://" se faltar
            if not server_url.startswith("http://") and not server_url.startswith("https://"):
                self._logger.info(f"Fazenda3D: URL sem 'http'. Adicionando 'http://' automaticamente.")
                server_url = "http://" + server_url.strip("/")
            
            try:
                # --- CORREÇÃO 1: MUDAR A ROTA ---
                # A rota no seu app.py é "/api/register_printer"
                url_de_conexao = f"{server_url}/api/register_printer"
                
                self._logger.info(f"Fazenda3D: Tentando conectar em: {url_de_conexao}")

                # --- CORREÇÃO 2: MUDAR O JSON ---
                # O seu app.py espera "token", não "api_key"
                payload = {
                    "token": api_key,
                    "nome_impressora": "OctoPrint" # Pode adicionar o nome da impressora aqui
                }

                response = requests.post(
                    url_de_conexao,
                    json=payload, 
                    timeout=10
                )

                if response.status_code == 200:
                    self._logger.info("Fazenda3D: Conectado e registrado no servidor com sucesso.")
                    
                    self._settings.set(["servidor_url"], server_url)
                    self._settings.set(["token"], api_key) 
                    self._settings.save()
                    self._logger.info("Fazenda3D: Configurações salvas.")

                    return jsonify(success=True, status="connected")
                else:
                    self._logger.warning(f"Fazenda3D: Falha. Servidor respondeu com status {response.status_code}. Body: {response.text}")
                    return jsonify(success=False, error=f"Servidor respondeu com erro {response.status_code}")

            except requests.exceptions.ConnectionError as e:
                self._logger.error(f"Fazenda3D: Erro de conexão ao tentar contatar {server_url}. Erro: {e}")
                return jsonify(success=False, error=f"Não foi possível conectar ao servidor (ConnectionError)")
            
            except requests.exceptions.Timeout as e:
                self._logger.error(f"Fazenda3D: Timeout ao tentar contatar {server_url}. Erro: {e}")
                return jsonify(success=False, error="Servidor demorou para responder (Timeout)")

            except requests.exceptions.RequestException as e:
                self._logger.error(f"Fazenda3D: Erro de 'requests' ao tentar contatar {server_url}. Erro: {e}")
                return jsonify(success=False, error=f"Erro na requisição: {e}")

    # ======== Loop periódico ========
    def _loop_status(self):
        servidor_url = self._settings.get(["servidor_url"])
        token = self._settings.get(["token"]) 
        nome = self._settings.get(["nome_impressora"])
        
        if not servidor_url or not token:
            return
        
        # --- 1. COLETAR DADOS DA IMPRESSORA ---
        state = self._printer.get_state_id()
        temps = self._printer.get_current_temperatures()
        
        # Tenta pegar o nome do arquivo sendo impresso (Job Name)
        job_name = None
        try:
            job_data = self._printer.get_current_job()
            if job_data and "job" in job_data and "file" in job_data["job"]:
                job_name = job_data["job"]["file"]["name"]
        except:
            pass
            
        # Tenta pegar o progresso (0-100%)
        try:
            progress = self._printer.get_current_data()["progress"]["completion"]
        except:
            progress = None

        # --- NOVO: PEGAR A URL DA WEBCAM CONFIGURADA NO OCTOPRINT ---
        # Isso lê o campo "Stream URL" nas configurações globais do OctoPrint
        webcam_url = self._settings.global_get(["webcam", "streamUrl"])
        if not webcam_url:
            webcam_url = ""
        # ------------------------------------------------------------
            
        payload = {
            "token": token,
            "nome_impressora": nome,
            "estado": state,
            "temperaturas": temps,
            "progresso": progress,
            "arquivo_imprimindo": job_name,
            "webcam_url": webcam_url  # <--- ENVIAMOS A URL AQUI
        }
        
        # --- 2. ENVIAR STATUS PARA O SERVIDOR ---
        try:
            url_status = servidor_url.rstrip("/") + "/api/status"
            requests.post(url_status, json=payload, timeout=5)
        except Exception as e:
            self._logger.error(f"Erro ao enviar status: {e}")

        # --- 3. VERIFICAR COMANDOS DE CONTROLE (PAUSE/CANCEL) ---
        try:
            url_cmd = servidor_url.rstrip("/") + "/api/printer/check_commands?token=" + token
            r = requests.get(url_cmd, timeout=5)
            if r.status_code == 200:
                cmd = r.json().get("command")
                if cmd == "pause":
                    self._printer.pause_print()
                    self._logger.info("Comando PAUSAR recebido do servidor.")
                elif cmd == "resume":
                    self._printer.resume_print()
                    self._logger.info("Comando RESUMIR recebido do servidor.")
                elif cmd == "cancel":
                    self._printer.cancel_print()
                    self._logger.info("Comando CANCELAR recebido do servidor.")
        except Exception as e:
            self._logger.error(f"Erro ao checar comandos: {e}")

        # --- 4. VERIFICAR FILA (Apenas se NÃO estiver imprimindo) ---
        # Se estiver imprimindo ou pausado, não busca novos arquivos para economizar rede
        if self._printer.is_printing() or self._printer.is_paused():
            return 

        try:
            url_fila = servidor_url.rstrip("/") + "/api/fila?token=" + token
            resp = requests.get(url_fila, timeout=5)
            if resp.status_code == 200:
                obj = resp.json()
                if obj.get("novo_arquivo"):
                    # Se tiver arquivo novo, chama a função de download
                    self._baixar_e_imprimir(obj.get("arquivo_url"))
        except Exception:
            pass
            
    def _baixar_e_imprimir(self, arquivo_url):
        self._logger.info(f"Fazenda3D: Iniciando download de: {arquivo_url}")
        
        try:
            import urllib.parse
            
            # 1. DESCOBRIR A PASTA DE UPLOADS
            # Tenta pegar pela configuração global (chave correta: 'folder', 'uploads')
            uploads_folder = self._settings.global_get(["folder", "uploads"])
            
            # Fallback de segurança: Se não encontrar a configuração, usa o padrão do Linux
            if not uploads_folder:
                self._logger.warning("Fazenda3D: Configuração de pasta não encontrada. Usando caminho padrão.")
                uploads_folder = os.path.expanduser("~/.octoprint/uploads")
            
            # Garante que a pasta existe
            if not os.path.exists(uploads_folder):
                os.makedirs(uploads_folder)

            # 2. LIMPAR O NOME DO ARQUIVO
            raw_filename = os.path.basename(urllib.parse.unquote(arquivo_url))
            # Remove caracteres estranhos
            filename = "".join(x for x in raw_filename if (x.isalnum() or x in "._- "))
            
            # Caminho final
            file_path = os.path.join(uploads_folder, filename)

            # 3. BAIXAR E SALVAR (Método "Raiz")
            r = requests.get(arquivo_url, stream=True, timeout=60)
            r.raise_for_status()

            self._logger.info(f"Fazenda3D: Salvando arquivo em: {file_path}")

            with open(file_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1024 * 8): 
                    if chunk:
                        f.write(chunk)
            
            self._logger.info("Fazenda3D: Download concluído e salvo no disco.")

            # 4. SELECIONAR E IMPRIMIR
            # O select_file espera o caminho relativo à pasta de uploads (apenas o nome do arquivo)
            self._printer.select_file(filename, False, printAfterSelect=True)
            
            self._logger.info(f"Fazenda3D: COMANDO DE IMPRESSÃO ENVIADO para {filename}")

        except Exception as e:
            self._logger.error(f"Fazenda3D: ERRO CRÍTICO ao baixar e imprimir: {e}")

    def on_shutdown(self):
        if self._timer:
            self._timer.cancel()

__plugin_name__ = "Fazenda 3D"
__plugin_version__ = "0.1.0"
__plugin_description__ = "Plugin que integra o OctoPrint com sistema central de fazenda 3D"
__plugin_pythoncompat__ = ">=3.7,<4"
__plugin_implementation__ = Fazenda3DPlugin()