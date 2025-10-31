from datetime import datetime
import logging
import os

from dotenv import load_dotenv
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes


# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Загружаем переменные из .env
load_dotenv()

# Читаем ключи из переменных окружения
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
API_KEY = os.getenv("API_KEY")  # Исправлено: убрал хардкодный ключ

if not TELEGRAM_TOKEN:
    raise ValueError("Не найден TELEGRAM_TOKEN в переменных окружения (.env)")
if not API_KEY:
    raise ValueError("Не найден API_KEY в переменных окружения (.env)")

# Город по умолчанию
DEFAULT_CITY = "Saint Petersburg"


def get_weather_data(city=DEFAULT_CITY):
    """Получает данные о погоде для указанного города"""
    params = {
        "q": city,
        "appid": API_KEY,
        "units": "metric",
        "lang": "ru",
    }

    try:
        r = requests.get(
            "https://api.openweathermap.org/data/2.5/weather", params=params
        )
        r.raise_for_status()  # проверяем ошибки HTTP
        data = r.json()
        return data
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при запросе к API погоды: {e}")
        return None
    except Exception as e:
        logger.error(f"Ошибка при обработке данных: {e}")
        return None


def format_weather_message(data):
    """Форматирует данные о погоде в читаемое сообщение"""
    if not data:
        return "❌ Не удалось получить данные о погоде. Попробуйте позже."

    try:
        city_name = data["name"]
        weather_desc = data["weather"][0]["description"].capitalize()
        temp = data["main"]["temp"]
        humidity = data["main"]["humidity"]
        pressure = data["main"].get("grnd_level", data["main"]["pressure"])
        wind_speed = data["wind"]["speed"]

        sunset_timestamp = data["sys"]["sunset"]
        sunset_time = datetime.fromtimestamp(sunset_timestamp).strftime("%H:%M:%S")

        message = (
            f"🌤 **Погода в {city_name}**\n\n"
            f"📝 **Описание:** {weather_desc}\n"
            f"🌡 **Температура:** {temp} °C\n"
            f"💧 **Влажность:** {humidity}%\n"
            f"📊 **Давление:** {pressure} гПа\n"
            f"💨 **Скорость ветра:** {wind_speed} м/с\n"
            f"🌅 **Закат:** {sunset_time}\n\n"
            f"🔄 Обновлено: {datetime.now().strftime('%H:%M:%S')}"
        )
        return message
    except KeyError as e:
        logger.error(f"Ошибка в структуре данных погоды: {e}")
        return "❌ Ошибка при обработке данных о погоде."


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start - показывает погоду в заданном городе"""
    user = update.effective_user

    # Получаем данные о погоде
    weather_data = get_weather_data(DEFAULT_CITY)
    weather_message = format_weather_message(weather_data)

    welcome_text = (
        f"Привет, {user.first_name}! 👋\n"
        f"Я бот, который показывает актуальную погоду.\n\n"
    )

    await update.message.reply_text(
        welcome_text + weather_message, parse_mode="Markdown"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /help - показывает справку"""
    help_text = (
        "📖 **Справка по командам:**\n\n"
        "/start - Показать погоду в Санкт-Петербурге\n"
        "/help - Показать эту справку\n"
        "/weather - Показать текущую погоду\n\n"
        "ℹ️ Бот автоматически показывает актуальную погоду "
        "для заранее заданного города."
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Дополнительная команда для быстрого доступа к погоде"""
    weather_data = get_weather_data(DEFAULT_CITY)
    weather_message = format_weather_message(weather_data)
    await update.message.reply_text(weather_message, parse_mode="Markdown")


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик ошибок"""
    logger.error(f"Ошибка при обработке update {update}: {context.error}")


def main():
    """Основная функция запуска бота"""
    try:
        # Создаем Application
        application = Application.builder().token(TELEGRAM_TOKEN).build()

        # Добавляем обработчики команд
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("weather", weather_command))

        # Добавляем обработчик ошибок
        application.add_error_handler(error_handler)

        # Запускаем бота
        print("Бот погоды запущен...")
        application.run_polling()

    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")


if __name__ == "__main__":
    main()
