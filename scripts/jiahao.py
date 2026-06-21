from __future__ import annotations

import random
import sys
import time
import signal

import click
from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich import box

console = Console()

# ── 假数据 ────────────────────────────────────────────────────────────

PORTS = [21, 22, 23, 25, 53, 80, 110, 135, 139, 143, 443, 445, 993, 995,
         1723, 3306, 3389, 5432, 5900, 6379, 8080, 8443, 27017]
PROTOCOLS = ["TCP", "UDP", "HTTP", "HTTPS", "FTP", "SSH", "SMTP", "DNS", "SMB"]
ENCRYPTIONS = ["AES-256-GCM", "ChaCha20-Poly1305", "RSA-4096", "ECDSA", "Ed25519"]
SERVICES = ["nginx/1.24.0", "Apache/2.4.57", "OpenSSH 9.3", "MySQL 8.0",
            "PostgreSQL 15", "Redis 7.0", "MongoDB 6.0", "Elasticsearch 8.9"]
DIR_PATHS = ["/etc/ssl/private", "/var/log/audit", "/root/.ssh", "/opt/classified",
             "/srv/backups", "/tmp/.hidden", "/usr/local/agent", "/home/admin/.config"]
USERS = ["root", "admin", "ubuntu", "deploy", "www-data", "postgres", "elasticsearch"]
PASSWORDS = ["admin123", "p@ssw0rd!", "secret2024", "toor", "letmein", "qwerty!@#"]

VULNS = [(f"CVE-2024-{random.randint(1000, 9999)}", random.uniform(5.0, 10.0))
         for _ in range(30)]


def _fake_ip() -> str:
    return f"{random.randint(1, 255)}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}"

def _fake_hash(length: int = 64) -> str:
    return "".join(random.choice("abcdef0123456789") for _ in range(length))


# ── 进度条 ────────────────────────────────────────────────────────────

class Progress:
    __slots__ = ("label", "color", "current", "total", "extra")
    def __init__(self, label: str, color: str, total: int, extra: str):
        self.label = label
        self.color = color
        self.current = 0
        self.total = total
        self.extra = extra

    def render(self) -> Text:
        pct = min(self.current / self.total * 100, 100)
        bar_w = 40
        filled = int(bar_w * min(self.current, self.total) / self.total)
        bar = "#" * filled + " " * (bar_w - filled)
        return Text.assemble(
            (f"  {self.label}  ", f"bold {self.color}"),
            ("[", "dim"),
            (bar, ""),
            ("]", "dim"),
            (f" {pct:.0f}%  ", "dim"),
            (self.extra, "dim"),
        )


# ── 日志生成器 ────────────────────────────────────────────────────────

def _log_scan() -> Text:
    return Text.assemble(
        ("[*] ", "dim yellow"),
        (f"Scanning {_fake_ip()}:{random.choice(PORTS)}/{random.choice(PROTOCOLS)}", ""),
    )

def _log_scan_result() -> Text:
    return Text.assemble(("  └─ open  ", "dim"), (random.choice(SERVICES), "dim green"))

def _log_vuln() -> Text:
    cve, score = random.choice(VULNS)
    sc = "bold red" if score > 8 else "yellow" if score > 6 else "dim cyan"
    return Text.assemble(("[!] ", sc), (cve, sc), (f"  CVSS: {score:.2f}", "dim"))

def _log_vuln_exploit() -> Text:
    return Text("  └─ Exploit available: metasploit", style="dim")

def _log_bruteforce() -> Text:
    return Text.assemble(
        ("[+] ", "dim cyan"),
        (f"Trying {random.choice(USERS)}@{_fake_ip()}", ""),
    )

def _log_bruteforce_success() -> Text:
    user = random.choice(USERS)
    pw = random.choice(PASSWORDS)
    return Text.assemble(
        ("[✓] ", "bold green"), (f"Found {user}:", "green"), (pw, "bold yellow"),
    )

def _log_decrypt() -> Text:
    return Text.assemble(
        ("[~] ", "dim magenta"), (f"Decrypting with {random.choice(ENCRYPTIONS)}", ""),
    )

def _log_decrypt_data() -> Text:
    return Text(f"  {_fake_hash(random.randint(16, 40))}", style="dim")

def _log_decrypt_result() -> Text:
    return Text.assemble(
        ("  └─ Plaintext: ", "dim"), (random.choice(PASSWORDS), "bold green"),
    )

def _log_exfil() -> Text:
    path = random.choice(DIR_PATHS)
    fname = random.choice(["shadow.bak", "id_rsa", "dump.sql", "config.yaml", "tokens.db"])
    return Text.assemble(
        ("[<] ", "dim blue"),
        (f"Exfiltrating {path}/{fname} ({random.randint(1, 950)} KB)", ""),
    )

def _log_proxy() -> Text:
    return Text.assemble(
        ("[#] Chain → ", "dim"), (_fake_ip(), "cyan"), (" → ...", "dim"),
    )

def _log_connection() -> Text:
    return Text.assemble(
        ("[C] ", "dim green"),
        (f"Connection to {_fake_ip()}:{random.choice(PORTS)}", "dim"),
    )


LOG_ITEMS: list[list] = [
    [_log_scan, _log_scan_result],
    [_log_vuln, _log_vuln_exploit],
    [_log_bruteforce, _log_bruteforce_success],
    [_log_decrypt, _log_decrypt_data, _log_decrypt_result],
    [_log_exfil],
    [_log_proxy],
    [_log_connection],
]


# ── 表格 ──────────────────────────────────────────────────────────────

def _make_scan_table() -> Table:
    t = Table(box=box.SIMPLE_HEAVY, padding=(0, 2), show_header=True,
              header_style="bold cyan", border_style="bright_black")
    t.add_column("HOST", style="dim")
    t.add_column("PORT")
    t.add_column("SERVICE", style="dim green")
    t.add_column("STATUS")
    for _ in range(random.randint(2, 5)):
        ip = _fake_ip()
        port = random.choice(PORTS)
        svc = random.choice(SERVICES)
        status = random.choice(["open", "open", "open", "filtered", "closed"])
        sc = "green" if status == "open" else "yellow" if status == "filtered" else "red"
        t.add_row(ip, str(port), svc, f"[{sc}]{status}[/{sc}]")
    return t

def _make_creds_table() -> Table:
    t = Table(box=box.SIMPLE_HEAVY, padding=(0, 2), show_header=True,
              header_style="bold yellow", border_style="bright_black")
    t.add_column("HOST", style="dim")
    t.add_column("USER")
    t.add_column("PASSWORD", style="bold yellow")
    for _ in range(random.randint(1, 3)):
        t.add_row(_fake_ip(), random.choice(USERS), random.choice(PASSWORDS))
    return t


# ── 主循环 ────────────────────────────────────────────────────────────

def run(speed_sec: tuple[float, float]) -> None:
    """流式输出。进度条活跃时暂停日志，原地更新进度；完成后放出缓冲。"""
    prog: Progress | None = None
    buf: list[Text] = []
    tables = [_make_scan_table, _make_creds_table]
    signal_received = False
    tick = 0

    # 随机冷却：进度条结束后等随机 tick 数才开始下一个
    cooldown: int = 0
    # 突发模式：一次连续来 1-3 个进度条
    burst: int = 0

    def _on_signal(sig, frame):
        nonlocal signal_received
        signal_received = True
    signal.signal(signal.SIGINT, _on_signal)

    def _emit(item: Text | Table) -> None:
        """输出一行/表格，若当前有进度条则先缓冲。"""
        if prog:
            buf.append(item) if isinstance(item, Text) else buf.append(Text())
        else:
            console.print(item)

    def _flush_buf() -> None:
        """释放缓冲的日志。"""
        for item in buf:
            console.print(item)
        buf.clear()

    def _start_progress() -> None:
        nonlocal prog
        # total 和 step 都随机化：有快有慢
        total = random.randint(15, 200) if random.random() < 0.6 else random.randint(200, 1200)
        kind = random.choice([
            ("SCAN",   "yellow", total, _fake_ip()),
            ("BRUTE",  "cyan",   total, f"{random.choice(USERS)}@{_fake_ip()}"),
            ("DL",     "blue",   total,
             random.choice(["dump.sql", "users.db", "shadow.bak", "id_rsa.tar.gz", "configs.zip", "tokens.json"])),
        ])
        prog = Progress(*kind)

    def _finish_progress() -> None:
        nonlocal prog, cooldown, burst
        assert prog
        console.print(Text(f"  {prog.label} DONE → {prog.extra}", style=f"dim {prog.color}"))
        _flush_buf()
        prog = None
        burst -= 1
        if burst <= 0:
            # 冷却时间随机 5~80 tick，极少数情况更长（制造悬念）
            cooldown = random.randint(5, 80)
            if random.random() < 0.08:
                cooldown = random.randint(80, 200)

    try:
        while not signal_received:
            tick += 1

            # ── 进度条生命周期 ──
            if prog is None:
                if cooldown > 0:
                    cooldown -= 1
                else:
                    # 冷却结束，决定是单次还是突发
                    if burst <= 0:
                        burst = 1 if random.random() < 0.3 else random.randint(2, 3) if random.random() < 0.25 else 1
                    _start_progress()

            if prog:
                # 步长随机：有时大步跳，有时小步磨
                if random.random() < 0.15:
                    step = random.randint(1, max(2, prog.total // 3))   # 偶尔大步
                else:
                    step = random.randint(1, max(2, prog.total // 15))  # 正常小步
                prog.current += step
                if prog.current >= prog.total:
                    _finish_progress()

            # ── 生成日志（有进度条时缓冲，否则直接输出） ──
            for _ in range(random.randint(1, 3)):
                group = random.choice(LOG_ITEMS)
                for i, gen in enumerate(group):
                    if i == 0 or random.random() < (0.3 if i == 1 else 0.1):
                        _emit(gen())

            # ── 偶尔表格 ──
            if tick % 30 == 0 and random.random() < 0.5:
                _emit(Text())
                _emit(random.choice(tables)())

            # ── 原地更新进度条 ──
            if prog:
                sys.stdout.write("\r\033[K")
                sys.stdout.flush()
                console.print(prog.render(), end="")

            time.sleep(random.uniform(*speed_sec))

    finally:
        # 清理
        sys.stdout.write("\r\033[K\n")
        sys.stdout.flush()

    console.print("[bold bright_green]> Session terminated.[/bold bright_green]")


@click.command(help="Simulate hacker-style terminal output. All fake, just for show.")
@click.option("--speed", type=click.Choice(["slow", "normal", "fast"]), default="normal", help="Output speed.")
def jiahao(speed: str) -> None:

    speed_map = {
        "slow":    (0.12, 0.40),
        "normal":  (0.06, 0.20),
        "fast":    (0.02, 0.10),
    }

    run(speed_map[speed])

if __name__ == "__main__":
    jiahao()