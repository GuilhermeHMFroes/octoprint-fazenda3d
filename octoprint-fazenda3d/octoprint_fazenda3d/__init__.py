# -*- coding: utf-8 -*-
from __future__ import absolute_import
import os
import threading
import time
import requests
import flask
import socketio # Biblioteca nova
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
        self.sio = None # Cliente SocketIO
        self.streaming = False
        self.stream_thread = None

    def on_after_startup(self):
        self._logger.info("Fazenda3DPlugin: Iniciando serviços...")
        
        # 1. Inicia o Loop de Status (HTTP - Mantemos para compatibilidade)
        interval = 5.0
        self._timer = octoprint.util.RepeatedTimer(interval, self._loop_status)
        self._timer.start()

        # 2. Inicia conexão WebSocket (O Túnel)
        self.connect_socket()

    def connect_socket(self):
        # Roda em thread separada para não travar o boot do OctoPrint
        t = threading.Thread(target=self._socket_worker)
        t.daemon = True
        t.start()

    def _socket_worker(self):
        server_url = self._settings.get(["servidor_url"])
        if not server_url:
            return

        self.sio = socketio.Client()

        @self.sio.on('connect')
        def on_connect():
            self._logger.info("WS: Conectado ao Servidor na Nuvem!")
            token = self._settings.get(["token"])
            # Autentica entrando na sala
            self.sio.emit('printer_connect', {'token': token})

        @self.sio.on('execute_command')
        def on_command(data):
            # Recebe comando instantâneo (G-code, Pause, etc)
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

        try:
            # Conecta e fica esperando (wait)
            self.sio.connect(server_url, namespaces=['/'])
            self.sio.wait()
        except Exception as e:
            self._logger.error(f"WS: Erro de conexão socket: {e}")
            # Tenta reconectar em 30s se cair
            time.sleep(30)
            self._socket_worker()

    def _video_stream_loop(self):
        """Captura MJPEG local e envia quadros via Socket"""
        # URL Local da câmera (Onde o mjpg_streamer está rodando NA MÁQUINA)
        # Se for OctoPi padrão: http://127.0.0.1:8080/?action=stream
        local_stream_url = "http://127.0.0.1:8080/?action=stream"
        token = self._settings.get(["token"])

        try:
            stream = requests.get(local_stream_url, stream=True, timeout=5)
            bytes_buffer = bytes()

            for chunk in stream.iter_content(chunk_size=1024):
                if not self.streaming:
                    break # Para o loop se o servidor mandar parar
                
                bytes_buffer += chunk
                
                # Procura início (0xff 0xd8) e fim (0xff 0xd9) do JPEG
                a = bytes_buffer.find(b'\xff\xd8')
                b = bytes_buffer.find(b'\xff\xd9')
                
                if a != -1 and b != -1:
                    jpg = bytes_buffer[a:b+2]
                    bytes_buffer = bytes_buffer[b+2:]
                    
                    # Envia o quadro para a nuvem
                    # Emitir binary data via socketio é eficiente
                    if self.sio and self.sio.connected:
                        self.sio.emit('video_frame', {'token': token, 'image': jpg})
                        # Pequeno delay para controlar FPS (opcional, 0.1 = 10fps)
                        time.sleep(0.05) 
                        
        except Exception as e:
            self._logger.error(f"WS: Erro no loop de vídeo: {e}")
            self.streaming = False

    # ... (MANTENHA AS OUTRAS FUNÇÕES: get_settings_defaults, _loop_status, ETC) ...
    # ... (Elas são necessárias para o sistema funcionar enquanto o socket conecta) ...
    
    def get_settings_defaults(self):
        return dict(servidor_url="", token="", nome_impressora="")

    def get_template_vars(self):
        return dict(servidor_url=self._settings.get(["servidor_url"]), token=self._settings.get(["token"]), nome_impressora=self._settings.get(["nome_impressora"]))
    
    def get_template_configs(self):
        return [dict(type="settings", custom_bindings=False)]

    def _loop_status(self):
        # MANTENHA A SUA FUNÇÃO _loop_status ATUAL AQUI
        # Ela ainda é útil para atualizar temperaturas no banco de dados
        # e baixar arquivos (download via HTTP é mais robusto que via socket para arquivos grandes)
        pass 

    # Mantenha o método _baixar_e_imprimir que corrigimos antes
    def _baixar_e_imprimir(self, arquivo_url):
         # ... (seu código atual de download) ...
         pass

    def on_shutdown(self):
        if self._timer: self._timer.cancel()
        if self.sio: self.sio.disconnect()

__plugin_name__ = "Fazenda 3D Cloud"
__plugin_version__ = "0.2.0"
__plugin_description__ = "Versão Cloud com WebSockets"
__plugin_pythoncompat__ = ">=3,<4"
__plugin_implementation__ = Fazenda3DPlugin()