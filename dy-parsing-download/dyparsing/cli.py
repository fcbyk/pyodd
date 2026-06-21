"""
抖音视频解析下载 CLI 工具
"""
import asyncio
import re
from pathlib import Path

import click
import httpx
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress
from rich.table import Table

from byksdk import plugin
from dyparsing.douyin.crawler import DouyinWebCrawler

console = Console()


def extract_aweme_id(text: str) -> str:
    """从抖音链接或分享文案中提取作品 ID"""
    patterns = [
        r"video/(\d+)",
        r"note/(\d+)",
        r"modal_id=(\d+)",
        r"[?&]vid=(\d+)",
        r"aweme_id[=:](\d+)",
        r"v\.douyin\.com/(\w+)",
        r"iesdouyin\.com/share/video/(\d+)",
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            return m.group(1)
    return ""


async def resolve_short_link(short_code: str) -> str:
    """解析 v.douyin.com 短链接，跟随重定向获取真实作品 ID"""
    url = f"https://v.douyin.com/{short_code}"
    async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        }
        resp = await client.get(url, headers=headers)
        location = resp.headers.get("location", "")
        if location:
            # 从重定向 URL 中提取数字 aweme_id
            m = re.search(r"video/(\d+)", location)
            if m:
                return m.group(1)
            m = re.search(r"note/(\d+)", location)
            if m:
                return m.group(1)
    return ""


def format_duration(ms: int) -> str:
    """毫秒转可读时长"""
    s = ms // 1000
    m, s = divmod(s, 60)
    return f"{m}:{s:02d}"


def format_count(n: int) -> str:
    """格式化数字"""
    if n >= 10000:
        return f"{n / 10000:.1f}万"
    return str(n)


def dedup_qualities(bit_rate: list) -> list[dict]:
    """按分辨率去重，每档只保留最高码率"""
    order = {"4": 0, "1440": 1, "1080": 2, "720": 3, "540": 4}
    label_map = {"4": "4K", "1440": "2K", "1080": "1080p", "720": "720p", "540": "540p"}

    groups: dict[str, dict] = {}
    for br in bit_rate:
        name = br.get("gear_name", "")
        kbps = int(br.get("bit_rate", 0)) // 1000
        addr = br.get("play_addr", {}).get("url_list", [])
        if not addr:
            continue

        # 从 gear_name 提取分辨率数字
        m = re.search(r"_(\d+)_?\d*$", name)
        if not m:
            continue
        res = m.group(1)
        if res not in label_map:
            continue

        is_bvc1 = "bvc1" in name.lower()
        key = res
        if key not in groups or kbps > groups[key]["kbps"]:
            groups[key] = {"label": f"{label_map[res]}{' (bvc1)' if is_bvc1 else ''}", "url": addr[0].replace("playwm", "play"), "kbps": kbps}

    result = []
    for k in sorted(groups, key=lambda x: order.get(x, 99)):
        g = groups[k]
        result.append({"label": f"{g['label']} - {g['kbps']}kbps", "url": g["url"]})
    return result


async def parse_video(aweme_id: str, cookie: str = ""):
    """解析单个抖音作品"""
    crawler = DouyinWebCrawler(cookie=cookie)
    raw = await crawler.fetch_one_video(aweme_id)

    if not raw or not isinstance(raw, dict) or "aweme_detail" not in raw:
        console.print("[red]解析失败，请检查 Cookie 是否有效[/red]")
        return None

    detail = raw["aweme_detail"]
    if detail is None:
        console.print("[red]未获取到作品数据，可能 ID 无效或接口受限[/red]")
        return None

    aweme_type = detail.get("aweme_type", 0)
    desc = detail.get("desc", "无描述")

    author = detail.get("author", {})
    nickname = author.get("nickname", "未知")
    unique_id = author.get("unique_id", "")

    statistics = detail.get("statistics", {})
    digg = statistics.get("digg_count", 0)
    comment = statistics.get("comment_count", 0)
    share = statistics.get("share_count", 0)
    play = statistics.get("play_count", 0)

    video = detail.get("video", {})
    duration = video.get("duration", 0)

    is_image = aweme_type in (2, 68, 150)
    type_name = "图集" if is_image else "视频"

    qualities = []
    if is_image:
        images = detail.get("images", [])
        for img in images:
            urls = img.get("url_list", [])
            if urls:
                qualities.append({"label": "原图", "url": urls[0]})
    else:
        qualities = dedup_qualities(video.get("bit_rate", []))

    cover_list = video.get("origin_cover", {}).get("url_list", [])
    cover = cover_list[0] if cover_list else ""

    return {
        "aweme_id": aweme_id,
        "type": type_name,
        "desc": desc,
        "nickname": nickname,
        "unique_id": unique_id,
        "duration": format_duration(duration) if not is_image else "-",
        "digg": digg,
        "comment": comment,
        "share": share,
        "play": play,
        "cover": cover,
        "qualities": qualities,
        "is_image": is_image,
    }


async def download_file(url: str, filepath: Path, desc: str = ""):
    """异步下载文件"""
    async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Referer": "https://www.douyin.com/",
        }
        async with client.stream("GET", url, headers=headers) as resp:
            total = int(resp.headers.get("content-length", 0))
            filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, "wb") as f:
                with Progress() as progress:
                    task = progress.add_task(f"[cyan]{desc}[/cyan]", total=total or None)
                    async for chunk in resp.aiter_bytes(1024 * 64):
                        f.write(chunk)
                        progress.update(task, advance=len(chunk))
    console.print(f"[green]已保存: {filepath}[/green]")


@click.command(name="dy", help="抖音视频解析下载工具")
@click.argument("input_text", required=False)
@click.option("--no-download", "-n", is_flag=True, help="只解析不下载")
@click.option("--set-cookie", default=None, help="设置抖音 Cookie（从浏览器开发者工具获取）")
@click.option("--download-dir", "-d", default=None, help="设置下载目录，默认 ./downloads")
@click.option("--show-config", is_flag=True, help="显示当前配置信息")
def dy(input_text: str | None,
       no_download: bool, set_cookie: str | None, download_dir: str | None,
       show_config: bool):
    
    store = plugin("dy-parsing-download").state()

    # --show-config: 显示当前配置
    if show_config:
        cookie = store.get("cookie", "")
        table = Table(title="dy 插件配置", show_header=False)
        table.add_column("Key", style="bold cyan")
        table.add_column("Value")
        table.add_row("Cookie", f"[green]{cookie[:50]}...[/green]" if cookie else "[red]未设置[/red]")
        table.add_row("存储路径", str(store.path))
        console.print(table)
        return

    # --set-cookie: 设置 Cookie
    if set_cookie:
        store.set("cookie", set_cookie)
        console.print(Panel.fit(
            f"[green]Cookie 已保存到 {store.path}[/green]\n\n"
            "现在可以正常使用了:  byk dy <URL>"
        ))
        return

    # 下载目录（-d 临时生效，默认 ./downloads）
    dl_dir = Path(download_dir or "./downloads").expanduser().resolve()
    try:
        dl_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        console.print(f"[red]无法创建下载目录: {dl_dir}[/red]\n[dim]{e}[/dim]")
        return

    # 解析视频（先尝试，失败再提示设置 Cookie）
    cookie = store.get("cookie", "")

    if not input_text:
        console.print("[dim]粘贴抖音链接、分享文案或作品 ID（Ctrl+C 退出）[/dim]")
        try:
            input_text = click.prompt("", prompt_suffix="")
        except click.Abort:
            return
        if not input_text.strip():
            return

    # 纯数字 → 直接作为作品 ID
    if input_text.strip().isdigit():
        vid = input_text.strip()
    else:
        vid = extract_aweme_id(input_text)
        if not vid:
            console.print("[red]未能从输入中提取作品 ID，请检查链接或文案[/red]")
            return

    # 短链接需要先解析
    if not vid.isdigit():
        console.print(f"[dim]解析短链接: {vid}[/dim]")
        resolved = asyncio.run(resolve_short_link(vid))
        if not resolved:
            console.print("[red]短链接解析失败，无法获取真实作品 ID[/red]")
            return
        vid = resolved

    console.print(f"[dim]解析作品: {vid}[/dim]", highlight=False)

    data = asyncio.run(parse_video(vid, cookie=cookie))
    if data is None:
        if not cookie:
            console.print(Panel.fit(
                "[yellow]未配置 Cookie，部分接口可能需要登录才能访问[/yellow]\n\n"
                "获取方式:\n"
                "  1. 浏览器打开 https://www.douyin.com 并登录\n"
                "  2. F12 → Application → Cookies → 复制全部 Cookie\n"
                "  3. 运行: byk dy --set-cookie \"你的Cookie\"\n\n"
                "[dim]也可通过 --show-config 查看当前配置[/dim]"
            ))
        return

    console.print(f"类型：[yellow bold]{data['type']}[/yellow bold]  时长：[yellow]{data['duration']}[/yellow]")
    console.print(f"作者：{data['nickname']} (@{data['unique_id']})", highlight=False)
    console.print(f"描述：{data['desc']}", highlight=False)
    console.print(f"点赞：{format_count(data['digg'])}  评论：{format_count(data['comment'])}  分享：{format_count(data['share'])}", highlight=False)

    qualities = data["qualities"]
    if qualities and not data["is_image"]:
        console.print()
        console.print("[bold green]可下载清晰度:[/bold green]")
        for i, q in enumerate(qualities):
            console.print(f"  [bold]{i + 1}[/bold]  {q['label']}")

    if no_download:
        return

    qualities = data["qualities"]
    if not qualities:
        console.print("[yellow]无可下载的资源[/yellow]")
        return

    if data["is_image"]:
        should = click.confirm(
            f"\n是否下载这 {len(qualities)} 张图片？", default=True
        )
        if not should:
            return
        for i, q in enumerate(qualities):
            ext = ".jpg"
            filepath = dl_dir / f"{vid}_{i + 1}{ext}"
            asyncio.run(download_file(q["url"], filepath, f"图片 {i + 1}/{len(qualities)}"))
    else:
        console.print(f"\n[dim]回车下载最高画质，输入 1-{len(qualities)} 选择清晰度，其他输入则退出[/dim]")
        choice = click.prompt(
            "选择清晰度",
            type=str, default="1", show_default=False
        )
        try:
            idx = int(choice)
            if idx < 1 or idx > len(qualities):
                raise ValueError
        except ValueError:
            console.print("[dim]已取消下载[/dim]")
            return
        selected = qualities[idx - 1]
        ext = ".mp4"
        filepath = dl_dir / f"{vid}{ext}"
        asyncio.run(download_file(selected["url"], filepath, f'{selected["label"]}'))