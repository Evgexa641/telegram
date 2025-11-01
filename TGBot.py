import asyncio
from datetime import datetime
import logging
import os

from aiogram import Bot, Dispatcher, Router, types
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from aiohttp import web
from dotenv import load_dotenv
from flask import Flask, jsonify
import requests


# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Загружаем переменные из .env
load_dotenv()

# Читаем ключи из переменных окружения
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
API_KEY = os.getenv("API_KEY")

if not TELEGRAM_TOKEN:
    raise ValueError("Не найден TELEGRAM_TOKEN в переменных окружения (.env)")
if not API_KEY:
    raise ValueError("Не найден API_KEY в переменных окружения (.env)")

# Город по умолчанию
DEFAULT_CITY = "Saint Petersburg"

# Настройки вебхука
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://your-domain.com")
WEBHOOK_PATH = f"/webhook/{TELEGRAM_TOKEN}"
PORT = int(os.getenv("PORT", 5000))

# Инициализация бота и диспетчера
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

# Создаем Flask приложение
flask_app = Flask(__name__)


@flask_app.route("/health", methods=["GET"])
def health_check():
    """Хелсчек эндпоинт для мониторинга"""
    return jsonify(
        {
            "status": "healthy",
            "service": "telegram-weather-bot",
            "timestamp": datetime.now().isoformat(),
        }
    )


@flask_app.route("/", methods=["GET"])
def index():
    """Корневой эндпоинт"""
    return jsonify(
        {
            "message": "Telegram Weather Bot is running",
            "status": "active",
            "timestamp": datetime.now().isoformat(),
        }
    )


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


@router.message(commands=["start"])
async def start_command(message: types.Message) -> None:
    """Обработчик команды /start - показывает погоду в заданном городе"""
    user = message.from_user

    # Получаем данные о погоде
    weather_data = get_weather_data(DEFAULT_CITY)
    weather_message = format_weather_message(weather_data)

    welcome_text = (
        f"Привет, {user.first_name}! 👋\n"
        f"Я бот, который показывает актуальную погоду.\n\n"
    )

    await message.answer(welcome_text + weather_message, parse_mode="Markdown")


@router.message(commands=["help"])
async def help_command(message: types.Message) -> None:
    """Обработчик команды /help - показывает справку"""
    help_text = (
        "📖 **Справка по командам:**\n\n"
        "/start - Показать погоду в Санкт-Петербурге\n"
        "/help - Показать эту справку\n"
        "/weather - Показать текущую погоду\n\n"
        "ℹ️ Бот автоматически показывает актуальную погоду "
        "для заранее заданного города."
    )
    await message.answer(help_text, parse_mode="Markdown")


@router.message(commands=["weather"])
async def weather_command(message: types.Message) -> None:
    """Дополнительная команда для быстрого доступа к погоде"""
    weather_data = get_weather_data(DEFAULT_CITY)
    weather_message = format_weather_message(weather_data)
    await message.answer(weather_message, parse_mode="Markdown")


async def on_startup(bot: Bot) -> None:
    """Действия при запуске бота"""
    await bot.set_webhook(f"{WEBHOOK_URL}{WEBHOOK_PATH}")
    logger.info(f"Webhook установлен: {WEBHOOK_URL}{WEBHOOK_PATH}")


async def on_shutdown(bot: Bot) -> None:
    """Действия при остановке бота"""
    await bot.delete_webhook()
    logger.info("Webhook удален")


async def aiohttp_app():
    """Создание aiohttp приложения для вебхуков"""
    app = web.Application()

    # Регистрируем обработчик вебхуков
    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=TELEGRAM_TOKEN,
    )

    webhook_requests_handler.register(app, path=WEBHOOK_PATH)

    # Настраиваем startup/shutdown обработчики
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    return app


def run_flask():
    """Запускает Flask приложение"""
    logger.info(f"Запуск Flask сервера на порту {PORT}")
    flask_app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)


async def main():
    """Основная функция запуска бота"""
    try:
        # Настраиваем диспетчер
        dp.startup.register(on_startup)
        dp.shutdown.register(on_shutdown)

        # Создаем aiohttp приложение для вебхуков
        app = await aiohttp_app()

        # Запускаем Flask в отдельном потоке
        import threading

        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()

        # Запускаем aiohttp сервер
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", PORT)
        await site.start()

        logger.info(f"Бот запущен на порту {PORT}")

        # Бесконечный цикл
        await asyncio.Future()

    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")


if __name__ == "__main__":
    asyncio.run(main())
