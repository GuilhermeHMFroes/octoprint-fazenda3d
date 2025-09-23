/*
 * ViewModel para o Plugin Fazenda3D
 */
$(function() {
    function Fazenda3DViewModel(parameters) {
        var self = this;

        // Pegamos o settingsViewModel (primeiro parâmetro)
        self.settingsViewModel = parameters[0];

        // Função chamada pelo botão
        self.connectToServer = function() {
            var url = self.settingsViewModel.settings.plugins.fazenda3d.servidor_url();
            var token = self.settingsViewModel.settings.plugins.fazenda3d.token();
            var nome = self.settingsViewModel.settings.plugins.fazenda3d.nome_impressora();

            if (!url || !token) {
                alert("Preencha URL e Token primeiro.");
                return;
            }

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
                    alert("Impressora registrada com sucesso!");
                },
                error: function() {
                    alert("Erro ao conectar ao servidor.");
                }
            });
        };
    }

    // registra o viewmodel com dependência de settingsViewModel
    OCTOPRINT_VIEWMODELS.push({
        construct: Fazenda3DViewModel,
        dependencies: ["settingsViewModel"],
        elements: ["#tab_plugin_fazenda3d"] // id da aba/tab
    });
});
