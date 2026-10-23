"""Synthetic budgeted transport and reserved-return composition contracts."""
from copy import deepcopy
from email.message import Message
import json
import unittest
from unittest.mock import patch

from exchange.wallet_api_client import WalletAPIRefused
from exchange.wallet_direct_return_task import WalletDirectReturnTask
from integration import test_wallet_direct_return_task as original
from integration import test_wallet_api_client as protocol


class BudgetedDirectReturnCompositionContracts(unittest.TestCase):
    def test_original_unknown_response_keeps_same_task_and_durable_no_resend_guard(self):
        with original.direct_task() as (task,client,state,value,options):
            binding = task.binding()
            state["mode"] = "unknown-execute"
            before = len(state["calls"])
            with self.assertRaises(WalletAPIRefused):
                task.execute("4")
            self.assertEqual(len(original.executes(state)),1)
            rebuilt = WalletDirectReturnTask(client,**options)
            with self.assertRaisesRegex(WalletAPIRefused,"RECONCILE_FIRST"):
                rebuilt.execute("4")
            self.assertEqual(len(original.executes(state)),1)
            self.assertEqual(task.binding(),binding)
            paths = [path for _,path,_ in state["calls"][before:]]
            # Retain the original client session checks; only one execute may be sent.
            self.assertEqual(paths,["/auth/session","/auth/tasks/execute","/auth/session"])

    def test_ambiguous_execute_response_cannot_replace_cookies_or_reset_original_attempt(self):
        with original.direct_task() as (task,client,state,value,options):
            requests = []
            prior_cookies = deepcopy([vars(cookie) for cookie in client._jar])
            class Socket:
                def settimeout(self,timeout):
                    pass
            class Response:
                status = 200
                def __init__(self):
                    self.headers = Message()
                    self.headers["Content-Type"] = "application/json"
                    self.headers["Content-Length"] = "2"
                    self.headers["Content-Length"] = "2"
                    self.headers["Set-Cookie"] = "replacement=INVALID; Path=/"
                def getheader(self,key,default=None):
                    return self.headers.get(key,default)
                def close(self):
                    pass
            class Connection:
                def __init__(self,*args,**kwargs):
                    self.sock = Socket()
                def connect(self):
                    pass
                def request(self,method,path,body,headers):
                    requests.append({"method":method,"path":path,
                                     "body":body,"headers":deepcopy(headers)})
                def getresponse(self):
                    return Response()
                def close(self):
                    pass
            original_request = client._request
            def request_with_execute_transport(path, payload=None):
                if path == "tasks/execute":
                    with patch("exchange.wallet_api_client.http.client.HTTPConnection",
                               side_effect=Connection):
                        return original_request(path, payload)
                return original_request(path, payload)
            with patch.object(client, "_request", side_effect=request_with_execute_transport):
                with self.assertRaises(WalletAPIRefused):
                    task.execute("4")
                with self.assertRaisesRegex(WalletAPIRefused,"RECONCILE_FIRST"):
                    WalletDirectReturnTask(client,**options).execute("4")
            self.assertEqual(len(requests),1)
            self.assertEqual(requests[0]["method"],"POST")
            self.assertEqual(requests[0]["path"],"/auth/tasks/execute")
            self.assertEqual(json.loads(requests[0]["body"]),
                             dict(protocol.EXECUTE,expectedBudgetRevision="4"))
            self.assertEqual([vars(cookie) for cookie in client._jar],prior_cookies)
            self.assertEqual(original.executes(state),[])
