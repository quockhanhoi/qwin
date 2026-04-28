import json, random, time
from urllib.parse import urlencode
import httpx, requests
from undetected_chromedriver import Chrome, ChromeOptions

def encode_all(s):
    return "".join("%{0:0>2}".format(format(ord(c), "x")) for c in s)

def mouse_movement():
    return [[random.randint(15,450), random.randint(15,450), round(time.time())] for _ in range(random.randint(10,25))]

HEADERS = {
    "Authority": "hcaptcha.com", "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.102 Safari/537.36",
    "Content-Type": "application/x-www-form-urlencoded", "Origin": "https://assets.hcaptcha.com",
    "Sec-Fetch-Site": "same-site", "Sec-Fetch-Mode": "cors", "Sec-Fetch-Dest": "empty",
    "Accept-Language": "en-US,en;q=0.9",
}

class HCaptcha:
    def __init__(self, host, sitekey):
        self._host = host
        self._sitekey = sitekey
        opts = ChromeOptions()
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--headless=new")
        self.driver = Chrome(options=opts)
        self.hsw_code = httpx.get("https://newassets.hcaptcha.com/c/e1efca35/hsw.js").text
        self._config = self._site_config()

    def _site_config(self):
        try:
            r = requests.get(
                "https://staging.hmt.ai/checksiteconfig?host=%s&sitekey=%s&sc=1&swa=1" % (self._host, encode_all(self._sitekey)),
                headers=HEADERS, timeout=5
            ).json()
            if r.get("pass"): return r["c"]
        except: pass
        return None

    def _get_hsw(self, req):
        return self.driver.execute_script(f"{self.hsw_code}; return hsw('{req}')")

    def solve(self):
        try:
            self._config = self._site_config()
            payload = urlencode({
                "host": self._host, "sitekey": self._sitekey, "hl": "en",
                "motionData": json.dumps({"mm": mouse_movement(), "st": round(time.time()), "prev": {"expiredResponse": False}}),
                "n": self._get_hsw(self._config["req"]), "c": json.dumps(self._config)
            })
            h = {**HEADERS, "Content-Length": str(len(payload))}
            gc = requests.post("https://staging.hmt.ai/getcaptcha?s=%s" % encode_all(self._sitekey), data=payload, headers=h, timeout=8)
            if "generated_pass_UUID" in gc.text: return gc.json()["generated_pass_UUID"]
            gc_json = gc.json()
            question = gc_json["requester_question"]["en"].replace("Please click each image containing a ", "").lower()
            accepted = {t["task_key"]: "true" if question in t.get("datapoint_uri","").lower() else "false" for t in gc_json["tasklist"]}
            self._config = gc_json["c"]
            ck = requests.post(
                "https://staging.hmt.ai/checkcaptcha/%s/%s" % (encode_all(self._sitekey), gc_json["key"]),
                json={"answers": accepted, "serverdomain": self._host, "sitekey": self._sitekey, "job_mode": "image_label_binary",
                      "motionData": json.dumps({"mm": mouse_movement(), "st": round(time.time()), "prev": {"expiredResponse": False}}),
                      "n": self._get_hsw(self._config["req"]), "c": json.dumps(self._config)},
                headers={**HEADERS, "content-type": "application/json;charset=UTF-8"}, timeout=8
            ).json()
            return ck.get("generated_pass_UUID")
        except Exception as e:
            print(f"[Captcha] {e}")
            return None

    def close(self):
        try: self.driver.quit()
        except: pass
