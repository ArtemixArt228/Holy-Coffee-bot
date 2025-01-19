import os
from datetime import datetime

import pytz
from supabase import Client, create_client


class Database:
    def __init__(self):
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_KEY")
        self.client: Client = create_client(self.url, self.key)
        self.timezone = pytz.timezone("Europe/Kyiv")

    def get_current_time(self):
        """Returns the current time localized to Ukrainian time."""
        return datetime.now(self.timezone).strftime("%Y-%m-%d %H:%M:%S")

    # Reservation logic
    def get_available_slots(self, date, start_hour=10, end_hour=21):
        current_time = datetime.now(self.timezone)
        current_hour = current_time.hour

        # Fetch reserved slots
        reserved_slots = (
            self.client.table("reservations").select("slot").eq("date", date).execute()
        )
        reserved_slots = {row["slot"] for row in reserved_slots.data}

        # Determine available slots
        if date == current_time.strftime("%Y-%m-%d"):  # If today
            all_slots = {
                f"{hour}:00"
                for hour in range(max(start_hour, current_hour + 1), end_hour + 1)
            }
        else:  # Future dates
            all_slots = {f"{hour}:00" for hour in range(start_hour, end_hour + 1)}

        # Return available slots
        return sorted(all_slots - reserved_slots)

    def reserve_slot(self, date, slot, user_id, username):
        created_at = self.get_current_time()
        try:
            response = (
                self.client.table("reservations")
                .insert(
                    {
                        "date": date,
                        "slot": slot,
                        "user_id": user_id,
                        "username": username,
                        "created_at": created_at,
                    }
                )
                .execute()
            )
            return response.data[0]["id"]
        except Exception as e:
            return None

    # User details logic
    def update_user_details(self, reservation_id, name, surname, phone):
        try:
            self.client.table("reservations").update(
                {"name": name, "surname": surname, "phone": phone}
            ).eq("id", reservation_id).execute()
            return True
        except Exception as e:
            return None

    # Payment logic
    def update_payment_status(self, reservation_id, status, payment_id, payment_method):
        """Update the payment status of a reservation."""
        self.client.table("reservations").update(
            {
                "payment_status": status,
                "payment_method": payment_method,
                "payment_id": payment_id,
            }
        ).eq("id", reservation_id).execute()

    # Fetch user reservations
    def get_user_current_reservations(self, user_id):
        current_time = self.get_current_time()
        response = (
            self.client.table("reservations")
            .select("slot, date, created_at")
            .filter("user_id", "eq", user_id)
            .filter("date", "gte", current_time.split(" ")[0])
            .order("date")
            .execute()
        )
        return response.data

    def get_all_user_reservations(self, user_id):
        response = (
            self.client.table("reservations")
            .select("slot, date, created_at")
            .filter("user_id", "eq", user_id)
            .order("date")
            .execute()
        )
        return response.data

    # Cancel reservation logic
    def cancel_slot(self, user_id, date, slot):
        response = (
            self.client.table("reservations")
            .delete()
            .match({"user_id": user_id, "date": date, "slot": slot})
            .execute()
        )
        return response.data

    def cancel_reservations(self, user_id):
        self.client.table("reservations").delete().eq("user_id", user_id).execute()
