$(function() {
    function Fazenda3DViewModel(parameters) {
        var self = this;

        self.settingsViewModel = parameters[0];

        self.servidor_url = ko.observable();
        self.token = ko.observable();
        self.nome_impressora = ko.observable();

        self.connectionStatus = ko.observable("Desconectado");

        self.onBeforeBinding = function() {
            self.servidor_url(self.settingsViewModel.settings.plugins.fazenda3d.servidor_url());
            self.token(self.settingsViewModel.settings.plugins.fazenda3d.token());
            self.nome_impressora(self.settingsViewModel.settings.plugins.fazenda3d.nome_impressora());
        };

        self.connectToServer = function() {
            var url = self.servidor_url();
            var token = self.token();
            var nome = self.nome_impressora();

            console.log("Enviando para Python:", url, token, nome);

            // Envia direto para o Python via SimpleApiPlugin
            OctoPrint.simpleApiCommand("fazenda3d", "connect", {
                servidor_url: url,
                token: token,
                nome_impressora: nome
            }).done(function(resp) {
                console.log("Resposta Python", resp);
                if (resp.success) {
                    self.connectionStatus("Conectado ao servidor!");
                } else {
                    self.connectionStatus("Falha: " + (resp.message || "Erro"));
                }
            }).fail(function(err) {
                console.error("Erro API plugin", err);
                self.connectionStatus("Erro ao enviar dados ao plugin");
            });
        };
    }

    OCTOPRINT_VIEWMODELS.push({
        construct: Fazenda3DViewModel,
        dependencies: ["settingsViewModel"],
        elements: ["#tab_plugin_fazenda3d"]
    });
});
