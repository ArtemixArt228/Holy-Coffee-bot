import asyncio
import logging
from datetime import datetime, time, timedelta

from telegram import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

WORKING_HOURS_END = time(21, 0)  # Working hours end at 6:00 PM
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
        if now.time() > WORKING_HOURS_END:
            now += timedelta(days=1)

        now = get_next_valid_date(now)

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

        date = query.data
        context.user_data["selected_date"] = date
        await query.edit_message_text(
            text=f"Date selected: {date}\nUse /reserve to view available slots."
        )

    # Slot selection logic
    async def reserve(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        date = context.user_data.get("selected_date")
        if not date:
            await update.message.reply_text(
                "Будь ласка, спочатку оберіть дату за допомогою команди /select_date 🙏"
            )
            return

        available_slots = self.db.get_available_slots(date)
        if not available_slots:
            await update.message.reply_text(
                f"На жаль, на {date} немає вільних місць 😥 Можливо, спробуйте іншу дату?😉️"
            )
            return

        keyboard = [
            [InlineKeyboardButton(slot, callback_data=f"{date} {slot}")]
            for slot in available_slots
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"Вільні місця на {date} ✔", reply_markup=reply_markup
        )

    async def handle_slot_selection(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        query = update.callback_query
        await query.answer()

        try:
            date, slot = query.data.split()
            user_id = query.from_user.id
            username = query.from_user.username or query.from_user.first_name
            print(query.from_user)

            reservation_id = self.db.reserve_slot(date, slot, user_id, username)

            if reservation_id:
                await query.edit_message_text(
                    text=f"Reservation confirmed for {date} at {slot}!"
                )
                context.user_data["reservation_id"] = reservation_id

                # Ask for user details
                await self.ask_user_details(query, context)
            else:
                await query.edit_message_text(
                    text=f"Sorry, {slot} on {date} is already reserved."
                )

        except Exception as e:
            print(f"Error: {e}")  # Log the error for debugging
            await query.edit_message_text(
                text="An error occurred while processing your reservation. Please try again."
            )

    # User details logic
    async def ask_user_details(
        self, query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Ask the user for their phone number, surname, and name."""
        await query.message.reply_text(
            text=(
                "Thank you for your reservation! Please provide the following details:\n\n"
                "1. Full Name\n"
                "2. Surname\n"
                "3. Phone Number\n\n"
                "Reply in the format:\n"
                "`Name, Surname, Phone Number`\n"
            ),
            parse_mode="Markdown",
        )

    async def handle_user_details(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the user's reply with their details."""
        user_details = update.message.text.strip()  # Correctly use update.message
        try:
            name, surname, phone = [item.strip() for item in user_details.split(",")]
            print(f"Received details - Name: {name}, Surname: {surname}, Phone: {phone}")

            # Save details to the database or update reservation
            reservation_id = context.user_data.get("reservation_id")
            if reservation_id:
                self.db.update_user_details(reservation_id, name, surname, phone)
                await update.message.reply_text(
                    text="Thank you! Your details have been saved successfully. 😊"
                )

                # Ask payment preference after saving user details
                await self.ask_payment_preference(update, context)
            else:
                await update.message.reply_text(
                    text="It seems your reservation ID is missing. Please contact support."
                )
        except ValueError:
            await update.message.reply_text(
                text="Invalid format! Please reply with:\n`Name, Surname, Phone Number`",
                parse_mode="Markdown",
            )

    # Payments logic
    async def ask_payment_preference(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Ask the user for their payment preference."""
        keyboard = [
            [
                InlineKeyboardButton("Pay Online 💳", callback_data="payment:online"),
                InlineKeyboardButton("Pay at Cafe ☕", callback_data="payment:cafe"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(  # Use update.message here
            text="How would you like to pay for your reservation?",
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
            await query.edit_message_text(
                text="It seems your reservation ID is missing. Please contact support."
            )
            return

        if choice == "online":
            # Send a payment request (example implementation)
            payment_id = await self.send_payment_request(user_id, reservation_id)
            if payment_id:
                # Save payment ID in the database
                self.db.update_payment_status(reservation_id, "paid", payment_id)
                await query.edit_message_text(
                    text="Payment successful! Your reservation is confirmed. 🎉"
                )
            else:
                await query.edit_message_text(
                    text="Payment failed. Please try again or choose another payment method."
                )
        elif choice == "cafe":
            # Update payment status in the database
            self.db.update_payment_status(reservation_id, "pending", None)
            await query.edit_message_text(
                text="You have chosen to pay at the cafe. Please arrive on time. 😊"
            )

    async def send_payment_request(self, user_id: int, reservation_id: int) -> str:
        """Simulate sending a payment request and return a payment ID."""
        # Replace this with actual payment gateway integration
        try:
            # Simulate payment gateway processing
            await asyncio.sleep(2)  # Simulating network delay
            payment_id = f"PAY-{reservation_id}-{user_id}"
            return payment_id
        except Exception as e:
            print(f"Payment request failed: {e}")
            return None

    # User reservation view logic
    async def view_user_current_reservations(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        user_id = update.message.from_user.id

        reservations = self.db.get_user_current_reservations(user_id)
        if not reservations:
            await update.message.reply_text("No reservations found.")
            return

        message = "Current Reservations:\n"
        for slot, date, created_at in reservations:
            message += f"Зарезервовано на {date} о {slot}\n"
        await update.message.reply_text(message)

    async def view_user_all_reservations(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        user_id = update.message.from_user.id

        reservations = self.db.get_all_user_reservations(user_id)
        if not reservations:
            await update.message.reply_text("No reservations found.")
            return

        message = "Your history of Reservations:\n"
        for slot, date, created_at in reservations:
            message += f"Зарезервовано на {date} о {slot}\n"
        await update.message.reply_text(message)

    # User canceling reservation logic
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.message.from_user.id
        self.db.cancel_reservations(user_id)
        await update.message.reply_text("Your reservations have been canceled.")

    async def cancel_reservation(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        user_id = update.message.from_user.id

        # Fetch all user reservations
        reservations = self.db.get_user_current_reservations(user_id)
        if not reservations:
            await update.message.reply_text("No reservations found.")
            return

        # Build InlineKeyboard with reservation details
        keyboard = [
            [
                InlineKeyboardButton(
                    f"{reservation[1]} at {reservation[0]}",  # Display: Date at Slot
                    callback_data=f"cancel:{reservation[1]}:{reservation[0]}",  # Data: cancel:date:slot
                )
            ]
            for reservation in reservations
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Select a reservation to cancel:", reply_markup=reply_markup
    )

    async def handle_cancel_reservation(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        query = update.callback_query
        await query.answer()

        try:
            # Extract "cancel", date, and slot using maxsplit
            prefix, date, slot = query.data.split(":", 2)
            if prefix != "cancel":
                raise ValueError("Callback data does not start with 'cancel'")

            user_id = query.from_user.id

            if self.db.cancel_slot(user_id, date, slot):
                await query.edit_message_text(
                    text=f"Reservation for {date} at {slot} has been canceled."
                )
            else:
                await query.edit_message_text(
                    text=f"Failed to cancel reservation for {date} at {slot}. It may not exist."
                )
        except ValueError:
            await query.edit_message_text(
                text=f"Invalid callback data format: {query.data}. Unable to process cancellation."
            )
        except Exception as e:
            await query.edit_message_text(
                text="An error occurred while processing your request. Please try again."
            )
            print(f"Error: {e}")
