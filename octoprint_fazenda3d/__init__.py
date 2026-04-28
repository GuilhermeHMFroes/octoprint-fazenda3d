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
from flask import jsonify

import octoprint.filemanager.util

import urllib.parse

import base64



class Fazenda3DPlugin(octoprint.plugin.SettingsPlugin,
                      octoprint.plugin.TemplatePlugin,
                      octoprint.plugin.StartupPlugin,
                      octoprint.plugin.SimpleApiPlugin,
                      octoprint.plugin.AssetPlugin):

    def __init__(self):
        super(Fazenda3DPlugin, self).__init__()
        self._timer = None
        self.sio = None
        self._token_valido = True
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

            # Garantir que o loop status (HTTP) também volte se tiver sido parado
            if self._timer is None:
                interval = 5.0
                self._timer = octoprint.util.RepeatedTimer(interval, self._loop_status)
                self._timer.start()

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
        
        while not self._shutdown_signal and self._token_valido:
            server_url = self._settings.get(["servidor_url"])
            
            # Se não tiver URL, espera um pouco e tenta ler de novo (caso o usuário tenha acabado de salvar)
            if not server_url:
                time.sleep(5)
                continue

            if self.sio is None:
                #self.sio = socketio.Client()
                self.sio = socketio.Client(reconnection=False)

                # --- EVENTOS ---
                @self.sio.on('connect', namespace='/')
                def on_connect():
                    #self._logger.info("WS: Conectado!")
                    token = self._settings.get(["token"])
                    self.sio.emit('printer_connect', {'token': token}, namespace='/')

                @self.sio.on('server_ack', namespace='/')
                def on_server_ack(data):
                    # AGORA SIM: O servidor confirmou que o token existe e te aceitou na sala
                    self._logger.info("WS: Autenticado e Conectado com sucesso!")

                @self.sio.on('server_error', namespace='/')
                def on_server_error(data):
                    # O servidor te chutou porque o token é inválido
                    self._logger.error(f"WS: Erro de Autenticação: {data.get('message')}")
                    self._token_valido = False
                    self.sio.disconnect() # Desconecta imediatamente

                @self.sio.on('disconnect')
                def on_disconnect():
                    self._logger.info("WS: Desconectado do servidor.")
                    self.streaming = False
                    self.stream_thread = None

                @self.sio.on('execute_command', namespace='/')
                def on_command(data):

                    # LOG DE EMERGÊNCIA - Isso TEM que aparecer se o socket chegar
                    self._logger.info(f"!!! DEBUG SOCKET RECEBIDO: {data}")

                    # O servidor envia como 'command', então buscamos essa chave
                    cmd = data.get('command') or data.get('cmd') 

                    
                    if not cmd:
                        self._logger.error("Fazenda3D: Recebido execute_command mas o comando está vazio.")
                        return

                    self._logger.info(f"WS: Comando recebido: {cmd}")
                    
                    if cmd == 'pause': 
                        self._printer.pause_print()
                    elif cmd == 'resume': 
                        self._printer.resume_print()
                    elif cmd == 'cancel': 
                        self._printer.cancel_print()
                    else: 
                        # Para comandos G-Code puros (G28, G0, etc)
                        self._printer.commands(cmd)

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
        
                    # REMOVA o namespaces=['/'] daqui e force o websocket
                    self.sio.connect(
                        server_url, 
                        transports=['websocket'], # Força apenas websocket
                        socketio_path='/socket.io'
                    )
                    self.sio.wait()

                else:
                    time.sleep(2)
                    
            except Exception as e:

                if not self._token_valido:
                    break

                self._logger.warning(f"WS: Falha na conexão. Tentando em 30s. Erro: {e}")
                self.streaming = False 
                time.sleep(30)

        self._logger.info("WS: Worker encerrado (Token inválido ou Shutdown).")

    def _video_stream_loop(self):

        # Pega a URL do stream das configurações do OctoPrint
        stream_url = self._settings.global_get(["webcam", "stream"])
        if not stream_url:
            stream_url = "http://127.0.0.1:8080/?action=stream" # Default

        self._logger.info(f"Fazenda3D: Iniciando stream a partir de: {stream_url}")
        
        try:
            # Conectando ao stream local do mjpg-streamer
            res = requests.get(stream_url, stream=True, timeout=10)
            
            # Buffer para reconstruir as imagens do MJPEG
            bytes_buffer = bytes()
            for chunk in res.iter_content(chunk_size=4096):
                if not self.streaming: 
                    break
                
                bytes_buffer += chunk
                a = bytes_buffer.find(b'\xff\xd8') # Início do JPEG
                b = bytes_buffer.find(b'\xff\xd9') # Fim do JPEG
                
                if a != -1 and b != -1:
                    jpg = bytes_buffer[a:b+2]
                    bytes_buffer = bytes_buffer[b+2:]
                    
                    # Converte para Base64 para enviar via JSON no Socket
                    img_base64 = base64.b64encode(jpg).decode('utf-8')
                    
                    self.sio.emit('video_frame', {
                        'token': self._settings.get(["token"]),
                        'image': img_base64
                    })
                    
                    # Controle de FPS (ex: ~15 FPS para não sobrecarregar)
                    time.sleep(0.06) 

        except Exception as e:
            self._logger.error(f"Erro no loop de vídeo: {e}")
        finally:
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
            #requests.post(url_status, json=payload, timeout=2) 

            resp_status = requests.post(url_status, json=payload, timeout=2)
            
            if resp_status.status_code == 401:
                self._logger.error("Fazenda3D: Token recusado pelo servidor (401). Parando monitoramento.")
                self._parar_tudo() # Função auxiliar para limpar a bagunça
                return
            
            if not self._printer.is_printing() and not self._printer.is_paused():
                url_fila = servidor_url.rstrip("/") + "/api/fila?token=" + token

                # 2. Verificamos o GET da Fila
                #resp = requests.get(url_fila, timeout=2)
                resp_fila = requests.get(url_fila, timeout=2)

                if resp_fila.status_code == 401:
                    self._logger.error("Fazenda3D: Acesso à fila negado (401). Parando monitoramento.")
                    self._parar_tudo()
                    return

                if resp_fila.status_code == 200:
                    obj = resp_fila.json()
                    if obj.get("novo_arquivo"):
                        self._baixar_e_imprimir(obj.get("arquivo_url"))

        except Exception:
            pass

    def _parar_tudo(self):
        """Cancela o timer e desconecta o socket para cessar logs no servidor"""
        if self._timer:
            self._timer.cancel()
            self._timer = None
            self._logger.info("Fazenda3D: RepeatedTimer cancelado.")
        
        if self.sio and self.sio.connected:
            try:
                self.sio.disconnect()
                self._logger.info("Fazenda3D: Socket desconectado.")
            except:
                pass

    def _baixar_e_imprimir(self, arquivo_url):
        self._logger.info(f"Fazenda3D: Iniciando download de: {arquivo_url}")
        try:
            # 1. Extrair e limpar o nome do arquivo
            raw_filename = os.path.basename(urllib.parse.unquote(arquivo_url))
            filename = "".join(x for x in raw_filename if (x.isalnum() or x in "._- "))

            # --- NOVO: REMOVER ARQUIVO ANTIGO SE EXISTIR ---
            if self._file_manager.file_exists("local", filename):
                self._logger.info(f"Fazenda3D: Removendo arquivo existente: {filename}")
                self._file_manager.remove_file("local", filename)

            # 2. Download via requests (stream)
            r = requests.get(arquivo_url, stream=True, timeout=60)
            r.raise_for_status()

            # 3. Preparar o StreamWrapper
            meu_arquivo = octoprint.filemanager.util.StreamWrapper(filename, r.raw)

            # 4. SALVAR VIA FILE MANAGER
            # Agora que deletamos o antigo, o add_file não encontrará resistência
            self._file_manager.add_file(
                "local", 
                filename,
                meu_arquivo
            )

            self._logger.info(f"Fazenda3D: Arquivo {filename} salvo com sucesso.")

            # 5. Pequeno delay para garantir a indexação
            time.sleep(1.5)

            # 6. Selecionar e Imprimir
            self._printer.select_file(filename, False, printAfterSelect=True)
            self._logger.info(f"Fazenda3D: Impressão disparada para {filename}")

        except Exception as e:
            self._logger.error(f"Fazenda3D: Erro crítico no processo: {str(e)}")

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