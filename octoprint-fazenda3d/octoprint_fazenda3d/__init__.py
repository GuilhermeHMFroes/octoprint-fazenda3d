# -*- coding: utf-8 -*-
from __future__ import absolute_import
import os
import threading
import time
import requests
import flask
import socketio
import octoprint.plugin
import octoprint.util
import octoprint.filemanager.destinations
from octoprint.filemanager.util import StreamWrapper

class Fazenda3DPlugin(octoprint.plugin.SettingsPlugin,
                      octoprint.plugin.TemplatePlugin,
                      octoprint.plugin.StartupPlugin,
                      octoprint.plugin.SimpleApiPlugin,
                      octoprint.plugin.AssetPlugin):

    def __init__(self):
        super(Fazenda3DPlugin, self).__init__()
        self._timer = None
        self.sio = None
        self.streaming = False
        self.stream_thread = None
        self._shutdown_signal = False # Flag para saber quando parar

    def on_after_startup(self):
        self._logger.info("Fazenda3DPlugin: Iniciando serviços...")
        
        # 1. Inicia o Loop de Status (HTTP - Mantido para compatibilidade)
        interval = 5.0
        self._timer = octoprint.util.RepeatedTimer(interval, self._loop_status)
        self._timer.start()

        # 2. Inicia conexão WebSocket (O Túnel)
        self.connect_socket()

    def connect_socket(self):
        t = threading.Thread(target=self._socket_worker)
        t.daemon = True # Importante: Se o OctoPrint fechar, essa thread morre junto
        t.start()

    def _socket_worker(self):
        server_url = self._settings.get(["servidor_url"])
        
        # Se não tiver URL configurada, nem tenta
        if not server_url:
            self._logger.info("WS: URL do servidor não configurada. WebSockets desativado.")
            return

        self.sio = socketio.Client()

        # --- DEFINIÇÃO DOS EVENTOS ---
        @self.sio.on('connect')
        def on_connect():
            self._logger.info("WS: Conectado ao Servidor na Nuvem!")
            token = self._settings.get(["token"])
            self.sio.emit('printer_connect', {'token': token})

        @self.sio.on('disconnect')
        def on_disconnect():
            self._logger.info("WS: Desconectado do servidor.")
            self.streaming = False

        @self.sio.on('execute_command')
        def on_command(data):
            cmd = data.get('cmd')
            self._logger.info(f"WS: Comando recebido: {cmd}")
            if cmd == 'pause': self._printer.pause_print()
            elif cmd == 'resume': self._printer.resume_print()
            elif cmd == 'cancel': self._printer.cancel_print()
            else: self._printer.commands(cmd)

        @self.sio.on('start_video')
        def on_start_video(data):
            self._logger.info("WS: Servidor pediu vídeo. Iniciando stream...")
            self.streaming = True
            if self.stream_thread is None or not self.stream_thread.is_alive():
                self.stream_thread = threading.Thread(target=self._video_stream_loop)
                self.stream_thread.daemon = True
                self.stream_thread.start()

        @self.sio.on('stop_video')
        def on_stop_video(data):
            self._logger.info("WS: Servidor parou vídeo.")
            self.streaming = False

        # --- LOOP DE CONEXÃO ROBUSTO (AQUI ESTÁ A CORREÇÃO) ---
        while not self._shutdown_signal:
            try:
                if not self.sio.connected:
                    self._logger.info(f"WS: Tentando conectar a {server_url}...")
                    # Tenta conectar. Se falhar, vai pular pro 'except'
                    self.sio.connect(server_url, namespaces=['/'])
                    self.sio.wait() # Fica aqui bloqueado enquanto estiver conectado
                else:
                    time.sleep(1)
            except Exception as e:
                # Se der erro (servidor offline), NÃO CRASHA O PLUGIN.
                # Apenas avisa no log e espera 30 segundos.
                self._logger.warning(f"WS: Falha na conexão (Servidor Offline?). Tentando em 30s. Erro: {e}")
                self.streaming = False # Garante que para de tentar enviar vídeo
                time.sleep(30)

    def _video_stream_loop(self):
        """Captura MJPEG local e envia quadros via Socket"""
        local_stream_url = "http://127.0.0.1:8080/?action=stream"
        token = self._settings.get(["token"])

        try:
            stream = requests.get(local_stream_url, stream=True, timeout=5)
            bytes_buffer = bytes()

            for chunk in stream.iter_content(chunk_size=1024):
                if not self.streaming: break
                
                bytes_buffer += chunk
                a = bytes_buffer.find(b'\xff\xd8')
                b = bytes_buffer.find(b'\xff\xd9')
                
                if a != -1 and b != -1:
                    jpg = bytes_buffer[a:b+2]
                    bytes_buffer = bytes_buffer[b+2:]
                    
                    if self.sio and self.sio.connected:
                        try:
                            self.sio.emit('video_frame', {'token': token, 'image': jpg})
                            time.sleep(0.05) 
                        except Exception:
                            # Se falhar o envio, encerra o loop de vídeo para não travar
                            break
                        
        except Exception as e:
            self._logger.error(f"WS: Erro no loop de vídeo: {e}")
            self.streaming = False

    # --- FUNÇÕES PADRÃO DO OCTOPRINT ---
    
    def get_settings_defaults(self):
        return dict(servidor_url="", token="", nome_impressora="")

    def get_template_vars(self):
        return dict(servidor_url=self._settings.get(["servidor_url"]), token=self._settings.get(["token"]), nome_impressora=self._settings.get(["nome_impressora"]))
    
    def get_template_configs(self):
        return [dict(type="settings", custom_bindings=False)]

    def _loop_status(self):
        # MANTEMOS O LOOP HTTP COMO BACKUP E PARA DADOS LENTOS
        servidor_url = self._settings.get(["servidor_url"])
        token = self._settings.get(["token"]) 
        if not servidor_url or not token: return
        
        try:
            # Coleta dados simples para atualizar o banco
            state = self._printer.get_state_id()
            temps = self._printer.get_current_temperatures()
            webcam_url = self._settings.global_get(["webcam", "streamUrl"]) or ""
            
            job_name = None
            try:
                job_data = self._printer.get_current_job()
                if job_data and "job" in job_data and "file" in job_data["job"]:
                    job_name = job_data["job"]["file"]["name"]
            except: pass
            
            payload = {
                "token": token,
                "nome_impressora": self._settings.get(["nome_impressora"]),
                "estado": state,
                "temperaturas": temps,
                "arquivo_imprimindo": job_name,
                "webcam_url": webcam_url
            }
            
            # Envia via HTTP (polling lento) apenas para garantir atualização do banco
            url_status = servidor_url.rstrip("/") + "/api/status"
            requests.post(url_status, json=payload, timeout=2) # Timeout curto para não travar
            
            # Verificação de arquivos na fila via HTTP (Download é melhor via HTTP)
            if not self._printer.is_printing() and not self._printer.is_paused():
                url_fila = servidor_url.rstrip("/") + "/api/fila?token=" + token
                resp = requests.get(url_fila, timeout=2)
                if resp.status_code == 200:
                    obj = resp.json()
                    if obj.get("novo_arquivo"):
                        self._baixar_e_imprimir(obj.get("arquivo_url"))

        except Exception:
            # Se der erro no HTTP, apenas ignora silenciosamente
            # (O Log já vai estar cheio de avisos do Socket, não precisamos spammar aqui)
            pass

    def _baixar_e_imprimir(self, arquivo_url):
        self._logger.info(f"Fazenda3D: Iniciando download de: {arquivo_url}")
        try:
            import urllib.parse
            uploads_folder = self._settings.global_get(["folder", "uploads"])
            if not uploads_folder: uploads_folder = os.path.expanduser("~/.octoprint/uploads")
            if not os.path.exists(uploads_folder): os.makedirs(uploads_folder)

            raw_filename = os.path.basename(urllib.parse.unquote(arquivo_url))
            filename = "".join(x for x in raw_filename if (x.isalnum() or x in "._- "))
            file_path = os.path.join(uploads_folder, filename)

            r = requests.get(arquivo_url, stream=True, timeout=60)
            r.raise_for_status()

            with open(file_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1024 * 8): 
                    if chunk: f.write(chunk)
            
            self._printer.select_file(filename, False, printAfterSelect=True)
            self._logger.info(f"Fazenda3D: Impressão iniciada: {filename}")
        except Exception as e:
            self._logger.error(f"Fazenda3D: Erro no download: {e}")

    def on_shutdown(self):
        self._shutdown_signal = True # Avisa o loop para parar
        if self._timer: self._timer.cancel()
        if self.sio: 
            try: self.sio.disconnect()
            except: pass

__plugin_name__ = "Fazenda 3D"
__plugin_version__ = "0.2.1"
__plugin_description__ = "Versão Cloud Resiliente"
__plugin_pythoncompat__ = ">=3,<4"
__plugin_implementation__ = Fazenda3DPlugin()