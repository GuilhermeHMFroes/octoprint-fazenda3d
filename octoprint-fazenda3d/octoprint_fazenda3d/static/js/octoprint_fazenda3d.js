/*
 * View model for OctoPrint-Fazenda3D
 *
 * Author: Guilhemre Froes
 * License: AGPL-3.0
 */
$(function() {
    function Octoprint_fazenda3dViewModel(parameters) {
        var self = this;

        // assign the injected parameters, e.g.:
        // self.loginStateViewModel = parameters[0];
        // self.settingsViewModel = parameters[1];

        // TODO: Implement your plugin's view model here.
    }

    /* view model class, parameters for constructor, container to bind to
     * Please see http://docs.octoprint.org/en/main/plugins/viewmodels.html#registering-custom-viewmodels for more details
     * and a full list of the available options.
     */
    OCTOPRINT_VIEWMODELS.push({
        construct: Octoprint_fazenda3dViewModel,
        // ViewModels your plugin depends on, e.g. loginStateViewModel, settingsViewModel, ...
        dependencies: [ /* "loginStateViewModel", "settingsViewModel" */ ],
        // Elements to bind to, e.g. #settings_plugin_octoprint_fazenda3d, #tab_plugin_octoprint_fazenda3d, ...
        elements: [ /* ... */ ]
    });
});
