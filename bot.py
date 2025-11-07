import logging
import sqlite3
import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from config_secret import TOKEN, ADMIN_USER_IDS

# Configuración del logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


# --- CONFIGURACIÓN ---
TOKEN = "TU_TOKEN_AQUI" # Reemplazar por un texto genérico o dejarlo vacío
ADMIN_USER_IDS = [00000000, 11111111] 
# ---------------------

# --- Constantes para validación ---
VALID_CAJAS = ['cfg', 'sc', 'trd']
VALID_MONEDAS = ['usd', 'cup', 'cup-t']

# --- Constantes para Tasas de Cambio ---
TASA_USD_CUP = 410.0      # 1 USD = 410 CUP
TASA_USD_CUP_T = 410.0    # 1 USD = 410 CUP-T (usamos la misma por ahora)
# ----------------------------------------

def setup_database():
    """Crea la BD y las tablas 'Movimientos' y 'Productos' si no existen."""
    conn = sqlite3.connect("contabilidad.db") 
    cursor = conn.cursor()
    
    # Tabla Movimientos (Ya existente)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Movimientos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha TIMESTAMP NOT NULL,
        tipo TEXT NOT NULL, 
        monto REAL NOT NULL,
        moneda TEXT NOT NULL,
        caja TEXT NOT NULL,
        user_id INTEGER NOT NULL,
        descripcion TEXT 
    )
    """)
    
    # 🌟 NUEVA TABLA: Productos (con columna moneda_costo) 
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Productos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        codigo TEXT UNIQUE NOT NULL,      
        nombre TEXT NOT NULL,
        costo_unitario REAL NOT NULL,     
        moneda_costo TEXT NOT NULL DEFAULT 'usd', -- AÑADIMOS LA MONEDA DEL COSTO
        precio_venta REAL,                
        stock INTEGER NOT NULL DEFAULT 0  
    )
    """)
    
    conn.commit()
    conn.close()
    logger.info("Base de datos lista con tablas Movimientos y Productos.")

# def fix_db_productos_schema():
#     """Añade la columna 'moneda_costo' a la tabla Productos si no existe."""
#     conn = sqlite3.connect("contabilidad.db") 
#     cursor = conn.cursor()
    
#     try:
#         # Comando SQL para añadir la columna
#         cursor.execute("ALTER TABLE Productos ADD COLUMN moneda_costo TEXT NOT NULL DEFAULT 'usd'")
#         conn.commit()
#         logger.info("✅ Columna 'moneda_costo' añadida a la tabla Productos.")
#     except sqlite3.OperationalError as e:
#         # Esto ocurre si la columna ya fue añadida (es lo que queremos evitar)
#         if 'duplicate column name' in str(e):
#             logger.info("La columna 'moneda_costo' ya existía, no se hizo ninguna modificación.")
#         else:
#             raise e
#     finally:
#         conn.close()


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manejador para el comando /start."""
    user_id = update.effective_user.id
    if user_id not in ADMIN_USER_IDS:
        await update.message.reply_text("⛔ No tienes permiso para usar este bot.")
        logger.warning(f"Intento de acceso denegado del user_id: {user_id}")
        return

    user = update.effective_user
    await update.message.reply_html(
        f"¡Hola {user.first_name}! 👋\n\n"
        f"Soy tu asistente contable. Estoy listo.\n\n"
        f"<b>Comandos:</b>\n"
        f"<code>/ingreso [monto] [moneda] [caja]</code>\n"
        f"<code>/gasto [monto] [moneda] [caja] [motivo...]</code>\n"
        f"<code>/balance</code>"
    )

async def ingreso_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manejador para el comando /ingreso."""
    user_id = update.effective_user.id

    if user_id not in ADMIN_USER_IDS:
        await update.message.reply_text("⛔ No tienes permiso.")
        return

    try:
        if len(context.args) != 3:
            raise ValueError("Formato incorrecto.")

        monto_str = context.args[0]
        moneda = context.args[1].lower()
        caja = context.args[2].lower()

        try:
            monto = float(monto_str)
            if monto <= 0: raise ValueError()
        except ValueError:
            await update.message.reply_text("Error: El monto debe ser un número positivo.")
            return

        if moneda not in VALID_MONEDAS:
            await update.message.reply_text(f"Error: Moneda '{moneda}' no válida. Usa: {', '.join(VALID_MONEDAS)}")
            return
            
        if caja not in VALID_CAJAS:
            await update.message.reply_text(f"Error: Caja '{caja}' no válida. Usa: {', '.join(VALID_CAJAS)}")
            return

        conn = sqlite3.connect("contabilidad.db")
        cursor = conn.cursor()
        fecha_actual = datetime.datetime.now()
        
        cursor.execute(
            "INSERT INTO Movimientos (fecha, tipo, monto, moneda, caja, user_id, descripcion) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (fecha_actual, 'ingreso', monto, moneda, caja, user_id, "Ingreso") # Añadimos "Ingreso" como descripción
        )
        
        conn.commit()
        conn.close()

        await update.message.reply_html(
            f"✅ <b>¡Ingreso registrado!</b>\n\n"
            f"<b>Monto:</b> {monto:.2f} {moneda.upper()}\n"
            f"<b>Caja:</b> {caja.upper()}"
        )
        logger.info(f"Ingreso registrado: {monto} {moneda} en {caja} por {user_id}")

    except ValueError:
        await update.message.reply_html(
            "<b>Error de formato.</b>\n"
            "Uso correcto: <code>/ingreso [monto] [moneda] [caja]</code>\n"
            "Ejemplo: <code>/ingreso 100 usd cfg</code>"
        )
    except Exception as e:
        logger.error(f"Error inesperado en /ingreso: {e}")
        await update.message.reply_text("Ocurrió un error inesperado.")


# --- FASE 5: NUEVA FUNCIÓN PARA /gasto ---
async def gasto_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manejador para el comando /gasto."""
    user_id = update.effective_user.id

    if user_id not in ADMIN_USER_IDS:
        await update.message.reply_text("⛔ No tienes permiso.")
        return

    try:
        # Necesitamos al menos 4 argumentos: monto, moneda, caja, y al menos una palabra de motivo
        if len(context.args) < 4:
            raise ValueError("Formato incorrecto.")

        # 1. Asignar y validar
        monto_str = context.args[0]
        moneda = context.args[1].lower()
        caja = context.args[2].lower()
        
        # 2. Unir el resto de las palabras como la descripción
        # context.args[3:] es una lista de todas las palabras desde la 4ta hasta el final
        descripcion = " ".join(context.args[3:]) 

        try:
            monto = float(monto_str)
            if monto <= 0: raise ValueError()
        except ValueError:
            await update.message.reply_text("Error: El monto debe ser un número positivo.")
            return

        if moneda not in VALID_MONEDAS:
            await update.message.reply_text(f"Error: Moneda '{moneda}' no válida. Usa: {', '.join(VALID_MONEDAS)}")
            return
            
        if caja not in VALID_CAJAS:
            await update.message.reply_text(f"Error: Caja '{caja}' no válida. Usa: {', '.join(VALID_CAJAS)}")
            return

        # 3. Guardar en la Base de Datos
        conn = sqlite3.connect("contabilidad.db")
        cursor = conn.cursor()
        fecha_actual = datetime.datetime.now()
        
        cursor.execute(
            "INSERT INTO Movimientos (fecha, tipo, monto, moneda, caja, user_id, descripcion) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (fecha_actual, 'gasto', monto, moneda, caja, user_id, descripcion) # Guardamos el 'tipo' y la 'descripcion'
        )
        
        conn.commit()
        conn.close()

        # 4. Confirmar al usuario
        await update.message.reply_html(
            f"💸 <b>¡Gasto registrado!</b>\n\n"
            f"<b>Monto:</b> {monto:.2f} {moneda.upper()}\n"
            f"<b>Caja:</b> {caja.upper()}\n"
            f"<b>Motivo:</b> {descripcion}"
        )
        logger.info(f"Gasto registrado: {monto} {moneda} en {caja} por {user_id}")

    except ValueError:
        await update.message.reply_html(
            "<b>Error de formato.</b>\n"
            "Uso correcto: <code>/gasto [monto] [moneda] [caja] [motivo...]</code>\n"
            "Ejemplo: <code>/gasto 5000 cup sc pago de luz</code>"
        )
    except Exception as e:
        logger.error(f"Error inesperado en /gasto: {e}")
        await update.message.reply_text("Ocurrió un error inesperado.")
# ----------------------------------------------


# --- FASE 6: NUEVA FUNCIÓN PARA /balance ---
async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manejador para el comando /balance."""
    user_id = update.effective_user.id

    if user_id not in ADMIN_USER_IDS:
        await update.message.reply_text("⛔ No tienes permiso.")
        return
    
    try:
        conn = sqlite3.connect("contabilidad.db")
        cursor = conn.cursor()

        # 1. La consulta SQL "Mágica"
        # Suma todos los 'ingreso' y resta (ELSE -monto) todos los 'gasto'
        # Agrupados por caja y moneda
        cursor.execute("""
            SELECT caja, moneda, SUM(CASE WHEN tipo = 'ingreso' THEN monto ELSE -monto END) as total
            FROM Movimientos
            GROUP BY caja, moneda
            ORDER BY caja, moneda
        """)
        
        resultados = cursor.fetchall() # Obtiene todas las filas (ej: [('cfg', 'usd', 100.0), ('cfg', 'cup', 5000.0)])
        conn.close()

        if not resultados:
            await update.message.reply_text("No hay ningún movimiento registrado todavía.")
            return

        # 2. Formatear la respuesta
        respuesta = "--- 📊 Balance General ---\n\n"
        
        balances_por_caja = {} # Usamos un diccionario para agrupar
        
        # Agrupamos los resultados por caja
        for caja, moneda, total in resultados:
            if caja not in balances_por_caja:
                balances_por_caja[caja] = []
            
            # Guardamos el texto formateado de la moneda
            balances_por_caja[caja].append(f"  • {total:,.2f} {moneda.upper()}")

        # 3. Construimos el texto final
        for caja, lineas in balances_por_caja.items():
            respuesta += f"<b>CAJA: {caja.upper()}</b>\n"
            respuesta += "\n".join(lineas) # Unimos todas las líneas de esa caja
            respuesta += "\n\n" # Añadimos un espacio antes de la siguiente caja

        await update.message.reply_html(respuesta)

    except Exception as e:
        logger.error(f"Error inesperado en /balance: {e}")
        await update.message.reply_text("Ocurrió un error inesperado al calcular el balance.")
# ----------------------------------------------

# --- FASE 7 (REFACTORIZADA): FUNCIÓN PARA /cambio (Conversión Automática) ---
async def cambio_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Manejador refactorizado para el comando /cambio. 
    Formato: /cambio [monto] [moneda_origen]-[moneda_destino] [caja_origen] a [caja_destino]
    """
    user_id = update.effective_user.id
    if user_id not in ADMIN_USER_IDS:
        await update.message.reply_text("⛔ No tienes permiso.")
        return

    try:
        # Formato esperado: [monto] [moneda_origen]-[moneda_destino] [caja_origen] a [caja_destino]
        if len(context.args) != 5 or context.args[3].lower() != 'a':
            raise ValueError("Formato incorrecto. Faltan argumentos o la palabra 'a'.")

        # 1. Parsear los argumentos
        monto_origen = float(context.args[0])
        mon_par = context.args[1].lower() # Ej: 'usd-cup'
        caja_origen = context.args[2].lower()
        caja_destino = context.args[4].lower() # El argumento [3] es 'a'

        # 2. Separar las monedas del par
        if '-' not in mon_par:
             raise ValueError("El formato de moneda debe ser [moneda_origen]-[moneda_destino]. Ejemplo: usd-cup.")

        monedas = mon_par.split('-')
        moneda_origen = monedas[0].lower()
        moneda_destino = monedas[1].lower()
        
        # Validaciones de montos y cajas
        if monto_origen <= 0: raise ValueError("El monto debe ser positivo.")
        if moneda_origen not in VALID_MONEDAS or moneda_destino not in VALID_MONEDAS:
            raise ValueError(f"Moneda no válida. Usa: {', '.join(VALID_MONEDAS)}")
        if caja_origen not in VALID_CAJAS or caja_destino not in VALID_CAJAS:
            raise ValueError(f"Caja no válida. Usa: {', '.join(VALID_CAJAS)}")

        # 3. Determinar la Tasa de Conversión (Usando TASA_USD_CUP = 410.0)
        tasa_uso = 0.0
        
        # De USD a CUP o CUP-T
        if moneda_origen == 'usd' and moneda_destino in ('cup', 'cup-t'):
            tasa_uso = TASA_USD_CUP
        # De CUP o CUP-T a USD
        elif moneda_origen in ('cup', 'cup-t') and moneda_destino == 'usd':
            tasa_uso = 1 / TASA_USD_CUP # Invertimos la tasa
        # Si es la misma moneda, la tasa es 1:1 (ej. usd-usd)
        elif moneda_origen == moneda_destino:
             tasa_uso = 1.0
        else:
            # Puedes añadir más lógicas de conversión si es necesario
            raise ValueError(f"Conversión {moneda_origen}-{moneda_destino} no está soportada o tasa no definida.")

        # 4. Calcular el Monto de Destino
        monto_destino = monto_origen * tasa_uso

        # 5. Guardar en la Base de Datos (Doble Transacción)
        descripcion_movimiento = (
            f"CAMBIO AUTOMÁTICO: {monto_origen:,.2f} {moneda_origen.upper()} a {monto_destino:,.2f} "
            f"{moneda_destino.upper()} (@ 1 {moneda_origen.upper()} = {tasa_uso:.4f} {moneda_destino.upper()})"
        )
        
        conn = sqlite3.connect("contabilidad.db")
        cursor = conn.cursor()
        fecha_actual = datetime.datetime.now()
        
        # TRANSACCIÓN 1: Gasto (Salida de Origen)
        cursor.execute(
            "INSERT INTO Movimientos (fecha, tipo, monto, moneda, caja, user_id, descripcion) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (fecha_actual, 'gasto', monto_origen, moneda_origen, caja_origen, user_id, descripcion_movimiento)
        )
        
        # TRANSACCIÓN 2: Ingreso (Entrada a Destino)
        cursor.execute(
            "INSERT INTO Movimientos (fecha, tipo, monto, moneda, caja, user_id, descripcion) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (fecha_actual, 'ingreso', monto_destino, moneda_destino, caja_destino, user_id, descripcion_movimiento)
        )
        
        conn.commit()
        conn.close()

        # 6. Confirmación
        await update.message.reply_html(
            f"🔄 <b>¡Conversión Automática Registrada!</b>\n\n"
            f"<b>Salida:</b> -{monto_origen:,.2f} {moneda_origen.upper()} ({caja_origen.upper()})\n"
            f"<b>Entrada:</b> +{monto_destino:,.2f} {moneda_destino.upper()} ({caja_destino.upper()})\n"
            f"<b>Tasa Usada:</b> 1 {moneda_origen.upper()} = {tasa_uso:.4f} {moneda_destino.upper()}"
        )
        logger.info(descripcion_movimiento)

    except ValueError as e:
        await update.message.reply_html(
            f"<b>Error de formato o cálculo:</b> {e}\n"
            "Uso correcto: <code>/cambio [monto] [moneda_origen]-[moneda_destino] [caja_origen] a [caja_destino]</code>\n"
            "Ejemplos:\n"
            "<code>/cambio 100 usd-cup cfg a sc</code>\n"
            "<code>/cambio 41000 cup-usd cfg a cfg</code>"
        )
    except Exception as e:
        logger.error(f"Error inesperado en /cambio: {e}")
        await update.message.reply_text("Ocurrió un error inesperado al registrar el cambio.")


# --- FASE 8: NUEVA FUNCIÓN PARA /pago (Pago de Vendedor) ---
async def pago_vendedor_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Registra el pago de un vendedor (ingreso)."""
    user_id = update.effective_user.id
    if user_id not in ADMIN_USER_IDS:
        await update.message.reply_text("⛔ No tienes permiso.")
        return

    try:
        # Formato esperado: [vendedor] [monto] [moneda] [caja]
        if len(context.args) != 4:
            raise ValueError("Formato incorrecto.")

        vendedor = context.args[0].capitalize() 
        monto_str = context.args[1]
        moneda = context.args[2].lower()
        caja = context.args[3].lower()

        # Validaciones
        monto = float(monto_str)
        if monto <= 0: raise ValueError()
        if moneda not in VALID_MONEDAS: raise ValueError(f"Moneda no válida: {moneda}")
        if caja not in VALID_CAJAS: raise ValueError(f"Caja no válida: {caja}")

        conn = sqlite3.connect("contabilidad.db")
        cursor = conn.cursor()
        fecha_actual = datetime.datetime.now()
        
        descripcion = f"PAGO de Vendedor: {vendedor}"
        
        # Es un INGRESO en la caja
        cursor.execute(
            "INSERT INTO Movimientos (fecha, tipo, monto, moneda, caja, user_id, descripcion) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (fecha_actual, 'ingreso', monto, moneda, caja, user_id, descripcion)
        )
        
        conn.commit()
        conn.close()

        await update.message.reply_html(
            f"✅ <b>Pago de Vendedor Registrado!</b>\n\n"
            f"<b>Vendedor:</b> {vendedor}\n"
            f"<b>Monto:</b> +{monto:.2f} {moneda.upper()} en {caja.upper()}"
        )
        logger.info(f"Pago de Vendedor {vendedor} registrado.")

    except (ValueError, Exception) as e:
        await update.message.reply_html(
            "<b>Error de formato.</b>\n"
            "Uso correcto: <code>/pago [vendedor] [monto] [moneda] [caja]</code>\n"
            "Ejemplo: <code>/pago Juan 500 cup cfg</code>"
        )
        logger.error(f"Error en /pago: {e}")


# --- FASE 8: NUEVA FUNCIÓN PARA /pago_proveedor (Pago a Proveedor) ---
async def pago_proveedor_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Registra un pago a proveedor (gasto)."""
    user_id = update.effective_user.id
    if user_id not in ADMIN_USER_IDS:
        await update.message.reply_text("⛔ No tienes permiso.")
        return

    try:
        # Formato esperado: [proveedor] [monto] [moneda] [caja] [motivo...]
        if len(context.args) < 5:
            raise ValueError("Formato incorrecto.")

        proveedor = context.args[0].capitalize() 
        monto_str = context.args[1]
        moneda = context.args[2].lower()
        caja = context.args[3].lower()
        
        # El motivo es todo el resto de los argumentos
        motivo = " ".join(context.args[4:])

        # Validaciones
        monto = float(monto_str)
        if monto <= 0: raise ValueError()
        if moneda not in VALID_MONEDAS: raise ValueError(f"Moneda no válida: {moneda}")
        if caja not in VALID_CAJAS: raise ValueError(f"Caja no válida: {caja}")

        conn = sqlite3.connect("contabilidad.db")
        cursor = conn.cursor()
        fecha_actual = datetime.datetime.now()
        
        descripcion = f"PAGO a Proveedor: {proveedor} - Motivo: {motivo}"
        
        # Es un GASTO de la caja
        cursor.execute(
            "INSERT INTO Movimientos (fecha, tipo, monto, moneda, caja, user_id, descripcion) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (fecha_actual, 'gasto', monto, moneda, caja, user_id, descripcion)
        )
        
        conn.commit()
        conn.close()

        await update.message.reply_html(
            f"💸 <b>Pago a Proveedor Registrado!</b>\n\n"
            f"<b>Proveedor:</b> {proveedor}\n"
            f"<b>Monto:</b> -{monto:.2f} {moneda.upper()} de {caja.upper()}\n"
            f"<b>Motivo:</b> {motivo}"
        )
        logger.info(f"Pago a Proveedor {proveedor} registrado.")

    except (ValueError, Exception) as e:
        await update.message.reply_html(
            "<b>Error de formato.</b>\n"
            "Uso correcto: <code>/pago_proveedor [proveedor] [monto] [moneda] [caja] [motivo...]</code>\n"
            "Ejemplo: <code>/pago_proveedor Pedro 50 usd cfg pago flete</code>"
        )
        logger.error(f"Error en /pago_proveedor: {e}")


# --- FASE 9 (MODIFICADA): FUNCIÓN PARA /entrada (Registro de Compra/Stock) ---
async def entrada_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Registra la entrada de mercancía (compra de stock), guardando la moneda de costo. 
    Formato: /entrada [código] [unidades] [costo_total] [moneda] [caja] [proveedor/nota...]
    """
    user_id = update.effective_user.id
    if user_id not in ADMIN_USER_IDS:
        await update.message.reply_text("⛔ No tienes permiso.")
        return

    try:
        # Necesitamos al menos 6 argumentos
        if len(context.args) < 6:
            raise ValueError("Faltan argumentos.")

        # 1. Parsear argumentos
        codigo = context.args[0].upper()
        unidades = int(context.args[1])
        costo_total = float(context.args[2])
        moneda = context.args[3].lower() # Esta es la moneda del gasto y del costo
        caja = context.args[4].lower()
        
        nota_compra = " ".join(context.args[5:])

        # 2. Validaciones
        if unidades <= 0: raise ValueError("Las unidades deben ser un número entero positivo.")
        if costo_total <= 0: raise ValueError("El costo total debe ser un número positivo.")
        if moneda not in VALID_MONEDAS: raise ValueError(f"Moneda no válida. Usa: {', '.join(VALID_MONEDAS)}")
        if caja not in VALID_CAJAS: raise ValueError(f"Caja no válida. Usa: {', '.join(VALID_CAJAS)}")
        
        costo_unitario = costo_total / unidades

        conn = sqlite3.connect("contabilidad.db")
        cursor = conn.cursor()
        
        # --- A. Gestión del Inventario (Tabla Productos) ---
        
        cursor.execute("SELECT stock, nombre FROM Productos WHERE codigo = ?", (codigo,))
        producto_existente = cursor.fetchone()
        
        if producto_existente:
            # Producto existe: Actualizar stock, costo y la moneda del costo
            stock_anterior, nombre_prod = producto_existente
            nuevo_stock = stock_anterior + unidades

            cursor.execute(
                "UPDATE Productos SET stock = ?, costo_unitario = ?, moneda_costo = ? WHERE codigo = ?", 
                (nuevo_stock, costo_unitario, moneda, codigo) # <-- Moneda registrada aquí
            )
            accion_inventario = f"Actualización de stock de {nombre_prod}: {stock_anterior} -> {nuevo_stock} unidades."
        else:
            # Producto NO existe: Insertar nuevo producto
            nombre_prod = f"Producto {codigo}"
            
            cursor.execute(
                "INSERT INTO Productos (codigo, nombre, costo_unitario, moneda_costo, stock) VALUES (?, ?, ?, ?, ?)",
                (codigo, nombre_prod, costo_unitario, moneda, unidades) # <-- Moneda registrada aquí
            )
            accion_inventario = f"Nuevo producto ({codigo}) creado. Stock inicial: {unidades}."

        # --- B. Registro Financiero (Tabla Movimientos) ---

        fecha_actual = datetime.datetime.now()
        descripcion_gasto = f"COMPRA: {unidades} x {codigo} | Costo unitario: {costo_unitario:.4f} {moneda.upper()} | Nota: {nota_compra}"
        
        cursor.execute(
            "INSERT INTO Movimientos (fecha, tipo, monto, moneda, caja, user_id, descripcion) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (fecha_actual, 'gasto', costo_total, moneda, caja, user_id, descripcion_gasto)
        )
        
        conn.commit()
        conn.close()

        # 5. Confirmar al usuario
        await update.message.reply_html(
            f"📦 <b>¡Entrada de Mercancía Registrada!</b>\n\n"
            f"<b>Producto:</b> {codigo} ({nombre_prod})\n"
            f"<b>Unidades Añadidas:</b> {unidades}\n"
            f"<b>Costo Unitario:</b> {costo_unitario:,.2f} {moneda.upper()}\n"
            f"<b>Acción Inventario:</b> {accion_inventario}\n"
            f"<b>Gasto Registrado:</b> -{costo_total:,.2f} {moneda.upper()} de {caja.upper()}"
        )

    except ValueError as e:
        await update.message.reply_html(
            f"<b>Error de formato o validación:</b> {e}\n"
            "Uso correcto: <code>/entrada [código] [unidades] [costo_total] [moneda] [caja] [proveedor/nota...]</code>\n"
            "Ejemplo: <code>/entrada SHIRT01 50 1000 usd cfg 'Compra a proveedor A'</code>"
        )
    except Exception as e:
        logger.error(f"Error inesperado en /entrada: {e}")
        await update.message.reply_text("Ocurrió un error inesperado al registrar la entrada.")


# --- FASE 9.5 (MODIFICADA): FUNCIÓN PARA /stock (Reporte de Inventario) ---
async def stock_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manejador para el comando /stock: Muestra el inventario actual con la moneda de costo correcta."""
    user_id = update.effective_user.id
    if user_id not in ADMIN_USER_IDS:
        await update.message.reply_text("⛔ No tienes permiso.")
        return

    try:
        conn = sqlite3.connect("contabilidad.db")
        cursor = conn.cursor()

        # Seleccionamos todos los campos relevantes, incluyendo moneda_costo
        cursor.execute("""
            SELECT codigo, nombre, stock, costo_unitario, moneda_costo
            FROM Productos
            WHERE stock > 0
            ORDER BY codigo
        """)
        
        resultados = cursor.fetchall() 
        conn.close()

        if not resultados:
            await update.message.reply_text("El inventario está actualmente vacío (stock = 0).")
            return

        respuesta = "--- 📋 Inventario Actual (Costo Original) ---\n\n"
        
        # Diccionario para valorizar por moneda (opcional, para el resumen)
        total_valor_costo_por_moneda = {}

        for codigo, nombre, stock, costo_unitario, moneda_costo in resultados:
            
            valor_costo_articulo = stock * costo_unitario
            moneda_upper = moneda_costo.upper()
            
            # Acumular el valor total por moneda
            if moneda_upper not in total_valor_costo_por_moneda:
                total_valor_costo_por_moneda[moneda_upper] = 0.0
            total_valor_costo_por_moneda[moneda_upper] += valor_costo_articulo
            
            respuesta += (
                f"📦 <b>{codigo}</b> ({nombre})\n"
                f"  • Stock: {stock:,.0f} unidades\n"
                f"  • Costo Unitario: {costo_unitario:,.2f} {moneda_upper}\n" 
                f"  • Valor Total (Costo): {valor_costo_articulo:,.2f} {moneda_upper}\n\n"
            )

        respuesta += "--------------------------------------\n"
        respuesta += f"📊 <b>Resumen de Valor de Inventario:</b>\n"
        
        # Mostrar el resumen por cada moneda
        for moneda, total in total_valor_costo_por_moneda.items():
             respuesta += f"Total {moneda}: {total:,.2f} {moneda}\n"


        await update.message.reply_html(respuesta)

    except Exception as e:
        logger.error(f"Error inesperado en /stock: {e}")
        await update.message.reply_text("Ocurrió un error inesperado al generar el reporte de stock.")

# --- FASE 10: NUEVA FUNCIÓN PARA /venta (Ingreso y Consumo de Stock) ---
async def venta_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Registra una venta, consume stock y registra el ingreso.
    Formato: /venta [código] [unidades] [monto_total] [moneda] [caja] [vendedor/nota...]
    """
    user_id = update.effective_user.id
    if user_id not in ADMIN_USER_IDS:
        await update.message.reply_text("⛔ No tienes permiso.")
        return

    try:
        # Necesitamos al menos 6 argumentos
        if len(context.args) < 6:
            raise ValueError("Faltan argumentos.")

        # 1. Parsear argumentos
        codigo = context.args[0].upper()
        unidades = int(context.args[1])
        monto_total = float(context.args[2])
        moneda = context.args[3].lower()
        caja = context.args[4].lower()
        
        # El resto es la descripción de la venta (vendedor, cliente, nota, etc.)
        nota_venta = " ".join(context.args[5:])

        # 2. Validaciones iniciales
        if unidades <= 0: raise ValueError("Las unidades deben ser un número entero positivo.")
        if monto_total <= 0: raise ValueError("El monto total debe ser un número positivo.")
        if moneda not in VALID_MONEDAS: raise ValueError(f"Moneda no válida. Usa: {', '.join(VALID_MONEDAS)}")
        if caja not in VALID_CAJAS: raise ValueError(f"Caja no válida. Usa: {', '.join(VALID_CAJAS)}")
        
        precio_unitario = monto_total / unidades

        conn = sqlite3.connect("contabilidad.db")
        cursor = conn.cursor()
        
        # --- A. Verificación de Stock (Lectura) ---
        cursor.execute("SELECT stock, costo_unitario, moneda_costo, nombre FROM Productos WHERE codigo = ?", (codigo,))
        producto_existente = cursor.fetchone()
        
        if not producto_existente:
            conn.close()
            raise ValueError(f"Producto con código {codigo} no encontrado en el inventario.")

        stock_anterior, costo_unitario, moneda_costo, nombre_prod = producto_existente
        
        if stock_anterior < unidades:
            conn.close()
            raise ValueError(f"Stock insuficiente. Solo quedan {stock_anterior} unidades de {codigo}.")
            
        # --- B. Gestión del Inventario (Escritura) ---
        
        nuevo_stock = stock_anterior - unidades

        cursor.execute(
            "UPDATE Productos SET stock = ? WHERE codigo = ?", 
            (nuevo_stock, codigo)
        )
        
        # --- C. Registro Financiero (Escritura) ---

        fecha_actual = datetime.datetime.now()
        
        # Calcular la ganancia bruta (para el reporte final)
        costo_venta = unidades * costo_unitario
        
        # Descripción de la transacción
        descripcion_ingreso = (
            f"VENTA: {unidades} x {codigo} | "
            f"Precio unitario: {precio_unitario:,.2f} {moneda.upper()} | "
            f"Costo Total: {costo_venta:,.2f} {moneda_costo.upper()} | "
            f"Nota: {nota_venta}"
        )
        
        # Es un INGRESO (entrada de dinero)
        cursor.execute(
            "INSERT INTO Movimientos (fecha, tipo, monto, moneda, caja, user_id, descripcion) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (fecha_actual, 'ingreso', monto_total, moneda, caja, user_id, descripcion_ingreso)
        )
        
        conn.commit()
        conn.close()

        # 4. Confirmar al usuario
        await update.message.reply_html(
            f"✅ <b>¡Venta Registrada!</b>\n\n"
            f"<b>Producto:</b> {codigo} ({nombre_prod})\n"
            f"<b>Unidades Vendidas:</b> {unidades}\n"
            f"<b>Precio de Venta Unitario:</b> {precio_unitario:,.2f} {moneda.upper()}\n"
            f"<b>Ingreso Registrado:</b> +{monto_total:,.2f} {moneda.upper()} a {caja.upper()}\n"
            f"<b>Stock Restante:</b> {nuevo_stock} unidades.\n\n"
            f"<i>Ganancia Bruta: ({monto_total:,.2f} {moneda.upper()} - {costo_venta:,.2f} {moneda_costo.upper()})</i>"
        )
        logger.info(f"Venta de {unidades}x{codigo} registrada por {user_id}")

    except ValueError as e:
        await update.message.reply_html(
            f"<b>Error:</b> {e}\n"
            "Uso correcto: <code>/venta [código] [unidades] [monto_total] [moneda] [caja] [vendedor/nota...]</code>\n"
            "Ejemplo: <code>/venta SHIRT01 2 20 usd cfg 'Vendido por María'</code>"
        )
    except Exception as e:
        logger.error(f"Error inesperado en /venta: {e}")
        await update.message.reply_text("Ocurrió un error inesperado al registrar la venta.")


def main() -> None:
    """Función principal que inicia el bot."""
    setup_database()
    # # --- EJECUCIÓN ÚNICA: ARREGLA LA TABLA ---
    # fix_db_productos_schema() 
    # # ----------------------------------------
    
    application = Application.builder().token(TOKEN).build()

    # Añadimos los manejadores
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("ingreso", ingreso_command))
    
    # --- FASES 5 y 6: AÑADIMOS LOS NUEVOS MANEJADORES ---
    application.add_handler(CommandHandler("gasto", gasto_command))
    application.add_handler(CommandHandler("balance", balance_command))
    # ----------------------------------------------------
    
    # --- FASES 7 & 8: NUEVOS MANEJADORES ---
    application.add_handler(CommandHandler("cambio", cambio_command)) 
    application.add_handler(CommandHandler("pago", pago_vendedor_command)) 
    application.add_handler(CommandHandler("pago_proveedor", pago_proveedor_command))
    # ----------------------------------------

    # --- FASE 9: NUEVO MANEJADOR DE INVENTARIO ---
    application.add_handler(CommandHandler("entrada", entrada_command)) 
    # ---------------------------------------------
    
    # --- FASE 9.5: NUEVO MANEJADOR DE INVENTARIO ---
    application.add_handler(CommandHandler("stock", stock_command)) 
    # ---------------------------------------------
    
    # --- FASE 10: NUEVO MANEJADOR DE VENTA ---
    application.add_handler(CommandHandler("venta", venta_command)) 
    # ----------------------------------------
    
    print("¡Bot corriendo! Presiona CTRL+C para detenerlo.")
    application.run_polling()


if __name__ == "__main__":
    main()