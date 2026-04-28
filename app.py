from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from hcaptcha import HCaptcha
import requests, time, threading, os

app = Flask(__name__, static_folder="static", static_url_path="")
CORS(app)

UA      = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
BHN     = "https://bot-hosting.net"
HOST    = "bot-hosting.net"
SITEKEY = "21335a07-5b97-4a79-b1e9-b197dc35017a"

_client = None
_lock   = threading.Lock()

def get_client():
    global _client
    with _lock:
        if _client is None:
            print("[Boot] Starting Chrome...")
            _client = HCaptcha(HOST, SITEKEY)
            print("[Boot] Chrome ready")
    return _client

threading.Thread(target=get_client, daemon=True).start()

def bh(method, path, token, body=None):
    h = {"authorization": token, "user-agent": UA, "content-type": "application/json"}
    fn = requests.get if method == "GET" else requests.post
    r  = fn(BHN + path, json=body, headers=h, timeout=12)
    return r.json() if r.content else {}

def mask(t):
    return t[:4] + "***" + t[-4:] if t and len(t) > 8 else "***"

# ── API Routes ────────────────────────────────────────────────────

@app.route("/api/info")
def api_info():
    token = request.args.get("token","").strip()
    if not token: return jsonify({"ok": False, "msg": "Thiếu token"}), 400
    try:
        me = bh("GET", "/api/me", token)
        if not me or me.get("error"): return jsonify({"ok": False, "msg": "Token sai"}), 401
        st = bh("GET", "/api/freeCoinsStatus", token)
        sv = bh("GET", "/api/servers", token)
        cd = st.get("cooldown") or st.get("timeLeft") or 0
        return jsonify({
            "ok": True,
            "username": me.get("username"),
            "coins":    me.get("coins"),
            "servers":  len(sv) if isinstance(sv, list) else 0,
            "claimable": bool(st.get("claimable")),
            "cooldown":  int(cd),
            "token":     mask(token)
        })
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)}), 500

@app.route("/api/claim", methods=["POST"])
def api_claim():
    body  = request.get_json(force=True) or {}
    token = body.get("token","").strip()
    if not token: return jsonify({"ok": False, "msg": "Thiếu token"}), 400
    t0 = time.time()
    try:
        st = bh("GET", "/api/freeCoinsStatus", token)
        if not st.get("claimable"):
            cd = st.get("cooldown") or st.get("timeLeft") or 0
            return jsonify({"ok": False, "msg": "Cooldown", "cooldown": int(cd)})

        print(f"[Claim] Giải captcha cho {mask(token)}...")
        ts  = time.time()
        cap = get_client().solve()
        ms  = int((time.time()-ts)*1000)
        if not cap: return jsonify({"ok": False, "msg": "Giải captcha thất bại"}), 500
        print(f"[Claim] Solved {ms}ms")

        result = bh("POST", "/api/freeCoins", token, {"hCaptchaResponse": cap})
        ok     = bool(result.get("success"))
        me     = bh("GET", "/api/me", token) if ok else {}
        return jsonify({
            "ok":      ok,
            "msg":     result.get("message",""),
            "coins":   me.get("coins"),
            "captchaMs": ms,
            "tookMs":  int((time.time()-t0)*1000),
            "token":   mask(token)
        })
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)}), 500

@app.route("/", defaults={"p": ""})
@app.route("/<path:p>")
def index(p):
    return send_from_directory("static", "index.html")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"✅ Running on port {port}")
    app.run(host="0.0.0.0", port=port, threaded=True)
