"""Graba las fixtures del recorrido de navegador desde backends REALES ya levantados (ver README.md).

Solo biblioteca estándar. Uso:
  python record_fixtures.py --out . [--cicytex URL] [--producer URL] [--lab URL]
No inventa valores: cada archivo es el cuerpo JSON devuelto por el backend. Única normalización
(documentada en el README): identificadores/instantes de ejecución que cambian en cada corrida.
"""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

FIXED_INSTANT = "2023-07-07T00:00:00Z"
CICYTEX_KEY = {"sensor_id": "CP1_S1", "emission_date": "2023-07-06", "horizon_days": 1}
PRODUCER = {
    "pergamino-ensemble-demo": ("2023-06-13", ["2023-06-13", "2023-06-14", "2023-06-15", "2023-06-16", "2023-06-17"]),
    "melchor-romero-demo": ("2024-10-20", ["2024-10-20", "2024-10-21", "2024-10-22", "2024-10-23", "2024-10-24"]),
}
REVEAL_STEPS = 4  # fechas reveladas por encima de la primera emisión que recorre el script de navegador


def call(base: str, method: str, path: str, body: dict | None = None) -> tuple[int, object]:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(base + path, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, json.loads(response.read() or "null")
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or "null")


def write(out: Path, relative: str, payload: object) -> None:
    target = out / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print("escrito", relative)


def need(status: int, payload: object, what: str) -> object:
    if status >= 400:
        raise SystemExit(f"{what}: HTTP {status} {payload}")
    return payload


def record_cicytex(base: str, out: Path) -> None:
    api = "/api/v2/cicytex/replay"
    write(out, "cicytex/catalog.json", need(*call(base, "GET", f"{api}/catalog"), "catalog"))
    write(out, "cicytex/provenance.json", need(*call(base, "GET", f"{api}/provenance"), "provenance"))
    created = need(*call(base, "POST", f"{api}/sessions", CICYTEX_KEY), "create")
    session_id = created["session_id"]
    steps = [created]
    for _ in range(3):
        steps.append(need(*call(base, "POST", f"{api}/sessions/{session_id}/advance"), "advance"))
    for step in steps:
        step["session_id"] = "recorded"
    write(out, "cicytex/session-steps.json", {"key": CICYTEX_KEY, "steps": steps})
    feedback = need(*call(base, "POST", f"{api}/sessions/{session_id}/feedback", {"estado_validacion": "confirmada"}), "feedback")
    feedback["estado_validacion"] = "confirmada"
    feedback["observacion"] = None
    if "registered_at" in feedback:
        feedback["registered_at"] = FIXED_INSTANT
    write(out, "cicytex/feedback.json", feedback)


def plus(iso: str, days: int) -> str:
    return (date.fromisoformat(iso) + timedelta(days=days)).isoformat()


def record_producer(base: str, out: Path) -> None:
    for sensor, (first, emissions) in PRODUCER.items():
        root = f"/api/v2/sensors/{sensor}/historical"
        reveals = {(e, e) for e in emissions} | {(first, plus(first, n)) for n in range(1, REVEAL_STEPS + 1)}
        for emission, revealed in sorted(reveals):
            query = "" if emission == revealed else f"?revealed_through={revealed}"
            status, payload = call(base, "GET", f"{root}/{emission}/forecasts{query}")
            if status == 200:
                write(out, f"{sensor}/forecasts__{emission}__{revealed}.json", payload)
            else:
                print("omitido (sin emisión preparada)", sensor, emission, revealed, status)
        for revealed in sorted({r for _, r in reveals}):
            status, payload = call(base, "GET", f"{root}/{revealed}/readings?days=10")
            if status == 200:
                write(out, f"{sensor}/readings__{revealed}.json", payload)


def record_lab(base: str, out: Path) -> None:
    sensor = "lab-fixture"
    end = date.today() - timedelta(days=6)
    for index in range(120):
        day = end - timedelta(days=119 - index)
        values = {
            "timestamp": f"{day.isoformat()}T00:00:00Z",
            "soil_moisture": 0.30 + 0.05 * ((index % 10) / 10),
            "temperature": 20 + (index % 7),
            "relative_humidity": 60 + (index % 5),
            "precipitation": 0.0 if index % 4 else 2.0,
            "solar_radiation": 18 + (index % 6),
            "wind_speed": 2 + (index % 3),
            "procedencia": "sintetico",
        }
        need(*call(base, "POST", f"/sensors/{sensor}/readings", values), "ingest")
    quality = need(*call(base, "GET", f"/quality/{sensor}"), "quality")
    write(out, "lab/quality-template.json", quality)
    run = need(*call(base, "POST", f"/forecast/{sensor}/run"), "forecast run")
    write(out, "lab/forecast-run.json", run)
    write(out, "lab/feedback-list.json", need(*call(base, "GET", f"/feedback/{sensor}"), "feedback list"))
    status, payload = call(base, "GET", f"/models/{sensor}/active")
    write(out, "lab/models-active.json", {"status": status, "body": payload})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=".")
    parser.add_argument("--cicytex")
    parser.add_argument("--producer")
    parser.add_argument("--lab")
    args = parser.parse_args()
    out = Path(args.out)
    if args.cicytex:
        record_cicytex(args.cicytex.rstrip("/"), out)
    if args.producer:
        record_producer(args.producer.rstrip("/"), out)
    if args.lab:
        record_lab(args.lab.rstrip("/"), out)
