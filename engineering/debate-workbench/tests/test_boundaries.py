import socket
import unittest
from unittest.mock import patch
from config import AppError, Settings
from network import resolve
from provider import profile

class BoundaryTests(unittest.TestCase):
    def test_private_destinations_and_literal_ips_rejected(self):
        for ip in ("127.0.0.1","192.168.1.1","169.254.169.254","::1","198.18.0.1"):
            with patch("network.socket.getaddrinfo",return_value=[(socket.AF_INET,0,0,"",(ip,443))]):
                with self.assertRaises(AppError):
                    resolve("https://provider.example",local=False,api=True)
        for url in ("https://127.0.0.1","https://[::1]","https://router.local","https://example.com:8443","http://example.com","https://user:pass@example.com"):
            with self.assertRaises(AppError):
                resolve(url,api=True)

    def test_fake_ip_only_local(self):
        with patch("network.socket.getaddrinfo",return_value=[(socket.AF_INET,0,0,"",("198.18.0.1",443))]):
            resolve("https://provider.example",local=True,api=True)
            with self.assertRaises(AppError):
                resolve("https://provider.example",local=False,api=True)

    def test_mixed_dns_rejected(self):
        with patch("network.socket.getaddrinfo",return_value=[(socket.AF_INET,0,0,"",("8.8.8.8",443)),(socket.AF_INET,0,0,"",("127.0.0.1",443))]):
            with self.assertRaises(AppError):
                resolve("https://provider.example",api=True)

    def test_remote_requires_https(self):
        with self.assertRaises(ValueError):
            Settings(remote=True,origin="http://public.example")
        Settings(remote=True,origin="https://public.example")

    def test_bad_profile(self):
        for base in ("http://example.com","https://example.com?secret=x","https://example.com/#x","https://user@example.com"):
            with self.assertRaises(AppError):
                profile("openai",base,"model","test-token")
