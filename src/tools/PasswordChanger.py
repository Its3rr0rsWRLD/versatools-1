import httpc
from Tool import Tool
import concurrent.futures
from utils import Utils
import os
import re

class PasswordChanger(Tool):
    def __init__(self, app):
        super().__init__("Password Changer", "Change password of many cookies", app)

        self.new_password_file_path = os.path.join(self.files_directory, "password-changed-cookies.txt")

    def run(self):
        f = open(self.new_password_file_path, 'w')
        f.seek(0)
        f.truncate()

        cookies, lines = self.get_cookies(None, True)
        new_password = self.config["new_password"]

        req_sent = 0
        req_failed = 0
        total_req = len(cookies)

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.config["max_workers"]) as executor:
            self.results = [executor.submit(self.change_password, upc, new_password) for upc in lines]

            for future in concurrent.futures.as_completed(self.results):
                if future.cancelled():
                    continue

                try:
                    is_success, response_text = future.result()
                except Exception as err:
                    is_success, response_text = False, str(err)

                if is_success:
                    req_sent += 1
                    upc = response_text

                    f.write(upc+"\n")
                    f.flush()
                else:
                    req_failed += 1

                self.print_status(req_sent, req_failed, total_req, response_text, is_success, "Password changed")

        f.close()

        # replace cookies
        with open(self.cookies_file_path, 'w') as destination_file:
            with open(self.new_password_file_path, 'r') as source_file:
                destination_file.seek(0)
                destination_file.truncate()
                destination_file.write(source_file.read())

        os.remove(self.new_password_file_path)

    @Utils.handle_exception(2)
    def change_password(self, upc, new_password):
        """
        Update password of upc
        """
        try:
            username = upc.split(":")[0]
            current_password = upc.split(":")[1]
            cookie = re.compile(r'_\|WARNING:-DO-NOT-SHARE-THIS\.-.*').search(upc).group(0)
        except Exception:
            return False, f"Upc is not formatted correctly {upc[:39]}..."

        proxies = self.get_random_proxy() if self.config["use_proxy"] else None

        with httpc.Session(proxies=proxies) as client:
            user_agent = httpc.get_random_user_agent()
            csrf_token = self.get_csrf_token(cookie, client)

            req_url = "https://auth.roblox.com/v2/user/passwords/change"
            req_cookies = { ".ROBLOSECURITY": cookie }
            req_headers = httpc.get_roblox_headers(user_agent, csrf_token)
            req_json = {"currentPassword": current_password, "newPassword": new_password}

            response = client.post(req_url, headers=req_headers, json=req_json, cookies=req_cookies)

        try:
            new_cookie = response.headers["Set-Cookie"].split(".ROBLOSECURITY=")[1].split(";")[0]
        except Exception:
            raise Exception("New cookie not found "+ Utils.return_res(response))

        success = response.status_code == 200

        return success, f"{username}:{new_password}:{new_cookie}"
