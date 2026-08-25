# 🧵 Sistema de Control de Inventario - Avíos Textil

Aplicación web para el control de inventario de hilos y avíos para taller textil, desarrollada con Python, Streamlit y Pandas.

## ✨ Características

- **Gestión de inventario**: Agregar, editar y eliminar productos de avíos textiles
- **Categorías**: Hilo, Botón, Cierre, Tela, Etiqueta, Otro
- **Control de stock**: Registro de entradas y salidas de mercancía
- **Gestión de compras y pagos**: 
  - Registro de precio de compra
  - Estado de pago (pendiente/cancelado)
  - Número de guía/factura
  - Fecha de compra
  - Historial completo de pagos con fecha de cancelación
- **Alertas de stock bajo**: Notificación automática cuando el stock está por debajo del mínimo
- **Historial de movimientos**: Registro completo de todas las operaciones
- **Reportes**: Estadísticas y gráficos del inventario y pagos
- **Exportación de datos**: Exportar a CSV para respaldo y análisis
- **Filtros y búsqueda**: Búsqueda rápida de productos

## 📋 Requisitos

- Python 3.8 o superior
- pip (gestor de paquetes de Python)

## 🚀 Instalación

1. Navegar al directorio del proyecto:
```bash
cd avios
```

2. Crear un entorno virtual (opcional pero recomendado):
```bash
python -m venv venv
```

3. Activar el entorno virtual:
- Windows:
```bash
venv\Scripts\activate
```
- Linux/Mac:
```bash
source venv/bin/activate
```

4. Instalar las dependencias:
```bash
pip install -r requirements.txt
```

## 🎮 Uso

Ejecutar la aplicación:
```bash
streamlit run app.py
```

La aplicación se abrirá automáticamente en tu navegador en `http://localhost:8501`

## 📖 Funcionalidades

### 📋 Ver Inventario
- Visualización completa del inventario
- Filtros por categoría y color
- Búsqueda de productos
- Resaltado de stock bajo
- Estadísticas rápidas

### ➕ Agregar Producto
- Formulario para agregar nuevos productos
- Campos: nombre, categoría, color, tamaño, stock, precio de venta, precio de compra
- Información de compras: estado de pago, fecha de compra, número de guía/factura
- Validación de datos obligatorios

### 📥 Registrar Entrada
- Aumentar stock de productos existentes
- Registro automático en historial de movimientos
- Notas y motivos de la entrada

### 📤 Registrar Salida
- Disminuir stock de productos
- Validación de stock disponible
- Registro automático en historial de movimientos
- Alertas de stock bajo

### 💰 Compras y Pagos
- **Productos Pendientes**: Lista de productos con pagos pendientes
- **Registrar Pago**: Formulario para registrar pagos con:
  - Monto del pago
  - Método de pago (efectivo, transferencia, tarjeta, cheque, otro)
  - Referencia de pago
  - Observaciones
  - Actualización automática del estado a "Cancelado"
- **Historial de Pagos**: Registro completo con:
  - Fecha de pago
  - Producto pagado
  - Monto
  - Método de pago
  - Referencia
  - Observaciones
  - Filtros por fecha
  - Exportación a CSV

### 📊 Reportes
- **Inventario**: Gráficos por categoría, top productos, valor del inventario
- **Movimientos**: Historial con filtros de fecha, resumen de entradas/salidas
- **Pagos**: 
  - Pagos por método de pago
  - Productos con mayor monto de pagos
  - Resumen financiero (total pagado, total pendiente, total compras)
- **Alertas**: Lista de productos con stock bajo y exportación

### ⚙️ Configuración
- Información de archivos de datos (inventario, movimientos, pagos)
- Exportación de datos a CSV
- Opción para limpiar todo el inventario (con confirmación)

## 📁 Archivos de Datos

La aplicación crea automáticamente dos archivos CSV:

- `inventario.csv`: Contiene todos los productos del inventario
- `movimientos.csv`: Contiene el historial de todos los movimientos

## 🔧 Personalización

Puedes personalizar la aplicación modificando el archivo `app.py`:

- Cambiar categorías en el selectbox de categoría
- Modificar el diseño y colores
- Agregar nuevos campos a los productos
- Personalizar las alertas de stock

## 📦 Estructura del Proyecto

```
avios/
├── app.py                 # Aplicación principal
├── requirements.txt       # Dependencias de Python
├── README.md             # Este archivo
├── inventario.csv        # Archivo de datos (se crea automáticamente)
└── movimientos.csv       # Historial de movimientos (se crea automáticamente)
```

## 🤝 Contribución

Este proyecto fue creado para el control de inventario de avíos textiles. Si deseas agregar funcionalidades o reportar problemas, siéntete libre de modificar el código según tus necesidades.

## 📄 Licencia

Este proyecto es de código abierto y puede ser utilizado libremente.

## 🆘 Soporte

Para problemas o preguntas:
- Revisa la documentación de Streamlit: https://docs.streamlit.io
- Revisa la documentación de Pandas: https://pandas.pydata.org/docs/