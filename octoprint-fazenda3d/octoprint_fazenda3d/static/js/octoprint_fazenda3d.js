$(function() {
    function Fazenda3DViewModel(parameters) {
        var self = this;

        // acessa settingsViewModel para carregar dados salvos
        self.settingsViewModel = parameters[0];

        // observables ligadas ao template Jinja2
        self.servidor_url = ko.observable();
        self.token = ko.observable();
        self.nome_impressora = ko.observable();

        // status de conexão
        self.connectionStatus = ko.observable("Desconectado");

        // Ao inicializar o viewmodel, carrega valores já salvos
        self.onBeforeBinding = function() {
            self.servidor_url(self.settingsViewModel.settings.plugins.fazenda3d.servidor_url());
            self.token(self.settingsViewModel.settings.plugins.fazenda3d.token());
            self.nome_impressora(self.settingsViewModel.settings.plugins.fazenda3d.nome_impressora());
        };

        // Botão para testar conexão com o servidor
        self.connectToServer = function() {
            var url = self.servidor_url();
            var token = self.token();
            var nome = self.nome_impressora();

            if (!url || !token) {
                self.connectionStatus("Preencha URL e Token");
                return;
            }

            self.connectionStatus("Conectando...");
            $.ajax({
                url: url.replace(/\/$/, "") + "/api/status",
                type: "POST",
                data: JSON.stringify({
                    token: token,
                    nome_impressora: nome || "Impressora sem nome",
                    estado: "operational"
                }),
                contentType: "application/json",
                success: function(resp) {
                    if (resp.success) {
                        self.connectionStatus("Conectado com sucesso!");
                    } else {
                        self.connectionStatus("Falha: " + (resp.message || "Erro"));
                    }
                },
                error: function() {
                    self.connectionStatus("Erro ao conectar");
                }
            });
        };
    }

    // registra o viewmodel no OctoPrint
    OCTOPRINT_VIEWMODELS.push({
        construct: Fazenda3DViewModel,
        dependencies: ["settingsViewModel"],
        elements: ["#tab_plugin_fazenda3d"]
    });
});
