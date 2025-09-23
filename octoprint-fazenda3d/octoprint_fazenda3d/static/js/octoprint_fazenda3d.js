$(function() {
    function Fazenda3DViewModel(parameters) {
        var self = this;

        self.servidor_url = ko.observable();
        self.token = ko.observable();
        self.nome_impressora = ko.observable();
        self.connectionStatus = ko.observable("Desconectado");

        self.connectToServer = function() {
            // monta objeto
            const dados = {
                command: "connect",
                servidor_url: self.servidor_url(),
                token: self.token(),
                nome_impressora: self.nome_impressora()
            };

            // loga no console tudo que vai ser enviado
            console.log("=== Clique no botão Conectar ao Servidor ===");
            console.log("Servidor URL digitado:", self.servidor_url());
            console.log("Token digitado:", self.token());
            console.log("Nome digitado:", self.nome_impressora());
            console.log("Payload que será enviado:", dados);

            fetch(API_BASEURL + "plugin/fazenda3d", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-Api-Key": UI_API_KEY
                },
                body: JSON.stringify(dados)
            })
            .then(r => r.json())
            .then(resp => {
                console.log("Resposta do plugin:", resp);
                if (resp.success) {
                    self.connectionStatus("Conectado com sucesso!");
                } else {
                    self.connectionStatus("Falha: " + (resp.message || "Erro"));
                }
            })
            .catch(err => {
                console.error("Erro ao chamar plugin:", err);
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
