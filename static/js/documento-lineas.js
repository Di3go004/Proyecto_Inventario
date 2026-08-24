/*
 * Líneas de un documento de bodega (FO-SE-013 / FO-SE-012).
 *
 * Una boleta lleva varios productos, así que la tabla del detalle se puede
 * ir agrandando sin recargar la página. Cada fila nueva se clona de un
 * <template> y se le engancha su propio buscador con sugerencias.
 *
 * También avisa en el momento si una salida se pasa del stock disponible.
 * Es solo una ayuda visual: quien decide de verdad es el servidor, que
 * recalcula el stock desde los movimientos antes de guardar (RF-08).
 */
(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', function () {
    var cuerpo = document.getElementById('cuerpo-lineas');
    if (!cuerpo) return;

    var plantilla = document.getElementById('plantilla-linea');
    var boton = document.getElementById('agregar-linea');
    var esSalida = document.getElementById('form-documento').dataset.tipo === 'salida';

    function renumerar() {
      cuerpo.querySelectorAll('tr.linea').forEach(function (fila, indice) {
        var numero = fila.querySelector('.linea-numero');
        if (numero) numero.textContent = String(indice + 1);
      });
      // Con una sola línea no tiene sentido ofrecer quitarla.
      var sobra = cuerpo.querySelectorAll('tr.linea').length > 1;
      cuerpo.querySelectorAll('.quitar-linea').forEach(function (btn) {
        btn.disabled = !sobra;
      });
    }

    function revisarCantidad(fila) {
      if (!esSalida) return;
      var disponible = fila.dataset.stock;
      var campo = fila.querySelector('.linea-cantidad');
      var aviso = fila.querySelector('.linea-aviso');
      if (!aviso || disponible === undefined || !campo.value) {
        if (aviso) aviso.textContent = '';
        return;
      }
      var pedido = parseInt(campo.value, 10);
      if (!isNaN(pedido) && pedido > parseInt(disponible, 10)) {
        aviso.textContent = 'Solo hay ' + disponible + ' en existencia.';
        fila.classList.add('linea-sin-stock');
      } else {
        aviso.textContent = '';
        fila.classList.remove('linea-sin-stock');
      }
    }

    function agregarFila() {
      var fila = plantilla.content.firstElementChild.cloneNode(true);
      cuerpo.appendChild(fila);
      window.iniciarAutocompletar(fila);
      renumerar();
      var texto = fila.querySelector('.autocompletar-texto');
      if (texto) texto.focus();
      return fila;
    }

    if (boton) boton.addEventListener('click', agregarFila);

    cuerpo.addEventListener('click', function (evento) {
      var quitar = evento.target.closest('.quitar-linea');
      if (!quitar) return;
      if (cuerpo.querySelectorAll('tr.linea').length <= 1) return;
      quitar.closest('tr.linea').remove();
      renumerar();
    });

    cuerpo.addEventListener('autocompletar:seleccion', function (evento) {
      var fila = evento.target.closest('tr.linea');
      if (!fila) return;
      var item = evento.detail;
      fila.dataset.stock = item.stock;
      var info = fila.querySelector('.linea-info');
      if (info) info.textContent = item.bodega + ' · existencia ' + item.stock;
      revisarCantidad(fila);
    });

    cuerpo.addEventListener('autocompletar:limpieza', function (evento) {
      var fila = evento.target.closest('tr.linea');
      if (!fila) return;
      delete fila.dataset.stock;
      var info = fila.querySelector('.linea-info');
      if (info) info.textContent = '';
      var aviso = fila.querySelector('.linea-aviso');
      if (aviso) aviso.textContent = '';
      fila.classList.remove('linea-sin-stock');
    });

    cuerpo.addEventListener('input', function (evento) {
      if (evento.target.classList.contains('linea-cantidad')) {
        revisarCantidad(evento.target.closest('tr.linea'));
      }
    });

    // Enter dentro del detalle agrega otra línea en vez de enviar el
    // documento a medias — enviar es siempre con el botón de abajo.
    cuerpo.addEventListener('keydown', function (evento) {
      if (evento.key === 'Enter' && evento.target.classList.contains('linea-cantidad')) {
        evento.preventDefault();
        agregarFila();
      }
    });

    if (!cuerpo.querySelectorAll('tr.linea').length) agregarFila();
    renumerar();
  });
})();
