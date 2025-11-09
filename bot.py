import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from config_secret import ( TOKEN, ADMIN_USER_IDS )
from db_manager import setup_database
from config_vars import (
    VALID_MONEDAS, VALID_CAJAS, TASA_USD_CUP
)

# Importamos los handlers
from handlers.contabilidad import (
    ingreso_command, gasto_command, balance_command, 
    cambio_command, pago_proveedor_command,
    pago_vendedor_command, deudas_command, historial_command,
    exportar_command, set_tasa_command,
)
from handlers.inventario import (
    entrada_command, stock_command, venta_command, ganancia_command,
    consignar_command, stock_consignado_command
)
# -------------------------------

# Configuración de logging (mantener)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


def main() -> None:
    """Función principal que inicia el bot."""
    setup_database()
    
    application = Application.builder().token(TOKEN).build()

    # --- REGISTRO DE MANEJADORES ---
    # Contabilidad
    application.add_handler(CommandHandler("set_tasa", set_tasa_command))
    application.add_handler(CommandHandler("ingreso", ingreso_command))
    application.add_handler(CommandHandler("gasto", gasto_command))
    application.add_handler(CommandHandler("balance", balance_command))
    application.add_handler(CommandHandler("cambio", cambio_command))
    application.add_handler(CommandHandler("pago_vendedor", pago_vendedor_command))
    application.add_handler(CommandHandler("pago_proveedor", pago_proveedor_command))
    application.add_handler(CommandHandler("deudas", deudas_command))
    application.add_handler(CommandHandler("historial", historial_command))
    application.add_handler(CommandHandler("exportar", exportar_command))
    
    # Inventario
    application.add_handler(CommandHandler("entrada", entrada_command))
    application.add_handler(CommandHandler("stock", stock_command))
    application.add_handler(CommandHandler("venta", venta_command)) 
    application.add_handler(CommandHandler("ganancia", ganancia_command))
    application.add_handler(CommandHandler("consignar", consignar_command))
    application.add_handler(CommandHandler("stock_consignado", stock_consignado_command))
    # -------------------------------
    
    print("¡Bot corriendo! Presiona CTRL+C para detenerlo.")
    application.run_polling()


if __name__ == '__main__':
    main()