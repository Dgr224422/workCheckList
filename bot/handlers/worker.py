from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.handlers.states import WorkerStates


router = Router()


@router.message(F.text == "📝 Выполнить чек-лист")
async def start_submission(message: Message, state: FSMContext) -> None:
    db = message.bot["db"]
    checklists = await db.list_checklists()
    if not checklists:
        await message.answer("Чек-листов пока нет. Обратитесь к администратору.")
        return

    await state.set_state(WorkerStates.choosing_checklist)
    options = "\n".join(f"{c.id}. {c.title}" for c in checklists)
    await message.answer(f"Выберите ID чек-листа:\n{options}")


@router.message(WorkerStates.choosing_checklist)
async def choose_checklist(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer("Отправьте числовой ID чек-листа.")
        return

    checklist_id = int(text)
    db = message.bot["db"]
    checklists = await db.list_checklists()
    checklist_map = {c.id: c for c in checklists}
    if checklist_id not in checklist_map:
        await message.answer("Чек-лист не найден.")
        return

    items = await db.get_checklist_items(checklist_id)
    if not items:
        await message.answer("В этом чек-листе нет пунктов. Обратитесь к администратору.")
        await state.clear()
        return

    submission_id = await db.create_submission(message.from_user.id, checklist_id)
    await state.update_data(
        checklist_id=checklist_id,
        checklist_title=checklist_map[checklist_id].title,
        items=[{"id": i.id, "text": i.text} for i in items],
        index=0,
        submission_id=submission_id,
        answers=[],
    )
    await state.set_state(WorkerStates.answering_item)
    await message.answer(
        f"Старт отчета по чек-листу: {checklist_map[checklist_id].title}\n"
        f"Пункт 1/{len(items)}: {items[0].text}\n"
        "Ответьте: да/нет"
    )


@router.message(WorkerStates.answering_item)
async def answer_item(message: Message, state: FSMContext) -> None:
    answer = (message.text or "").strip().lower()
    if answer not in {"да", "нет"}:
        await message.answer("Пожалуйста, ответьте только: да или нет.")
        return

    data = await state.get_data()
    idx = data["index"]
    items = data["items"]
    answers = data["answers"]
    answers.append({"item_id": items[idx]["id"], "done": answer == "да", "comment": ""})
    await state.update_data(answers=answers)

    if answer == "нет":
        await state.set_state(WorkerStates.answering_comment)
        await message.answer("Укажите комментарий, почему пункт не выполнен:")
        return

    await _next_item_or_finish(message, state)


@router.message(WorkerStates.answering_comment)
async def answer_comment(message: Message, state: FSMContext) -> None:
    comment = (message.text or "").strip()
    if not comment:
        await message.answer("Комментарий не может быть пустым.")
        return

    data = await state.get_data()
    answers = data["answers"]
    answers[-1]["comment"] = comment
    await state.update_data(answers=answers)
    await _next_item_or_finish(message, state)


async def _next_item_or_finish(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    idx = data["index"] + 1
    items = data["items"]

    if idx >= len(items):
        db = message.bot["db"]
        submission_id = data["submission_id"]
        for answer in data["answers"]:
            await db.add_submission_item(
                submission_id=submission_id,
                item_id=answer["item_id"],
                done=answer["done"],
                comment=answer["comment"],
            )

        done_count = sum(1 for ans in data["answers"] if ans["done"])
        await state.clear()
        await message.answer(
            f"Отчет #{submission_id} сохранен. Выполнено пунктов: {done_count}/{len(items)}"
        )
        return

    await state.set_state(WorkerStates.answering_item)
    await state.update_data(index=idx)
    await message.answer(f"Пункт {idx + 1}/{len(items)}: {items[idx]['text']}\nОтветьте: да/нет")


@router.message(F.text == "📊 Мои отчеты")
async def my_reports(message: Message) -> None:
    db = message.bot["db"]
    submissions = await db.get_user_submissions(message.from_user.id)
    if not submissions:
        await message.answer("У вас пока нет отчетов.")
        return

    lines = ["Ваши последние отчеты:"]
    for sub in submissions[:15]:
        lines.append(f"#{sub.id} | чек-лист {sub.checklist_id} | {sub.created_at}")
    await message.answer("\n".join(lines))
