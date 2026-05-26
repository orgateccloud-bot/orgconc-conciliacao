/* /ui/ foi unificado com /app (dashboard Aurora Blue).
 * Backup do meta-refresh: redireciona via JS se o usuario chegou aqui.
 */
(function () {
  "use strict";
  // Redireciona imediatamente, preservando query string se houver
  const target = "/app" + window.location.search + window.location.hash;
  window.location.replace(target);
})();
