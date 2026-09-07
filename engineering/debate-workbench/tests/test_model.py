import unittest
import httpx
from model import Model, Reply
from provider import Provider, profile
from config import AppError

class ModelContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_anthropic_contract(self):
        async def sender(method, url, **kwargs):
            self.assertEqual(url, "https://provider.example/anthropic/v1/messages")
            self.assertEqual(kwargs["headers"]["x-api-key"], "test-token")
            self.assertNotIn("test-token", str(kwargs["payload"]))
            self.assertEqual(kwargs["payload"]["model"], "test-model")
            return httpx.Response(200, json={"content":[{"type":"text","text":"{}"}],"usage":{"input_tokens":3,"output_tokens":1}})
        cfg=profile("anthropic","https://provider.example/anthropic","test-model","test-token")
        text,usage=await Model(lambda:cfg,Provider(sender=sender)).request("system","prompt",schema=Reply.model_json_schema())
        self.assertEqual(text,"{}")
        self.assertEqual(usage["input_tokens"],3)

    async def test_openai_contract_and_key_redaction(self):
        async def sender(method, url, **kwargs):
            self.assertEqual(url,"https://api.openai.com/v1/chat/completions")
            self.assertIn("max_completion_tokens",kwargs["payload"])
            self.assertEqual(kwargs["payload"]["messages"][0]["role"],"system")
            return httpx.Response(200,json={"choices":[{"message":{"content":"test-token OK"},"finish_reason":"stop"}],"usage":{"prompt_tokens":2,"completion_tokens":1}})
        cfg=profile("openai","https://api.openai.com/v1","test","test-token")
        text,usage=await Provider(sender=sender).request(cfg,"system","prompt")
        self.assertNotIn("test-token",text)
        self.assertEqual(usage["output_tokens"],1)

    async def test_provider_body_is_not_exposed(self):
        async def sender(*args,**kwargs):
            return httpx.Response(401,json={"secret":"test-token"})
        with self.assertRaises(AppError) as raised:
            await Provider(sender=sender).request(profile("openai","https://provider.example","test","test-token"),"s","p")
        self.assertNotIn("test-token",str(raised.exception))

    async def test_missing_connection_never_falls_back(self):
        with self.assertRaises(AppError):
            await Model().request("system","prompt")
