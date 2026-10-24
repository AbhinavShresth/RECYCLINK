from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.core.security import hash_password
from app.main import app
from app.models.identity import User, UserProfile, UserRole


def csrf(client):
    return {"X-CSRF-Token": client.cookies["csrf_token"]}


def login_admin(client, email="bin-admin@example.test"):
    override = app.dependency_overrides[get_db]
    generator = override()
    db: Session = next(generator)
    user = User(email=email, password_hash=hash_password("recyclink-admin-test-password"))
    user.profile = UserProfile(full_name="Bin Administrator", preferred_language="en")
    user.roles = [UserRole(role_code="ADMIN"), UserRole(role_code="USER")]
    db.add(user)
    db.commit()
    generator.close()
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "recyclink-admin-test-password"})
    assert response.status_code==200


def test_bin_threshold_alert_deduplication_and_collection_resolution(client):
    login_admin(client)
    created=client.post("/api/v1/bins",json={"bin_code":"DUP-01","label":"Demo paper bin","category_code":"paper","latitude":28.6,"longitude":77.2,"capacity_grams":10000,"fill_percent":92,"service_area":"Central"},headers=csrf(client))
    assert created.status_code==201,created.text
    bin_row=created.json()
    assert bin_row["sensor_source"]=="SIMULATED"
    assert client.get("/api/v1/bins/alerts").json()[0]["alert_type"]=="HIGH_FILL"
    for _ in range(3):
        reading=client.post(f"/api/v1/bins/{bin_row['id']}/readings",json={"fill_percent":96,"battery_percent":90},headers=csrf(client))
        assert reading.status_code==201
    alerts=client.get("/api/v1/bins/alerts").json()
    assert len(alerts)==1 and alerts[0]["alert_type"]=="HIGH_FILL"
    overflow=client.post(f"/api/v1/bins/{bin_row['id']}/readings",json={"fill_percent":100,"battery_percent":90},headers=csrf(client))
    assert overflow.status_code==201
    alerts=client.get("/api/v1/bins/alerts").json()
    assert len(alerts)==1 and alerts[0]["alert_type"]=="OVERFLOW"
    too_much=client.post(f"/api/v1/bins/{bin_row['id']}/collect",json={"collected_quantity_grams":10001},headers=csrf(client))
    assert too_much.status_code==409
    collected=client.post(f"/api/v1/bins/{bin_row['id']}/collect",json={"collected_quantity_grams":6000,"notes":"Demo collection"},headers=csrf(client))
    assert collected.status_code==201,collected.text
    assert collected.json()["bin"]["fill_percent"]==40
    assert client.get("/api/v1/bins/alerts").json()==[]
    assert len(client.get(f"/api/v1/bins/{bin_row['id']}/readings").json())==6


def test_simulator_is_seeded_bounded_and_user_overflow_report_deduplicates(client):
    login_admin(client)
    ids=[]
    for code in ["SIM-A","SIM-B"]:
        response=client.post("/api/v1/bins",json={"bin_code":code,"label":code,"category_code":"plastic","latitude":28.6,"longitude":77.2,"capacity_grams":5000,"fill_percent":50},headers=csrf(client))
        assert response.status_code==201
        ids.append(response.json()["id"])
    tick=client.post("/api/v1/bins/simulator/tick",json={"seed":17,"offline_probability":0},headers=csrf(client))
    assert tick.status_code==200 and tick.json()["simulated_readings"]==2
    rows=client.get("/api/v1/bins").json()
    simulated=[row for row in rows if row["bin_code"].startswith("SIM-")]
    assert len(simulated)==2
    first_fill={row["bin_code"]:row["fill_percent"] for row in simulated}
    repeat=client.post("/api/v1/bins/simulator/tick",json={"seed":17,"offline_probability":0},headers=csrf(client))
    assert repeat.status_code==200
    rows_again=client.get("/api/v1/bins").json()
    simulated_again=[row for row in rows_again if row["bin_code"].startswith("SIM-")]
    assert all(abs((row["fill_percent"]-first_fill[row["bin_code"]])-(first_fill[row["bin_code"]]-50))<1e-8 for row in simulated_again)
    assert all(0<=row["fill_percent"]<=100 for row in simulated)
    assert all(row["sensor_source"]=="SIMULATED" for row in simulated)

    household=TestClient(client.app)
    registered=household.post("/api/v1/auth/register",json={"email":"overflow-reporter@example.test","password":"recyclink-test-password","full_name":"Bin Reporter"})
    assert registered.status_code==201
    first=household.post(f"/api/v1/bins/{ids[0]}/report-overflow",headers=csrf(household))
    second=household.post(f"/api/v1/bins/{ids[0]}/report-overflow",headers=csrf(household))
    assert first.status_code==201 and first.json()["duplicate_open_alert"] is False
    assert second.status_code==200 and second.json()["duplicate_open_alert"] is True
    current=client.get(f"/api/v1/bins/{ids[0]}/readings").json()
    assert current[-1]["sensor_source"]=="SIMULATED"
