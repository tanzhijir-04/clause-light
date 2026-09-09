from __future__ import annotations


async def test_contract_text_is_not_logged(v2_client, org_api_key, caplog) -> None:
    secret_text = "本合同高度敏感且不可进入日志"
    await v2_client.post(
        "/api/v2/contracts",
        headers={"X-API-Key": org_api_key, "Idempotency-Key": "privacy-001"},
        json={"title": "隐私测试", "contract_type": "other", "text_content": secret_text},
    )
    assert secret_text not in caplog.text
