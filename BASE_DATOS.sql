-- =====================================================================
-- Sistema de Control de Bodega — Esquema de base de datos (PostgreSQL)
-- =====================================================================
-- Este archivo es el diseño lógico de la base de datos descrita en
-- PLAN.md, REQUERIMIENTOS_FUNCIONALES.md y REQUERIMIENTOS_NO_FUNCIONALES.md.
-- Está pensado para revisarse y para construir el ERD a partir de él.
--
-- Nota sobre usuarios/login: aquí se modela "usuarios" como una tabla
-- propia para que el ERD sea autocontenido. En la implementación real con
-- Django, el login/contraseña normalmente lo maneja la tabla interna
-- auth_user (con hash de contraseña ya resuelto por el framework) y esta
-- tabla "usuarios" pasaría a ser un "perfil" 1 a 1 con rol_id — la lógica
-- y las relaciones con el resto del sistema son las mismas.
-- =====================================================================


-- ---------------------------------------------------------------------
-- 1. ROLES Y USUARIOS
-- ---------------------------------------------------------------------
-- roles es una tabla (no un simple CHECK) porque además del nombre
-- puede interesar guardar una descripción de qué puede hacer cada uno,
-- y porque el sistema ya nace con 3 roles pero el diseño no debería
-- romperse si algún día agregan un cuarto rol.

CREATE TABLE roles (
    id              SERIAL PRIMARY KEY,
    nombre          VARCHAR(30) NOT NULL UNIQUE,   -- administrador | operador | contabilidad
    descripcion     VARCHAR(200)
);

CREATE TABLE usuarios (
    id              SERIAL PRIMARY KEY,
    nombre_completo VARCHAR(150) NOT NULL,
    usuario         VARCHAR(50)  NOT NULL UNIQUE,  -- login
    contrasena_hash VARCHAR(255) NOT NULL,
    rol_id          INTEGER NOT NULL REFERENCES roles(id) ON DELETE RESTRICT,
    activo          BOOLEAN NOT NULL DEFAULT TRUE, -- se desactiva, no se borra (ver nota abajo)
    fecha_creacion  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Por qué "activo" en vez de DELETE: todo movimiento/préstamo queda
-- asociado a un usuario (RNF-04, trazabilidad). Si se pudiera borrar un
-- usuario de verdad, se perdería o se rompería ese historial. Por eso el
-- registro se desactiva (ya no puede iniciar sesión) pero nunca se elimina.


-- ---------------------------------------------------------------------
-- 2. BODEGAS Y CATEGORÍAS (compartidas por ambos módulos)
-- ---------------------------------------------------------------------
-- Se modela "bodega" como tabla (no como texto fijo "Bodega 1"/"Bodega 2")
-- para cumplir RNF-09 (poder agregar más bodegas a futuro sin rediseñar).

CREATE TABLE bodegas (
    id              SERIAL PRIMARY KEY,
    nombre          VARCHAR(50) NOT NULL UNIQUE,       -- 'Bodega 1', 'Bodega 2', 'Bodega Técnica'
    tipo            VARCHAR(10) NOT NULL,               -- 'venta' | 'tecnica'
    descripcion     VARCHAR(200),
    CONSTRAINT chk_bodega_tipo CHECK (tipo IN ('venta', 'tecnica'))
);

-- categorias agrupa productos dentro de cada módulo (ej. "Básculas",
-- "Repuestos", "Equipo Técnico"). Es una sola tabla para los dos módulos
-- porque la relación con articulos/activos ya indica a cuál pertenece;
-- el campo "modulo" evita mezclar categorías de venta con las técnicas
-- en los formularios.

CREATE TABLE categorias (
    id              SERIAL PRIMARY KEY,
    nombre          VARCHAR(100) NOT NULL,
    modulo          VARCHAR(10) NOT NULL,               -- 'ventas' | 'tecnica'
    CONSTRAINT chk_categoria_modulo CHECK (modulo IN ('ventas', 'tecnica')),
    CONSTRAINT uq_categoria UNIQUE (nombre, modulo)
);


-- ---------------------------------------------------------------------
-- 3. PROVEEDORES
-- ---------------------------------------------------------------------
-- En los Excel actuales el mismo proveedor (KEERDA, BRECKNELL, LOCOSC,
-- AVERY WEIGH TRONIX...) se repite en muchas filas escrito a mano cada
-- vez. Se normaliza en su propia tabla para no duplicar el nombre y para
-- poder reutilizarlo tanto en el catálogo (proveedor habitual del
-- artículo) como en cada ingreso concreto (RF-05).

CREATE TABLE proveedores (
    id              SERIAL PRIMARY KEY,
    nombre          VARCHAR(150) NOT NULL UNIQUE,
    contacto        VARCHAR(150),
    telefono        VARCHAR(50)
);


-- ---------------------------------------------------------------------
-- 4. MÓDULO VENTAS — Bodega 1 y Bodega 2  (FO-SE-053)
-- ---------------------------------------------------------------------

CREATE TABLE articulos (
    id                SERIAL PRIMARY KEY,
    codigo_interno    VARCHAR(50)  NOT NULL UNIQUE,     -- el código que se captura/escanea
    numero_serie      VARCHAR(100) UNIQUE,               -- pedido por el usuario: identificador único adicional
    nombre_producto   VARCHAR(200) NOT NULL,
    marca             VARCHAR(100),
    modelo            VARCHAR(100),
    capacidad         VARCHAR(50),
    bodega_id         INTEGER NOT NULL REFERENCES bodegas(id)    ON DELETE RESTRICT,
    categoria_id      INTEGER          REFERENCES categorias(id) ON DELETE SET NULL,
    proveedor_id      INTEGER          REFERENCES proveedores(id) ON DELETE SET NULL,
    precio            NUMERIC(10,2) NOT NULL DEFAULT 0,
    imagen            VARCHAR(300),                       -- ruta del archivo subido desde el equipo (prioridad)
    imagen_url        VARCHAR(300),                       -- alternativa: link externo, si no se subió archivo

    -- Stock: se recalcula solo, ver trigger más abajo (RF-08). No se
    -- vuelve a escribir a mano semana a semana como en el Excel actual.
    stock_actual      INTEGER NOT NULL DEFAULT 0,

    -- Umbrales de alerta pedidos por el usuario para Bodega 1
    -- (óptimo 20 / alerta 5 / crítico 2), configurables por artículo.
    stock_optimo      INTEGER NOT NULL DEFAULT 20,
    stock_alerta      INTEGER NOT NULL DEFAULT 5,
    stock_critico     INTEGER NOT NULL DEFAULT 2,

    activo            BOOLEAN NOT NULL DEFAULT TRUE,     -- para "descontinuar" sin borrar el histórico
    fecha_creacion      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_actualizacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_stock_no_negativo CHECK (stock_actual >= 0),
    CONSTRAINT chk_umbrales_orden CHECK (stock_critico <= stock_alerta AND stock_alerta <= stock_optimo)
);

CREATE INDEX idx_articulos_bodega ON articulos(bodega_id);

-- movimientos_venta reemplaza los formatos en papel FO-SE-013 (ingreso) y
-- FO-SE-012 (salida). Se modelan juntos en una sola tabla, distinguidos
-- por tipo_documento, porque comparten casi todas las columnas y porque
-- así una salida de préstamo/demo puede "cerrarse" (registrar su regreso)
-- actualizando la misma fila en vez de crear una tabla aparte — el mismo
-- patrón de una sola fila con salida+entrada que ya usan en FO-SE-066.

CREATE TABLE movimientos_venta (
    id                SERIAL PRIMARY KEY,
    folio             VARCHAR(30),                       -- correlativo, para mantener numeración como hoy

    tipo_documento    VARCHAR(10) NOT NULL,               -- 'ingreso' | 'salida'
    tipo_transaccion  VARCHAR(20) NOT NULL,               -- 'venta' | 'prestamo_demo' | 'repuestos' | 'materiales_otro' | 'ajuste_inicial'

    articulo_id       INTEGER NOT NULL REFERENCES articulos(id) ON DELETE RESTRICT,
    cantidad          INTEGER NOT NULL,

    fecha             TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    usuario_id        INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE RESTRICT,  -- quién lo registró en el sistema

    solicitado_por    VARCHAR(150),                       -- campo "Solicitado por" del formato en papel
    entregado_por     VARCHAR(150),                       -- solo en salidas
    cliente_nombre    VARCHAR(150),                       -- solo en salidas de venta
    proveedor_id      INTEGER REFERENCES proveedores(id) ON DELETE SET NULL, -- solo en ingresos

    no_factura        VARCHAR(50),
    no_boleta         VARCHAR(50),
    envio_recibo      VARCHAR(100),
    observacion       TEXT,

    -- Cierre de préstamo/demo (equivalente a "DEVUELTO POR" en FO-SE-012):
    fecha_devolucion  TIMESTAMP,                          -- NULL mientras el equipo sigue afuera
    devuelto_por      VARCHAR(150),

    CONSTRAINT chk_tipo_documento CHECK (tipo_documento IN ('ingreso', 'salida')),
    CONSTRAINT chk_tipo_transaccion CHECK (tipo_transaccion IN ('venta', 'prestamo_demo', 'repuestos', 'materiales_otro', 'ajuste_inicial')),  -- 'ajuste_inicial': saldo con el que arranca un artículo nuevo por carga masiva (RF-09)
    CONSTRAINT chk_cantidad_positiva CHECK (cantidad > 0),
    -- Solo un movimiento de tipo préstamo/demo puede tener datos de devolución:
    CONSTRAINT chk_devolucion_solo_prestamo CHECK (
        tipo_transaccion = 'prestamo_demo' OR (fecha_devolucion IS NULL AND devuelto_por IS NULL)
    )
);

CREATE INDEX idx_mov_venta_articulo_fecha ON movimientos_venta(articulo_id, fecha);

-- Índice parcial: encuentra rápido los préstamos/demo que siguen abiertos
-- (RF-06/RF-14 — "qué hay actualmente afuera en demo o préstamo").
CREATE INDEX idx_mov_venta_prestamos_abiertos
    ON movimientos_venta(articulo_id)
    WHERE tipo_transaccion = 'prestamo_demo' AND fecha_devolucion IS NULL;


-- ---------------------------------------------------------------------
-- 5. MÓDULO ACTIVOS — Bodega Técnica  (FO-SE-065)
-- ---------------------------------------------------------------------
-- A diferencia de articulos, cada activo es una unidad física que se
-- identifica y se presta (no se "cuenta" como stock de un mismo modelo).

CREATE TABLE activos (
    id                SERIAL PRIMARY KEY,
    codigo_interno    VARCHAR(50)  NOT NULL UNIQUE,
    nombre_producto   VARCHAR(200) NOT NULL,
    marca             VARCHAR(100),
    modelo            VARCHAR(100),
    categoria_id      INTEGER REFERENCES categorias(id) ON DELETE SET NULL,
    bodega_id         INTEGER NOT NULL REFERENCES bodegas(id) ON DELETE RESTRICT,
    proveedor_id      INTEGER REFERENCES proveedores(id) ON DELETE SET NULL,

    precio            NUMERIC(10,2) NOT NULL DEFAULT 0,   -- pedido por el usuario: para valorizar la bodega técnica
    imagen            VARCHAR(300),                       -- ruta del archivo subido desde el equipo (prioridad)
    imagen_url        VARCHAR(300),                       -- alternativa: link externo, si no se subió archivo

    -- Estado pedido por el usuario: 3 valores, "de_baja" es definitivo.
    estado            VARCHAR(20) NOT NULL DEFAULT 'buen_estado',

    fecha_creacion      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_actualizacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_estado_activo CHECK (estado IN ('buen_estado', 'mal_estado', 'de_baja'))
);

CREATE INDEX idx_activos_bodega ON activos(bodega_id);

-- prestamos_activos reemplaza FO-SE-066: una fila = un ciclo completo de
-- préstamo (sale y, cuando regresa, se completan las columnas de regreso
-- en la misma fila), igual que en el formato de papel.

CREATE TABLE prestamos_activos (
    id                SERIAL PRIMARY KEY,
    activo_id         INTEGER NOT NULL REFERENCES activos(id) ON DELETE RESTRICT,
    cantidad          INTEGER NOT NULL DEFAULT 1,

    solicitante       VARCHAR(150) NOT NULL,
    fecha_salida      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    entregado_por     VARCHAR(150),
    estado_al_salir   VARCHAR(20) NOT NULL,

    fecha_regreso     TIMESTAMP,                          -- NULL mientras el activo sigue afuera
    recibido_por      VARCHAR(150),
    estado_al_regresar VARCHAR(20),

    observacion       TEXT,
    usuario_id        INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE RESTRICT,

    CONSTRAINT chk_cantidad_prestamo CHECK (cantidad > 0),
    CONSTRAINT chk_estado_al_salir CHECK (estado_al_salir IN ('buen_estado', 'mal_estado')),
    CONSTRAINT chk_estado_al_regresar CHECK (estado_al_regresar IS NULL OR estado_al_regresar IN ('buen_estado', 'mal_estado', 'de_baja'))
);

-- Regla de negocio clave de RF-07: un mismo activo no puede tener dos
-- préstamos abiertos a la vez. Se garantiza con un índice único parcial
-- (solo cuenta las filas donde fecha_regreso todavía es NULL) en vez de
-- validarlo solamente en la aplicación.
CREATE UNIQUE INDEX ux_prestamo_abierto_por_activo
    ON prestamos_activos(activo_id)
    WHERE fecha_regreso IS NULL;


-- =====================================================================
-- 6. AUTOMATIZACIONES (triggers)
-- =====================================================================

-- 6.1 Mantener fecha_actualizacion al día en articulos y activos.
CREATE OR REPLACE FUNCTION fn_set_fecha_actualizacion()
RETURNS TRIGGER AS $$
BEGIN
    NEW.fecha_actualizacion = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_articulos_fecha_actualizacion
    BEFORE UPDATE ON articulos
    FOR EACH ROW EXECUTE FUNCTION fn_set_fecha_actualizacion();

CREATE TRIGGER trg_activos_fecha_actualizacion
    BEFORE UPDATE ON activos
    FOR EACH ROW EXECUTE FUNCTION fn_set_fecha_actualizacion();


-- 6.2 RF-08: stock_actual se DERIVA de los movimientos, no se acumula.
--
-- Version anterior de este archivo: sumaba/restaba un delta solo al INSERT.
-- Se cambio porque editar o borrar un movimiento dejaba el stock
-- desincronizado sin avisar (comprobado en pruebas). Ahora, ante cualquier
-- cambio (alta, edicion o borrado), el stock se vuelve a calcular completo:
--
--     ingresos - salidas + salidas de prestamo/demo ya devueltas
--
-- La implementacion real vive en Python (ventas/models.py:
-- Articulo.calcular_stock_desde_movimientos + MovimientoVenta.save/delete),
-- porque ahi tambien se puede devolver un mensaje claro al usuario cuando
-- una salida supera el stock. Este bloque queda como referencia del ERD y
-- para quien prefiera resolverlo con triggers en la base de datos.
CREATE OR REPLACE FUNCTION fn_recalcular_stock_articulo(p_articulo_id INTEGER)
RETURNS VOID AS $$
BEGIN
    UPDATE articulos SET stock_actual = COALESCE((
        SELECT SUM(
            CASE
                WHEN m.tipo_documento = 'ingreso' THEN m.cantidad
                -- Un prestamo/demo ya devuelto salio y volvio: neto cero.
                WHEN m.tipo_documento = 'salida'
                     AND m.tipo_transaccion = 'prestamo_demo'
                     AND m.fecha_devolucion IS NOT NULL THEN 0
                WHEN m.tipo_documento = 'salida' THEN -m.cantidad
                ELSE 0
            END
        )
        FROM movimientos_venta m
        WHERE m.articulo_id = p_articulo_id
    ), 0)
    WHERE id = p_articulo_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION fn_sincronizar_stock_venta()
RETURNS TRIGGER AS $$
BEGIN
    IF (TG_OP = 'DELETE') THEN
        PERFORM fn_recalcular_stock_articulo(OLD.articulo_id);
        RETURN OLD;
    END IF;
    PERFORM fn_recalcular_stock_articulo(NEW.articulo_id);
    -- Si el movimiento cambio de articulo, hay que recalcular tambien el anterior.
    IF (TG_OP = 'UPDATE' AND OLD.articulo_id <> NEW.articulo_id) THEN
        PERFORM fn_recalcular_stock_articulo(OLD.articulo_id);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Un solo trigger cubre alta, edicion y borrado (antes solo cubria el alta).
CREATE TRIGGER trg_mov_venta_sincroniza_stock
    AFTER INSERT OR UPDATE OR DELETE ON movimientos_venta
    FOR EACH ROW EXECUTE FUNCTION fn_sincronizar_stock_venta();


-- 6.4 No permitir crear un préstamo de un activo que ya está "de_baja".
CREATE OR REPLACE FUNCTION fn_validar_activo_disponible()
RETURNS TRIGGER AS $$
DECLARE
    v_estado VARCHAR(20);
BEGIN
    SELECT estado INTO v_estado FROM activos WHERE id = NEW.activo_id;
    IF v_estado = 'de_baja' THEN
        RAISE EXCEPTION 'El activo % está dado de baja y no se puede prestar', NEW.activo_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_prestamo_activo_disponible
    BEFORE INSERT ON prestamos_activos
    FOR EACH ROW EXECUTE FUNCTION fn_validar_activo_disponible();


-- =====================================================================
-- 7. VISTAS DE APOYO PARA REPORTES (RF-11 / RF-14)
-- =====================================================================

-- Nivel de alerta de stock por artículo (Bodega 1 principalmente).
CREATE OR REPLACE VIEW vista_alertas_stock AS
SELECT
    a.id, a.codigo_interno, a.nombre_producto, b.nombre AS bodega,
    a.stock_actual, a.stock_optimo, a.stock_alerta, a.stock_critico,
    CASE
        WHEN a.stock_actual <= a.stock_critico THEN 'critico'
        WHEN a.stock_actual <= a.stock_alerta  THEN 'alerta'
        WHEN a.stock_actual >= a.stock_optimo  THEN 'optimo'
        ELSE 'normal'
    END AS nivel_alerta
FROM articulos a
JOIN bodegas b ON b.id = a.bodega_id
WHERE a.activo = TRUE;

-- Equipos de venta actualmente afuera en préstamo/demo.
CREATE OR REPLACE VIEW vista_prestamos_venta_abiertos AS
SELECT m.id, a.codigo_interno, a.nombre_producto, m.cantidad,
       m.solicitado_por, m.fecha AS fecha_salida
FROM movimientos_venta m
JOIN articulos a ON a.id = m.articulo_id
WHERE m.tipo_transaccion = 'prestamo_demo' AND m.fecha_devolucion IS NULL;

-- Activos de Bodega Técnica actualmente prestados y quién los tiene.
CREATE OR REPLACE VIEW vista_activos_prestados AS
SELECT p.id, ac.codigo_interno, ac.nombre_producto, p.solicitante,
       p.fecha_salida, p.estado_al_salir
FROM prestamos_activos p
JOIN activos ac ON ac.id = p.activo_id
WHERE p.fecha_regreso IS NULL;


-- =====================================================================
-- 8. DATOS INICIALES (seed)
-- =====================================================================

INSERT INTO roles (nombre, descripcion) VALUES
    ('administrador', 'Acceso total: catálogo, usuarios, carga masiva, reportes'),
    ('operador',      'Registra movimientos y préstamos, sin editar el catálogo'),
    ('contabilidad',  'Solo lectura a todo el sistema');

INSERT INTO bodegas (nombre, tipo, descripcion) VALUES
    ('Bodega 1', 'venta',   'Indicadores, pesas, básculas, masas patrón, kits de conversión, celdas de montaje, balanzas'),
    ('Bodega 2', 'venta',   'Repuestos: celdas de carga, partes de báscula, accesorios, conectores, pantallas remotas, básculas de supermercado'),
    ('Bodega Técnica', 'tecnica', 'Herramientas y activos de uso interno de la empresa');
