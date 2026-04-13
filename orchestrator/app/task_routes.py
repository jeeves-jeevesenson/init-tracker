from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from .db import get_session
from .programs import get_program_with_slices, list_programs, program_to_dict
from .tasks import get_task_with_latest_run, list_tasks, task_to_dict

router = APIRouter(tags=["tasks"])


@router.get("/tasks")
def get_tasks(
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
):
    tasks = list_tasks(session, limit=limit)
    payload = []
    for task in tasks:
        resolved_task, latest_run = get_task_with_latest_run(session, task.id or 0)
        if resolved_task is None:
            continue
        payload.append(task_to_dict(resolved_task, latest_run))
    return {"ok": True, "count": len(payload), "tasks": payload}


@router.get("/tasks/{task_id}")
def get_task(task_id: int, session: Session = Depends(get_session)):
    task, latest_run = get_task_with_latest_run(session, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    return {"ok": True, "task": task_to_dict(task, latest_run)}


@router.get("/programs")
def get_programs(
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
):
    programs = list_programs(session, limit=limit)
    payload = []
    for program in programs:
        resolved, slices = get_program_with_slices(session, program.id or 0)
        if resolved is None:
            continue
        payload.append(program_to_dict(resolved, slices))
    return {"ok": True, "count": len(payload), "programs": payload}


@router.get("/programs/{program_id}")
def get_program(program_id: int, session: Session = Depends(get_session)):
    program, slices = get_program_with_slices(session, program_id)
    if program is None:
        raise HTTPException(status_code=404, detail="program not found")
    return {"ok": True, "program": program_to_dict(program, slices)}
