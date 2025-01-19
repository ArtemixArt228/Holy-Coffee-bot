import logging
from datetime import datetime, time, timedelta

from telegram import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

WORKING_HOURS_END = time(21, 0)  # Working hours end at 09:00 PM
DAYS_IN_WEEK = 7  # Number of days to show in the calendar

def get_next_valid_date(start_date: datetime) -> datetime:
    """Get the next valid date considering working hours."""
    if start_date.time() > WORKING_HOURS_END:
        start_date += timedelta(days=1)
    return start_date


def generate_dates(start_date: datetime, days: int) -> list[datetime]:
    """Generate dates within working hours for the next 'days' days."""
    dates = []
    current_date = get_next_valid_date(start_date)

    for _ in range(days):
        dates.append(current_date)
        current_date += timedelta(days=1)
    return dates

class Handlers:
    def __init__(self, db):
        self.db = db

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(
            "Ласкаво просимо до нашого Holy Coffee bot ✨✨✨ Використовуйте /select_date, щоб забронювати ігрову кімнату 🚪"
        )

    # Date selection logic
    async def select_date(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        now = datetime.now()

        available_dates = generate_dates(now, DAYS_IN_WEEK)

        keyboard = [
            [
                InlineKeyboardButton(
                    date.strftime("%Y-%m-%d"), callback_data=date.strftime("%Y-%m-%d")
                )
            ]
            for date in available_dates
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "Оберіть дату бронювання 📆", reply_markup=reply_markup
        )

    async def handle_date_selection(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        query = update.callback_query
        await query.answer()

        # Store the selected date
        date = query.data
        context.user_data["selected_date"] = date

        # Notify the user of the selected date
        await query.edit_message_text(
            text=f"Дата обрана: {date} 📅\nШукаємо доступні слоти... ⏳"
        )

        # Call the reserve handler and pass the query as an argument
        await self.reserve(update, context, query=query)

    # Slot selection logic
    async def reserve(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, query=None
    ) -> None:
        date = context.user_data.get("selected_date")
        if not date:
            if query:
                await query.message.reply_text(
                    "Будь ласка, спочатку оберіть дату за допомогою команди /select_date 🙏"
                )
            else:
                await update.message.reply_text(
                    "Будь ласка, спочатку оберіть дату за допомогою команди /select_date 🙏"
                )
            return

        available_slots = self.db.get_available_slots(date)
        if not available_slots:
            if query:
                await query.message.reply_text(
                    f"На жаль, на {date} немає вільних місць 😥 Можливо, спробуйте іншу дату?😉️"
                )
            else:
                await update.message.reply_text(
                    f"На жаль, на {date} немає вільних місць 😥 Можливо, спробуйте іншу дату?😉️"
                )
            return

        keyboard = [
            [InlineKeyboardButton(slot, callback_data=f"{date} {slot}")]
            for slot in available_slots
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if query:
            await query.message.reply_text(
                f"Вільні місця на {date} ✔", reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                f"Вільні місця на {date} ✔", reply_markup=reply_markup
            )

    async def handle_slot_selection(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        query = update.callback_query
        await query.answer()

        date, slot = query.data.split()
        user_id = query.from_user.id
        username = query.from_user.username or query.from_user.first_name

        reservation_id = self.db.reserve_slot(date, slot, user_id, username)

        if reservation_id:
            await query.edit_message_text(
                text=f"Бронювання підтверджено на {date} о {slot}! ✅🎉"
            )
            context.user_data["reservation_id"] = reservation_id
            context.user_data["slot_selected"] = True

            # Ask for user details
            await self.ask_user_details(query, context)
        else:
            await query.edit_message_text(
                text=f"На жаль, {slot} {date} вже заброньовано. 😔❌"
            )

    # User details logic
    async def ask_user_details(
        self, query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Ask the user for their phone number, surname, and name."""
        if not context.user_data.get("slot_selected"):
            return

        await query.message.reply_text(
            text=(
                "Дякуємо за ваше бронювання! 🎉 Будь ласка, надайте наступні дані:\n\n"
                "1. Ім'я 👤\n"
                "2. Прізвище 📝\n"
                "3. Номер телефону 📞\n\n"
                "Відповідайте у форматі:\n"
                "`Ім'я, Прізвище, Номер телефону`\n"
            ),
            parse_mode="Markdown",
        )

    async def handle_user_details(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the user's reply with their details."""
        user_details = update.message.text.strip()  # Correctly use update.message
        name, surname, phone = [item.strip() for item in user_details.split(",")]

        # Save details to the database or update reservation
        reservation_id = context.user_data.get("reservation_id")
        if reservation_id:
            self.db.update_user_details(reservation_id, name, surname, phone)
            await update.message.reply_text(
                text="Дякуємо! Ваші дані успішно збережено. 😊✅"
            )

            # Ask payment preference after saving user details
            await self.ask_payment_preference(update, context)
        else:
            await update.message.reply_text(
                text="Схоже, ваш ID бронювання відсутній. Будь ласка, спробуйте забронювати слот ще раз. 📞🛠️"
            )

    # Payments logic
    async def ask_payment_preference(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Ask the user for their payment preference."""
        keyboard = [
            [
                InlineKeyboardButton(
                    "Оплатити онлайн 💳", callback_data="payment:online"
                ),
                InlineKeyboardButton(
                    "Оплатити в кафе ☕", callback_data="payment:cafe"
                ),
            ]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            text="Як ви бажаєте оплатити своє бронювання? 💳☕",
            reply_markup=reply_markup,
        )

    async def handle_payment_choice(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        query = update.callback_query
        await query.answer()

        choice = query.data.split(":")[1]  # Extract 'online' or 'cafe'
        reservation_id = context.user_data.get("reservation_id")
        user_id = query.from_user.id

        if not reservation_id:
            await update.message.reply_text(
                text="Схоже, ваш ID бронювання відсутній. Будь ласка, спробуйте забронювати слот ще раз. 📞🛠️"
            )
            return

        if choice == "online":
            self.db.update_payment_status(
                reservation_id, "paid", f"payment_{user_id}_{reservation_id}", "Онлайн"
            )
            await query.edit_message_text(
                text=(
                    "Ви обрали оплату онлайн. 🖥️💳 Ось реквізити для оплати:\n\n"
                    "IBAN: UA123456789012345678901234567\n"
                    "Або номер карти: 1234 5678 9012 3456\n\n"
                    "📌 У призначенні платежу ОБОВ'ЯЗКОВО вкажіть дату, обраний час бронювання та ваше прізвище.\n\n"
                    "Дякуємо! Чекаємо в Holy Coffee 😊☕"
                )
            )

        elif choice == "cafe":
            self.db.update_payment_status(reservation_id, "pending", None, "В кафе")
            await query.edit_message_text(
                text="Ви обрали оплату в кафе. Будь ласка, приходьте вчасно. 😊☕"
            )

    # User reservation view logic
    async def view_user_current_reservations(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        user_id = update.message.from_user.id

        reservations = self.db.get_user_current_reservations(user_id)
        if not reservations:
            await update.message.reply_text("У вас немає активних бронювань. 😔")
            return

        message = "Ваші поточні бронювання:\n\n"
        for reservation in reservations:
            slot = reservation["slot"]
            date = reservation["date"]
            created_at = reservation["created_at"]
            try:
                created_at_dt = datetime.fromisoformat(created_at)
                formatted_created_at = created_at_dt.strftime("%d.%m.%Y %H:%M")
            except ValueError:
                formatted_created_at = "Невідомий час"

            message += (
                f"📅 Дата: *{date}*\n"
                f"⏰ Час: *{slot}*\n"
                f"📝 Заброньовано: {formatted_created_at}\n"
                f"-----------------------\n"
            )

        await update.message.reply_text(message, parse_mode="Markdown")

    async def view_user_all_reservations(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        user_id = update.message.from_user.id

        reservations = self.db.get_all_user_reservations(user_id)
        if not reservations:
            await update.message.reply_text("У вас немає історії бронювань. 😔")
            return

        message = "Історія ваших бронювань:\n\n"
        for reservation in reservations:
            slot = reservation["slot"]
            date = reservation["date"]
            created_at = reservation["created_at"]
            try:
                created_at_dt = datetime.fromisoformat(created_at)
                formatted_created_at = created_at_dt.strftime("%d.%m.%Y %H:%M")
            except ValueError:
                formatted_created_at = "Невідомий час"

            message += (
                f"📅 Дата: *{date}*\n"
                f"⏰ Час: *{slot}*\n"
                f"📝 Заброньовано: {formatted_created_at}\n"
                f"-----------------------\n"
            )

        await update.message.reply_text(message, parse_mode="Markdown")

    # User canceling reservation logic
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.message.from_user.id
        self.db.cancel_reservations(user_id)
        await update.message.reply_text("Ваші бронювання було скасовано. ❌")

    async def cancel_reservation(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        user_id = update.message.from_user.id

        # Fetch all user reservations
        reservations = self.db.get_user_current_reservations(user_id)
        if not reservations:
            await update.message.reply_text("У вас немає активних бронювань. 😔")
            return

        # Build InlineKeyboard with reservation details
        keyboard = [
            [
                InlineKeyboardButton(
                    f"📅 {reservation["date"]} ⏰ {reservation["slot"]}",  # Display: Date and Slot
                    callback_data=f"cancel:{reservation["date"]}:{reservation["slot"]}",  # Data: cancel:date:slot
                )
            ]
            for reservation in reservations
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Оберіть бронювання для скасування: ⬇", reply_markup=reply_markup
        )

    async def handle_cancel_reservation(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        query = update.callback_query
        await query.answer()

        # Extract "cancel", date, and slot using maxsplit
        prefix, date, slot = query.data.split(":", 2)
        if prefix != "cancel":
            raise ValueError("Дані зворотного виклику не починаються з 'cancel'")

        user_id = query.from_user.id

        if self.db.cancel_slot(user_id, date, slot):
            await query.edit_message_text(
                text=f"Ваше бронювання на {date} о {slot} було успішно скасовано. ❌"
            )
        else:
            await query.edit_message_text(
                text=f"Не вдалося скасувати бронювання на {date} о {slot}. Можливо, воно не існує. ⚠️"
            )
