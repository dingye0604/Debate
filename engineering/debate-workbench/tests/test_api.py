import io
import time
import unittest
import uuid
import zipfile
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from app import create_app
from config import Settings, AppError
from provider import profile
from visitors import owner_id
from test_workflow import FakeModel, FakeSearch

class FakeProvider:
    def __init__(self):
        self.calls=[]
    async def probe(self,cfg):
        self.calls.append((cfg.protocol,cfg.model))
        if cfg.key == "invalid-test-key":
            raise AppError("密钥无效。")

class ApiTests(unittest.TestCase):
    def setUp(self):
        self.root=Path("test-artifacts")/("api-"+uuid.uuid4().hex)
        self.provider=FakeProvider()
        self.app=create_app(Settings(data=self.root),self.provider,lambda owner:FakeModel(),FakeSearch)
        self.client=TestClient(self.app)
        self.client.__enter__()
        self.config=self.client.get("/api/config").json()
        self.headers={"X-Debate-Client":"workbench","X-CSRF-Token":self.config["csrf"]}

    def tearDown(self):
        self.client.__exit__(None,None,None)

    def connect(self,client=None,headers=None,key="test-key-alpha",model="private-model-alpha"):
        return (client or self.client).post("/api/connection/connect",headers=headers or self.headers,
            json={"protocol":"openai","base":"https://provider.example/v1","model":model,"key":key})

    def create(self):
        response=self.client.post("/api/sessions",headers=self.headers,json={"topic":"科技发展是否使人更自由","side":"正方"})
        self.assertEqual(response.status_code,200,response.text)
        sid=response.json()["id"]
        for _ in range(100):
            data=self.client.get("/api/sessions/"+sid).json()
            if data["status"]!="running":
                return data
            time.sleep(.01)
        self.fail("generation did not settle")

    def test_no_personal_fallback(self):
        self.assertFalse(self.config["configured"])
        with patch.dict("os.environ",{"ANTHROPIC_AUTH_TOKEN":"never-load","ANTHROPIC_MODEL":"never-load"}):
            r=self.client.post("/api/sessions",headers=self.headers,json={"topic":"测试辩题测试","side":"正方"})
        self.assertEqual(r.status_code,409)
        self.assertEqual(self.provider.calls,[])
        self.assertEqual(self.client.get("/api/sessions").json(),[])

    def test_two_visitors_cannot_read_act_or_download(self):
        self.assertEqual(self.connect().status_code,200)
        a=self.create()
        with TestClient(self.app) as other:
            cfg=other.get("/api/config").json()
            h={"X-Debate-Client":"workbench","X-CSRF-Token":cfg["csrf"]}
            self.assertFalse(cfg["configured"])
            self.assertEqual(other.get("/api/sessions").json(),[])
            self.assertEqual(other.get("/api/sessions/"+a["id"]).status_code,409)
            for kind in ("zip","merged","0"):
                self.assertEqual(other.get("/api/sessions/"+a["id"]+"/download/"+kind).status_code,409)
            self.assertEqual(other.post("/api/sessions/"+a["id"]+"/action",headers=h,json={"action":"rework","revision":a["revision"],"target":0}).status_code,409)
            self.assertEqual(self.connect(other,h,key="test-key-beta",model="private-model-beta").status_code,200)
            alpha=owner_id(self.client.cookies.get("debate_visitor"))
            beta=owner_id(other.cookies.get("debate_visitor"))
            self.assertNotEqual(alpha,beta)
            self.assertEqual(self.app.state.visitors.require(alpha).key,"test-key-alpha")
            self.assertEqual(self.app.state.visitors.require(beta).key,"test-key-beta")
            body=self.client.get("/api/config").text
            self.assertNotIn("private-model",body)
            self.assertNotIn("provider.example",body)
            self.assertNotIn("test-key",body)

    def test_exports_and_disk_never_contain_credentials(self):
        self.connect()
        s=self.create()
        data=self.client.get("/api/sessions/"+s["id"]+"/download/zip")
        self.assertEqual(data.status_code,200)
        with zipfile.ZipFile(io.BytesIO(data.content)) as z:
            self.assertEqual(len(z.namelist()),7)
            for n in z.namelist():
                self.assertNotIn(b"test-key-alpha",z.read(n))
        for file in self.root.rglob("*"):
            if file.is_file():
                self.assertNotIn("test-key-alpha",file.read_text(encoding="utf-8"))
                self.assertNotIn("private-model-alpha",file.read_text(encoding="utf-8"))

    def test_expiry_disconnect_and_restart(self):
        self.connect()
        s=self.create()
        owner=owner_id(self.client.cookies.get("debate_visitor"))
        vault=self.app.state.visitors
        cfg,_=vault.keys[owner]
        vault.keys[owner]=(cfg,time.time()-1)
        self.assertFalse(self.client.get("/api/config").json()["configured"])
        self.assertEqual(self.client.post("/api/sessions/"+s["id"]+"/action",headers=self.headers,json={"action":"reply","revision":s["revision"],"text":"我的判断"}).status_code,409)
        self.assertEqual(self.client.get("/api/sessions/"+s["id"]+"/download/zip").status_code,200)
        self.connect()
        self.assertEqual(self.client.post("/api/disconnect",headers=self.headers,json={}).status_code,200)
        self.assertFalse(self.client.get("/api/config").json()["configured"])
        restarted=create_app(Settings(data=self.root),self.provider,lambda owner:FakeModel(),FakeSearch)
        with TestClient(restarted) as client:
            client.cookies.update(self.client.cookies)
            self.assertFalse(client.get("/api/config").json()["configured"])
            self.assertEqual(client.get("/api/sessions/"+s["id"]).status_code,200)

    def test_csrf_host_body_and_validation_redaction(self):
        r=self.client.post("/api/sessions",json={"topic":"测试辩题测试","side":"正方"})
        self.assertEqual(r.status_code,403)
        h={**self.headers,"Origin":"https://evil.example"}
        self.assertEqual(self.client.post("/api/disconnect",headers=h,json={}).status_code,403)
        self.assertEqual(self.client.get("/",headers={"host":"evil.example"}).status_code,400)
        self.assertIn("javascript",self.client.get("/static/markdown.mjs").headers["content-type"])
        self.assertEqual(self.client.get("/static/../config.py").status_code,404)
        r=self.client.post("/api/connection/connect",headers=self.headers,json={"key":"do-not-echo","protocol":{}})
        self.assertEqual(r.status_code,422)
        self.assertNotIn("do-not-echo",r.text)
        self.assertEqual(self.client.post("/api/disconnect",headers=self.headers,content=b"x"*50001).status_code,413)
        self.assertIn("HttpOnly",self.client.get("/api/config").headers["set-cookie"])

    def test_failed_connection_not_saved(self):
        self.assertEqual(self.connect(key="invalid-test-key").status_code,409)
        self.assertFalse(self.client.get("/api/config").json()["configured"])

    def test_remote_secure_cookie_origin_and_https(self):
        remote=create_app(Settings(data=self.root/"remote",origin="https://debate.example",remote=True),self.provider)
        with TestClient(remote,base_url="https://debate.example") as c:
            r=c.get("/api/config")
            self.assertIn("__Host-debate=",r.headers["set-cookie"])
            self.assertIn("Secure",r.headers["set-cookie"])
            self.assertEqual(r.json()["mode"],"remote")
            h={"X-Debate-Client":"workbench","X-CSRF-Token":r.json()["csrf"],"Origin":"http://debate.example"}
            self.assertEqual(c.post("/api/disconnect",headers=h,json={}).status_code,403)
            self.assertEqual(c.get("http://debate.example/api/config").status_code,403)
