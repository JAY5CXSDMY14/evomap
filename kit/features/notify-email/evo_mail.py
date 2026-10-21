"""SMTP 发信（第十八轮从内核 evo_notify 搬出来，属于功能包 notify-email）。"""
import os, smtplib, ssl, sys
from email.message import EmailMessage

from evo_notify import env, _fake_dir, _append


def send_mail(subject, text):
    """SMTP 发信，配置全在环境变量：EVO_SMTP_HOST、EVO_SMTP_PORT（默认 465）、EVO_SMTP_USER、EVO_SMTP_PASS、
    EVO_SMTP_TLS（ssl 默认 / starttls / none）、EVO_MAIL_FROM（默认同 USER）、EVO_MAIL_TO（逗号分隔）。没配返回 None。"""
    host, to = env("EVO_SMTP_HOST"), env("EVO_MAIL_TO")
    if not host or not to:
        return None
    frm = env("EVO_MAIL_FROM") or env("EVO_SMTP_USER") or "evo@localhost"
    fd = _fake_dir()
    if fd:
        _append(os.path.join(fd, "mail.log"), {"to": to, "from": frm, "subject": subject, "text": text})
        return True
    msg = EmailMessage(); msg["Subject"] = subject; msg["From"] = frm; msg["To"] = to; msg.set_content(text)
    mode = (env("EVO_SMTP_TLS") or "ssl").lower(); port = int(env("EVO_SMTP_PORT") or (465 if mode == "ssl" else 587))
    try:
        s = smtplib.SMTP_SSL(host, port, timeout=20, context=ssl.create_default_context()) if mode == "ssl" else smtplib.SMTP(host, port, timeout=20)
        with s:
            if mode == "starttls":
                s.starttls(context=ssl.create_default_context())
            if env("EVO_SMTP_USER"):
                s.login(env("EVO_SMTP_USER"), env("EVO_SMTP_PASS") or "")
            s.send_message(msg)
        return True
    except Exception as e:
        print(f"邮件没发出去：{e}", file=sys.stderr)
        return False
