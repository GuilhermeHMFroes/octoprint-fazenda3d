// Em ~/octoprint-fazenda3d/octoprint_fazenda3d/static/js/octoprint_fazenda3d.js
$(function() {
    function Fazenda3DViewModel(parameters) {
        var self = this;

        // --- DEBUG 1 ---
        // (Isto agora deve estar a aparecer no seu console)
        console.log("Fazenda3DViewModel FOI CONSTRUÍDO!");

        // Recebe as configurações globais do OctoPrint
        self.settings = parameters[0];

        self.servidor_url = ko.observable();
        self.token = ko.observable();
        self.connectionStatus = ko.observable("Desconectado");

        // Sincroniza os dados ao abrir a aba ---
        self.onBeforeBinding = function() {
            // Tenta encontrar as configurações do plugin. 
            // O OctoPrint usa o identificador do plugin (geralmente o nome da pasta ou definido no setup.py)
            var settings = self.settings.settings.plugins.octoprint_fazenda3d || self.settings.settings.plugins.octoprint_fazenda3d;
            
            if (settings) {
                // Preenche os observáveis com os valores salvos
                if (settings.servidor_url) self.servidor_url(settings.servidor_url());
                if (settings.token) self.token(settings.token());
                console.log("Fazenda3D: Dados carregados com sucesso.", self.servidor_url());
            } else {
                console.warn("Fazenda3D: Não foi possível encontrar as configurações no objeto 'plugins'.");
            }
        };

        self.connectToServer = function() {

            console.log("BOTÃO CLICADO! Enviando:", self.servidor_url());

            self.connectionStatus("Salvando e Conectando...");

            var payload = {
                servidor_url: self.servidor_url(), 
                token: self.token()
            };

            OctoPrint.simpleApiCommand("octoprint_fazenda3d", "connect", payload)
                .done(function(response) {
                    // Sincroniza o settingsViewModel local para que, se você der F5, 
                    // o valor novo já esteja lá antes mesmo do Python responder

                    console.log("Resposta do Python:", response);

                    var config = self.settings.settings.plugins.octoprint_fazenda3d;
                    config.servidor_url(self.servidor_url());
                    config.token(self.token());
                    
                    self.connectionStatus("URL Atualizada! Tentando conectar...");

                    console.log("Sucesso ao salvar nova URL:", payload.servidor_url);
                    
                })
                .fail(function() {

                    console.error("Erro na chamada API");

                    self.connectionStatus("Erro ao salvar configurações.");

                });
        };

    } // Fim do Fazenda3DViewModel

    OCTOPRINT_VIEWMODELS.push({
        construct: Fazenda3DViewModel,
        dependencies: ["settingsViewModel"], 
        elements: ["#tab_plugin_fazenda3d"]
    });

});