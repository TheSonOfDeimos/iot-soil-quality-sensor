# main.py — Pico W Captive Portal + Scanner + Join Test (compat version, no f-strings)
# - Open AP + DNS catch-all + HTTP captive portal
# - Scan nearby Wi-Fi networks (/networks, /scan.json)
# - Join test form (/join, POST /test-credentials)
# - Extra detailed logging (password echoed in logs as requested)
# - Compatible with older MicroPython (no f-strings, no .fileno())

import network, socket, time, sys, uselect, ubinascii

# ===== CONFIG =====
COUNTRY = "GB"
SSID    = "PicoW-Captive"
AP_IP_FALLBACK = ("192.168.4.1","255.255.255.0","192.168.4.1","192.168.4.1")
HTTP_PORT = 80
DNS_PORT  = 53
SCAN_TIMEOUT_S = 6
JOIN_TIMEOUT_S = 25
STATUS_LOG_PERIOD_S = 1.0
# ==================

print("=== Pico W Captive Portal + Scanner + Join Test (Compat) ===")
try:
    network.country(COUNTRY)
    print("[i] Regulatory domain set to {}".format(COUNTRY))
except Exception as e:
    print("[i] network.country() not available: {}".format(e))

sta = network.WLAN(network.STA_IF)
ap  = network.WLAN(network.AP_IF)

def fmt_mac(mac):
    try:
        return ":".join("{:02X}".format(b) for b in mac)
    except Exception:
        try:
            return ubinascii.hexlify(mac).decode()
        except Exception:
            return "?"

print("[i] Resetting Wi-Fi state...")
for iface, name in ((sta,"STA"), (ap,"AP")):
    try:
        if iface.active():
            iface.active(False)
            print("    - {} disabled".format(name))
    except Exception as e:
        print("    - {} disable error: {}".format(name, e))
time.sleep(0.2)

def ap_try_set(k, v):
    try:
        ap.config(**{k:v})
        print("    - AP config {}={!r}".format(k, v))
        return True
    except Exception as e:
        print("    - AP config {} unsupported: {}".format(k, e))
        return False

print("[i] Configure OPEN AP...")
if not ap_try_set("essid", SSID):
    print("[!] 'essid' not accepted; cannot continue.")
    sys.exit(1)
for k,v in (("password",""),("key",""),("pwd",""),("authmode",0),("security",0)):
    ap_try_set(k,v)

print("[i] Activating AP...")
ap.active(True)
try:
    sta.active(False)
except Exception:
    pass

print("[i] Waiting for AP to be active...")
for _ in range(50):
    if ap.active():
        break
    time.sleep(0.1)
if not ap.active():
    raise RuntimeError("[!] AP failed to start")

try:
    ip, netmask, gw, dns = ap.ifconfig()
except Exception as e:
    print("[i] ifconfig failed: {}".format(e))
    ip, netmask, gw, dns = AP_IP_FALLBACK

print("[+] AP UP (OPEN)")
print("    SSID : {}".format(SSID))
print("    IP   : {}".format(ip))
try:
    print("    AP MAC: {}".format(fmt_mac(ap.config('mac'))))
except Exception:
    pass

# ---------- Utils ----------
AUTH_MAP = {
    0: "OPEN", 1: "WEP", 2: "WPA-PSK", 3: "WPA2-PSK", 4: "WPA/WPA2-PSK", 5: "WPA2-EAP"
}

def fmt_bssid(bssid_bytes):
    return fmt_mac(bssid_bytes)

def url_decode(s):
    try:
        s = s.replace('+', ' ')
        out = bytearray()
        i = 0
        bs = s.encode() if isinstance(s, str) else s
        while i < len(bs):
            c = bs[i]
            if c == ord('%') and i+2 < len(bs):
                try:
                    out.append(int(bs[i+1:i+3].decode(), 16))
                    i += 3
                    continue
                except Exception:
                    pass
            out.append(c)
            i += 1
        return out.decode()
    except Exception:
        return s

def url_encode(s):
    safe = b"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.~"
    bs = s.encode() if isinstance(s, str) else s
    out = bytearray()
    for b in bs:
        if b in safe:
            out.append(b)
        elif b == 0x20:
            out.append(ord('+'))
        else:
            out.extend(("%{:02X}".format(b)).encode())
    return out.decode()

def parse_query(qs):
    res = {}
    if not qs:
        return res
    parts = qs.split('&')
    for part in parts:
        if '=' in part:
            k,v = part.split('=',1)
            res[url_decode(k)] = url_decode(v)
        else:
            res[url_decode(part)] = ''
    return res

def parse_form_urlencoded(body):
    return parse_query(body)

def html_escape(s):
    try:
        s = s or ""
        s = s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;")
        return s
    except Exception:
        return s

def now_ms():
    return time.ticks_ms()

# ---------- Wi-Fi Scan ----------
def scan_networks():
    print("[i] Starting Wi-Fi scan (temporarily enabling STA)...")
    try:
        sta.active(True)
        try:
            mac = sta.config('mac')
            print("    STA MAC: {}".format(fmt_mac(mac)))
        except Exception:
            pass
    except Exception as e:
        print("[!] Could not enable STA: {}".format(e))
        return []

    try:
        if sta.isconnected():
            print("    - STA was connected; disconnecting first")
            try:
                sta.disconnect()
            except Exception:
                pass
    except Exception:
        pass

    nets = []
    try:
        t0 = now_ms()
        res = sta.scan() or []
        for tup in res:
            try:
                ssid_raw, bssid, ch, rssi, auth = tup[:5]
                hidden = bool(tup[5]) if len(tup) >= 6 else False
            except Exception as e:
                print("[!] Unexpected scan tuple: {} err: {}".format(tup, e))
                continue

            try:
                ssid = ssid_raw.decode() if isinstance(ssid_raw, (bytes, bytearray)) else str(ssid_raw)
            except Exception:
                ssid = str(ssid_raw)

            nets.append({
                "ssid": ssid,
                "bssid": fmt_bssid(bssid),
                "channel": int(ch),
                "rssi": int(rssi),
                "security": AUTH_MAP.get(int(auth), "UNKNOWN({})".format(int(auth))),
                "hidden": hidden,
                "authcode": int(auth),
            })

        dt = time.ticks_diff(now_ms(), t0)
        print("[+] Scan complete: {} networks in {} ms".format(len(nets), dt))
        nets_sorted = sorted(nets, key=lambda x: x["rssi"], reverse=True)
        for n in nets_sorted:
            suf = " hidden" if n["hidden"] else ""
            print("    - {ssid} ({bssid}) ch{ch} RSSI {rssi} dBm [{sec}]{suf}".format(
                ssid=(n["ssid"] or "<hidden>"), bssid=n["bssid"], ch=n["channel"],
                rssi=n["rssi"], sec=n["security"], suf=suf))
    except Exception as e:
        print("[!] Scan failed: {}".format(e))
        nets = []
    finally:
        try:
            sta.active(False)
            print("[i] STA disabled after scan")
        except Exception:
            pass
    return nets

def ssid_visible(target_ssid):
    if not target_ssid:
        return False
    try:
        sta.active(True)
        res = sta.scan() or []
        names = []
        for t in res:
            ssid_raw = t[0]
            try:
                name = ssid_raw.decode() if isinstance(ssid_raw, (bytes, bytearray)) else str(ssid_raw)
            except Exception:
                name = str(ssid_raw)
            names.append(name)
        found = target_ssid in names
        print("[i] Visibility check for '{}': {}".format(target_ssid, "FOUND" if found else "NOT FOUND"))
        return found
    except Exception as e:
        print("[i] Visibility check failed: {}".format(e))
        return False
    finally:
        try:
            sta.active(False)
        except Exception:
            pass

# ---------- Wi-Fi Join Test ----------
STAT_STR = {
    getattr(network, "STAT_IDLE", 0): "IDLE",
    getattr(network, "STAT_CONNECTING", 1): "CONNECTING",
    getattr(network, "STAT_WRONG_PASSWORD", -3): "WRONG_PASSWORD",
    getattr(network, "STAT_NO_AP_FOUND", -2): "NO_AP_FOUND",
    getattr(network, "STAT_CONNECT_FAIL", -1): "CONNECT_FAIL",
    getattr(network, "STAT_GOT_IP", 5): "GOT_IP",
}

def status_to_str(s):
    return STAT_STR.get(s, str(s))

def test_credentials(ssid, password, strict=False):
    print("="*60)
    print("[i] BEGIN test for SSID: '{}'".format(ssid or "<empty>"))
    print("[i] Password (PLAIN): '{}'".format(password))  # echo requested
    print("[i] Strict mode: {}".format(strict))
    print("[i] Pre-check: verifying SSID visibility...")
    _visible = ssid_visible(ssid)
    if not _visible:
        print("[!] SSID not visible in quick scan (could be 5 GHz/hidden/out-of-range). Proceeding anyway.")

    ap_was_active = False
    try:
        ap_was_active = ap.active()
    except Exception:
        pass

    if strict and ap_was_active:
        try:
            ap.active(False)
            print("[i] AP temporarily DISABLED for strict test")
        except Exception as e:
            print("[i] Could not disable AP: {}".format(e))

    try:
        sta.active(True)
        try:
            print("[i] STA MAC: {}".format(fmt_mac(sta.config('mac'))))
        except Exception:
            pass
    except Exception as e:
        if strict and ap_was_active:
            try:
                ap.active(True); ap_try_set("essid", SSID)
            except Exception:
                pass
        return False, {"reason": "STA enable failed: {}".format(e)}

    try:
        if sta.isconnected():
            print("    - STA was connected; disconnecting first")
            try:
                sta.disconnect()
            except Exception:
                pass
    except Exception:
        pass

    try:
        if password:
            print("[>] sta.connect(ssid='{}', password='***len={}***')".format(ssid or "<empty>", len(password)))
            sta.connect(ssid, password)
        else:
            print("[>] sta.connect(ssid='{}')  # OPEN network".format(ssid or "<empty>"))
            sta.connect(ssid)
    except Exception as e:
        print("[!] connect() raised: {}".format(e))
        try:
            sta.active(False)
        except Exception:
            pass
        if strict and ap_was_active:
            try:
                ap.active(True); ap_try_set("essid", SSID)
                for k,v in (("password",""),("key",""),("pwd",""),("authmode",0),("security",0)):
                    ap_try_set(k,v)
                print("[i] AP restored after connect() exception")
            except Exception:
                pass
        return False, {"reason": "connect() raised: {}".format(e)}

    t0 = time.time()
    next_log = t0
    got_ip = False
    ip_tuple = None
    last_status = None

    print("[i] Waiting for connection and DHCP ...")
    while time.time() - t0 < JOIN_TIMEOUT_S:
        try:
            st = sta.status()
        except Exception:
            st = None

        if (st != last_status) or (time.time() >= next_log):
            try:
                isconn = sta.isconnected()
            except Exception:
                isconn = False
            print("    - status={} ({})  isconnected={}".format(status_to_str(st), st, isconn))
            last_status = st
            next_log = time.time() + STATUS_LOG_PERIOD_S

        try:
            if sta.isconnected():
                ip_tuple = sta.ifconfig()
                if ip_tuple and ip_tuple[0] and ip_tuple[0] != "0.0.0.0":
                    got_ip = True
                    break
        except Exception:
            pass

        time.sleep(0.25)

    info = {}
    try:
        info["status"] = status_to_str(sta.status())
    except Exception:
        info["status"] = "unknown"

    if got_ip:
        print("[+] CONNECTED to '{}' -> {}  gw={} dns={}".format(ssid or "<empty>", ip_tuple[0], ip_tuple[2], ip_tuple[3]))
        ok = True
        info.update({"ip": ip_tuple[0], "netmask": ip_tuple[1], "gw": ip_tuple[2], "dns": ip_tuple[3]})
    else:
        try:
            s = sta.status()
        except Exception:
            s = None
        reason = "Timed out waiting for DHCP"
        if s == getattr(network, "STAT_WRONG_PASSWORD", -3):
            reason = "Wrong password"
        elif s == getattr(network, "STAT_NO_AP_FOUND", -2):
            reason = "No AP found (maybe 5 GHz/out-of-range)"
        elif s == getattr(network, "STAT_CONNECT_FAIL", -1):
            reason = "Connection failed (router rejected)"
        info["reason"] = reason
        print("[!] FAILED to connect to '{}': {} (status {})".format(ssid or "<empty>", reason, status_to_str(s)))
        ok = False

    try:
        if sta.isconnected():
            print("[i] Disconnecting STA...")
            try:
                sta.disconnect()
            except Exception:
                pass
    except Exception:
        pass
    try:
        sta.active(False)
        print("[i] STA disabled after test")
    except Exception:
        pass

    if strict and ap_was_active:
        try:
            ap.active(True)
            ap_try_set("essid", SSID)
            for k,v in (("password",""),("key",""),("pwd",""),("authmode",0),("security",0)):
                ap_try_set(k,v)
            print("[i] AP restored after strict test")
        except Exception:
            pass

    print("[i] END test for SSID: '{}'  -> {}".format(ssid or "<empty>", "OK" if ok else "FAIL"))
    print("="*60)
    return ok, info

# ---------- DNS catch-all (UDP/53) ----------
def build_dns_response(query, answer_ip):
    if len(query) < 12:
        return b""
    tid = query[0:2]
    flags = b"\x81\x80"
    header = tid + flags + b"\x00\x01\x00\x01\x00\x00\x00\x00"
    q = query[12:]
    try:
        end = q.find(b"\x00") + 1
        qname = q[:end]
        qtype_qclass = q[end:end+4] if len(q) >= end+4 else b"\x00\x01\x00\x01"
    except Exception:
        qname = b"\x00"
        qtype_qclass = b"\x00\x01\x00\x01"
    question = qname + qtype_qclass
    ans_name_ptr = b"\xC0\x0C"
    ans_type_class = b"\x00\x01\x00\x01"
    ttl = b"\x00\x00\x00\x3C"
    rdlen = b"\x00\x04"
    rdata = bytes(map(int, answer_ip.split(".")))
    answer = ans_name_ptr + ans_type_class + ttl + rdlen + rdata
    return header + question + answer

def make_dns_sock():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    except Exception:
        pass
    s.bind(("0.0.0.0", DNS_PORT))
    print("[+] DNS catch-all on udp/{} -> {}".format(DNS_PORT, ip))
    return s

# ---------- HTTP server ----------
def make_http_sock():
    s = socket.socket()
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    except Exception:
        pass
    s.bind(("0.0.0.0", HTTP_PORT))
    s.listen(5)
    print("[+] HTTP server on http://{}:{}/".format(ip, HTTP_PORT))
    return s

def http_send(conn, status_line, headers, body=b""):
    try:
        if not isinstance(body, (bytes, bytearray)):
            body = body.encode()
        hdr = [status_line]
        for k,v in headers:
            hdr.append("{}: {}".format(k, v))
        wire = ("\r\n".join(hdr) + "\r\n\r\n").encode() + body
        conn.send(wire)
    except Exception:
        pass

def read_http_request(conn):
    conn.settimeout(5)
    data = b""
    while True:
        chunk = conn.recv(512)
        if not chunk:
            break
        data += chunk
        if b"\r\n\r\n" in data or len(data) > 8192:
            break
    parts = data.split(b"\r\n\r\n",1)
    head = parts[0]
    body = parts[1] if len(parts) > 1 else b""
    lines = head.split(b"\r\n")
    reqline = lines[0] if lines else b""
    rl = reqline.split()
    method = rl[0].decode() if len(rl)>=1 else "GET"
    fullpath = rl[1].decode() if len(rl)>=2 else "/"
    sp = fullpath.split("?",1)
    path = sp[0]
    qs = sp[1] if len(sp)>1 else ""
    headers = {}
    for ln in lines[1:]:
        if b":" in ln:
            kv = ln.split(b":",1)
            k = kv[0].decode().strip().lower()
            v = kv[1].decode().strip()
            headers[k] = v
    clen = int(headers.get("content-length","0") or "0")
    while len(body) < clen:
        more = conn.recv(min(1024, clen - len(body)))
        if not more:
            break
        body += more
    return method, path, qs, headers, body

# ---------- Pages ----------
def page_root():
    return ("""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pico W Captive Portal</title></head>
<body>
<h1>Pico W Captive Portal</h1>
<p>You are connected to <b>%s</b>.</p>
<p><a href="/networks">Scan &amp; select a Wi-Fi hotspot</a></p>
<pre>IP: %s
Security: OPEN (no password)</pre>
</body></html>""" % (SSID, ip))

def page_networks(nets):
    rows = ["<tr><th>SSID</th><th>BSSID</th><th>Ch</th><th>RSSI</th><th>Security</th><th></th></tr>"]
    nets_sorted = sorted(nets, key=lambda x: x["rssi"], reverse=True)
    for n in nets_sorted:
        ssid_disp = html_escape(n["ssid"] or "<hidden>")
        join_link = "/join?ssid=" + url_encode(n["ssid"] or "")
        rows.append(
            "<tr>"
            "<td>{}</td>".format(ssid_disp) +
            "<td><code>{}</code></td>".format(html_escape(n['bssid'])) +
            "<td>{}</td>".format(n['channel']) +
            "<td>{} dBm</td>".format(n['rssi']) +
            "<td>{}</td>".format(html_escape(n['security'])) +
            "<td><a href=\"{}\">Test password</a></td>".format(join_link) +
            "</tr>"
        )
    table = "<table border='1' cellpadding='6' cellspacing='0'>{}</table>".format("".join(rows))
    return ("""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Nearby Wi-Fi Networks</title></head>
<body>
<h1>Nearby Wi-Fi Networks</h1>
<p><a href="/">Home</a> · <a href="/networks">Rescan</a> · <a href="/scan.json">JSON</a></p>
%s
</body></html>""" % table)

def page_join_form(ssid):
    ssid_disp = html_escape(ssid or "")
    notice = "<p style='color:red'><b>Note:</b> For diagnostics, the password will be printed to device logs in plaintext.</p>"
    return ("""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Test Wi-Fi Password</title></head>
<body>
<h1>Test Wi-Fi Password</h1>
<p><a href="/">Home</a> · <a href="/networks">Back to list</a></p>
%s
<form method="POST" action="/test-credentials">
  <label>SSID<br><input name="ssid" value="%s" required></label><br><br>
  <label>Password (leave blank for open networks)<br>
    <input type="password" name="password" value="">
  </label><br><br>
  <label><input type="checkbox" name="strict" value="1"> Strict test (temporarily turn off AP)</label><br><br>
  <button type="submit">Test Connect</button>
</form>
</body></html>""" % (notice, ssid_disp))

def page_test_result(ssid, ok, info):
    msg = "Success! Connected." if ok else ("Failed: " + html_escape(info.get("reason","")))
    lines = []
    for k in ("status","ip","netmask","gw","dns"):
        if k in info:
            lines.append("{}: {}".format(k, html_escape(str(info[k]))))
    detail = "\n".join(lines) if lines else "No extra details."
    return ("""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Test Result</title></head>
<body>
<h1>Wi-Fi Test Result</h1>
<p><a href="/">Home</a> · <a href="/networks">Scan again</a></p>
<p><b>SSID:</b> %s</p>
<p><b>%s</b></p>
<pre>%s</pre>
</body></html>""" % (html_escape(ssid or ""), html_escape(msg), html_escape(detail)))

# Known captive-portal probes → redirect to "/"
PROBE_PATHS = {
    "/generate_204", "/gen_204",
    "/hotspot-detect.html", "/library/test/success.html",
    "/ncsi.txt", "/connecttest.txt", "/redirect",
}

# ---------- Sockets ----------
def make_dns_sock():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    except Exception:
        pass
    s.bind(("0.0.0.0", DNS_PORT))
    print("[+] DNS catch-all on udp/{} -> {}".format(DNS_PORT, ip))
    return s

def make_http_sock():
    s = socket.socket()
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    except Exception:
        pass
    s.bind(("0.0.0.0", HTTP_PORT))
    s.listen(5)
    print("[+] HTTP server on http://{}:{}/".format(ip, HTTP_PORT))
    return s

dns_sock  = make_dns_sock()
http_sock = make_http_sock()

# ---------- Poll loop (no .fileno) ----------
poll = uselect.poll()
poll.register(dns_sock, uselect.POLLIN)
poll.register(http_sock, uselect.POLLIN)
http_conns = []

try:
    while True:
        # register client sockets
        for c in http_conns:
            try:
                poll.register(c, uselect.POLLIN)
            except Exception:
                pass

        events = poll.poll(250)

        # unregister again
        for c in http_conns:
            try:
                poll.unregister(c)
            except Exception:
                pass

        for sock_obj, event in events:
            # DNS
            if sock_obj is dns_sock and (event & uselect.POLLIN):
                try:
                    data, addr = dns_sock.recvfrom(512)
                    resp = build_dns_response(data, ip)
                    if resp:
                        dns_sock.sendto(resp, addr)
                except Exception:
                    pass

            # HTTP listener
            elif sock_obj is http_sock and (event & uselect.POLLIN):
                try:
                    conn, remote = http_sock.accept()
                    conn.settimeout(6)
                    http_conns.append(conn)
                except Exception:
                    pass

            # Existing HTTP client
            elif (sock_obj in http_conns) and (event & uselect.POLLIN):
                try:
                    method, path, qs, headers, body = read_http_request(sock_obj)

                    if path in PROBE_PATHS:
                        http_send(sock_obj, "HTTP/1.1 302 Found",
                                  [("Location","/"), ("Cache-Control","no-store"),
                                   ("Content-Length","0")], b"")

                    elif path == "/" and method == "GET":
                        body_html = page_root().encode()
                        http_send(sock_obj, "HTTP/1.1 200 OK",
                                  [("Content-Type","text/html; charset=utf-8"),
                                   ("Cache-Control","no-store"),
                                   ("Content-Length", str(len(body_html)))], body_html)

                    elif path == "/networks" and method == "GET":
                        nets = scan_networks()
                        page = page_networks(nets).encode()
                        http_send(sock_obj, "HTTP/1.1 200 OK",
                                  [("Content-Type","text/html; charset=utf-8"),
                                   ("Cache-Control","no-store"),
                                   ("Content-Length", str(len(page)))], page)

                    elif path == "/scan.json" and method == "GET":
                        nets = scan_networks()
                        items = []
                        for n in nets:
                            items.append('{{"ssid":"{ssid}","bssid":"{bssid}","channel":{ch},"rssi":{rssi},"security":"{sec}","hidden":{hid}}}'.format(
                                ssid=(n["ssid"].replace('"','\\"') if n["ssid"] else ""),
                                bssid=n["bssid"],
                                ch=n["channel"], rssi=n["rssi"],
                                sec=n["security"].replace('"','\\"'),
                                hid="true" if n["hidden"] else "false"
                            ))
                        body_json = ("[" + ",".join(items) + "]").encode()
                        http_send(sock_obj, "HTTP/1.1 200 OK",
                                  [("Content-Type","application/json"),
                                   ("Cache-Control","no-store"),
                                   ("Content-Length", str(len(body_json)))], body_json)

                    elif path == "/join" and method == "GET":
                        params = parse_query(qs)
                        ssid_param = params.get("ssid","")
                        page = page_join_form(ssid_param).encode()
                        http_send(sock_obj, "HTTP/1.1 200 OK",
                                  [("Content-Type","text/html; charset=utf-8"),
                                   ("Cache-Control","no-store"),
                                   ("Content-Length", str(len(page)))], page)

                    elif path == "/test-credentials" and method == "POST":
                        ctype = headers.get("content-type","")
                        if "application/x-www-form-urlencoded" in ctype:
                            form = parse_form_urlencoded(body.decode())
                            ssid = form.get("ssid","")
                            password = form.get("password","")
                            strict = form.get("strict","") in ("1","on","true","yes")
                            ok, info = test_credentials(ssid, password, strict=strict)
                            page = page_test_result(ssid, ok, info).encode()
                            http_send(sock_obj, "HTTP/1.1 200 OK",
                                      [("Content-Type","text/html; charset=utf-8"),
                                       ("Cache-Control","no-store"),
                                       ("Content-Length", str(len(page)))], page)
                        else:
                            msg = b"Unsupported Content-Type"
                            http_send(sock_obj, "HTTP/1.1 415 Unsupported Media Type",
                                      [("Content-Type","text/plain; charset=utf-8"),
                                       ("Content-Length", str(len(msg)))], msg)

                    else:
                        msg = b"Not found"
                        http_send(sock_obj, "HTTP/1.1 404 Not Found",
                                  [("Content-Type","text/plain; charset=utf-8"),
                                   ("Content-Length", str(len(msg)))], msg)

                except Exception as e:
                    try:
                        err = ("Error: %r" % e).encode()
                        http_send(sock_obj, "HTTP/1.1 500 Internal Server Error",
                                  [("Content-Type","text/plain; charset=utf-8"),
                                   ("Content-Length", str(len(err)))], err)
                    except Exception:
                        pass
                finally:
                    try:
                        http_conns.remove(sock_obj)
                    except Exception:
                        pass
                    try:
                        sock_obj.close()
                    except Exception:
                        pass

except KeyboardInterrupt:
    print("\n[i] Stopping server...")
finally:
    for c in http_conns:
        try:
            c.close()
        except Exception:
            pass
    try:
        dns_sock.close(); print("[i] DNS socket closed")
    except Exception:
        pass
    try:
        http_sock.close(); print("[i] HTTP socket closed")
    except Exception:
        pass
    try:
        ap.active(False); print("[i] AP disabled")
    except Exception:
        pass
    try:
        sta.active(False); print("[i] STA disabled")
    except Exception:
        pass
    print("=== Shutdown complete ===")
