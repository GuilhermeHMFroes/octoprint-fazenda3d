// Em static/js/octoprint_fazenda3d.js

$(function() {
    function Fazenda3DViewModel(parameters) {
        var self = this;

        // --- DECLARAÇÃO ---
        // (Isso já estava correto)
        self.servidor_url = ko.observable();
        self.token = ko.observable();
        self.nome_impressora = ko.observable(); // Não usado, mas ok
        self.connectionStatus = ko.observable("Desconectado"); // Status inicial

        // --- FUNÇÃO DE CONECTAR (CORRIGIDA) ---
        self.connectToServer = function() {
            
            // Correção 1: Use a variável correta (connectionStatus) para DEFINIR o valor
            self.connectionStatus("Conectando...");

            // 1. Crie o payload
            var payload = {
                // Correção 2: Use os nomes corretos (servidor_url e token) para LER o valor
                server_url: self.servidor_url(), 
                api_key: self.token()
            };
            
            // 2. Envie o payload junto com o comando
            OctoPrint.simpleApiCommand("fazenda3d", "connect", payload)
                .done(function(response) {
                    if(response.success) {
                        // Correção 3: Use a variável correta
                        self.connectionStatus("Conectado");
                    } else {
                        // Correção 4: Use a variável correta
                        self.connectionStatus("Falha: " + (response.error || "Erro desconhecido"));
                    }
                })
                .fail(function() {
                    // Correção 5: Use a variável correta
                    self.connectionStatus("Erro de comunicação com o plugin (verifique o log)");
                });
        };

    } // Fim do Fazenda3DViewModel

    // --- REGISTRO DO VIEWMODEL ---
    // (Isso já estava correto)
    OCTOPRINT_VIEWMODELS.push({
        construct: Fazenda3DViewModel,
        dependencies: [], // Você não parece estar usando o settingsViewModel, então pode remover
        elements: ["#tab_plugin_fazenda3d"] // O ID da sua aba
    });
});