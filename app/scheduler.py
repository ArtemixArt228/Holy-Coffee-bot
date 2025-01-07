from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler


def check_for_reminders(application, db):
    now = datetime.now()
    reminder_time = now + timedelta(minutes=15)
    reminder_time_str = reminder_time.strftime("%Y-%m-%d %H:%M:%S")

    upcoming_reservations = db.execute_query(
        "SELECT slot, user_id FROM reservations WHERE slot = ?",
        (reminder_time_str,),
        fetch_all=True,
    )

    for slot, user_id in upcoming_reservations:
        application.bot.send_message(
            chat_id=user_id,
            text=f"Reminder: Your playroom reservation is at {slot}. Please arrive on time!",
        )


def setup_scheduler(application, db):
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        check_for_reminders, "interval", minutes=1, args=[application, db]
    )
    scheduler.start()
