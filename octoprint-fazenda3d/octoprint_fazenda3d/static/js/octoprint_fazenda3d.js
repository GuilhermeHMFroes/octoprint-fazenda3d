// Em ~/octoprint-fazenda3d/octoprint_fazenda3d/static/js/octoprint_fazenda3d.js
$(function() {
    function Fazenda3DViewModel(parameters) {
        var self = this;

        // --- DEBUG 1 ---
        // (Isto agora deve estar a aparecer no seu console)
        console.log("Fazenda3DViewModel FOI CONSTRUÍDO!");

        self.servidor_url = ko.observable();
        self.token = ko.observable();
        self.nome_impressora = ko.observable();
        self.connectionStatus = ko.observable("Desconectado");

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
        dependencies: [], 
        elements: ["#tab_plugin_fazenda3d"]
    });
});