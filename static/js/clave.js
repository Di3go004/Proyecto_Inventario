/*
 * La casilla "Generar una contraseña segura" y el campo para escribirla son
 * excluyentes, y la pantalla lo tiene que mostrar así.
 *
 * Antes podían quedar las dos activas a la vez y ganaba la generada, en
 * silencio: alguien escribía la contraseña que quería, el sistema guardaba
 * otra al azar y se quedaba sin poder entrar sin entender por qué. El
 * servidor ya da prioridad a la escrita; esto evita que la duda aparezca.
 */
(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', function () {
    var generar = document.getElementById('id_generar');
    var clave = document.getElementById('id_clave');
    if (!generar || !clave) return;

    function actualizarPista() {
      clave.placeholder = generar.checked ? 'Se genera sola al guardar' : '';
    }

    generar.addEventListener('change', function () {
      // Marcar "generar" descarta lo que se hubiera escrito, para que no
      // queden dos contraseñas distintas a la vista.
      if (generar.checked) clave.value = '';
      actualizarPista();
    });

    // Y empezar a escribir desmarca la casilla: es lo que la persona quiere.
    clave.addEventListener('input', function () {
      if (clave.value) generar.checked = false;
      actualizarPista();
    });

    actualizarPista();
  });
})();
