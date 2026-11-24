from fastapi.testclient import TestClient

from main import app

# TestClient дергает приложение напрямую, сервер поднимать не надо
client = TestClient(app)


def test_list_and_sort():
    # проверяем сортировку: цены в ответе должны идти по убыванию
    r = client.get("/cars?sort_by=price&order=desc")
    assert r.status_code == 200
    prices = [c["price"] for c in r.json()]
    assert prices == sorted(prices, reverse=True)


def test_bad_sort_field():
    # сортировка по полю которого нет - должна быть ошибка валидации (422)
    assert client.get("/cars?sort_by=hack").status_code == 422


def test_stats():
    # статистика есть ровно по четырем числовым полям
    r = client.get("/cars/stats")
    assert r.status_code == 200
    assert set(r.json().keys()) == {"year", "price", "mileage", "power"}


def test_add_update_delete():
    # проходим весь путь машины: добавили -> поменяли цену -> удалили
    new_car = {"brand": "Ford", "model": "Focus", "color": "blue",
               "year": 2015, "price": 700000, "mileage": 120000, "power": 125}
    r = client.post("/cars", json=new_car)
    assert r.status_code == 201
    car_id = r.json()["id"]

    # обновляем цену и смотрим что она реально поменялась в базе
    new_car["price"] = 650000
    r = client.put(f"/cars/{car_id}", json=new_car)
    assert r.json()["price"] == 650000
    assert client.get(f"/cars/{car_id}").json()["price"] == 650000

    # удалили, после этого машины быть уже не должно (404)
    assert client.delete(f"/cars/{car_id}").status_code == 200
    assert client.get(f"/cars/{car_id}").status_code == 404


def test_not_found():
    # удаление и обновление несуществующего id возвращают 404
    assert client.delete("/cars/999999").status_code == 404
    assert client.put("/cars/999999", json={"brand": "a", "model": "b", "color": "c",
                                            "year": 2000, "price": 1, "mileage": 0,
                                            "power": 1}).status_code == 404
