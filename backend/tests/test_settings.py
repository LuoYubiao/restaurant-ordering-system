"""系统设置接口测试。

Tests for the system settings endpoints.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict

from fastapi.testclient import TestClient


def _contains_chinese(text: str) -> bool:
    """判断字符串是否包含中文字符。

    Return ``True`` when the text contains at least one CJK character.

    :param text: 待检测文本 / text to inspect
    :return: 是否包含中文 / whether it contains Chinese
    """
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def test_get_settings_default_structure(client: TestClient) -> None:
    """``GET /api/settings`` 应返回完整的默认配置结构。

    ``GET /api/settings`` should return the full default settings structure.
    """
    resp = client.get("/api/settings")
    assert resp.status_code == 200, resp.text
    body: Dict[str, Any] = resp.json()

    assert body["shopName"] == "我的小店"
    assert body["serverPort"] == 8000
    assert body["printCounterTicket"] is True
    assert body["printKitchenTicket"] is True

    printer = body["printer"]
    assert set(printer.keys()) == {
        "mode",
        "host",
        "port",
        "usbVendorId",
        "usbProductId",
        "paperWidth",
    }
    assert printer["mode"] == "mock"
    assert printer["port"] == 9100
    assert printer["paperWidth"] == 58


def test_update_settings_persists(client: TestClient, data_dir: str) -> None:
    """``PUT /api/settings`` 修改后应持久化，GET 与 config.json 均能读到新值。

    ``PUT /api/settings`` should persist changes; both the follow-up GET and the
    ``config.json`` file must reflect the new values.
    """
    payload = {
        "shopName": "深夜食堂",
        "printer": {"mode": "mock", "paperWidth": 80},
    }
    resp = client.put("/api/settings", json=payload)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["shopName"] == "深夜食堂"
    assert body["printer"]["paperWidth"] == 80
    assert body["restartRequired"] is False

    # 再 GET 应读到新值 / A follow-up GET must return the new values
    got = client.get("/api/settings").json()
    assert got["shopName"] == "深夜食堂"
    assert got["printer"]["paperWidth"] == 80

    # config.json 文件内容应已更新 / The config.json file must be updated
    config_path = os.path.join(data_dir, "config.json")
    assert os.path.exists(config_path)
    with open(config_path, "r", encoding="utf-8") as fp:
        saved = json.load(fp)
    assert saved["shopName"] == "深夜食堂"
    assert saved["printer"]["paperWidth"] == 80


def test_update_settings_rejects_invalid(client: TestClient) -> None:
    """非法参数应被拒绝（返回 422 或 400），且不写入配置。

    Illegal parameters must be rejected (422 or 400) without persisting.
    """
    invalid_payloads = [
        {"printer": {"mode": "foo"}},
        {"printer": {"paperWidth": 100}},
        {"printer": {"mode": "network", "host": ""}},
        {"serverPort": 80},
    ]
    for payload in invalid_payloads:
        resp = client.put("/api/settings", json=payload)
        assert resp.status_code in (400, 422), f"{payload} -> {resp.status_code}: {resp.text}"

    # 非法请求不应改动配置 / Illegal requests must not change the config
    body = client.get("/api/settings").json()
    assert body["shopName"] == "我的小店"
    assert body["serverPort"] == 8000
    assert body["printer"]["mode"] == "mock"
    assert body["printer"]["paperWidth"] == 58


def test_restart_required_flag(client: TestClient) -> None:
    """修改 serverPort 时 restartRequired 为 True，仅改 shopName 时为 False。

    ``restartRequired`` is ``True`` when ``serverPort`` changes and ``False``
    when only ``shopName`` changes.
    """
    resp = client.put("/api/settings", json={"serverPort": 8123})
    assert resp.status_code == 200, resp.text
    assert resp.json()["restartRequired"] is True

    resp = client.put("/api/settings", json={"shopName": "只改店名"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["restartRequired"] is False


def test_test_print_mock_writes_file(client: TestClient, data_dir: str) -> None:
    """mock 模式下测试打印应成功，并在 printed/ 目录产生小票文件。

    In mock mode the test print should succeed and write a ticket file into the
    ``printed/`` directory.
    """
    resp = client.post("/api/settings/test-print")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True
    assert body["message"]

    printed_dir = os.path.join(data_dir, "printed")
    assert os.path.isdir(printed_dir)
    files = os.listdir(printed_dir)
    assert any(name.endswith(".txt") for name in files), files


def test_test_print_network_unreachable_returns_200(client: TestClient) -> None:
    """network 模式指向不可达地址时应返回 200 且 ok=false，message 为中文。

    In network mode pointing at an unreachable address, the endpoint must return
    HTTP 200 with ``ok=false`` and a readable Chinese message (never 500).
    """
    resp = client.put(
        "/api/settings",
        json={"printer": {"mode": "network", "host": "127.0.0.1", "port": 1}},
    )
    assert resp.status_code == 200, resp.text

    resp = client.post("/api/settings/test-print")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is False
    assert body["message"]
    assert _contains_chinese(body["message"])


def test_status_fields(client: TestClient) -> None:
    """``GET /api/settings/status`` 应包含 port / isMockPrinter / lanUrls 等字段。

    ``GET /api/settings/status`` should include port, isMockPrinter, lanUrls and
    the URL/page keys for the settings page.
    """
    resp = client.get("/api/settings/status")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["port"] == 8000
    assert body["isMockPrinter"] is True
    assert body["printerMode"] == "mock"
    assert set(body["lanUrls"].keys()) == {"counter", "kitchen", "admin", "settings"}
    assert body["lanUrls"]["counter"].endswith("/counter")
    assert body["lanUrls"]["kitchen"].endswith("/kitchen")
    assert body["lanUrls"]["admin"].endswith("/admin")
    assert body["lanUrls"]["settings"].endswith("/settings")
    assert body["dbPath"].endswith(os.path.join("data", "restaurant.db"))
    assert body["printedDir"].endswith("printed")
    assert body["version"] == "1.0.0"
