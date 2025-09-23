$(function() {
    function Fazenda3DViewModel(parameters) {
        var self = this;

        self.settingsViewModel = parameters[0];

        self.servidor_url = ko.observable();
        self.token = ko.observable();
        self.nome_impressora = ko.observable();

        self.connectionStatus = ko.observable("Desconectado");

        self.onBeforeBinding = function() {
            // carrega valores salvos do plugin
            self.servidor_url(self.settingsViewModel.settings.plugins.fazenda3d.servidor_url());
            self.token(self.settingsViewModel.settings.plugins.fazenda3d.token());
            self.nome_impressora(self.settingsViewModel.settings.plugins.fazenda3d.nome_impressora());
        };

        self.connectToServer = function() {
            // Salva nos settings do OctoPrint
            self.settingsViewModel.settings.plugins.fazenda3d.servidor_url(self.servidor_url());
            self.settingsViewModel.settings.plugins.fazenda3d.token(self.token());
            self.settingsViewModel.settings.plugins.fazenda3d.nome_impressora(self.nome_impressora());
            self.settingsViewModel.saveData(); // só aqui

            // Debug no console do navegador
            console.log("Conectar ao servidor:");
            console.log("URL:", self.servidor_url());
            console.log("Token:", self.token());
            console.log("Nome:", self.nome_impressora());

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
                    console.log("Resposta do servidor", resp);
                    if (resp.success) {
                        self.connectionStatus("Conectado com sucesso!");
                    } else {
                        self.connectionStatus("Falha: " + (resp.message || "Erro"));
                    }
                },
                error: function(err) {
                    console.error("Erro AJAX", err);
                    self.connectionStatus("Erro ao conectar");
                }
            });
        };
    }

    OCTOPRINT_VIEWMODELS.push({
        construct: Fazenda3DViewModel,
        dependencies: ["settingsViewModel"],
        elements: ["#tab_plugin_fazenda3d"]
    });
});
