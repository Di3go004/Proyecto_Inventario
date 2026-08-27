/*
 * RF-13 — Buscador con sugerencias mientras se escribe.
 *
 * Sustituye al lector de código de barras que se descartó: el operador
 * escribe parte del código o del nombre y elige de una lista, sin tener que
 * saberse el código completo ni abrir el catálogo en otra pestaña.
 *
 * JavaScript sin librerías a propósito: el sistema corre en la red local de
 * la empresa y muchas veces sin salida a internet (RNF-01), así que no puede
 * depender de un CDN.
 *
 * Uso en la plantilla:
 *
 *   <div class="autocompletar" data-url="/api/ventas/articulos/">
 *     <input type="text"   class="autocompletar-texto" autocomplete="off">
 *     <input type="hidden" class="autocompletar-valor" name="linea_articulo">
 *   </div>
 *
 * Al elegir una opción dispara el evento "autocompletar:seleccion" sobre el
 * contenedor, con el resultado completo en event.detail.
 */
(function () {
  'use strict';

  var ESPERA_MS = 180;      // ni tan rápido que dispare por cada tecla, ni tan lento que se sienta trabado
  var MINIMO_LETRAS = 2;

  function crearLista(contenedor) {
    var lista = document.createElement('ul');
    lista.className = 'autocompletar-lista';
    lista.setAttribute('role', 'listbox');
    lista.hidden = true;
    contenedor.appendChild(lista);
    return lista;
  }

  function iniciar(contenedor) {
    if (contenedor.dataset.iniciado === 'si') return;
    contenedor.dataset.iniciado = 'si';

    var campoTexto = contenedor.querySelector('.autocompletar-texto');
    var campoValor = contenedor.querySelector('.autocompletar-valor');
    var lista = contenedor.querySelector('.autocompletar-lista') || crearLista(contenedor);
    var url = contenedor.dataset.url;

    var resultados = [];
    var resaltado = -1;
    var temporizador = null;
    var peticion = 0;

    campoTexto.setAttribute('role', 'combobox');
    campoTexto.setAttribute('aria-expanded', 'false');
    campoTexto.setAttribute('aria-autocomplete', 'list');

    function cerrar() {
      lista.hidden = true;
      lista.innerHTML = '';
      resaltado = -1;
      campoTexto.setAttribute('aria-expanded', 'false');
    }

    function pintar() {
      lista.innerHTML = '';
      if (!resultados.length) {
        var vacio = document.createElement('li');
        vacio.className = 'autocompletar-vacio';
        vacio.textContent = 'Sin coincidencias';
        lista.appendChild(vacio);
        lista.hidden = false;
        campoTexto.setAttribute('aria-expanded', 'true');
        return;
      }

      resultados.forEach(function (item, indice) {
        var opcion = document.createElement('li');
        opcion.className = 'autocompletar-opcion';
        opcion.setAttribute('role', 'option');
        opcion.dataset.indice = String(indice);

        var titulo = document.createElement('span');
        titulo.className = 'autocompletar-nombre';
        titulo.textContent = item.nombre;

        var meta = document.createElement('span');
        meta.className = 'autocompletar-meta';
        meta.textContent = item.codigo + (item.detalle ? ' · ' + item.detalle : '');

        var estado = document.createElement('span');
        estado.className = 'chip chip-' + (
          item.nivel === 'critico' ? 'critical' : item.nivel === 'alerta' ? 'warn' :
          item.nivel === 'optimo' ? 'good' : 'neutral'
        );
        estado.textContent = item.prestado === true ? 'Prestado'
          : item.prestado === false ? 'Disponible'
          : item.bodega + ' · ' + item.stock;

        var textos = document.createElement('span');
        textos.className = 'autocompletar-textos';
        textos.appendChild(titulo);
        textos.appendChild(meta);

        opcion.appendChild(textos);
        opcion.appendChild(estado);

        // mousedown y no click: el click llega después del blur del input y
        // para entonces la lista ya se cerró.
        opcion.addEventListener('mousedown', function (evento) {
          evento.preventDefault();
          elegir(indice);
        });

        lista.appendChild(opcion);
      });

      lista.hidden = false;
      campoTexto.setAttribute('aria-expanded', 'true');
    }

    function marcar(nuevo) {
      var opciones = lista.querySelectorAll('.autocompletar-opcion');
      if (!opciones.length) return;
      if (resaltado >= 0 && opciones[resaltado]) {
        opciones[resaltado].classList.remove('resaltada');
      }
      resaltado = (nuevo + opciones.length) % opciones.length;
      opciones[resaltado].classList.add('resaltada');
      opciones[resaltado].scrollIntoView({ block: 'nearest' });
    }

    function elegir(indice) {
      var item = resultados[indice];
      if (!item) return;
      campoValor.value = item.id;
      campoTexto.value = item.codigo + ' — ' + item.nombre;
      contenedor.classList.add('tiene-seleccion');
      cerrar();
      contenedor.dispatchEvent(new CustomEvent('autocompletar:seleccion', {
        detail: item, bubbles: true,
      }));
      // Salta directo al siguiente campo (normalmente la cantidad): así se
      // captura una línea entera sin soltar el teclado.
      var siguiente = contenedor.dataset.siguiente
        ? contenedor.closest('tr, form').querySelector(contenedor.dataset.siguiente)
        : null;
      if (siguiente) siguiente.focus();
    }

    function buscar() {
      var consulta = campoTexto.value.trim();
      if (consulta.length < MINIMO_LETRAS) {
        resultados = [];
        cerrar();
        return;
      }
      var miPeticion = ++peticion;
      // El separador se decide mirando la URL: la pantalla de ingreso ya le
      // manda "?incluir=tecnica", y concatenar otro "?" la rompería.
      var separador = url.indexOf('?') === -1 ? '?' : '&';
      fetch(url + separador + 'q=' + encodeURIComponent(consulta), {
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      })
        .then(function (respuesta) { return respuesta.json(); })
        .then(function (datos) {
          // Descarta respuestas viejas que llegaron tarde y pisarían a la
          // que corresponde a lo que hay escrito ahora.
          if (miPeticion !== peticion) return;
          resultados = datos.resultados || [];
          pintar();
        })
        .catch(function () { cerrar(); });
    }

    campoTexto.addEventListener('input', function () {
      // Se cambió el texto: la selección anterior ya no vale.
      campoValor.value = '';
      contenedor.classList.remove('tiene-seleccion');
      contenedor.dispatchEvent(new CustomEvent('autocompletar:limpieza', { bubbles: true }));
      clearTimeout(temporizador);
      temporizador = setTimeout(buscar, ESPERA_MS);
    });

    campoTexto.addEventListener('keydown', function (evento) {
      if (lista.hidden) {
        if (evento.key === 'ArrowDown') buscar();
        return;
      }
      if (evento.key === 'ArrowDown') {
        evento.preventDefault();
        marcar(resaltado + 1);
      } else if (evento.key === 'ArrowUp') {
        evento.preventDefault();
        marcar(resaltado - 1);
      } else if (evento.key === 'Enter') {
        // Enter con la lista abierta elige; no envía el formulario a medias.
        evento.preventDefault();
        elegir(resaltado >= 0 ? resaltado : 0);
      } else if (evento.key === 'Escape') {
        cerrar();
      }
    });

    campoTexto.addEventListener('blur', function () {
      setTimeout(cerrar, 120);
    });
  }

  // Se expone para poder inicializar las filas que se agregan después.
  window.iniciarAutocompletar = function (raiz) {
    (raiz || document).querySelectorAll('.autocompletar').forEach(iniciar);
  };

  document.addEventListener('DOMContentLoaded', function () {
    window.iniciarAutocompletar(document);
  });
})();
