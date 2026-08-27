import streamlit as st
import pandas as pd
import numpy as np
import os
import threading
from datetime import datetime

# Configuración de la página
st.set_page_config(
    page_title="Control de Inventario - Avíos Textil",
    page_icon="🧵",
    layout="wide"
)

# Archivo de datos (respaldo local cuando no hay base de datos en la nube)
DATA_FILE = "inventario.csv"
MOVIMIENTOS_FILE = "movimientos.csv"
PAGOS_FILE = "pagos.csv"

COLUMNAS_INVENTARIO = ['id', 'nombre', 'categoria', 'color', 'tamaño', 'stock_actual',
                       'stock_minimo', 'precio_unitario', 'precio_compra', 'estado_pago',
                       'fecha_compra', 'numero_guia_factura', 'proveedor', 'ubicacion', 'fecha_registro']
COLUMNAS_MOVIMIENTOS = ['id', 'fecha', 'tipo', 'producto_id', 'producto_nombre',
                        'cantidad', 'motivo', 'usuario']
COLUMNAS_PAGOS = ['id', 'fecha_pago', 'producto_id', 'producto_nombre',
                  'monto', 'metodo_pago', 'referencia', 'observaciones']

# Base de datos en la nube (Turso). Se activa al configurar los secretos
# TURSO_DATABASE_URL y TURSO_AUTH_TOKEN. Sin ellos se usan los CSV locales.
def _db_config():
    try:
        url = st.secrets["TURSO_DATABASE_URL"]
        token = st.secrets["TURSO_AUTH_TOKEN"]
        if url and token:
            # HTTPS es más confiable que websocket (wss) para libsql-client
            if url.startswith("libsql://"):
                url = "https://" + url[len("libsql://"):]
            return url, token
    except Exception:
        pass
    return None, None

DB_URL, DB_TOKEN = _db_config()
USE_DB = bool(DB_URL and DB_TOKEN)

_db_lock = threading.RLock()


@st.cache_resource
def _db_client():
    import libsql_client
    return libsql_client.create_client_sync(DB_URL, auth_token=DB_TOKEN)


@st.cache_resource
def _db_inicializar():
    """Crea las tablas si no existen y migra los CSV la primera vez."""
    client = _db_client()
    with _db_lock:
        client.batch([
            """CREATE TABLE IF NOT EXISTS inventario (
                id INTEGER PRIMARY KEY, nombre TEXT, categoria TEXT, color TEXT,
                tamaño TEXT, stock_actual INTEGER, stock_minimo INTEGER,
                precio_unitario REAL, precio_compra REAL, estado_pago TEXT,
                fecha_compra TEXT, numero_guia_factura TEXT, proveedor TEXT,
                ubicacion TEXT, fecha_registro TEXT)""",
            """CREATE TABLE IF NOT EXISTS movimientos (
                id INTEGER PRIMARY KEY, fecha TEXT, tipo TEXT, producto_id INTEGER,
                producto_nombre TEXT, cantidad INTEGER, motivo TEXT, usuario TEXT)""",
            """CREATE TABLE IF NOT EXISTS pagos (
                id INTEGER PRIMARY KEY, fecha_pago TEXT, producto_id INTEGER,
                producto_nombre TEXT, monto REAL, metodo_pago TEXT,
                referencia TEXT, observaciones TEXT)""",
            "CREATE TABLE IF NOT EXISTS meta (clave TEXT PRIMARY KEY, valor TEXT)",
        ])
        # Migración única: si nunca se migró, importar los CSV existentes
        rs = client.execute("SELECT valor FROM meta WHERE clave = 'migrado'")
        if not rs.rows:
            for tabla, archivo, columnas in [
                ("inventario", DATA_FILE, COLUMNAS_INVENTARIO),
                ("movimientos", MOVIMIENTOS_FILE, COLUMNAS_MOVIMIENTOS),
                ("pagos", PAGOS_FILE, COLUMNAS_PAGOS),
            ]:
                if os.path.exists(archivo):
                    df = pd.read_csv(archivo)
                    for c in columnas:
                        if c not in df.columns:
                            df[c] = None
                    if not df.empty:
                        _db_guardar_tabla(tabla, df, columnas)
            client.execute("INSERT OR REPLACE INTO meta (clave, valor) VALUES ('migrado', '1')")
    return True


def _db_leer_tabla(tabla, columnas):
    client = _db_client()
    with _db_lock:
        rs = client.execute(f"SELECT {','.join(columnas)} FROM {tabla}")
        return pd.DataFrame(list(rs.rows), columns=list(rs.columns))


def _db_guardar_tabla(tabla, df, columnas):
    client = _db_client()
    stmts = [f"DELETE FROM {tabla}"]
    for _, fila in df.iterrows():
        valores = []
        for c in columnas:
            v = fila[c]
            if pd.isna(v):
                valores.append(None)
            elif isinstance(v, (int, np.integer)):
                valores.append(int(v))
            elif isinstance(v, (float, np.floating)):
                valores.append(float(v))
            else:
                valores.append(str(v))
        placeholders = ",".join(["?"] * len(columnas))
        stmts.append((f"INSERT INTO {tabla} ({','.join(columnas)}) VALUES ({placeholders})", valores))
    with _db_lock:
        client.batch(stmts)


if USE_DB:
    _db_inicializar()


def _normalizar_inventario(df):
    # Asegurar columnas nuevas (compatibilidad con datos antiguos)
    for campo in ['precio_compra', 'estado_pago', 'fecha_compra', 'numero_guia_factura']:
        if campo not in df.columns:
            df[campo] = None
    # Forzar tipos numéricos para evitar errores al comparar o estilizar
    for campo in ['stock_actual', 'stock_minimo']:
        df[campo] = pd.to_numeric(df[campo], errors='coerce').fillna(0).astype(int)
    return df


# Funciones de gestión de datos
def cargar_inventario():
    if USE_DB:
        return _normalizar_inventario(_db_leer_tabla("inventario", COLUMNAS_INVENTARIO))
    if os.path.exists(DATA_FILE):
        return _normalizar_inventario(pd.read_csv(DATA_FILE))
    df = pd.DataFrame(columns=COLUMNAS_INVENTARIO)
    df.to_csv(DATA_FILE, index=False)
    return df

def guardar_inventario(df):
    for campo in ['stock_actual', 'stock_minimo']:
        df[campo] = pd.to_numeric(df[campo], errors='coerce').fillna(0).astype(int)
    if USE_DB:
        _db_guardar_tabla("inventario", df, COLUMNAS_INVENTARIO)
    else:
        df.to_csv(DATA_FILE, index=False)

def cargar_movimientos():
    if USE_DB:
        return _db_leer_tabla("movimientos", COLUMNAS_MOVIMIENTOS)
    if os.path.exists(MOVIMIENTOS_FILE):
        return pd.read_csv(MOVIMIENTOS_FILE)
    df = pd.DataFrame(columns=COLUMNAS_MOVIMIENTOS)
    df.to_csv(MOVIMIENTOS_FILE, index=False)
    return df

def guardar_movimientos(df):
    if USE_DB:
        _db_guardar_tabla("movimientos", df, COLUMNAS_MOVIMIENTOS)
    else:
        df.to_csv(MOVIMIENTOS_FILE, index=False)

def cargar_pagos():
    if USE_DB:
        return _db_leer_tabla("pagos", COLUMNAS_PAGOS)
    if os.path.exists(PAGOS_FILE):
        return pd.read_csv(PAGOS_FILE)
    df = pd.DataFrame(columns=COLUMNAS_PAGOS)
    df.to_csv(PAGOS_FILE, index=False)
    return df

def guardar_pagos(df):
    if USE_DB:
        _db_guardar_tabla("pagos", df, COLUMNAS_PAGOS)
    else:
        df.to_csv(PAGOS_FILE, index=False)

def generar_id(df):
    if df.empty:
        return 1
    return df['id'].max() + 1


def etiqueta_producto(fila):
    return f"{fila['nombre']} ({fila['color']} - {fila['tamaño']}) [ID:{int(fila['id'])}]"


def opciones_productos(df):
    return {etiqueta_producto(fila): int(fila['id']) for _, fila in df.iterrows()}

# Interfaz principal
st.title("🧵 Sistema de Control de Inventario - Avíos Textil")
st.markdown("---")

# Sidebar para navegación
with st.sidebar:
    st.header("Navegación")
    pagina = st.radio(
        "Selecciona una opción:",
        ["📋 Ver Inventario", "➕ Agregar Producto", "📥 Registrar Entrada", 
         "📤 Registrar Salida", "🕒 Historial", "💰 Compras y Pagos", "📊 Reportes", "⚙️ Configuración"]
    )

# Cargar datos
df_inventario = cargar_inventario()
df_movimientos = cargar_movimientos()
df_pagos = cargar_pagos()

# Inicializar carritos en session_state
if 'carrito_entrada' not in st.session_state:
    st.session_state.carrito_entrada = []
if 'carrito_salida' not in st.session_state:
    st.session_state.carrito_salida = []

# PÁGINA: VER INVENTARIO
if pagina == "📋 Ver Inventario":
    st.header("📋 Inventario Actual")
    
    # Filtros
    col1, col2, col3 = st.columns(3)
    with col1:
        filtro_categoria = st.selectbox("Filtrar por categoría:", ["Todas"] + list(df_inventario['categoria'].unique()) if not df_inventario.empty else ["Todas"])
    with col2:
        filtro_color = st.selectbox("Filtrar por color:", ["Todos"] + list(df_inventario['color'].unique()) if not df_inventario.empty else ["Todos"])
    with col3:
        busqueda = st.text_input("🔍 Buscar producto:")
    
    # Aplicar filtros
    df_filtrado = df_inventario.copy()
    if filtro_categoria != "Todas":
        df_filtrado = df_filtrado[df_filtrado['categoria'] == filtro_categoria]
    if filtro_color != "Todos":
        df_filtrado = df_filtrado[df_filtrado['color'] == filtro_color]
    if busqueda:
        df_filtrado = df_filtrado[df_filtrado['nombre'].str.contains(busqueda, case=False, na=False)]
    
    # Mostrar tabla
    if not df_filtrado.empty:
        # Resaltar stock bajo
        def highlight_stock_bajo(val):
            if val < 10:
                return 'background-color: #ffcccc'
            return ''
        
        st.dataframe(
            df_filtrado.style.map(highlight_stock_bajo, subset=['stock_actual']),
            use_container_width=True,
            hide_index=True
        )
        
        # Opción para editar estado de pago
        st.markdown("---")
        st.subheader("⚡ Edición Rápida de Estado de Pago")
        opciones_editar = opciones_productos(df_filtrado)
        producto_editar = st.selectbox("Seleccionar producto para editar estado de pago:", 
                                     ["Seleccionar..."] + list(opciones_editar.keys()))
        
        if producto_editar != "Seleccionar...":
            id_editar = opciones_editar[producto_editar]
            producto_info = df_filtrado[df_filtrado['id'] == id_editar].iloc[0]
            col1, col2 = st.columns(2)
            with col1:
                estado_actual = producto_info['estado_pago'] if pd.notna(producto_info['estado_pago']) else "Sin estado"
                st.info(f"Estado actual: {estado_actual}")
            with col2:
                nuevo_estado = st.selectbox("Nuevo estado:", ["Pendiente", "Cancelado"])
            
            if st.button(f"Actualizar estado de '{producto_editar}'"):
                idx = df_inventario[df_inventario['id'] == id_editar].index[0]
                estado_anterior = df_inventario.at[idx, 'estado_pago']
                df_inventario.at[idx, 'estado_pago'] = nuevo_estado
                guardar_inventario(df_inventario)
                
                # Si se cambió a Cancelado, registrar automáticamente en historial
                if nuevo_estado == "Cancelado" and estado_anterior != "Cancelado":
                    monto_registro = producto_info['precio_compra'] if pd.notna(producto_info['precio_compra']) else 0
                    
                    nuevo_pago = {
                        'id': generar_id(df_pagos),
                        'fecha_pago': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'producto_id': producto_info['id'],
                        'producto_nombre': producto_editar,
                        'monto': monto_registro,
                        'metodo_pago': 'No especificado',
                        'referencia': 'Cambio de estado automático',
                        'observaciones': f'Cambiado de "{estado_anterior}" a "Cancelado" desde edición rápida'
                    }
                    df_pagos = pd.concat([df_pagos, pd.DataFrame([nuevo_pago])], ignore_index=True)
                    guardar_pagos(df_pagos)
                    st.success(f"✅ Estado de '{producto_editar}' actualizado a: {nuevo_estado}")
                    st.info(f"📝 Registro automático creado en historial con fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                else:
                    st.success(f"✅ Estado de '{producto_editar}' actualizado a: {nuevo_estado}")
                
                st.rerun()
        
        # Estadísticas rápidas
        st.subheader("📊 Estadísticas")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total productos", len(df_filtrado))
        with col2:
            st.metric("Stock total", df_filtrado['stock_actual'].sum())
        with col3:
            st.metric("Stock bajo", len(df_filtrado[df_filtrado['stock_actual'] < 10]))
        with col4:
            st.metric("Valor total", f"${df_filtrado['stock_actual'].sum() * df_filtrado['precio_unitario'].sum():.2f}")
    else:
        st.info("No hay productos en el inventario. Agrega el primero en la sección 'Agregar Producto'.")

# PÁGINA: AGREGAR PRODUCTO
elif pagina == "➕ Agregar Producto":
    st.header("➕ Agregar Nuevo Producto")
    
    with st.form("form_agregar"):
        col1, col2 = st.columns(2)
        
        with col1:
            nombre = st.text_input("Nombre del producto*", placeholder="Ej: Hilo algodón rojo")
            categoria = st.selectbox("Categoría*", ["Hilo", "Botón", "Cierre", "Tela", "Etiqueta", "Otro"])
            color = st.text_input("Color", placeholder="Ej: Rojo")
            tamaño = st.text_input("Tamaño/Medida", placeholder="Ej: 500g, 15mm")
        
        with col2:
            stock_actual = st.number_input("Stock actual*", min_value=0, value=0)
            stock_minimo = st.number_input("Stock mínimo (alerta)", min_value=0, value=10)
            precio_unitario = st.number_input("Precio unitario (venta)*", min_value=0.0, value=0.0, step=0.01)
            precio_compra = st.number_input("Precio de compra", min_value=0.0, value=0.0, step=0.01)
            estado_pago = st.selectbox("Estado de pago", ["Pendiente", "Cancelado"])
            fecha_compra = st.date_input("Fecha de compra/guía")
            numero_guia_factura = st.text_input("Número guía/factura", placeholder="Ej: FAC-001, GUI-123")
            proveedor = st.text_input("Proveedor", placeholder="Ej: Telas S.A.")
            ubicacion = st.text_input("Ubicación en almacén", placeholder="Ej: Estante A, Caja 3")
        
        submitted = st.form_submit_button("Agregar Producto")
        
        if submitted:
            color_norm = color if color else "Sin especificar"
            tamaño_norm = tamaño if tamaño else "Sin especificar"
            duplicado = (
                (df_inventario['nombre'].str.strip().str.lower() == nombre.strip().lower()) &
                (df_inventario['color'].str.strip().str.lower() == color_norm.strip().lower()) &
                (df_inventario['tamaño'].str.strip().str.lower() == tamaño_norm.strip().lower())
            ).any() if nombre else False
            
            if not nombre or stock_actual < 0 or precio_unitario < 0:
                st.error("❌ Por favor completa los campos obligatorios (nombre, stock actual, precio unitario)")
            elif duplicado:
                st.error(f"❌ Ya existe un producto '{nombre}' con color '{color_norm}' y tamaño '{tamaño_norm}'. Para sumar stock, usa 'Registrar Entrada'.")
            else:
                nuevo_id = generar_id(df_inventario)
                nuevo_producto = {
                    'id': nuevo_id,
                    'nombre': nombre,
                    'categoria': categoria,
                    'color': color if color else "Sin especificar",
                    'tamaño': tamaño if tamaño else "Sin especificar",
                    'stock_actual': stock_actual,
                    'stock_minimo': stock_minimo,
                    'precio_unitario': precio_unitario,
                    'precio_compra': precio_compra if precio_compra > 0 else None,
                    'estado_pago': estado_pago,
                    'fecha_compra': fecha_compra.strftime("%Y-%m-%d") if fecha_compra else None,
                    'numero_guia_factura': numero_guia_factura if numero_guia_factura else "Sin especificar",
                    'proveedor': proveedor if proveedor else "Sin especificar",
                    'ubicacion': ubicacion if ubicacion else "Sin especificar",
                    'fecha_registro': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                
                df_inventario = pd.concat([df_inventario, pd.DataFrame([nuevo_producto])], ignore_index=True)
                guardar_inventario(df_inventario)
                st.success(f"✅ Producto '{nombre}' agregado exitosamente con ID: {nuevo_id}")
                st.rerun()

# PÁGINA: REGISTRAR ENTRADA
elif pagina == "📥 Registrar Entrada":
    st.header("📥 Registrar Entrada de Mercancía")
    
    if df_inventario.empty:
        st.warning("No hay productos en el inventario. Primero agrega productos.")
    else:
        # Búsqueda rápida por texto (puedes escribir nombre, color, tamaño o ID)
        busqueda_ent = st.text_input("🔍 Buscar producto (nombre, color, tamaño o ID):", placeholder="Ej: cierre, azul, 30 cm, 2")
        
        df_filtrado_ent = df_inventario.copy()
        if busqueda_ent:
            texto = busqueda_ent.strip().lower()
            mascara = (
                df_filtrado_ent['nombre'].astype(str).str.lower().str.contains(texto, na=False) |
                df_filtrado_ent['color'].astype(str).str.lower().str.contains(texto, na=False) |
                df_filtrado_ent['tamaño'].astype(str).str.lower().str.contains(texto, na=False) |
                (df_filtrado_ent['id'].astype(str) == texto)
            )
            df_filtrado_ent = df_filtrado_ent[mascara]
        
        if df_filtrado_ent.empty:
            st.warning("No hay productos que coincidan con la búsqueda.")
        else:
            # Agregar productos al carrito
            with st.form("form_agregar_carrito_entrada"):
                col1, col2 = st.columns([3, 1])
                with col1:
                    opciones_carrito = opciones_productos(df_filtrado_ent)
                    producto_carrito = st.selectbox("Producto:", list(opciones_carrito.keys()))
                with col2:
                    cantidad_carrito = st.number_input("Cantidad:", min_value=1, value=1)
                
                if st.form_submit_button("➕ Agregar"):
                    if producto_carrito:
                        id_carrito = opciones_carrito[producto_carrito]
                        producto_info = df_filtrado_ent[df_filtrado_ent['id'] == id_carrito].iloc[0]
                        # Verificar si ya está en el carrito
                        ya_en_carrito = False
                        for item in st.session_state.carrito_entrada:
                            if item['id'] == id_carrito:
                                item['cantidad'] += cantidad_carrito
                                ya_en_carrito = True
                                break
                        
                        if not ya_en_carrito:
                            st.session_state.carrito_entrada.append({
                                'id': id_carrito,
                                'producto': producto_carrito,
                                'cantidad': cantidad_carrito,
                                'stock_actual': int(producto_info['stock_actual'])
                            })
                        
                        st.success(f"✅ {cantidad_carrito} unidades agregadas")
                        st.rerun()
            
            # Mostrar carrito
            if st.session_state.carrito_entrada:
                st.markdown("---")
                st.subheader("📋 Productos a ingresar")
                
                df_carrito = pd.DataFrame(st.session_state.carrito_entrada)
                df_carrito = df_carrito.rename(columns={'producto': 'Producto', 'cantidad': 'Cantidad', 'stock_actual': 'Stock actual'})
                st.dataframe(df_carrito[['Producto', 'Cantidad', 'Stock actual']], use_container_width=True, hide_index=True)
                
                # Motivo general para todas las entradas
                motivo_general = st.text_input("Motivo (opcional):", placeholder="Ej: Compra a proveedor XYZ")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("🧹 Limpiar lista"):
                        st.session_state.carrito_entrada = []
                        st.rerun()
                with col2:
                    if st.button("✅ Registrar entradas", type="primary"):
                        total_entradas = len(st.session_state.carrito_entrada)
                        # Procesar todos los items del carrito
                        for item in st.session_state.carrito_entrada:
                            # Actualizar stock
                            idx = df_inventario[df_inventario['id'] == item['id']].index[0]
                            df_inventario.at[idx, 'stock_actual'] += item['cantidad']
                            
                            # Registrar movimiento
                            nuevo_movimiento = {
                                'id': generar_id(df_movimientos),
                                'fecha': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                'tipo': 'ENTRADA',
                                'producto_id': df_inventario.at[idx, 'id'],
                                'producto_nombre': item['producto'],
                                'cantidad': item['cantidad'],
                                'motivo': motivo_general if motivo_general else "Sin especificar",
                                'usuario': "Usuario"
                            }
                            df_movimientos = pd.concat([df_movimientos, pd.DataFrame([nuevo_movimiento])], ignore_index=True)
                        
                        guardar_inventario(df_inventario)
                        guardar_movimientos(df_movimientos)
                        
                        st.session_state.carrito_entrada = []
                        st.success(f"✅ {total_entradas} entradas registradas exitosamente")
                        st.rerun()
            else:
                st.info("🛒 La lista está vacía. Busca un producto y presiona 'Agregar' para registrar entradas.")

# PÁGINA: REGISTRAR SALIDA
elif pagina == "📤 Registrar Salida":
    st.header("📤 Registrar Salida de Mercancía")
    
    if df_inventario.empty:
        st.warning("No hay productos en el inventario. Primero agrega productos.")
    else:
        # Búsqueda rápida por texto (puedes escribir nombre, color, tamaño o ID)
        busqueda_sal = st.text_input("🔍 Buscar producto (nombre, color, tamaño o ID):", placeholder="Ej: cierre, azul, 30 cm, 2", key="busqueda_salida")
        
        df_filtrado_sal = df_inventario.copy()
        if busqueda_sal:
            texto = busqueda_sal.strip().lower()
            mascara = (
                df_filtrado_sal['nombre'].astype(str).str.lower().str.contains(texto, na=False) |
                df_filtrado_sal['color'].astype(str).str.lower().str.contains(texto, na=False) |
                df_filtrado_sal['tamaño'].astype(str).str.lower().str.contains(texto, na=False) |
                (df_filtrado_sal['id'].astype(str) == texto)
            )
            df_filtrado_sal = df_filtrado_sal[mascara]
        
        if df_filtrado_sal.empty:
            st.warning("No hay productos que coincidan con la búsqueda.")
        else:
            # Agregar productos al carrito
            with st.form("form_agregar_carrito_salida"):
                col1, col2 = st.columns([3, 1])
                with col1:
                    opciones_carrito_sal = opciones_productos(df_filtrado_sal)
                    producto_carrito_sal = st.selectbox("Producto:", list(opciones_carrito_sal.keys()))
                with col2:
                    cantidad_carrito_sal = st.number_input("Cantidad:", min_value=1, value=1)
                
                if st.form_submit_button("➕ Agregar"):
                    if producto_carrito_sal:
                        id_carrito_sal = opciones_carrito_sal[producto_carrito_sal]
                        producto_info = df_filtrado_sal[df_filtrado_sal['id'] == id_carrito_sal].iloc[0]
                        # Cantidad ya solicitada en el carrito para este producto
                        cantidad_en_carrito = sum(item['cantidad'] for item in st.session_state.carrito_salida if item['id'] == id_carrito_sal)
                        stock_disponible = int(producto_info['stock_actual']) - cantidad_en_carrito
                        
                        if cantidad_carrito_sal > stock_disponible:
                            st.error(f"❌ Stock insuficiente: quedan {stock_disponible} unidades disponibles de '{producto_carrito_sal}'")
                        else:
                            ya_en_carrito = False
                            for item in st.session_state.carrito_salida:
                                if item['id'] == id_carrito_sal:
                                    item['cantidad'] += cantidad_carrito_sal
                                    ya_en_carrito = True
                                    break
                            
                            if not ya_en_carrito:
                                st.session_state.carrito_salida.append({
                                    'id': id_carrito_sal,
                                    'producto': producto_carrito_sal,
                                    'cantidad': cantidad_carrito_sal,
                                    'stock_actual': int(producto_info['stock_actual'])
                                })
                            
                            st.success(f"✅ {cantidad_carrito_sal} unidades agregadas")
                            st.rerun()
            
            # Mostrar carrito
            if st.session_state.carrito_salida:
                st.markdown("---")
                st.subheader("📋 Productos a retirar")
                
                df_carrito = pd.DataFrame(st.session_state.carrito_salida)
                df_carrito = df_carrito.rename(columns={'producto': 'Producto', 'cantidad': 'Cantidad', 'stock_actual': 'Stock actual'})
                st.dataframe(df_carrito[['Producto', 'Cantidad', 'Stock actual']], use_container_width=True, hide_index=True)
                
                # Motivo general para todas las salidas
                motivo_general_sal = st.text_input("Motivo (opcional):", placeholder="Ej: Pedido cliente XYZ")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("🧹 Limpiar lista", key="limpiar_carrito_sal"):
                        st.session_state.carrito_salida = []
                        st.rerun()
                with col2:
                    if st.button("✅ Registrar salidas", type="primary", key="procesar_salidas"):
                        total_salidas = len(st.session_state.carrito_salida)
                        excedidos = []
                        # Procesar todos los items del carrito
                        for item in st.session_state.carrito_salida:
                            idx = df_inventario[df_inventario['id'] == item['id']].index[0]
                            if item['cantidad'] > df_inventario.at[idx, 'stock_actual']:
                                excedidos.append(item['producto'])
                                continue
                            
                            # Actualizar stock
                            df_inventario.at[idx, 'stock_actual'] -= item['cantidad']
                            
                            # Registrar movimiento
                            nuevo_movimiento = {
                                'id': generar_id(df_movimientos),
                                'fecha': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                'tipo': 'SALIDA',
                                'producto_id': item['id'],
                                'producto_nombre': item['producto'],
                                'cantidad': item['cantidad'],
                                'motivo': motivo_general_sal if motivo_general_sal else "Sin especificar",
                                'usuario': "Usuario"
                            }
                            df_movimientos = pd.concat([df_movimientos, pd.DataFrame([nuevo_movimiento])], ignore_index=True)
                        
                        guardar_inventario(df_inventario)
                        guardar_movimientos(df_movimientos)
                        
                        st.session_state.carrito_salida = []
                        if excedidos:
                            st.warning(f"⚠️ No se procesaron salidas por stock insuficiente: {', '.join(excedidos)}")
                        st.success(f"✅ {total_salidas - len(excedidos)} salidas registradas exitosamente")
                        st.rerun()
            else:
                st.info("🛒 La lista está vacía. Busca un producto y presiona 'Agregar' para registrar salidas.")

# PÁGINA: HISTORIAL DE MOVIMIENTOS
elif pagina == "🕒 Historial":
    st.header("🕒 Historial de Entradas y Salidas")
    
    if df_movimientos.empty:
        st.info("No hay movimientos registrados todavía. Las entradas y salidas que registres aparecerán aquí.")
    else:
        df_hist = df_movimientos.copy()
        df_hist['fecha_dt'] = pd.to_datetime(df_hist['fecha'], errors='coerce')
        
        # Filtros
        col1, col2 = st.columns(2)
        with col1:
            filtro_tipo = st.selectbox("Tipo de movimiento:", ["Todos", "ENTRADA", "SALIDA"])
        with col2:
            busqueda_hist = st.text_input("🔍 Buscar producto:", placeholder="Ej: cierre, elastico")
        
        if filtro_tipo != "Todos":
            df_hist = df_hist[df_hist['tipo'] == filtro_tipo]
        if busqueda_hist:
            df_hist = df_hist[df_hist['producto_nombre'].astype(str).str.contains(busqueda_hist.strip(), case=False, na=False)]
        
        if df_hist.empty:
            st.warning("No hay movimientos que coincidan con los filtros.")
        else:
            # Más reciente primero
            df_hist = df_hist.sort_values('fecha_dt', ascending=False)
            df_mostrar = df_hist[['fecha', 'tipo', 'producto_nombre', 'cantidad', 'motivo']].rename(columns={
                'fecha': 'Fecha', 'tipo': 'Tipo', 'producto_nombre': 'Producto',
                'cantidad': 'Cantidad', 'motivo': 'Motivo'
            })
            
            def color_tipo(val):
                if val == 'ENTRADA':
                    return 'background-color: #d4edda'
                return 'background-color: #f8d7da'
            
            st.dataframe(
                df_mostrar.style.map(color_tipo, subset=['Tipo']),
                use_container_width=True,
                hide_index=True
            )
            
            # Resumen
            col1, col2 = st.columns(2)
            with col1:
                st.metric("📥 Total entradas", int(df_hist[df_hist['tipo'] == 'ENTRADA']['cantidad'].sum()))
            with col2:
                st.metric("📤 Total salidas", int(df_hist[df_hist['tipo'] == 'SALIDA']['cantidad'].sum()))
            
            if st.button("📥 Exportar historial a CSV"):
                df_mostrar.to_csv("historial_movimientos.csv", index=False)
                st.success("✅ Historial exportado como 'historial_movimientos.csv'")

# PÁGINA: COMPRAS Y PAGOS
elif pagina == "💰 Compras y Pagos":
    st.header("💰 Gestión de Compras y Pagos")
    
    # Pestañas para gestión de pagos
    tab1, tab2, tab3 = st.tabs(["📋 Productos Pendientes", "💵 Registrar Pago", "📜 Historial de Pagos"])
    
    with tab1:
        st.subheader("📋 Productos con Pagos Pendientes")
        
        # Filtrar productos pendientes de pago (lógica simplificada)
        mask_pendiente = (df_inventario['estado_pago'].fillna('') == 'Pendiente')
        mask_precio_sin_estado = ((df_inventario['estado_pago'].fillna('') == '') & 
                                 (df_inventario['precio_compra'].notna()) & 
                                 (df_inventario['precio_compra'] > 0))
        
        productos_pendientes = df_inventario[mask_pendiente | mask_precio_sin_estado]
        
        st.write(f"Productos encontrados como pendientes: {len(productos_pendientes)}")
        
        if not productos_pendientes.empty:
            st.info(f"Se encontraron {len(productos_pendientes)} productos con pagos pendientes")
            
            # Mostrar tabla con información de pagos
            def highlight_pending(val):
                if val == 'Pendiente' or val == '':
                    return 'background-color: #fff3cd'
                return ''
            
            df_display = productos_pendientes[['nombre', 'categoria', 'precio_compra', 'estado_pago', 
                                               'fecha_compra', 'numero_guia_factura', 'proveedor']].copy()
            df_display['precio_compra'] = df_display['precio_compra'].apply(lambda x: f"${x:.2f}" if pd.notna(x) else "N/A")
            df_display['estado_pago'] = df_display['estado_pago'].fillna('Pendiente')
            
            st.dataframe(
                df_display.style.map(highlight_pending, subset=['estado_pago']),
                use_container_width=True,
                hide_index=True
            )
            
            # Total pendiente
            total_pendiente = productos_pendientes['precio_compra'].sum()
            st.metric("💰 Total Pendiente de Pago", f"${total_pendiente:.2f}")
            
            # Opción rápida para marcar como pagado
            st.markdown("---")
            st.subheader("⚡ Marcar Producto como Pagado (Con registro automático)")
            opciones_marcar = opciones_productos(productos_pendientes)
            producto_marcar = st.selectbox("Seleccionar producto para marcar como pagado:", 
                                         ["Seleccionar..."] + list(opciones_marcar.keys()))
            
            if producto_marcar != "Seleccionar...":
                id_marcar = opciones_marcar[producto_marcar]
                producto_info = productos_pendientes[productos_pendientes['id'] == id_marcar].iloc[0]
                monto_automatico = producto_info['precio_compra'] if pd.notna(producto_info['precio_compra']) else 0
                
                if st.button(f"✅ Marcar '{producto_marcar}' como Pagado"):
                    # Actualizar estado del producto
                    idx = df_inventario[df_inventario['id'] == id_marcar].index[0]
                    df_inventario.at[idx, 'estado_pago'] = 'Cancelado'
                    guardar_inventario(df_inventario)
                    
                    # Registrar pago automáticamente en historial
                    nuevo_pago = {
                        'id': generar_id(df_pagos),
                        'fecha_pago': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'producto_id': producto_info['id'],
                        'producto_nombre': producto_marcar,
                        'monto': monto_automatico,
                        'metodo_pago': 'No especificado',
                        'referencia': 'Cancelación automática',
                        'observaciones': 'Marcado como pagado mediante opción rápida'
                    }
                    df_pagos = pd.concat([df_pagos, pd.DataFrame([nuevo_pago])], ignore_index=True)
                    guardar_pagos(df_pagos)
                    
                    st.success(f"✅ '{producto_marcar}' marcado como pagado")
                    st.info(f"📝 Registro automático creado en historial con fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                    st.rerun()
        else:
            st.success("✅ No hay productos con pagos pendientes")
            st.info("💡 Para agregar productos con pagos pendientes, ve a 'Agregar Producto' y establece el estado de pago como 'Pendiente' o agrega un precio de compra")
            
            # Mostrar todos los productos para diagnóstico
            if not df_inventario.empty:
                st.markdown("---")
                st.subheader("🔍 Todos los productos (para diagnóstico)")
                st.dataframe(df_inventario[['nombre', 'precio_compra', 'estado_pago']], use_container_width=True, hide_index=True)
    
    with tab2:
        st.subheader("💵 Registrar Pago")
        
        if df_inventario.empty:
            st.warning("No hay productos en el inventario.")
            st.info("💡 Primero agrega productos en la sección 'Agregar Producto'")
        else:
            # Filtrar solo productos pendientes (manejar None y productos con precio_compra sin estado)
            productos_pendientes = df_inventario[
                (df_inventario['estado_pago'].fillna('') == 'Pendiente') |
                ((df_inventario['estado_pago'].fillna('') == '') & (df_inventario['precio_compra'].notna()) & (df_inventario['precio_compra'] > 0))
            ]
            
            if productos_pendientes.empty:
                st.info("No hay productos con pagos pendientes para registrar.")
                st.info("💡 Para registrar pagos, primero agrega productos con estado de pago 'Pendiente' o agrega un precio de compra en 'Agregar Producto'")
            else:
                opciones_pago = opciones_productos(productos_pendientes)
                producto = st.selectbox("Seleccionar producto a pagar:", list(opciones_pago.keys()))
                
                if producto:
                    id_pago = opciones_pago[producto]
                    producto_info = productos_pendientes[productos_pendientes['id'] == id_pago].iloc[0]
                    
                    # Mostrar información del producto
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        precio_compra = float(producto_info['precio_compra']) if pd.notna(producto_info['precio_compra']) else 0.0
                        st.info(f"💰 Precio compra: ${precio_compra:.2f}")
                    with col2:
                        st.info(f"📄 Guía/Factura: {producto_info['numero_guia_factura']}")
                    with col3:
                        st.info(f"📅 Fecha compra: {producto_info['fecha_compra']}")
                    
                    with st.form("form_pago"):
                        monto_pago = st.number_input("Monto a pagar*", min_value=0.0, max_value=precio_compra, value=precio_compra, step=0.01)
                        metodo_pago = st.selectbox("Método de pago*", ["Efectivo", "Transferencia", "Tarjeta", "Cheque", "Otro"])
                        referencia = st.text_input("Referencia (número de operación, cheque, etc.)", placeholder="Ej: OP-123456")
                        observaciones = st.text_area("Observaciones", placeholder="Notas adicionales sobre el pago")
                        
                        submitted = st.form_submit_button("Registrar Pago")
                        
                        if submitted:
                            if monto_pago > precio_compra:
                                st.error(f"❌ El monto (${monto_pago:.2f}) no puede exceder el precio de compra del proveedor (${precio_compra:.2f})")
                            elif monto_pago > 0:
                                # Actualizar estado del producto
                                idx = df_inventario[df_inventario['id'] == id_pago].index[0]
                                df_inventario.at[idx, 'estado_pago'] = 'Cancelado'
                                guardar_inventario(df_inventario)
                                
                                # Registrar pago en historial
                                nuevo_pago = {
                                    'id': generar_id(df_pagos),
                                    'fecha_pago': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                    'producto_id': producto_info['id'],
                                    'producto_nombre': producto,
                                    'monto': monto_pago,
                                    'metodo_pago': metodo_pago,
                                    'referencia': referencia if referencia else "Sin especificar",
                                    'observaciones': observaciones if observaciones else "Sin especificar"
                                }
                                df_pagos = pd.concat([df_pagos, pd.DataFrame([nuevo_pago])], ignore_index=True)
                                guardar_pagos(df_pagos)
                                
                                st.success(f"✅ Pago de ${monto_pago:.2f} registrado para '{producto}'")
                                st.info(f"Estado actualizado a: Cancelado")
                                st.rerun()
                            else:
                                st.error("❌ El monto debe ser mayor a 0")
    
    with tab3:
        st.subheader("📜 Historial de Pagos")
        
        if df_pagos.empty:
            st.info("No hay pagos registrados.")
        else:
            # Filtros de fecha
            col1, col2 = st.columns(2)
            with col1:
                fecha_inicio_pago = st.date_input("Fecha inicio", value=pd.to_datetime(df_pagos['fecha_pago']).min().date())
            with col2:
                fecha_fin_pago = st.date_input("Fecha fin", value=pd.to_datetime(df_pagos['fecha_pago']).max().date())
            
            # Filtrar pagos
            df_pagos['fecha_dt'] = pd.to_datetime(df_pagos['fecha_pago'])
            df_pagos_filtrados = df_pagos[
                (df_pagos['fecha_dt'].dt.date >= fecha_inicio_pago) & 
                (df_pagos['fecha_dt'].dt.date <= fecha_fin_pago)
            ]
            
            st.dataframe(df_pagos_filtrados[['fecha_pago', 'producto_nombre', 'monto', 'metodo_pago', 'referencia', 'observaciones']], 
                        use_container_width=True, hide_index=True)
            
            # Resumen de pagos
            st.write("### Resumen de Pagos")
            col1, col2 = st.columns(2)
            with col1:
                total_pagado = df_pagos_filtrados['monto'].sum()
                st.metric("💰 Total Pagado", f"${total_pagado:.2f}")
            with col2:
                num_pagos = len(df_pagos_filtrados)
                st.metric("📊 Número de Pagos", num_pagos)
            
            # Exportar historial
            if st.button("📥 Exportar Historial de Pagos a CSV"):
                df_pagos_filtrados.to_csv("historial_pagos.csv", index=False)
                st.success("✅ Historial exportado como 'historial_pagos.csv'")

# PÁGINA: REPORTES
elif pagina == "📊 Reportes":
    st.header("📊 Reportes y Estadísticas")
    
    if df_inventario.empty:
        st.warning("No hay datos para generar reportes.")
    else:
        # Pestañas de reportes
        tab1, tab2, tab3, tab4 = st.tabs(["📦 Inventario", "📝 Movimientos", "💰 Pagos", "⚠️ Alertas"])
        
        with tab1:
            st.subheader("Reporte de Inventario")
            
            # Por categoría
            st.write("### Stock por Categoría")
            df_categoria = df_inventario.groupby('categoria').agg({
                'stock_actual': 'sum',
                'precio_unitario': 'sum'
            }).reset_index()
            st.bar_chart(df_categoria.set_index('categoria')['stock_actual'])
            
            # Productos con mayor stock
            st.write("### Top 10 Productos con Mayor Stock")
            top_stock = df_inventario.nlargest(10, 'stock_actual')[['nombre', 'stock_actual', 'categoria']]
            st.dataframe(top_stock, use_container_width=True, hide_index=True)
            
            # Valor del inventario
            st.write("### Valor del Inventario por Categoría")
            df_valor = df_inventario.groupby('categoria').agg({
                'stock_actual': 'sum',
                'precio_unitario': 'mean'
            }).reset_index()
            df_valor['valor_total'] = df_valor['stock_actual'] * df_valor['precio_unitario']
            st.dataframe(df_valor[['categoria', 'valor_total']], use_container_width=True, hide_index=True)
        
        with tab2:
            st.subheader("Historial de Movimientos")
            
            if not df_movimientos.empty:
                # Filtros de fecha
                col1, col2 = st.columns(2)
                with col1:
                    fecha_inicio = st.date_input("Fecha inicio", value=pd.to_datetime(df_movimientos['fecha']).min().date())
                with col2:
                    fecha_fin = st.date_input("Fecha fin", value=pd.to_datetime(df_movimientos['fecha']).max().date())
                
                # Filtrar movimientos
                df_movimientos['fecha_dt'] = pd.to_datetime(df_movimientos['fecha'])
                df_filtrado = df_movimientos[
                    (df_movimientos['fecha_dt'].dt.date >= fecha_inicio) & 
                    (df_movimientos['fecha_dt'].dt.date <= fecha_fin)
                ]
                
                st.dataframe(df_filtrado[['fecha', 'tipo', 'producto_nombre', 'cantidad', 'motivo']], 
                            use_container_width=True, hide_index=True)
                
                # Resumen
                st.write("### Resumen de Movimientos")
                col1, col2 = st.columns(2)
                with col1:
                    total_entradas = df_filtrado[df_filtrado['tipo'] == 'ENTRADA']['cantidad'].sum()
                    st.metric("Total Entradas", total_entradas)
                with col2:
                    total_salidas = df_filtrado[df_filtrado['tipo'] == 'SALIDA']['cantidad'].sum()
                    st.metric("Total Salidas", total_salidas)
            else:
                st.info("No hay movimientos registrados.")
        
        with tab3:
            st.subheader("💰 Reporte de Pagos")
            
            if not df_pagos.empty:
                # Pagos por método
                st.write("### Pagos por Método")
                df_metodo = df_pagos.groupby('metodo_pago').agg({
                    'monto': 'sum',
                    'id': 'count'
                }).reset_index()
                df_metodo.columns = ['Método', 'Total', 'Cantidad']
                st.dataframe(df_metodo, use_container_width=True, hide_index=True)
                
                # Productos más pagados
                st.write("### Productos con Mayor Monto de Pagos")
                df_producto_pago = df_pagos.groupby('producto_nombre').agg({
                    'monto': 'sum'
                }).reset_index()
                df_producto_pago = df_producto_pago.sort_values('monto', ascending=False).head(10)
                st.dataframe(df_producto_pago, use_container_width=True, hide_index=True)
                
                # Resumen financiero
                st.write("### Resumen Financiero")
                col1, col2, col3 = st.columns(3)
                with col1:
                    total_pagado = df_pagos['monto'].sum()
                    st.metric("Total Pagado", f"${total_pagado:.2f}")
                with col2:
                    productos_pendientes = df_inventario[df_inventario['estado_pago'].fillna('') == 'Pendiente']
                    total_pendiente = productos_pendientes['precio_compra'].sum() if not productos_pendientes.empty else 0
                    st.metric("Total Pendiente", f"${total_pendiente:.2f}")
                with col3:
                    total_compras = total_pagado + total_pendiente
                    st.metric("Total Compras", f"${total_compras:.2f}")
            else:
                st.info("No hay pagos registrados.")
                st.info("💡 Los pagos aparecerán aquí cuando registres pagos en la sección 'Compras y Pagos'")
        
        with tab4:
            st.subheader("⚠️ Alertas de Stock Bajo")
            
            stock_bajo = df_inventario[df_inventario['stock_actual'] < df_inventario['stock_minimo']]
            
            if not stock_bajo.empty:
                st.warning(f"Se encontraron {len(stock_bajo)} productos con stock bajo")
                st.dataframe(stock_bajo[['nombre', 'categoria', 'stock_actual', 'stock_minimo', 'proveedor']], 
                            use_container_width=True, hide_index=True)
                
                # Opción para exportar alertas
                if st.button("📥 Exportar Alertas a CSV"):
                    stock_bajo.to_csv("alertas_stock_bajo.csv", index=False)
                    st.success("✅ Archivo exportado como 'alertas_stock_bajo.csv'")
            else:
                st.success("✅ No hay productos con stock bajo")

# PÁGINA: CONFIGURACIÓN
elif pagina == "⚙️ Configuración":
    st.header("⚙️ Configuración del Sistema")
    
    st.subheader("📁 Archivos de Datos")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.write(f"**Inventario:** {DATA_FILE}")
        if os.path.exists(DATA_FILE):
            st.info(f"✅ Archivo existe ({os.path.getsize(DATA_FILE)} bytes)")
        else:
            st.warning("❌ Archivo no existe")
    
    with col2:
        st.write(f"**Movimientos:** {MOVIMIENTOS_FILE}")
        if os.path.exists(MOVIMIENTOS_FILE):
            st.info(f"✅ Archivo existe ({os.path.getsize(MOVIMIENTOS_FILE)} bytes)")
        else:
            st.warning("❌ Archivo no existe")
    
    with col3:
        st.write(f"**Pagos:** {PAGOS_FILE}")
        if os.path.exists(PAGOS_FILE):
            st.info(f"✅ Archivo existe ({os.path.getsize(PAGOS_FILE)} bytes)")
        else:
            st.warning("❌ Archivo no existe")
    
    st.markdown("---")
    
    st.subheader("📥 Exportar Datos")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("Exportar Inventario a CSV"):
            df_inventario.to_csv("inventario_export.csv", index=False)
            st.success("✅ Inventario exportado como 'inventario_export.csv'")
    
    with col2:
        if st.button("Exportar Movimientos a CSV"):
            df_movimientos.to_csv("movimientos_export.csv", index=False)
            st.success("✅ Movimientos exportados como 'movimientos_export.csv'")
    
    with col3:
        if st.button("Exportar Pagos a CSV"):
            df_pagos.to_csv("pagos_export.csv", index=False)
            st.success("✅ Pagos exportados como 'pagos_export.csv'")
    
    st.markdown("---")
    
    st.subheader("⚠️ Zona de Peligro")
    st.warning("Estas acciones son irreversibles")
    
    with st.expander("🗑️ Limpiar Todo el Inventario"):
        st.error("❌ Esta acción eliminará todos los datos permanentemente")
        confirmacion = st.text_input("Escribe 'ELIMINAR' para confirmar", key="confirmacion_eliminar")
        
        if st.button("Confirmar Eliminación", key="btn_eliminar"):
            if confirmacion == "ELIMINAR":
                archivos_eliminados = []
                if os.path.exists(DATA_FILE):
                    os.remove(DATA_FILE)
                    archivos_eliminados.append(DATA_FILE)
                if os.path.exists(MOVIMIENTOS_FILE):
                    os.remove(MOVIMIENTOS_FILE)
                    archivos_eliminados.append(MOVIMIENTOS_FILE)
                if os.path.exists(PAGOS_FILE):
                    os.remove(PAGOS_FILE)
                    archivos_eliminados.append(PAGOS_FILE)
                
                if archivos_eliminados:
                    st.success(f"✅ Todos los datos han sido eliminados: {', '.join(archivos_eliminados)}")
                    st.rerun()
                else:
                    st.warning("⚠️ No se encontraron archivos para eliminar")
            else:
                st.error("❌ Confirmación incorrecta. Debes escribir exactamente 'ELIMINAR'")

# Footer
st.markdown("---")
st.markdown("🧵 Sistema de Control de Inventario - Avíos Textil | Desarrollado con Streamlit & Pandas")