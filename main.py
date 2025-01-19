from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from app.config import Config
from app.database import Database
from app.handlers import Handlers
from app.scheduler import setup_scheduler


# Main function
def main():
    db = Database()
    app = Application.builder().token(Config.BOT_TOKEN).build()
    handlers = Handlers(db)

    app.add_handler(CommandHandler("start", handlers.start))

    app.add_handler(CommandHandler("select_date", handlers.select_date))
    app.add_handler(CallbackQueryHandler(handlers.handle_date_selection, pattern=r"^\d{4}-\d{2}-\d{2}$"))

    app.add_handler(CommandHandler("reserve", handlers.reserve))
    app.add_handler(CallbackQueryHandler(handlers.handle_slot_selection, pattern=r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_user_details))

    app.add_handler(
        CallbackQueryHandler(
            handlers.handle_payment_choice, pattern=r"^payment:(online|cafe)$"
        )
    )

    app.add_handler(
        CommandHandler(
            "view_my_current_reservations", handlers.view_user_current_reservations
        )
    )
    app.add_handler(
        CommandHandler(
            "view_my_all_reservations", handlers.view_user_all_reservations
        )
    )

    app.add_handler(CommandHandler("cancel_reservation", handlers.cancel_reservation))
    app.add_handler(
        CallbackQueryHandler(
            handlers.handle_cancel_reservation, pattern=r"^cancel:.+:.+$"
        )
    )
    app.add_handler(CommandHandler("cancel_all_reservations", handlers.cancel))

    setup_scheduler(app, db)

    app.run_polling()


if __name__ == "__main__":
    main()
