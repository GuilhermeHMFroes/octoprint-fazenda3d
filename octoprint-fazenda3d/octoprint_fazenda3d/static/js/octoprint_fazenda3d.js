$(function() {
    function Fazenda3DViewModel(parameters) {
        var self = this;

        // --- DEBUG 1 ---
        console.log("Fazenda3DViewModel FOI CONSTRUÍDO!");

        // Estes nomes devem corresponder ao 'fazenda3d_tab.jinja2'
        self.servidor_url = ko.observable();
        self.token = ko.observable();
        self.nome_impressora = ko.observable();
        self.connectionStatus = ko.observable("Desconectado");

        self.connectToServer = function() {
            
            // --- DEBUG 2 ---
            console.log("Botão 'connectToServer' FOI CLICADO!");

            self.connectionStatus("Conectando...");

            // --- CORREÇÃO AQUI ---
            // Estes nomes devem corresponder ao 'get_api_commands' no Python
            var payload = {
                servidor_url: self.servidor_url(), 
                token: self.token()
            };
            
            // --- DEBUG 3 ---
            console.log("Enviando payload:", payload);

            OctoPrint.simpleApiCommand("fazenda3d", "connect", payload)
                .done(function(response) {
                    console.log("Resposta do servidor:", response);
                    if(response.success) {
                        self.connectionStatus("Conectado");
                    } else {
                        self.connectionStatus("Falha: " + (response.error || "Erro desconhecido"));
                    }
                })
                .fail(function(jqXHR, textStatus, errorThrown) {
                    console.error("Falha na chamada AJAX:", textStatus, errorThrown, jqXHR.responseText);
                    self.connectionStatus("Erro de comunicação com o plugin");
                });
        };

    } // Fim do Fazenda3DViewModel

    OCTOPRINT_VIEWMODELS.push({
        construct: Fazenda3DViewModel,
        dependencies: [], 
        elements: ["#tab_plugin_fazenda3d"] // ID da sua aba
    });
});