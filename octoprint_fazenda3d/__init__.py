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
from flask import jsonify


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
        self._shutdown_signal = False 

    # --- SEGURANÇA ---
    def is_api_protected(self):
        return False

    # --- COMANDOS PERMITIDOS ---
    def get_api_commands(self):
        return dict(
            connect=["servidor_url", "token"], # O JS manda esses dados
            testar=[],   
            ping=[],     
            save=[],
            update=[]
        )

    def on_api_command(self, command, data):

        self._logger.info(f"API RECEBIDA: comando={command}, dados={data}")

        if command == "connect":
            url_nova = data.get("servidor_url")
            token_novo = data.get("token")

            self._settings.set(["servidor_url"], url_nova)
            self._settings.set(["token"], token_novo)
            self._settings.save()

            self._logger.info(f"Configurações atualizadas via API. Nova URL: {url_nova}")
            
            # FORÇAR O RESET DO CLIENTE SOCKET
            # Isso fará o loop do _socket_worker sair do 'wait' ou do 'sleep' 
            # e ler a nova URL do servidor_url
            if self.sio:
                try:
                    self.sio.disconnect()
                    self.sio = None # Forçamos a recriação do objeto no worker
                except:
                    pass

            return jsonify(success=True)

    # --- INICIALIZAÇÃO ---
    def on_after_startup(self):
        self._logger.info("Fazenda3DPlugin: Iniciando serviços...")
        interval = 5.0
        self._timer = octoprint.util.RepeatedTimer(interval, self._loop_status)
        self._timer.start()
        self.connect_socket()

        

    def get_assets(self):
        return dict(
            js=["js/octoprint_fazenda3d.js"], 
            css=["css/octoprint_fazenda3d.css"]
        )

    def get_template_configs(self):
        return [
            dict(type="tab", name="Fazenda 3D", template="fazenda3d_tab.jinja2"),
            dict(type="settings", custom_bindings=False)
        ]

    # --- SOCKETS ---
    def connect_socket(self):
        t = threading.Thread(target=self._socket_worker)
        t.daemon = True 
        t.start()

    def _socket_worker(self):
        # Pequeno delay inicial para garantir que settings carregaram
        time.sleep(2)
        
        while not self._shutdown_signal:
            server_url = self._settings.get(["servidor_url"])
            
            # Se não tiver URL, espera um pouco e tenta ler de novo (caso o usuário tenha acabado de salvar)
            if not server_url:
                time.sleep(5)
                continue

            if self.sio is None:
                self.sio = socketio.Client()
                
                # --- EVENTOS ---
                @self.sio.on('connect')
                def on_connect():
                    self._logger.info("WS: Conectado ao Servidor na Nuvem!")
                    token = self._settings.get(["token"])
                    self.sio.emit('printer_connect', {'token': token})

                @self.sio.on('disconnect')
                def on_disconnect():
                    self._logger.info("WS: Desconectado do servidor.")
                    self.streaming = False
                    self.stream_thread = None

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
                    self._logger.info("WS: EVENTO RECEBIDO! Servidor pediu vídeo.")
                    self.streaming = True
                    if self.stream_thread is None or not self.stream_thread.is_alive():
                        self.stream_thread = threading.Thread(target=self._video_stream_loop)
                        self.stream_thread.daemon = True
                        self.stream_thread.start()

                @self.sio.on('stop_video')
                def on_stop_video(data):
                    self._logger.info("WS: Servidor parou vídeo.")
                    self.streaming = False
                    self.stream_thread = None

            try:
                if not self.sio.connected:
                    self._logger.info(f"WS: Tentando conectar a {server_url}...")
                    self.sio.connect(server_url, namespaces=['/'])
                    self.sio.wait()
                else:
                    time.sleep(2)
            except Exception as e:
                self._logger.warning(f"WS: Falha na conexão. Tentando em 30s. Erro: {e}")
                self.streaming = False 
                time.sleep(30)

    def _video_stream_loop(self):

        # BUSCA DINÂMICA: Puxa a URL configurada no "Classic Webcam"
        local_stream_url = self._settings.global_get(["webcam", "stream"])
        
        # Validação: Se for uma URL relativa (começa com /), adicionamos o localhost
        if local_stream_url and local_stream_url.startswith("/"):
            local_stream_url = "http://127.0.0.1" + local_stream_url
        
        # Fallback caso não esteja configurado
        if not local_stream_url:
            local_stream_url = "http://127.0.0.1:8080/?action=stream"

        self._logger.info(f"Fazenda3D: Iniciando stream a partir de: {local_stream_url}")
        token = self._settings.get(["token"])

        stream = None

        try:
            # Usamos stream=True para ler o MJPEG frame a frame
            stream = requests.get(local_stream_url, stream=True, timeout=10)
            bytes_buffer = bytes()

            for chunk in stream.iter_content(chunk_size=1024 * 4): # Buffer maior para 1080p
                if not self.streaming or self._shutdown_signal: 
                    break
                
                bytes_buffer += chunk
                a = bytes_buffer.find(b'\xff\xd8') # Início do JPEG
                b = bytes_buffer.find(b'\xff\xd9') # Fim do JPEG
                
                if a != -1 and b != -1:
                    jpg = bytes_buffer[a:b+2]
                    bytes_buffer = bytes_buffer[b+2:]
                    
                    if self.sio and self.sio.connected:

                        try:
                            # Envia o frame. O servidor Flask vai repassar isso para o React
                            self.sio.emit('video_frame', {'token': token, 'image': jpg})
                            time.sleep(0.1) # 10 FPS

                        except:
                            break

        except Exception as e:

            self._logger.error(f"WS: Erro no loop de vídeo: {e}")

        finally:

            if stream: stream.close() # Garante que a conexão com a câmera feche
            self.streaming = False
            self._logger.info("Fazenda3D: Loop de vídeo encerrado.")
    
    def get_settings_defaults(self):
        return dict(servidor_url="", token="", nome_impressora="")

    def get_template_vars(self):
        return dict(
            servidor_url=self._settings.get(["servidor_url"]), 
            token=self._settings.get(["token"]), 
            nome_impressora=self._settings.get(["nome_impressora"])
        )

    def _loop_status(self):
        servidor_url = self._settings.get(["servidor_url"])
        token = self._settings.get(["token"]) 
        if not servidor_url or not token: return
        
        try:
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
            
            url_status = servidor_url.rstrip("/") + "/api/status"
            requests.post(url_status, json=payload, timeout=2) 
            
            if not self._printer.is_printing() and not self._printer.is_paused():
                url_fila = servidor_url.rstrip("/") + "/api/fila?token=" + token
                resp = requests.get(url_fila, timeout=2)
                if resp.status_code == 200:
                    obj = resp.json()
                    if obj.get("novo_arquivo"):
                        self._baixar_e_imprimir(obj.get("arquivo_url"))

        except Exception:
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
        self._shutdown_signal = True 
        if self._timer: self._timer.cancel()
        if self.sio: 
            try: self.sio.disconnect()
            except: pass

__plugin_name__ = "Fazenda3D"
__plugin_version__ = "0.1.0" # Deve ser igual à do pyproject.toml
__plugin_description__ = "Plugin de Integração Cloud"
__plugin_pythoncompat__ = ">=3,<4"
__plugin_implementation__ = Fazenda3DPlugin()