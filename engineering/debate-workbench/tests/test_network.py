import socket
import unittest
import httpx
from unittest.mock import patch
import network

class PinningTests(unittest.IsolatedAsyncioTestCase):
    async def test_pinned_ip_and_original_tls_name(self):
        outer=self
        class Client:
            def __init__(self,**kwargs):
                outer.assertFalse(kwargs["trust_env"])
                outer.assertFalse(kwargs["follow_redirects"])
            async def __aenter__(self):return self
            async def __aexit__(self,*args):pass
            def build_request(self,*args,**kwargs):return httpx.Request(*args,**kwargs)
            async def send(self,request,**kwargs):
                outer.assertEqual(request.url.host,"8.8.8.8")
                outer.assertEqual(request.headers["Host"],"provider.example")
                outer.assertEqual(request.extensions["sni_hostname"],"provider.example")
                return httpx.Response(200,content=b'{"ok":true}',request=request)
        with patch("network.socket.getaddrinfo",return_value=[(socket.AF_INET,0,0,"",("8.8.8.8",443))]) as dns,patch("network.httpx.AsyncClient",Client):
            r=await network.request("POST","https://provider.example/v1/messages",api=True,payload={})
        self.assertTrue(r.json()["ok"])
        self.assertEqual(dns.call_count,1)
