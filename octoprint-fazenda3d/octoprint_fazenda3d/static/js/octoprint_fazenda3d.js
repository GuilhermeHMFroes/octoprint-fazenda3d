$(function() {
    function Fazenda3DViewModel(parameters) {
        var self = this;

        self.settingsViewModel = parameters[0];

        // Observável para status da conexão
        self.connectionStatus = ko.observable("Desconectado");

        self.connectToServer = function() {
            var url = self.settingsViewModel.settings.plugins.fazenda3d.servidor_url();
            var token = self.settingsViewModel.settings.plugins.fazenda3d.token();
            var nome = self.settingsViewModel.settings.plugins.fazenda3d.nome_impressora();

            if (!url || !token) {
                alert("Preencha URL e Token primeiro.");
                return;
            }

            self.connectionStatus("Conectando…");

            $.ajax({
                type: "POST",
                url: url.replace(/\/$/, "") + "/api/register_printer",
                contentType: "application/json",
                data: JSON.stringify({
                    token: token,
                    nome_impressora: nome,
                    ip: location.hostname
                }),
                success: function(resp) {
                    self.connectionStatus("Conectado");
                    alert("Impressora registrada com sucesso!");
                },
                error: function() {
                    self.connectionStatus("Erro na conexão");
                    alert("Erro ao conectar ao servidor.");
                }
            });
        };

        // opcional: checar status periodicamente
        self.checkStatus = function() {
            var url = self.settingsViewModel.settings.plugins.fazenda3d.servidor_url();
            var token = self.settingsViewModel.settings.plugins.fazenda3d.token();
            if (!url || !token) return;

            $.ajax({
                url: url.replace(/\/$/, "") + "/api/printers",
                type: "GET",
                success: function() {
                    self.connectionStatus("Conectado");
                },
                error: function() {
                    self.connectionStatus("Desconectado");
                }
            });
        };

        // Checa status a cada 10 s
        setInterval(self.checkStatus, 10000);
    }

    OCTOPRINT_VIEWMODELS.push({
        construct: Fazenda3DViewModel,
        dependencies: ["settingsViewModel"],
        elements: ["#tab_plugin_fazenda3d"]
    });
});
