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

    function resumen(item) {
      var partes = [item.bodega, 'existencia ' + item.stock];
      // Solo en el ingreso: es la columna "Nombre de proveedor" del
      // FO-SE-013, que ya no se escribe a mano sino que sale del catálogo.
      // Enseñarla acá confirma de dónde va a salir, y avisa a tiempo si al
      // producto le falta ese dato.
      if (!esSalida) partes.push(item.proveedor || 'sin proveedor registrado');
      return partes.join(' · ');
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
      if (window.iniciarSeriales) window.iniciarSeriales(fila.querySelector('.seriales'));
      renumerar();
      var texto = fila.querySelector('.autocompletar-texto');
      if (texto) texto.focus();
      return fila;
    }

    if (boton) boton.addEventListener('click', agregarFila);

    /*
     * Una línea de un producto que se controla por unidad no pide cantidad:
     * pide seriales, y la cantidad es cuántos son. Así no existe el caso de
     * "cantidad 3, dos seriales" — que es como la existencia del producto y
     * sus unidades terminarían diciendo cosas distintas.
     */
    function acomodarSeriales(fila, item) {
      var caja = fila.querySelector('.linea-seriales');
      if (!caja) return;

      var lleva = !!(item && item.lleva_serie);
      var cantidad = fila.querySelector('.linea-cantidad');

      // Se esconde ANTES de vaciarla: al vaciarse avisa del cambio, y el
      // aviso de una caja escondida no debe tocar la cantidad de la línea.
      caja.hidden = !lleva;

      if (cantidad) {
        cantidad.readOnly = lleva;
        cantidad.title = lleva ? 'Sale de cuántos seriales lleve la línea.' : '';
      }

      if (!lleva) {
        if (caja.vaciarSeriales) caja.vaciarSeriales();
        return;
      }
      // En la salida son los que el producto tiene en bodega; en el ingreso
      // no hay lista previa: son los que vienen llegando.
      if (caja.actualizarDisponibles) caja.actualizarDisponibles(item.seriales || []);
    }

    cuerpo.addEventListener('seriales:cambio', function (evento) {
      var fila = evento.target.closest('tr.linea');
      if (!fila || evento.target.hidden) return;
      var cantidad = fila.querySelector('.linea-cantidad');
      if (cantidad) cantidad.value = evento.detail.cuantos || '';
      revisarCantidad(fila);
    });

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
      if (info) info.textContent = resumen(item);
      // Se propone el precio del catalogo, que es el caso normal. Queda
      // editable: si la factura del proveedor trae otro, ese manda, y es el
      // que se guarda pegado al movimiento.
      var precio = fila.querySelector('.linea-precio');
      if (precio && !precio.value && item.precio) precio.value = item.precio;
      acomodarSeriales(fila, item);
      revisarCantidad(fila);
    });

    cuerpo.addEventListener('autocompletar:limpieza', function (evento) {
      var fila = evento.target.closest('tr.linea');
      if (!fila) return;
      delete fila.dataset.stock;
      var info = fila.querySelector('.linea-info');
      if (info) info.textContent = '';
      var precioVacio = fila.querySelector('.linea-precio');
      if (precioVacio) precioVacio.value = '';
      var aviso = fila.querySelector('.linea-aviso');
      if (aviso) aviso.textContent = '';
      acomodarSeriales(fila, null);
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
