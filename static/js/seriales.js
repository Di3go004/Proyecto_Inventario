/*
 * Captura de números de serie, uno por uno.
 *
 * Antes era un recuadro de texto con un serial por línea. Funcionaba, pero
 * los errores salían todos juntos al guardar: quien está cargando doscientos
 * seriales se enteraba al final de que el número 37 estaba repetido. Acá cada
 * serial se revisa al momento de agregarlo.
 *
 * El recuadro de texto NO desaparece: se esconde y sigue siendo el campo que
 * viaja al servidor. Así el servidor no se entera del cambio, las pruebas que
 * mandan texto plano siguen valiendo, y si el navegador no corre el script la
 * pantalla se puede usar igual.
 *
 * Dos modos:
 *   libre   — se escriben seriales nuevos (alta del producto, ingreso).
 *   elegir  — se toman de los que hay en bodega (salida). Ahí no se inventa
 *             nada: lo que no está en la lista no se acepta.
 *
 * Pegar una lista de Excel sigue funcionando: se reparte en varios.
 */
(function () {
  'use strict';

  // Lo que separa un serial de otro al pegar: saltos de línea, tabuladores
  // (una columna de Excel), comas y punto y coma.
  var SEPARADORES = /[\r\n\t,;]+/;

  // A partir de acá la lista de disponibles se vuelve una pared: se ofrece
  // el autocompletado del navegador en vez de pintarlos todos.
  var MAXIMO_A_LA_VISTA = 24;

  function limpiar(texto) {
    return (texto || '').trim();
  }

  function iguales(uno, otro) {
    return uno.toUpperCase() === otro.toUpperCase();
  }

  function iniciarSeriales(caja) {
    if (!caja || caja.dataset.listo === '1') return;

    var fuente = caja.querySelector('.seriales-fuente');
    if (!fuente) return;
    caja.dataset.listo = '1';

    var eligiendo = caja.dataset.modo === 'elegir';
    var disponibles = leerDisponibles(caja);
    var puestos = limpiar(fuente.value).split(/\r?\n/).map(limpiar).filter(Boolean);

    fuente.hidden = true;

    var lista = document.createElement('div');
    lista.className = 'seriales-lista';

    var entrada = document.createElement('input');
    entrada.type = 'text';
    entrada.className = 'seriales-entrada';
    entrada.autocomplete = 'off';
    entrada.placeholder = eligiendo ? 'Serial que sale…' : 'Escribe un serial y Enter';
    entrada.setAttribute('aria-label', 'Agregar número de serie');

    var aviso = document.createElement('span');
    aviso.className = 'seriales-aviso';
    aviso.setAttribute('role', 'status');

    var banca = document.createElement('div');
    banca.className = 'seriales-banca';

    caja.appendChild(lista);
    caja.appendChild(entrada);
    caja.appendChild(banca);
    caja.appendChild(aviso);

    var sugerencias = null;
    if (eligiendo) enlazarSugerencias();

    // --- estado ---------------------------------------------------------

    function leerDisponibles(donde) {
      try {
        return JSON.parse(donde.dataset.disponibles || '[]');
      } catch (error) {
        return [];
      }
    }

    function yaEsta(serial) {
      return puestos.some(function (puesto) { return iguales(puesto, serial); });
    }

    function existeEnBodega(serial) {
      return disponibles.some(function (libre) { return iguales(libre, serial); });
    }

    function guardar() {
      fuente.value = puestos.join('\n');
      // Para que la pantalla que contiene esta caja pueda reaccionar: en el
      // documento, la cantidad de la línea es cuántos seriales hay.
      caja.dispatchEvent(new CustomEvent('seriales:cambio', {
        bubbles: true,
        detail: { seriales: puestos.slice(), cuantos: puestos.length },
      }));
    }

    function decir(mensaje) {
      aviso.textContent = mensaje || '';
    }

    // --- agregar y quitar -----------------------------------------------

    function agregar(crudo) {
      var serial = limpiar(crudo);
      if (!serial) return false;

      if (yaEsta(serial)) {
        decir('"' + serial + '" ya está en la lista.');
        return false;
      }
      if (eligiendo && !existeEnBodega(serial)) {
        decir('"' + serial + '" no está en bodega.');
        return false;
      }

      puestos.push(serial);
      return true;
    }

    function agregarVarios(crudo) {
      var partes = String(crudo).split(SEPARADORES);
      var antes = puestos.length;
      decir('');
      partes.forEach(agregar);
      if (puestos.length !== antes) {
        pintar();
        guardar();
      }
      return puestos.length - antes;
    }

    function quitar(indice) {
      puestos.splice(indice, 1);
      decir('');
      pintar();
      guardar();
    }

    // --- pintado --------------------------------------------------------

    function pintar() {
      lista.textContent = '';

      puestos.forEach(function (serial, indice) {
        var chip = document.createElement('span');
        chip.className = 'serial-chip';

        var texto = document.createElement('span');
        texto.className = 'serial-chip-texto';
        texto.textContent = serial;

        var quitarlo = document.createElement('button');
        quitarlo.type = 'button';
        quitarlo.className = 'serial-chip-quitar';
        quitarlo.textContent = '×';
        quitarlo.title = 'Quitar ' + serial;
        quitarlo.setAttribute('aria-label', 'Quitar ' + serial);
        quitarlo.addEventListener('click', function () { quitar(indice); });

        chip.appendChild(texto);
        chip.appendChild(quitarlo);
        lista.appendChild(chip);
      });

      var cuenta = document.createElement('span');
      cuenta.className = 'seriales-cuenta';
      cuenta.textContent = puestos.length === 0
        ? 'Ninguno todavía'
        : puestos.length + (puestos.length === 1 ? ' unidad' : ' unidades');
      lista.appendChild(cuenta);

      pintarBanca();
    }

    /* En la salida, los que quedan por elegir: se agregan con un clic, que es
       más rápido y no se puede teclear mal. Si son demasiados se deja solo el
       autocompletado, porque una pared de seriales no ayuda a nadie. */
    function pintarBanca() {
      banca.textContent = '';
      if (!eligiendo) return;

      var quedan = disponibles.filter(function (serial) { return !yaEsta(serial); });
      if (!quedan.length || quedan.length > MAXIMO_A_LA_VISTA) return;

      var titulo = document.createElement('span');
      titulo.className = 'seriales-banca-titulo';
      titulo.textContent = 'En bodega:';
      banca.appendChild(titulo);

      quedan.forEach(function (serial) {
        var boton = document.createElement('button');
        boton.type = 'button';
        boton.className = 'serial-libre';
        boton.textContent = serial;
        boton.addEventListener('click', function () { agregarVarios(serial); });
        banca.appendChild(boton);
      });
    }

    function enlazarSugerencias() {
      var listaId = 'seriales-' + Math.random().toString(36).slice(2, 9);
      sugerencias = document.createElement('datalist');
      sugerencias.id = listaId;
      disponibles.forEach(function (serial) {
        var opcion = document.createElement('option');
        opcion.value = serial;
        sugerencias.appendChild(opcion);
      });
      caja.appendChild(sugerencias);
      entrada.setAttribute('list', listaId);
    }

    // --- teclado y pegado -------------------------------------------------

    entrada.addEventListener('keydown', function (evento) {
      if (evento.key === 'Enter') {
        // Enter acá agrega el serial; nunca envía el formulario a medias.
        evento.preventDefault();
        if (agregarVarios(entrada.value)) entrada.value = '';
        return;
      }
      // Retroceso con la caja vacía borra el último, como en los buscadores
      // que ya conocen.
      if (evento.key === 'Backspace' && !entrada.value && puestos.length) {
        quitar(puestos.length - 1);
      }
    });

    // Salir del campo con algo escrito lo agrega: es lo que espera quien
    // escribió el serial y se fue directo al botón de guardar.
    entrada.addEventListener('blur', function () {
      if (agregarVarios(entrada.value)) entrada.value = '';
    });

    entrada.addEventListener('paste', function (evento) {
      var pegado = (evento.clipboardData || window.clipboardData).getData('text');
      if (!pegado || !SEPARADORES.test(pegado)) return;   // uno solo: camino normal
      evento.preventDefault();
      agregarVarios(pegado);
      entrada.value = '';
    });

    /* La caja se puede reusar: la salida cambia de producto y con eso cambian
       los seriales que hay en bodega. */
    caja.actualizarDisponibles = function (nuevos) {
      disponibles = nuevos || [];
      var sobrevivientes = eligiendo
        ? puestos.filter(existeEnBodega)
        : puestos;
      if (sobrevivientes.length !== puestos.length) puestos = sobrevivientes;
      if (sugerencias) {
        sugerencias.textContent = '';
        disponibles.forEach(function (serial) {
          var opcion = document.createElement('option');
          opcion.value = serial;
          sugerencias.appendChild(opcion);
        });
      }
      decir('');
      pintar();
      guardar();
    };

    caja.vaciarSeriales = function () {
      puestos = [];
      decir('');
      pintar();
      guardar();
    };

    pintar();
  }

  function iniciarTodas(raiz) {
    (raiz || document).querySelectorAll('.seriales').forEach(iniciarSeriales);
  }

  window.iniciarSeriales = iniciarSeriales;
  window.iniciarSerialesEn = iniciarTodas;

  document.addEventListener('DOMContentLoaded', function () { iniciarTodas(document); });
})();
