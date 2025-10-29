$(function() {
    function Fazenda3DViewModel(parameters) {
        var self = this;

        self.servidor_url = ko.observable();
        self.token = ko.observable();
        self.nome_impressora = ko.observable();
        self.connectionStatus = ko.observable("Desconectado");

                self.connectToServer = function() {
            self.connectionStatusText("Conectando...");

            // --- CORREÇÃO AQUI ---
            // 1. Crie o payload pegando os valores atuais dos campos de texto.
            //    Use parênteses () para obter o valor de um observable do Knockout.
            var payload = {
                server_url: self.serverUrl(), 
                api_key: self.apiKey()
            };
            // ---------------------

            // 2. Envie o payload junto com o comando
            OctoPrint.simpleApiCommand("fazenda3d", "connect", payload) // <--- Use o payload aqui
                .done(function(response) {
                    if(response.success) {
                        self.connectionStatusText("Conectado");
                    } else {
                        // Se o python retornar um erro (ex: URL vazia), mostre-o
                        self.connectionStatusText("Falha: " + (response.error || "Erro desconhecido"));
                    }
                })
                .fail(function() {
                    // Isso acontece se o backend do Python falhar (erro 500)
                    self.connectionStatusText("Erro de comunicação com o plugin");
                });
        };

    }

    OCTOPRINT_VIEWMODELS.push({
        construct: Fazenda3DViewModel,
        dependencies: ["settingsViewModel"],
        elements: ["#tab_plugin_fazenda3d"]
    });
});
