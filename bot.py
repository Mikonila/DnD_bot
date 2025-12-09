import logging
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters
)
from database import Database
from config import ADMIN_IDS, DM_CONTACT, DB_NAME
import re

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

db = Database(db_name=DB_NAME)

# Состояния для админ-панели и отзывов
(WAITING_ONESHOT_NAME, WAITING_ONESHOT_DATE, WAITING_ONESHOT_STORY,
 WAITING_ONESHOT_LOCATION, WAITING_ONESHOT_PRICE, WAITING_ONESHOT_DRINK,
 WAITING_CAMPAIGN_NAME, WAITING_CAMPAIGN_DATE, WAITING_CAMPAIGN_DURATION,
 WAITING_CAMPAIGN_STORY, WAITING_CAMPAIGN_LOCATION, WAITING_CAMPAIGN_PRICE,
 WAITING_CAMPAIGN_DRINK, WAITING_REVIEW_TEXT) = range(14)

# Временное хранилище данных для админ-панели
admin_data = {}


def format_oneshot_info(oneshot: dict) -> str:
    text = f'Ваншот "{oneshot["name"]}"\n\n'
    text += f'Дата и время: {oneshot["date_time"]}\n'
    text += f'Сюжет: {oneshot["story"]}\n'
    text += f'Локация: {oneshot["location"]}\n'
    text += f'Стоимость: {oneshot["price"]}\n'
    if oneshot["free_drink"]:
        text += '\nВ стоимость входит бесплатный напиток!'
    return text


def format_campaign_info(campaign: dict) -> str:
    text = f'Кампания "{campaign["name"]}"\n\n'
    text += f'Дата и время: {campaign["date_time"]}\n'
    text += f'Длительность: {campaign["duration"]}\n'
    text += f'Сюжет: {campaign["story"]}\n'
    text += f'Локация: {campaign["location"]}\n'
    text += f'Стоимость: {campaign["price"]}\n'

    # Статус кампании
    try:
        # ВАЖНО: здесь предполагаем формат "YYYY-MM-DD HH:MM"
        event_dt = datetime.strptime(campaign["date_time"], "%Y-%m-%d %H:%M")
        now = datetime.now()
        if event_dt > now:
            status = "Еще не стартовала"
        else:
            status = f"Стартовала от {event_dt.strftime('%d/%m')}"
        text += f'\nСтатус: {status}'
    except ValueError:
        # Если дата введена в другом формате — просто не показываем статус
        pass

    if campaign["free_drink"]:
        text += '\nВ стоимость входит бесплатный напиток!'

    return text




async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id in ADMIN_IDS:
        keyboard = [
            [KeyboardButton("Зарегистрировать ваншот")],
            [KeyboardButton("Зарегистрировать кампанию")],
            [KeyboardButton("Посмотреть все регистрации")],
            [KeyboardButton("Удалить мероприятие")],
            [KeyboardButton("Удалить отзыв")],
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            "Добро пожаловать в админ-панель!\n\n"
            "Выберите действие:",
            reply_markup=reply_markup
        )
        return ConversationHandler.END
    else:
        keyboard = [
            [InlineKeyboardButton("Записаться на ваншот", callback_data="view_oneshots")],
            [InlineKeyboardButton("Присоединиться к D&D кампании", callback_data="view_campaigns")],
            [InlineKeyboardButton("Посмотреть все отзывы", callback_data="view_reviews")],
            [InlineKeyboardButton("Оставить отзыв", callback_data="leave_review")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Добро пожаловать в ДНД-клуб! 🎲\n\n"
            "Выберите, на что вы хотите записаться:",
            reply_markup=reply_markup
        )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if query.data == "view_oneshots":
        oneshots = db.get_upcoming_oneshots()
        if not oneshots:
            keyboard = [[InlineKeyboardButton("Уведомить о появлении", callback_data="notify_oneshot")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "На данный момент не запланировано ваншотов",
                reply_markup=reply_markup
            )
        else:
            oneshot = oneshots[0]
            keyboard = [[InlineKeyboardButton("Записаться", callback_data=f"register_oneshot_{oneshot['id']}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            text = "На данный момент планируется:\n\n" + format_oneshot_info(oneshot)
            await query.edit_message_text(text, reply_markup=reply_markup)
    
    elif query.data == "view_campaigns":
        campaigns = db.get_upcoming_campaigns()
        if not campaigns:
            keyboard = [[InlineKeyboardButton("Уведомить о появлении", callback_data="notify_campaign")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "На данный момент не запланировано кампаний",
                reply_markup=reply_markup
            )
        else:
            campaign = campaigns[0]
            keyboard = [[InlineKeyboardButton("Записаться", callback_data=f"register_campaign_{campaign['id']}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            text = "На данный момент планируется:\n\n" + format_campaign_info(campaign)
            await query.edit_message_text(text, reply_markup=reply_markup)
    
    elif query.data == "notify_oneshot":
        db.add_notification_request(user_id, "oneshot")
        await query.edit_message_text("Вы будете уведомлены, когда появится новый ваншот!")
    
    elif query.data == "notify_campaign":
        db.add_notification_request(user_id, "campaign")
        await query.edit_message_text("Вы будете уведомлены, когда появится новая кампания!")
    
    elif query.data.startswith("register_oneshot_"):
        oneshot_id = int(query.data.split("_")[2])
        oneshot = db.get_oneshot_by_id(oneshot_id)
        
        if oneshot:
            username = query.from_user.username
            first_name = query.from_user.first_name
            
            if db.register_for_oneshot(oneshot_id, user_id, username, first_name):
                await query.edit_message_text(
                    f'Спасибо! Вы записаны на "{oneshot["name"]}". '
                    "Ближе ко дню мероприятия я пришлю вам напоминание!"
                )
                
                # Уведомление админам
                for admin_id in ADMIN_IDS:
                    try:
                        registrations = db.get_registered_users_for_oneshot(oneshot_id)
                        user_info = f"@{username}" if username else first_name
                        await context.bot.send_message(
                            admin_id,
                            f"Новая запись на ваншот!\n\n"
                            f"Ваншот: {oneshot['name']}\n"
                            f"Пользователь: {user_info}\n"
                            f"Всего записей: {len(registrations)}"
                        )
                    except Exception as e:
                        logger.error(f"Ошибка отправки уведомления админу {admin_id}: {e}")
            else:
                await query.edit_message_text("Вы уже записаны на это мероприятие!")
    
    elif query.data.startswith("register_campaign_"):
        campaign_id = int(query.data.split("_")[2])
        campaign = db.get_campaign_by_id(campaign_id)
        
        if campaign:
            username = query.from_user.username
            first_name = query.from_user.first_name
            
            if db.register_for_campaign(campaign_id, user_id, username, first_name):
                await query.edit_message_text(
                    f'Спасибо! Вы записаны на "{campaign["name"]}". '
                    "Ближе ко дню мероприятия я пришлю вам напоминание!"
                )
                
                # Уведомление админам
                for admin_id in ADMIN_IDS:
                    try:
                        registrations = db.get_registered_users_for_campaign(campaign_id)
                        user_info = f"@{username}" if username else first_name
                        await context.bot.send_message(
                            admin_id,
                            f"Новая запись на кампанию!\n\n"
                            f"Кампания: {campaign['name']}\n"
                            f"Пользователь: {user_info}\n"
                            f"Всего записей: {len(registrations)}"
                        )
                    except Exception as e:
                        logger.error(f"Ошибка отправки уведомления админу {admin_id}: {e}")
            else:
                await query.edit_message_text("Вы уже записаны на это мероприятие!")
    elif query.data.startswith("delete_event_"):
        # delete_event_oneshot_123 или delete_event_campaign_456
        if user_id not in ADMIN_IDS:
            await query.answer("Недостаточно прав", show_alert=True)
            return

        parts = query.data.split("_")
        # ["delete", "event", "oneshot", "123"]
        if len(parts) != 4:
            await query.edit_message_text("Не удалось распознать мероприятие для удаления.")
            return

        _, _, event_type, event_id_str = parts
        event_id = int(event_id_str)

        if event_type == "oneshot":
            db.delete_oneshot(event_id)
            await query.edit_message_text("Ваншот удалён.")
        elif event_type == "campaign":
            db.delete_campaign(event_id)
            await query.edit_message_text("Кампания удалена.")
        else:
            await query.edit_message_text("Неизвестный тип мероприятия.")
    elif query.data == "view_reviews":
        reviews = db.get_all_reviews()
        if not reviews:
            text = "Пока нет отзывов."
        else:
            text = "Отзывы:\n\n"
            for review_id, username, first_name, review_text, created_at in reviews:
                user = f"@{username}" if username else first_name or "Пользователь"
                text += f"{user} ({created_at[:16]}):\n{review_text}"
                if user_id in ADMIN_IDS:
                    text += f"\n[Удалить](/delete_review_{review_id})"
                text += "\n\n"
        keyboard = [
            [InlineKeyboardButton("Записаться на ваншот", callback_data="view_oneshots")],
            [InlineKeyboardButton("Присоединиться к D&D кампании", callback_data="view_campaigns")],
            [InlineKeyboardButton("Посмотреть все отзывы", callback_data="view_reviews")],
            [InlineKeyboardButton("Оставить отзыв", callback_data="leave_review")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if user_id in ADMIN_IDS:
            await query.edit_message_text(text, parse_mode="Markdown", disable_web_page_preview=True, reply_markup=reply_markup)
        else:
            await query.edit_message_text(text, reply_markup=reply_markup)
    elif query.data.startswith("delete_review_"):
        if user_id not in ADMIN_IDS:
            await query.answer("Недостаточно прав", show_alert=True)
            return
        review_id = int(query.data.split("_")[2])
        db.delete_review(review_id)
        await query.edit_message_text("Отзыв удалён.")
    elif query.data == "leave_review":
        context.user_data['leave_review'] = True
        await query.edit_message_text("Напишите ваш отзыв одним сообщением:")
        # Не возвращаем WAITING_REVIEW_TEXT, просто завершаем функцию
        return


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    message = update.message
    
    # Не пересылаем сообщения админов
    if user_id in ADMIN_IDS:
        return
    
    # Пересылаем сообщение админам
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.forward_message(
                chat_id=admin_id,
                from_chat_id=message.chat_id,
                message_id=message.message_id
            )
        except Exception as e:
            logger.error(f"Ошибка пересылки сообщения админу {admin_id}: {e}")
    
    # Отвечаем пользователю
    await message.reply_text(
        f"Передал ваше сообщение админам! Если необходимо связаться с Мастером Днд: {DM_CONTACT}"
    )

async def show_all_registrations(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return  # чужих сюда не пускаем

    registrations = db.get_all_registrations()

    if not registrations:
        await update.message.reply_text("Пока что нет записей.")
        return

    lines = []
    for reg in registrations:
        # Ник / имя
        if reg["username"]:
            user_part = f"@{reg['username']}"
        elif reg["first_name"]:
            user_part = reg["first_name"]
        else:
            user_part = "Пользователь"

        # Ваншот или Кампания
        if reg["event_type"] == "oneshot":
            event_type_text = "Ваншот"
        else:
            event_type_text = "Кампания"

        line = (
            f"{event_type_text}: \"{reg['event_name']}\"\n"
            f"Пользователь {user_part}, id {reg['user_id']}"
        )
        lines.append(line)

    text = "Все регистрации:\n\n" + "\n\n".join(lines)
    await update.message.reply_text(text)


# Админ-панель для ваншотов
async def start_oneshot_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return ConversationHandler.END
    
    admin_data[update.effective_user.id] = {}
    await update.message.reply_text("Введите название ваншота:")
    return WAITING_ONESHOT_NAME


async def oneshot_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    admin_data[user_id]["name"] = update.message.text
    await update.message.reply_text("Введите дату и время (формат: ГГГГ-ММ-ДД ЧЧ:ММ):")
    return WAITING_ONESHOT_DATE


async def oneshot_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    admin_data[user_id]["date_time"] = update.message.text
    await update.message.reply_text("Введите сюжет:")
    return WAITING_ONESHOT_STORY


async def oneshot_story(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    admin_data[user_id]["story"] = update.message.text
    await update.message.reply_text("Введите локацию:")
    return WAITING_ONESHOT_LOCATION


async def oneshot_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    admin_data[user_id]["location"] = update.message.text
    await update.message.reply_text("Введите стоимость:")
    return WAITING_ONESHOT_PRICE


async def oneshot_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    admin_data[user_id]["price"] = update.message.text
    keyboard = [[InlineKeyboardButton("Да", callback_data="oneshot_drink_yes"),
                 InlineKeyboardButton("Нет", callback_data="oneshot_drink_no")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("В стоимость входит бесплатный напиток?", reply_markup=reply_markup)
    return WAITING_ONESHOT_DRINK


async def oneshot_drink(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    free_drink = query.data == "oneshot_drink_yes"
    admin_data[user_id]["free_drink"] = free_drink
    
    # Сохраняем ваншот
    data = admin_data[user_id]
    oneshot_id = db.add_oneshot(
        data["name"],
        data["date_time"],
        data["story"],
        data["location"],
        data["price"],
        data["free_drink"]
    )
    
    # Уведомляем пользователей, которые подписались на уведомления
    user_ids = db.get_users_to_notify("oneshot")
    oneshot = db.get_oneshot_by_id(oneshot_id)
    
    for uid in user_ids:
        try:
            keyboard = [[InlineKeyboardButton("Записаться", callback_data=f"register_oneshot_{oneshot_id}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            text = "Появился новый ваншот!\n\n" + format_oneshot_info(oneshot)
            await context.bot.send_message(uid, text, reply_markup=reply_markup)
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления пользователю {uid}: {e}")
    
    del admin_data[user_id]
    await query.edit_message_text(f"Ваншот '{data['name']}' успешно зарегистрирован!")
    return ConversationHandler.END


# Админ-панель для кампаний
async def start_campaign_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return ConversationHandler.END
    
    admin_data[update.effective_user.id] = {}
    await update.message.reply_text("Введите название кампании:")
    return WAITING_CAMPAIGN_NAME


async def campaign_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    admin_data[user_id]["name"] = update.message.text
    await update.message.reply_text("Введите дату и время (формат: ГГГГ-ММ-ДД ЧЧ:ММ):")
    return WAITING_CAMPAIGN_DATE


async def campaign_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    admin_data[user_id]["date_time"] = update.message.text
    await update.message.reply_text("Введите длительность:")
    return WAITING_CAMPAIGN_DURATION


async def campaign_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    admin_data[user_id]["duration"] = update.message.text
    await update.message.reply_text("Введите сюжет:")
    return WAITING_CAMPAIGN_STORY


async def campaign_story(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    admin_data[user_id]["story"] = update.message.text
    await update.message.reply_text("Введите локацию:")
    return WAITING_CAMPAIGN_LOCATION


async def campaign_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    admin_data[user_id]["location"] = update.message.text
    await update.message.reply_text("Введите стоимость:")
    return WAITING_CAMPAIGN_PRICE


async def campaign_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    admin_data[user_id]["price"] = update.message.text
    keyboard = [[InlineKeyboardButton("Да", callback_data="campaign_drink_yes"),
                 InlineKeyboardButton("Нет", callback_data="campaign_drink_no")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("В стоимость входит бесплатный напиток?", reply_markup=reply_markup)
    return WAITING_CAMPAIGN_DRINK


async def campaign_drink(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    free_drink = query.data == "campaign_drink_yes"
    admin_data[user_id]["free_drink"] = free_drink
    
    # Сохраняем кампанию
    data = admin_data[user_id]
    campaign_id = db.add_campaign(
        data["name"],
        data["date_time"],
        data["duration"],
        data["story"],
        data["location"],
        data["price"],
        data["free_drink"]
    )
    
    # Уведомляем пользователей, которые подписались на уведомления
    user_ids = db.get_users_to_notify("campaign")
    campaign = db.get_campaign_by_id(campaign_id)
    
    for uid in user_ids:
        try:
            keyboard = [[InlineKeyboardButton("Записаться", callback_data=f"register_campaign_{campaign_id}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            text = "Появилась новая кампания!\n\n" + format_campaign_info(campaign)
            await context.bot.send_message(uid, text, reply_markup=reply_markup)
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления пользователю {uid}: {e}")
    
    del admin_data[user_id]
    await query.edit_message_text(f"Кампания '{data['name']}' успешно зарегистрирована!")
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in admin_data:
        del admin_data[user_id]
    await update.message.reply_text("Отменено.")
    return ConversationHandler.END


async def check_and_send_reminders(context: ContextTypes.DEFAULT_TYPE):
    registrations = db.get_all_registrations_for_reminders()
    now = datetime.now()
    
    for reg in registrations:
        try:
            event_date = datetime.strptime(reg["date_time"], "%Y-%m-%d %H:%M")
            
            # Проверяем разные типы напоминаний
            reminders_to_check = [
                (timedelta(days=3), "3_days", "3 дня"),
                (timedelta(days=1), "1_day", "1 день"),
                (timedelta(hours=6), "6_hours", "6 часов")
            ]
            
            for time_delta, reminder_type, reminder_text in reminders_to_check:
                reminder_time = event_date - time_delta
                
                # Проверяем, нужно ли отправить напоминание (за последний час)
                time_diff = (now - reminder_time).total_seconds()
                if 0 <= time_diff < 3600:
                    # Проверяем, не было ли уже отправлено это напоминание
                    if not db.was_reminder_sent(
                        reg["event_type"],
                        reg["event_id"],
                        reg["user_id"],
                        reminder_type
                    ):
                        message = None
                        # Отправляем напоминание
                        if reg["event_type"] == "oneshot":
                            event = db.get_oneshot_by_id(reg["event_id"])
                            if event:
                                message = f'Напоминание: через {reminder_text} начнется ваншот "{reg["name"]}"!\n\n'
                                message += format_oneshot_info(event)
                        else:  # campaign
                            event = db.get_campaign_by_id(reg["event_id"])
                            if event:
                                message = f'Напоминание: через {reminder_text} начнется кампания "{reg["name"]}"!\n\n'
                                message += format_campaign_info(event)
                        
                        if message:
                            try:
                                await context.bot.send_message(reg["user_id"], message)
                                db.mark_reminder_sent(
                                    reg["event_type"],
                                    reg["event_id"],
                                    reg["user_id"],
                                    reminder_type
                                )
                                logger.info(f"Отправлено напоминание {reminder_type} пользователю {reg['user_id']} о {reg['name']}")
                            except Exception as e:
                                logger.error(f"Ошибка отправки напоминания пользователю {reg['user_id']}: {e}")
        
        except ValueError as e:
            logger.error(f"Ошибка парсинга даты для {reg.get('name', 'unknown')}: {e}")
        except Exception as e:
            logger.error(f"Ошибка обработки напоминания: {e}")


async def reminder_job(context: ContextTypes.DEFAULT_TYPE):
    await check_and_send_reminders(context)


async def start_delete_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return

    oneshots = db.get_upcoming_oneshots()
    campaigns = db.get_upcoming_campaigns()

    if not oneshots and not campaigns:
        await update.message.reply_text("Пока нет мероприятий для удаления.")
        return

    keyboard = []

    for o in oneshots:
        keyboard.append(
            [InlineKeyboardButton(
                f'Ваншот: {o["name"]} ({o["date_time"]})',
                callback_data=f'delete_event_oneshot_{o["id"]}',
            )]
        )

    for c in campaigns:
        keyboard.append(
            [InlineKeyboardButton(
                f'Кампания: {c["name"]} ({c["date_time"]})',
                callback_data=f'delete_event_campaign_{c["id"]}',
            )]
        )

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите мероприятие для удаления:", reply_markup=reply_markup)


async def start_delete_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return
    reviews = db.get_all_reviews()
    if not reviews:
        await update.message.reply_text("Пока нет отзывов для удаления.")
        return
    keyboard = []
    for review_id, username, first_name, review_text, created_at in reviews:
        user = f"@{username}" if username else first_name or "Пользователь"
        label = f"{user} ({created_at[:16]})"
        keyboard.append([InlineKeyboardButton(f"Удалить: {label}", callback_data=f"delete_review_{review_id}")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите отзыв для удаления:", reply_markup=reply_markup)


# --- Обработчик обычных сообщений (отзыв или пересылка админу) ---
async def universal_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('leave_review'):
        user_id = update.effective_user.id
        username = update.effective_user.username
        first_name = update.effective_user.first_name
        text = update.message.text
        db.add_review(user_id, username, first_name, text)
        keyboard = [
            [InlineKeyboardButton("Записаться на ваншот", callback_data="view_oneshots")],
            [InlineKeyboardButton("Присоединиться к D&D кампании", callback_data="view_campaigns")],
            [InlineKeyboardButton("Посмотреть все отзывы", callback_data="view_reviews")],
            [InlineKeyboardButton("Оставить отзыв", callback_data="leave_review")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Спасибо за ваш отзыв!", reply_markup=reply_markup)
        context.user_data.pop('leave_review', None)
    else:
        await handle_message(update, context)


def main():
    from config import BOT_TOKEN

    application = Application.builder().token(BOT_TOKEN).build()

    # --- Базовые хэндлеры ---
    # /start
    application.add_handler(CommandHandler("start", start))

    # --- Админские диалоги (ConversationHandler-ы) ---

    # Ваншоты
    oneshot_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Regex("^Зарегистрировать ваншот$"),
                start_oneshot_registration
            )
        ],
        states={
            WAITING_ONESHOT_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, oneshot_name)
            ],
            WAITING_ONESHOT_DATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, oneshot_date)
            ],
            WAITING_ONESHOT_STORY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, oneshot_story)
            ],
            WAITING_ONESHOT_LOCATION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, oneshot_location)
            ],
            WAITING_ONESHOT_PRICE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, oneshot_price)
            ],
            WAITING_ONESHOT_DRINK: [
                CallbackQueryHandler(oneshot_drink, pattern="^oneshot_drink_")
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Кампании
    campaign_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Regex("^Зарегистрировать кампанию$"),
                start_campaign_registration
            )
        ],
        states={
            WAITING_CAMPAIGN_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, campaign_name)
            ],
            WAITING_CAMPAIGN_DATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, campaign_date)
            ],
            WAITING_CAMPAIGN_DURATION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, campaign_duration)
            ],
            WAITING_CAMPAIGN_STORY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, campaign_story)
            ],
            WAITING_CAMPAIGN_LOCATION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, campaign_location)
            ],
            WAITING_CAMPAIGN_PRICE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, campaign_price)
            ],
            WAITING_CAMPAIGN_DRINK: [
                CallbackQueryHandler(campaign_drink, pattern="^campaign_drink_")
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(oneshot_conv_handler)
    application.add_handler(campaign_conv_handler)

    # --- Админские кнопки в обычном чате ---

    # Посмотреть все регистрации
    application.add_handler(
        MessageHandler(
            filters.Regex("^Посмотреть все регистрации$"),
            show_all_registrations,
        )
    )

    # Удалить мероприятие (и ваншоты, и кампании)
    application.add_handler(
        MessageHandler(
            filters.Regex("^Удалить мероприятие$"),
            start_delete_event,
        )
    )

    # Удалить отзыв
    application.add_handler(
        MessageHandler(
            filters.Regex("^Удалить отзыв$"),
            start_delete_review,
        )
    )

    # --- Общий обработчик всех callback-кнопок ---
    # ВАЖНО: добавляем ПОСЛЕ ConversationHandler-ов, чтобы
    # они успевали ловить свои oneshot_drink_ / campaign_drink_
    application.add_handler(CallbackQueryHandler(button_callback))

    # --- Обработчик обычных сообщений (универсальный) ---
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, universal_message_handler), group=-1)

    # --- JobQueue для напоминаний ---
    job_queue = application.job_queue
    if job_queue is not None:
        job_queue.run_repeating(reminder_job, interval=1800, first=60)
    else:
        logger.warning("JobQueue не инициализирован, напоминания работать не будут")

    application.run_polling(allowed_updates=Update.ALL_TYPES)



if __name__ == "__main__":
    main()

