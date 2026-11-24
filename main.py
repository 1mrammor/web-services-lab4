import sqlite3
from typing import List, Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# ---------------------------------------------------------------
# Лаба 4, вариант 5: Рынок автомобилей
# Простой REST API: хранение в SQLite, документация Swagger сама
# появляется по адресу /docs
# ---------------------------------------------------------------

app = FastAPI(
    title="Рынок автомобилей",
    description="Лаба 4. CRUD + сортировка + статистика по авто",
)

DB_NAME = "cars.db"

# список колонок, по которым можно сортировать
# (id тоже сюда, чтоб сортировать можно было по ВСЕМ полям)
SORT_FIELDS = Literal["id", "brand", "model", "color", "year", "price", "mileage", "power"]

# числовые поля, по ним считаем среднее / мин / макс
NUM_FIELDS = ["year", "price", "mileage", "power"]


# ---------- работа с БД ----------

def get_conn():
    # новое подключение на каждый запрос, так проще всего
    conn = sqlite3.connect(DB_NAME)
    # чтобы строки можно было превращать в словари
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cars (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            brand   TEXT    NOT NULL,
            model   TEXT    NOT NULL,
            color   TEXT    NOT NULL,
            year    INTEGER NOT NULL,
            price   REAL    NOT NULL,
            mileage INTEGER NOT NULL,
            power   INTEGER NOT NULL
        )
        """
    )
    # если таблица пустая - накидаем пару машин для примера
    count = conn.execute("SELECT COUNT(*) FROM cars").fetchone()[0]
    if count == 0:
        test_data = [
            ("Toyota", "Camry", "black", 2018, 1900000, 85000, 181),
            ("BMW", "X5", "white", 2020, 5200000, 40000, 249),
            ("Lada", "Vesta", "silver", 2021, 1100000, 25000, 106),
            ("Kia", "Rio", "red", 2019, 950000, 70000, 123),
            ("Audi", "A6", "grey", 2017, 2300000, 110000, 190),
        ]
        conn.executemany(
            "INSERT INTO cars (brand, model, color, year, price, mileage, power) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            test_data,
        )
    conn.commit()
    conn.close()


# создаем таблицу при запуске приложения
init_db()


# ---------- модели данных (pydantic сам проверяет что пришло) ----------

class CarIn(BaseModel):
    """Что присылает клиент (без id, его даёт база)"""
    brand: str = Field(description="Марка", examples=["Toyota"])
    model: str = Field(description="Модель", examples=["Camry"])
    color: str = Field(description="Цвет", examples=["black"])
    year: int = Field(ge=1900, le=2100, description="Год выпуска", examples=[2018])
    price: float = Field(gt=0, description="Цена, руб", examples=[1900000])
    mileage: int = Field(ge=0, description="Пробег, км", examples=[85000])
    power: int = Field(gt=0, description="Мощность, л.с.", examples=[181])


class Car(CarIn):
    """То что отдаём клиенту (с id)"""
    id: int


# ---------- ручки API ----------

@app.get("/cars", response_model=List[Car], summary="Список авто с сортировкой")
def get_cars(sort_by: SORT_FIELDS = "id", order: Literal["asc", "desc"] = "asc"):
    # sort_by и order можно вставлять в SQL напрямую, потому что
    # Literal пропустит только значения из списка выше (защита от инъекций)
    conn = get_conn()
    rows = conn.execute(f"SELECT * FROM cars ORDER BY {sort_by} {order}").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ВАЖНО: /cars/stats должна быть выше чем /cars/{car_id},
# иначе слово "stats" fastapi попытается принять за id
@app.get("/cars/stats", summary="Среднее, мин и макс по числовым полям")
def get_stats():
    conn = get_conn()
    result = {}
    for field in NUM_FIELDS:
        row = conn.execute(
            f"SELECT AVG({field}), MIN({field}), MAX({field}) FROM cars"
        ).fetchone()
        result[field] = {"avg": row[0], "min": row[1], "max": row[2]}
    conn.close()
    return result


@app.get("/cars/{car_id}", response_model=Car, summary="Одна машина по id")
def get_car(car_id: int):
    conn = get_conn()
    row = conn.execute("SELECT * FROM cars WHERE id = ?", (car_id,)).fetchone()
    conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Машина не найдена")
    return dict(row)


@app.post("/cars", response_model=Car, status_code=201, summary="Добавить машину")
def add_car(car: CarIn):
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO cars (brand, model, color, year, price, mileage, power) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (car.brand, car.model, car.color, car.year, car.price, car.mileage, car.power),
    )
    conn.commit()
    new_id = cur.lastrowid  # id который выдала база
    conn.close()
    return {"id": new_id, **car.model_dump()}


@app.put("/cars/{car_id}", response_model=Car, summary="Обновить машину по id")
def update_car(car_id: int, car: CarIn):
    conn = get_conn()
    cur = conn.execute(
        "UPDATE cars SET brand=?, model=?, color=?, year=?, price=?, mileage=?, power=? "
        "WHERE id=?",
        (car.brand, car.model, car.color, car.year, car.price, car.mileage, car.power, car_id),
    )
    conn.commit()
    conn.close()
    # rowcount = сколько строк обновилось, 0 значит такого id нет
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Машина не найдена")
    return {"id": car_id, **car.model_dump()}


@app.delete("/cars/{car_id}", summary="Удалить машину по id")
def delete_car(car_id: int):
    conn = get_conn()
    cur = conn.execute("DELETE FROM cars WHERE id = ?", (car_id,))
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Машина не найдена")
    return {"status": "deleted", "id": car_id}
