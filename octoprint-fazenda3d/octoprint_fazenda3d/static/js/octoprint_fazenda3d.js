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
        self.nome_impressora = ko.observable();
        self.connectionStatus = ko.observable("Desconectado");

        // Sincroniza os dados ao abrir a aba ---
        self.onBeforeBinding = function() {
            // Tenta encontrar as configurações do plugin. 
            // O OctoPrint usa o identificador do plugin (geralmente o nome da pasta ou definido no setup.py)
            var settings = self.settings.settings.plugins.octoprint_fazenda3d || self.settings.settings.plugins.fazenda3d;
            
            if (settings) {
                // Preenche os observáveis com os valores salvos
                if (settings.servidor_url) self.servidor_url(settings.servidor_url());
                if (settings.token) self.token(settings.token());
                console.log("Fazenda3D: Dados carregados com sucesso.");
            } else {
                console.warn("Fazenda3D: Não foi possível encontrar as configurações no objeto 'plugins'.");
            }
        };

        self.connectToServer = function() {
            
            console.log("Botão 'connectToServer' FOI CLICADO!");
            self.connectionStatus("Conectando...");

            var payload = {
                servidor_url: self.servidor_url(), 
                token: self.token()
            };
            
            console.log("Enviando payload:", payload);

            // --- A CORREÇÃO FINAL ESTÁ AQUI ---
            OctoPrint.simpleApiCommand("octoprint_fazenda3d", "connect", payload)
                .done(function(response) {
                    console.log("Resposta do servidor:", response);
                    if(response.success) {
                        self.connectionStatus("Conectado");
                    } else {
                        self.connectionStatus("Falha: " + (response.error || "Erro desconhecido"));
                    }
                })
                .fail(function(jqXHR, textStatus, errorThrown) {
                    // O erro 400 estava a fazer com que o código caísse aqui
                    console.error("Falha na chamada AJAX:", textStatus, errorThrown, jqXHR.responseText);
                    self.connectionStatus("Erro de comunicação com o plugin (verifique o ID)");
                });
        };

    } // Fim do Fazenda3DViewModel

    OCTOPRINT_VIEWMODELS.push({
        construct: Fazenda3DViewModel,
        dependencies: ["settingsViewModel"],
        elements: ["#tab_plugin_fazenda3d"]
    });
});