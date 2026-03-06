# workCheckList

Telegram-бот на **aiogram 3** для кинотеатра с раздельными БД по функциональным модулям.

## Что реализовано

- Раздельные БД:
  - `users.db` — роли пользователей.
  - `certificates.db` — сертификаты.
  - `popcorn.db` — отчёты попкорна.
  - `classes.db` — рейтинг классов.
  - `checklists.db` — чек-листы и напоминания.
  - `schedule.db` — график смен.
  - `posters.db` — учёт постеров (добавить/найти/повесить/удалить/снять).

- Раздел `Постеры`:
  - отдельная БД и хранение фото;
  - поиск по коду/названию/дате;
  - распознавание штрихкода по фото;
  - подсказки по частичному вводу (топ-5);
  - напоминания за 4 и 2 дня до выхода в 14:00 по МСК;
  - soft delete с архивом 365 дней и уведомлением system admin.

## Быстрый запуск (локально)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m app.main
```

`.env`:

```env
BOT_TOKEN=...
SYSTEM_ADMIN_ID=123456789
ADMIN_IDS=111,222
CLEANUP_DAYS=45
```

## Запуск на Raspberry Pi 4

Подробная инструкция: [deploy/raspberrypi/README.md](/Users/arsen/PycharmProjects/workCheckList/deploy/raspberrypi/README.md)

Коротко:

```bash
bash deploy/raspberrypi/setup_pi.sh
nano .env
bash deploy/raspberrypi/install_service.sh
```

Сервис:

```bash
sudo systemctl status workchecklist-bot.service
sudo journalctl -u workchecklist-bot.service -f
```

## Полезные пути

- Скрипт запуска: `scripts/run_bot.sh`
- Unit-шаблон: `deploy/systemd/workchecklist-bot.service`
- Логи: `logs/bot.log`

## Безопасность

- Параметризованные SQL-запросы.
- Роли: `system_admin/admin/worker/guest`.
- Разделение прав по Telegram ID.
- Валидация ключевых полей (дата, телефон, числовые значения).
