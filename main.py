import asyncio
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ChatAction
import requests
from config import TELEGRAM_BOT_TOKEN, DADATA_API_KEY

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

DADATA_URL = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/findById/party"
headers = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Authorization": f"Token {DADATA_API_KEY}"
}


def validate_input(query: str) -> bool:
    """Проверяет, что ввод соответствует формату ИНН или ОГРН"""
    return query.isdigit() and len(query) in (10, 12, 13)


async def get_organization_info(query: str) -> str:
    try:
        response = requests.post(
            DADATA_URL,
            json={"query": query},
            headers=headers,
            timeout=5
        )
        response.raise_for_status()

        result = response.json()
        if not result.get("suggestions"):
            return "❌ Организация не найдена. Проверьте правильность ИНН/ОГРН."

        suggestion = result["suggestions"][0]
        org_data = suggestion.get("data", {})

        # Безопасное извлечение данных
        name = org_data.get("name", {}).get("short_with_opf", "Не указано")
        inn = org_data.get("inn", "Не указан")
        ogrn = org_data.get("ogrn", "Не указан")
        address = org_data.get("address", {}).get("value", "Не указан")
        kpp = org_data.get("kpp", "Не указан")

        info = [
            f"🏢 *{name}*",
            f"📋 *ИНН:* {inn}",
            f"📄 *ОГРН:* {ogrn}",
            f"📍 *Адрес:* {address}",
            f"🔢 *КПП:* {kpp}",
        ]

        # Уставной капитал
        if "capital" in org_data and org_data["capital"] is not None:
            capital = org_data["capital"]
            info.append(f"💰 *Уставной капитал:* {capital.get('value', 'Не указан')} {capital.get('type', '')}")

        # Руководитель
        if "management" in org_data and org_data["management"] is not None:
            management = org_data["management"]
            info.append(
                f"👔 *Руководитель:* {management.get('name', 'Не указан')} ({management.get('post', 'Не указана')})")

        # Виды деятельности (с защитой от None)
        okveds = org_data.get("okveds") or []
        if okveds:
            main_okved = next((item for item in okveds if item and item.get("main")), None)
            if main_okved:
                info.append(f"🏭 *Основной вид деятельности:* {main_okved.get('name', 'Не указан')}")

        # Метро (с защитой от None)
        metro = (org_data.get("address", {}).get("data", {}).get("metro") or [])
        if metro:
            metro_info = ["🚇 *Ближайшее метро:*"]
            for station in metro[:3]:
                if station:
                    metro_info.append(
                        f"- {station.get('name', 'Неизвестно')} "
                        f"({station.get('line', 'Неизвестно')}, "
                        f"{station.get('distance', '?')} км)"
                    )
            info.append("\n".join(metro_info))

        return "\n".join(info)

    except requests.exceptions.RequestException as e:
        return f"⚠️ Ошибка при запросе к API: {str(e)}"
    except Exception as e:
        return f"⚠️ Неожиданная ошибка при обработке данных: {str(e)}"


@dp.message(Command("start"))
async def start_command(message: Message):
    await message.answer(
        "👋 Привет! Я помогу найти информацию об организации по ИНН или ОГРН.\n\n"
        "Просто отправь мне ИНН (10 или 12 цифр) или ОГРН (13 цифр).\n\n"
        "Примеры:\n"
        "- ИНН: 7710137066\n"
        "- ОГРН: 1027700132195"
    )


@dp.message(lambda message: validate_input(message.text))
async def handle_inn_or_ogrn(message: Message):
    await bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)
    info = await get_organization_info(message.text)
    await message.answer(info, parse_mode="Markdown")


@dp.message()
async def handle_invalid_input(message: Message):
    await message.answer(
        "❌ Пожалуйста, введите корректный ИНН (10 или 12 цифр) или ОГРН (13 цифр).\n\n"
        "Примеры:\n"
        "- ИНН: 7710137066\n"
        "- ОГРН: 1027700132195"
    )


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())