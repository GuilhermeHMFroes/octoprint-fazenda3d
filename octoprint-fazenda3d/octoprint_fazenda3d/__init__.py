# -*- coding: utf-8 -*-
from __future__ import absolute_import
import os
import requests
import octoprint.plugin
import octoprint.util


class Fazenda3DPlugin(octoprint.plugin.SettingsPlugin,
                      octoprint.plugin.TemplatePlugin,
                      octoprint.plugin.StartupPlugin):

    def __init__(self):
        super(Fazenda3DPlugin, self).__init__()
        self._timer = None

    # Chamado após o OctoPrint iniciar
    def on_after_startup(self):
        self._logger.info("Fazenda3DPlugin iniciado.")
        # Timer para envio periódico de status e checagem da fila
        interval = 5.0  # segundos
        self._timer = octoprint.util.RepeatedTimer(interval, self._loop_status)
        self._timer.start()

    # Configurações padrão do plugin
    def get_settings_defaults(self):
        return dict(
            servidor_url="",
            token="",
            nome_impressora=""
        )

    # Variáveis passadas ao template
    def get_template_vars(self):
        return dict(
            servidor_url=self._settings.get(["servidor_url"]),
            token=self._settings.get(["token"]),
            nome_impressora=self._settings.get(["nome_impressora"])
        )

    # Define onde aparece o painel: aba (tab) ou sidebar
    def get_template_configs(self):
        return [
            dict(type="tab", name="Fazenda 3D", template="fazenda3d_tab.jinja2")
            # se preferir lateral: dict(type="sidebar", name="Fazenda 3D", template="fazenda3d_tab.jinja2")
        ]
    
    def get_assets(self):
        return dict(
            js=["js/fazenda3d.js"]
        )

    # Loop periódico para enviar status e checar fila
    def _loop_status(self):

        #self._logger.info("Entrou no _loop_status")

        servidor = self._settings.get(["servidor_url"])
        token = self._settings.get(["token"])
        nome = self._settings.get(["nome_impressora"])

        self._logger.info("Entrou no loop. token: {}").format(token)

        if not servidor or not token:
            # não configurado ainda
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

        # Verificar fila
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

    # Baixar o G-code e disparar impressão
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

                # Selecionar o arquivo e mandar imprimir
                relpath = os.path.join("temp_uploads", filename)
                self._printer.select_file(relpath, False, printAfterSelect=True)
                self._logger.info(f"Iniciando impressão do arquivo {filename}.")
            else:
                self._logger.error(f"Erro ao baixar o arquivo: código {r.status_code}")
        except Exception as e:
            self._logger.error(f"Erro no processo de baixar e imprimir: {e}")

    # Limpar timer se o plugin for encerrado
    def on_shutdown(self):
        if self._timer:
            self._timer.cancel()

    


__plugin_name__ = "Fazenda 3D"
__plugin_version__ = "0.1.0"
__plugin_description__ = "Plugin que integra o OctoPrint com sistema central de fazenda 3D"
__plugin_pythoncompat__ = ">=3.7,<4"
__plugin_implementation__ = Fazenda3DPlugin()