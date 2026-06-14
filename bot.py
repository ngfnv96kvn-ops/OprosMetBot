#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import smtplib
import logging
from email.message import EmailMessage
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from config import BOT_TOKEN, YOUR_TELEGRAM_ID, EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECEIVER, SMTP_SERVER, SMTP_PORT

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

def condition_always(selected):
    return True

def condition_carcass_angar_other(selected):
    return any(t in selected for t in ['каркас здания', 'ангар', 'другое'])

def condition_fence(selected):
    return 'забор' in selected

def condition_canopy(selected):
    return 'навес' in selected

def condition_fence_gate_canopy(selected):
    return any(t in selected for t in ['забор', 'откатные ворота', 'распашные ворота', 'навес'])

def condition_sliding_gate(selected):
    return 'откатные ворота' in selected

def condition_swing_gate(selected):
    return 'распашные ворота' in selected

def condition_any_gate(selected):
    return ('откатные ворота' in selected) or ('распашные ворота' in selected)

def condition_heated(selected):
    return any(t in selected for t in ['каркас здания', 'ангар', 'другое'])

def condition_enclosure(selected):
    return any(t in selected for t in ['каркас здания', 'ангар', 'другое'])

def condition_gate_auto(selected):
    return any(t in selected for t in ['навес', 'откатные ворота', 'распашные ворота'])

def get_number_emoji(num):
    digit_emojis = {
        '0': '0️⃣', '1': '1️⃣', '2': '2️⃣', '3': '3️⃣', '4': '4️⃣',
        '5': '5️⃣', '6': '6️⃣', '7': '7️⃣', '8': '8️⃣', '9': '9️⃣'
    }
    digits = str(num)
    return ''.join(digit_emojis[d] for d in digits)

QUESTIONS_DATA = [
    ("Конфигурация:\n\n▪️ Прямоугольная в плане\n▪️ П-образная / Г-образная\n▪️ Арочная / радиусная\n▪️ Другая", 'single', condition_always),
    ("Укажите основные размеры (в метрах, приблизительно):\n\n▪️ Длина: _____ м\n▪️ Ширина (пролёт): _____ м\n▪️ Высота до низа конструкции / полезная высота: _____ м\n▪️ Высота в коньке (для скатных/арочных): _____ м", 'free', condition_carcass_angar_other),
    ("Общая длина ограждения (м):", 'free', condition_fence),
    ("Высота забора (м):", 'free', condition_fence),
    ("Расположение навеса:\n\n▪️ Примыкает к существующему зданию\n▪️ Отдельно стоящий", 'single', condition_canopy),
    ("Требуется ли защита от бокового ветра/осадков (стеновое ограждение)?\n\n▪️ да\n▪️ нет", 'single', condition_canopy),
    ("Тип кровли:\n\n▪️ Односкатная\n▪️ Двускатная\n▪️ Арочная\n▪️ Плоская", 'single', condition_carcass_angar_other),
    ("Тип заполнения:\n\n▪️ Профлист\n▪️ 3D-панели\n▪️ Кованые секции\n▪️ Сетка-рабица\n▪️ Штакетник\n▪️ Другое", 'multi', condition_fence_gate_canopy),
    ("Количество ворот откатных (ширина проёма: ___ м):", 'free', condition_sliding_gate),
    ("Количество ворот распашных (ширина проёма: ___ м):", 'free', condition_swing_gate),
    ("Количество калиток:", 'free', condition_any_gate),
    ("Будет ли внутри помещения поддерживаться постоянная температура (отапливаемое здание)?\n\n▪️ Да, постоянно отапливается (выше +10°C)\n▪️ Нет, неотапливаемое (холодный склад)\n▪️ Периодическое отопление (до +5°C, чтобы не было снега)", 'single', condition_heated),
    ("Есть ли агрессивная среда или особые условия?\n\n▪️ Повышенная влажность / бассейн\n▪️ Обычные условия, без агрессии", 'single', condition_always),
    ("Нужно ли учесть нагрузку от подвесного оборудования, коммуникаций?\n\n▪️ Подвесные пути, тельферы\n▪️ Потолочные обогреватели, вентканалы\n▪️ Ничего подвешиваться не будет", 'single', condition_always),
    ("Есть ли данные по грунтам или существующий фундамент?\n\n▪️ Будет отдельный проект фундаментов (учитываем только опорные реакции)\n▪️ Фундамент уже существует (нужна обвязка под стальные колонны, предоставим размеры)\n▪️ Нужен проект фундаментов в составе работ (укажите тип: столбчатый, плита, сваи)", 'single', condition_always),
    ("Тип крепления колонн/стоек к основанию:\n\n▪️ Анкерные болты в бетон (стандарт)\n▪️ Приварка к закладным деталям существующего фундамента\n▪️ Съёмное соединение (для временных конструкций)\n▪️ Стойки бетонируются в грунт (для заборов/навесов)", 'single', condition_always),
    ("Материал несущих конструкций (выбрать основной):\n\n▪️ Чёрный металл (сталь) с последующей окраской\n▪️ Оцинкованная сталь (без покраски)\n▪️ Нержавеющая сталь (для агрессивных сред или эстетики)\n▪️ Алюминиевые сплавы (лёгкие навесы, ограждения)\n▪️ Комбинированные", 'single', condition_always),
    ("Способ защиты от коррозии (если не оцинковка/нержавейка):\n\n▪️ Грунтовка ГФ-021 / аналог + эмаль (климатическое исполнение УХЛ)\n▪️ Горячее цинкование (на заводе) — самый долгий срок\n▪️ Огнезащитное покрытие (вспучивающаяся краска)", 'single', condition_always),
    ("Ограждающие конструкции (стены и кровля):\n\n▪️ Только металлокаркас, обшивку не проектируем\n▪️ Сэндвич-панели (кровельные и стеновые) — укажите толщину утеплителя: ___ мм\n▪️ Профлист (оцинкованный / окрашенный)\n▪️ Мягкая кровля по профлисту\n▪️ Деревянный/бетонный настил\n▪️ Другое", 'single', condition_enclosure),
    ("Размеры ворот (ширина × высота):", 'free', condition_enclosure),
    ("Нужны ли калитки, двери (количество и размеры):", 'free', condition_enclosure),
    ("Требуется ли светопрозрачное заполнение (зенитные фонари, ленты остекления):", 'free', condition_enclosure),
    ("Нужны ли погрузочные доки, пандусы?", 'free', condition_enclosure),
    ("Требуется ли организованный водосток (желоба, трубы) или свободный сброс воды?", 'free', condition_canopy),
    ("Нужен ли потолочный подшив (софиты) или каркас остаётся открытым?", 'free', condition_canopy),
    ("Тип открывания ворот:\n\n▪️ Автоматический привод (220В/380В)\n▪️ Ручной", 'single', condition_gate_auto),
    ("Нужны ли:\n\n▪️ Фотоэлементы\n▪️ Сигнальная лампа\n▪️ Радиоприёмник\n▪️ Не нужны", 'multi', condition_gate_auto),
    ("Устройство калитки:\n\n▪️ Встроенная в створку ворот\n▪️ Отдельно", 'single', condition_gate_auto),
    ("Требуется ли антивандальное исполнение:\n\n▪️ Усиленные петли\n▪️ Скрытый крепёж\n▪️ Не требуется", 'single', condition_gate_auto),
    ("Какая стадия проектирования требуется?\n\n▪️ Эскизный расчёт (для оценки металла и бюджета)\n▪️ Проект КМ (конструкции металлические) — для согласований\n▪️ Деталировочные чертежи КМД — для завода-изготовителя\n▪️ Полный комплект: КМ + КМД", 'single', condition_always),
    ("Ориентировочный бюджет на металлоконструкции (без монтажа):\n\n▪️ до 1 млн ₽\n▪️ 1 – 5 млн ₽\n▪️ 5 – 15 млн ₽\n▪️ свыше 15 млн ₽\n▪️ Сначала нужен расчёт, бюджет открытый", 'single', condition_always),
    ("Сроки:\n\n▪️ Желаемая дата начала проектирования: _______\n▪️ Планируемая дата начала монтажа: _______", 'free', condition_always),
    ("Предоставляете ли вы исходные данные? (можно выбрать несколько)\n\n▪️ Топографическая съёмка / генплан\n▪️ Геология (отчёт об изысканиях)\n▪️ Архитектурные чертежи / планы этажей\n▪️ Схема расстановки оборудования\n▪️ Ничего нет", 'multi', condition_always),
    ("Контактная информация:\n\n▪️ Город:\n▪️ Имя:\n▪️ Телефон:\n▪️ Телеграмм:\n▪️ Email:", 'free', condition_always),
]

def make_single_keyboard(options_text):
    lines = options_text.strip().split('\n')
    options = []
    for line in lines:
        line = line.strip()
        if line and (line.startswith('▪️') or line.startswith('-') or (line and line[0].isdigit())):
            clean = line.lstrip('▪️- ').strip()
            if clean:
                options.append(clean)
    if not options:
        options = [l.strip() for l in lines if l.strip()]
    keyboard = [options[i:i+2] for i in range(0, len(options), 2)]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

def extract_options(question_text):
    lines = question_text.split('\n')
    opts = []
    for line in lines:
        line = line.strip()
        if line.startswith('▪️'):
            opts.append(line[2:].strip())
    return opts

async def send_email_report(user_data):
    text = "📋 Анкета по металлоконструкциям\n\n"
    if 'selected_types' in user_data:
        text += f"Тип конструкции: {', '.join(user_data['selected_types'])}\n\n"
    for q_num, answer in user_data.items():
        if q_num == 'selected_types':
            continue
        if isinstance(q_num, int):
            idx = q_num - 2
            if 0 <= idx < len(QUESTIONS_DATA):
                q_text = QUESTIONS_DATA[idx][0]
                short_q = q_text.split('\n')[0][:80]
                text += f"{short_q}: {answer}\n\n"
    msg = EmailMessage()
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECEIVER
    msg["Subject"] = "Новая анкета металлоконструкций"
    msg.set_content(text)
    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)
        logging.info("Письмо отправлено")
    except Exception as e:
        logging.error(f"Ошибка почты: {e}")

async def send_telegram_copy(update, context, user_data):
    report_lines = ["✅ Ваши ответы на анкету:"]
    if 'selected_types' in user_data:
        report_lines.append(f"Тип конструкции: {', '.join(user_data['selected_types'])}")
    for q_num, answer in user_data.items():
        if q_num == 'selected_types':
            continue
        if isinstance(q_num, int):
            idx = q_num - 2
            if 0 <= idx < len(QUESTIONS_DATA):
                q_text = QUESTIONS_DATA[idx][0]
                header = q_text.split('\n')[0][:60]
                report_lines.append(f"{header}: {answer}")
    report = "\n\n".join(report_lines)
    chat_id = update.effective_chat.id
    await context.bot.send_message(chat_id=chat_id, text=report)
    if YOUR_TELEGRAM_ID:
        await context.bot.send_message(
            chat_id=YOUR_TELEGRAM_ID,
            text=f"📬 Новая анкета от @{update.effective_user.username or 'Пользователь'}\n\n{report}"
        )

async def show_multi_question(update, context, q_index, q_text, options):
    step = context.user_data.get('current_q_index')
    if 'multi_selected' not in context.user_data:
        context.user_data['multi_selected'] = {}
    if step not in context.user_data['multi_selected']:
        context.user_data['multi_selected'][step] = [False] * len(options)
    selected = context.user_data['multi_selected'][step]
    keyboard = []
    for i, opt in enumerate(options):
        status = "✅" if selected[i] else "⬜"
        keyboard.append([InlineKeyboardButton(f"{status} {opt}", callback_data=f"multi_{q_index}_{i}")])
    keyboard.append([InlineKeyboardButton("✅ Готово", callback_data=f"multi_done_{q_index}")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    chat_id = update.effective_chat.id
    await context.bot.send_message(chat_id=chat_id, text=q_text, reply_markup=reply_markup)

async def start(update, context):
    await update.message.reply_text("Добро пожаловать! Я бот для сбора данных по металлоконструкциям.\nДля отмены /cancel")
    context.user_data.clear()
    text = "1️⃣ Какой тип металлоконструкции вам нужен? (можно выбрать несколько)\n\n▪️ Каркас здания\n▪️ Ангар\n▪️ Навес / козырёк\n▪️ Забор\n▪️ Откатные ворота\n▪️ Распашные ворота\n▪️ Лестницы, площадки, эстакады\n▪️ Другое"
    options = ["Каркас здания", "Ангар", "Навес / козырёк", "Забор", "Откатные ворота", "Распашные ворота", "Лестницы, площадки, эстакады", "Другое"]
    keyboard = []
    for idx, opt in enumerate(options):
        keyboard.append([InlineKeyboardButton(f"⬜ {opt}", callback_data=f"type_{idx}_{opt}")])
    keyboard.append([InlineKeyboardButton("✅ Готово", callback_data="type_done")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, reply_markup=reply_markup)

async def type_callback(update, context):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "type_done":
        selected = context.user_data.get('temp_selected', [])
        if not selected:
            await query.edit_message_text("Вы не выбрали ни одного варианта. Пожалуйста, выберите хотя бы один.")
            return
        context.user_data['selected_types'] = selected
        await query.edit_message_text(f"Выбрано: {', '.join(selected)}")
        context.user_data['current_q_index'] = 0
        context.user_data['asked_count'] = 2
        await ask_next_question(update, context)
        return
    elif data.startswith("type_"):
        parts = data.split("_")
        idx = int(parts[1])
        opt = parts[2]
        if 'temp_selected' not in context.user_data:
            context.user_data['temp_selected'] = []
        if opt in context.user_data['temp_selected']:
            context.user_data['temp_selected'].remove(opt)
        else:
            context.user_data['temp_selected'].append(opt)
        options = ["Каркас здания", "Ангар", "Навес / козырёк", "Забор", "Откатные ворота", "Распашные ворота", "Лестницы, площадки, эстакады", "Другое"]
        keyboard = []
        for idx2, opt2 in enumerate(options):
            if opt2 in context.user_data['temp_selected']:
                status = "✅"
            else:
                status = "⬜"
            keyboard.append([InlineKeyboardButton(f"{status} {opt2}", callback_data=f"type_{idx2}_{opt2}")])
        keyboard.append([InlineKeyboardButton("✅ Готово", callback_data="type_done")])
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))

async def ask_next_question(update, context):
    selected_types = context.user_data.get('selected_types', [])
    current_idx = context.user_data.get('current_q_index', 0)
    while current_idx < len(QUESTIONS_DATA):
        q_text, q_type, condition = QUESTIONS_DATA[current_idx]
        if condition(selected_types):
            context.user_data['current_q_index'] = current_idx
            current_number = context.user_data.get('asked_count', 2)
            context.user_data['asked_count'] = current_number + 1
            number_prefix = get_number_emoji(current_number)
            display_text = f"{number_prefix} " + q_text
            if q_type == 'single':
                parts = display_text.split('\n\n', 1)
                options_part = parts[1] if len(parts) > 1 else display_text
                reply_markup = make_single_keyboard(options_part)
                await context.bot.send_message(chat_id=update.effective_chat.id, text=display_text, reply_markup=reply_markup)
            elif q_type == 'multi':
                await context.bot.send_message(chat_id=update.effective_chat.id, text="(Выберите несколько вариантов, затем нажмите 'Готово')")
                options = extract_options(q_text)
                await show_multi_question(update, context, current_idx, display_text, options)
            else:
                await context.bot.send_message(chat_id=update.effective_chat.id, text=display_text + "\n(Введите ваш ответ текстом)", reply_markup=ReplyKeyboardRemove())
            return
        current_idx += 1
    await finish_survey(update, context)

async def handle_message(update, context):
    q_index = context.user_data.get('current_q_index')
    if q_index is None:
        await update.message.reply_text("Начните с /start")
        return
    q_text, q_type, _ = QUESTIONS_DATA[q_index]
    if q_type == 'multi':
        await update.message.reply_text("Пожалуйста, используйте кнопки для выбора вариантов и нажмите 'Готово'.")
        return
    shown_number = context.user_data.get('asked_count', 2) - 1
    context.user_data[shown_number] = update.message.text
    next_idx = q_index + 1
    context.user_data['current_q_index'] = next_idx
    await ask_next_question(update, context)

async def handle_multi_callback(update, context):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data.startswith("multi_done_"):
        parts = data.split("_")
        q_index = int(parts[2])
        step = context.user_data.get('current_q_index')
        if step != q_index:
            return
        q_text, q_type, _ = QUESTIONS_DATA[q_index]
        options = extract_options(q_text)
        selected = context.user_data.get('multi_selected', {}).get(step, [])
        answer = ", ".join([opt for i, opt in enumerate(options) if i < len(selected) and selected[i]]) if any(selected) else "Ничего не выбрано"
        shown_number = context.user_data.get('asked_count', 2) - 1
        context.user_data[shown_number] = answer
        await query.edit_message_reply_markup(reply_markup=None)
        await context.bot.send_message(chat_id=update.effective_chat.id, text="✅ Ответ сохранён!")
        context.user_data.pop('multi_selected', None)
        next_idx = q_index + 1
        context.user_data['current_q_index'] = next_idx
        await ask_next_question(update, context)
        return
    elif data.startswith("multi_"):
        parts = data.split("_")
        q_index = int(parts[1])
        idx_option = int(parts[2])
        step = context.user_data.get('current_q_index')
        if step != q_index:
            return
        q_text, q_type, _ = QUESTIONS_DATA[q_index]
        options = extract_options(q_text)
        if 'multi_selected' not in context.user_data:
            context.user_data['multi_selected'] = {}
        if step not in context.user_data['multi_selected']:
            context.user_data['multi_selected'][step] = [False] * len(options)
        context.user_data['multi_selected'][step][idx_option] = not context.user_data['multi_selected'][step][idx_option]
        selected = context.user_data['multi_selected'][step]
        keyboard = []
        for i, opt in enumerate(options):
            status = "✅" if selected[i] else "⬜"
            keyboard.append([InlineKeyboardButton(f"{status} {opt}", callback_data=f"multi_{q_index}_{i}")])
        keyboard.append([InlineKeyboardButton("✅ Готово", callback_data=f"multi_done_{q_index}")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_reply_markup(reply_markup=reply_markup)
        return

async def finish_survey(update, context):
    user_data = {k: v for k, v in context.user_data.items() if isinstance(k, int)}
    user_data['selected_types'] = context.user_data.get('selected_types', [])
    await send_email_report(user_data)
    await send_telegram_copy(update, context, user_data)
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="🎉 Спасибо! Анкета успешно отправлена.\nМы свяжемся с вами.",
        reply_markup=ReplyKeyboardRemove()
    )
    context.user_data.clear()

async def cancel(update, context):
    await update.message.reply_text("❌ Опрос отменён.", reply_markup=ReplyKeyboardRemove())
    context.user_data.clear()

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('cancel', cancel))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(type_callback, pattern="^type_"))
    application.add_handler(CallbackQueryHandler(handle_multi_callback, pattern="^multi_"))
    print("✅ Бот для металлоконструкций запускается...")
    application.run_polling(poll_interval=1.0, timeout=30)

if __name__ == "__main__":
    main()
