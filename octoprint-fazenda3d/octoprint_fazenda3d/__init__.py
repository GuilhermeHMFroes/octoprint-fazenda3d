# -*- coding: utf-8 -*-
from __future__ import absolute_import
import os
import requests
import flask
import octoprint.plugin
import octoprint.util
from flask import jsonify

class Fazenda3DPlugin(octoprint.plugin.SettingsPlugin,
                      octoprint.plugin.TemplatePlugin,
                      octoprint.plugin.StartupPlugin,
                      octoprint.plugin.SimpleApiPlugin):  # <-- adiciona aqui

    def __init__(self):
        super(Fazenda3DPlugin, self).__init__()
        self._timer = None

    # Chamado após o OctoPrint iniciar
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

    def get_assets(self):
        return dict(js=["js/octoprint_fazenda3d.js"])

    # ======== SimpleApiPlugin ========
    def get_api_commands(self):
        return dict(connect=["servidor_url", "token", "nome_impressora"])

    def on_api_command(self, command, data):
        if command == "connect":
            server_url = data.get("server_url")
            api_key = data.get("api_key")

            if not server_url or not api_key:
                return jsonify(success=False, error="URL ou API Key não fornecidos")

            # --- ADICIONE O TRY...EXCEPT AQUI ---
            try:
                # Log para sabermos que ele está tentando
                self._logger.info(f"Fazenda3D: Tentando conectar em: {server_url}")

                response = requests.post(
                    f"{server_url}/api/printer/connect",
                    json={"api_key": api_key, "status": "idle"},
                    timeout=10  # Boa prática: adicione um timeout de 10 segundos
                )

                # Verifique se o servidor principal respondeu com sucesso
                if response.status_code == 200:
                    self._logger.info("Fazenda3D: Conectado ao servidor com sucesso.")
                    return jsonify(success=True, status="connected")
                else:
                    # O servidor respondeu, mas com um erro (ex: 401, 404, 500)
                    self._logger.warning(f"Fazenda3D: Falha ao conectar. Servidor respondeu com status {response.status_code}. Body: {response.text}")
                    return jsonify(success=False, error=f"Servidor respondeu com erro {response.status_code}")

            except requests.exceptions.ConnectionError as e:
                # Erro: Não conseguiu nem chegar no servidor (offline, recusou, etc.)
                self._logger.error(f"Fazenda3D: Erro de conexão ao tentar contatar {server_url}. Erro: {e}")
                return jsonify(success=False, error=f"Não foi possível conectar ao servidor (ConnectionError)")
            
            except requests.exceptions.Timeout as e:
                # Erro: Demorou demais para responder
                self._logger.error(f"Fazenda3D: Timeout ao tentar contatar {server_url}. Erro: {e}")
                return jsonify(success=False, error="Servidor demorou para responder (Timeout)")

            except requests.exceptions.RequestException as e:
                # Outro erro genérico da biblioteca requests (ex: URL mal formada)
                self._logger.error(f"Fazenda3D: Erro de 'requests' ao tentar contatar {server_url}. Erro: {e}")
                return jsonify(success=False, error=f"Erro na requisição: {e}")
            # --- FIM DO BLOCO TRY...EXCEPT ---

    # ======== Loop periódico ========
    def _loop_status(self):
        servidor = self._settings.get(["servidor_url"])
        token = self._settings.get(["token"])
        nome = self._settings.get(["nome_impressora"])
        self._logger.info(f"Loop Fazenda3D - servidor_url: {servidor}, token: {token}, nome: {nome}")

        if not servidor or not token:
            return

        try:
            state = self._printer.get_state_id()
            temps = self._printer.get_current_temperatures()
            try:
                progress = self._printer.get_current_data()["progress"]["completion"]
            except Exception:
                progress = None

            payload = {
                "token": token,
                "nome_impressora": nome,
                "estado": state,
                "temperaturas": temps,
                "progresso": progress
            }

            self._logger.debug(f"Enviando status ao servidor: {payload}")
            url_status = servidor.rstrip("/") + "/api/status"
            requests.post(url_status, json=payload, timeout=5)
        except Exception as e:
            self._logger.error(f"Erro ao construir ou enviar status: {e}")

        try:
            url_fila = servidor.rstrip("/") + "/api/fila?token=" + token
            resp = requests.get(url_fila, timeout=5)
            if resp.status_code == 200:
                obj = resp.json()
                if obj.get("novo_arquivo"):
                    arquivo_url = obj.get("arquivo_url")
                    if arquivo_url:
                        self._logger.info(f"Novo arquivo detectado na fila: {arquivo_url}")
                        self._baixar_e_imprimir(arquivo_url)
        except Exception as e:
            self._logger.error(f"Erro ao checar fila: {e}")

    def _baixar_e_imprimir(self, arquivo_url):
        try:
            r = requests.get(arquivo_url, timeout=10)
            if r.status_code == 200:
                arquivo_bytes = r.content
                folder = self._settings.global_get(["server", "uploads"])
                if not folder:
                    folder = os.path.join(os.path.dirname(__file__), "temp_uploads")
                os.makedirs(folder, exist_ok=True)
                filename = os.path.basename(arquivo_url)
                caminho_local = os.path.join(folder, filename)
                with open(caminho_local, "wb") as f:
                    f.write(arquivo_bytes)
                self._logger.info(f"Arquivo {filename} baixado com sucesso.")
                relpath = os.path.join("temp_uploads", filename)
                self._printer.select_file(relpath, False, printAfterSelect=True)
                self._logger.info(f"Iniciando impressão do arquivo {filename}.")
            else:
                self._logger.error(f"Erro ao baixar o arquivo: código {r.status_code}")
        except Exception as e:
            self._logger.error(f"Erro no processo de baixar e imprimir: {e}")

    def on_shutdown(self):
        if self._timer:
            self._timer.cancel()

__plugin_name__ = "Fazenda 3D"
__plugin_version__ = "0.1.0"
__plugin_description__ = "Plugin que integra o OctoPrint com sistema central de fazenda 3D"
__plugin_pythoncompat__ = ">=3.7,<4"
__plugin_implementation__ = Fazenda3DPlugin()
