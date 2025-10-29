$(function() {
    function Fazenda3DViewModel(parameters) {
        var self = this;

        // --- PASSO DE DEBUG 1 ---
        // Esta mensagem deve aparecer no Console ASSIM que a página carregar.
        console.log("Fazenda3DViewModel FOI CONSTRUÍDO!");
        // ------------------------

        self.servidor_url = ko.observable();
        self.token = ko.observable();
        self.nome_impressora = ko.observable();
        self.connectionStatus = ko.observable("Desconectado");

        self.connectToServer = function() {
            
            // --- PASSO DE DEBUG 2 ---
            // Esta mensagem deve aparecer no Console QUANDO o botão é clicado.
            console.log("O botão 'connectToServer' FOI CLICADO!");
            // ------------------------

            self.connectionStatus("Conectando...");

            var payload = {
                server_url: self.servidor_url(), 
                api_key: self.token()
            };
            
            OctoPrint.simpleApiCommand("fazenda3d", "connect", payload)
                .done(function(response) {
                    if(response.success) {
                        self.connectionStatus("Conectado");
                    } else {
                        self.connectionStatus("Falha: " + (response.error || "Erro desconhecido"));
                    }
                })
                .fail(function() {
                    self.connectionStatus("Erro de comunicação com o plugin (verifique o log)");
                });
        };

    } // Fim do Fazenda3DViewModel

    OCTOPRINT_VIEWMODELS.push({
        construct: Fazenda3DViewModel,
        dependencies: [], 
        elements: ["#tab_plugin_fazenda3d"]
    });
});